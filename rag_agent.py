from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from uuid import uuid4

import requests
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

from bm25_index import BM25Index


load_dotenv()


SUPPORTED_SUFFIXES = {".pdf", ".md", ".markdown", ".txt"}
DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_DASHSCOPE_EMBEDDING_URL = (
    "https://dashscope.aliyuncs.com/api/v1/services/embeddings/"
    "multimodal-embedding/multimodal-embedding"
)
DEFAULT_CHAT_MODEL = "qwen3.6-plus"
DEFAULT_EMBEDDING_MODEL = "tongyi-embedding-vision-flash-2026-03-06"


def dashscope_api_key() -> str:
    return os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY", "")


def dashscope_base_url() -> str:
    return os.getenv("DASHSCOPE_BASE_URL") or os.getenv("OPENAI_BASE_URL") or DEFAULT_DASHSCOPE_BASE_URL


@dataclass
class RagConfig:
    docs_dir: Path = Path("documents")
    upload_dir: Path = Path("data/uploads")
    resume_upload_dir: Path = Path("data/resume_uploads")
    job_upload_dir: Path = Path("data/job_uploads")
    chroma_dir: Path = Path("data/chroma")
    bm25_dir: Path = Path("data/bm25")
    history_path: Path = Path("data/history.jsonl")
    collection_name: str = "study_rag"
    chunk_size: int = int(os.getenv("RAG_CHUNK_SIZE", "700"))
    chunk_overlap: int = int(os.getenv("RAG_CHUNK_OVERLAP", "120"))
    top_k: int = int(os.getenv("RAG_TOP_K", "4"))
    min_relevance_score: float = float(os.getenv("RAG_MIN_RELEVANCE_SCORE", "0.45"))
    # Hybrid retrieval parameters
    enable_bm25: bool = os.getenv("RAG_ENABLE_BM25", "true").lower() == "true"
    bm25_weight: float = float(os.getenv("RAG_BM25_WEIGHT", "0.3"))
    vector_weight: float = float(os.getenv("RAG_VECTOR_WEIGHT", "0.7"))
    rrf_k: int = int(os.getenv("RAG_RRF_K", "60"))
    # Rerank parameters
    enable_rerank: bool = os.getenv("RAG_ENABLE_RERANK", "true").lower() == "true"
    rerank_top_n: int = int(os.getenv("RAG_RERANK_TOP_N", "10"))


@dataclass
class JobRequirementsExtraction:
    required_skills: list[str]
    preferred_skills: list[str]
    internship_requirements: list[str]


@dataclass
class JobPostingExtraction:
    company: str
    title: str
    location: str
    raw_description: str
    required_skills: list[str]
    preferred_skills: list[str]
    internship_requirements: list[str]


@dataclass
class ResumeTailoringResult:
    fit_assessment: str
    recommended_text: str
    evidence_basis: str
    gap_notes: str


@dataclass
class ResumeProfileExtraction:
    name: str = ""
    phone: str = ""
    email: str = ""
    city: str = ""
    target_role: str = ""
    preferred_locations: str = ""
    homepage: str = ""
    summary: str = ""
    education: str = ""
    skill: str = ""
    project: str = ""
    award: str = ""
    availability: str = ""


@dataclass
class SemanticMatchResult:
    semantic_score: float
    evidence_ids: list[str]
    model_explanation: str


class DashScopeMultimodalEmbeddings(Embeddings):
    """LangChain embedding adapter for DashScope multimodal independent vectors."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_EMBEDDING_MODEL,
        endpoint: str = DEFAULT_DASHSCOPE_EMBEDDING_URL,
        dimension: int = 768,
        timeout: int = 60,
        batch_size: int = 8,
    ):
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint
        self.dimension = dimension
        self.timeout = timeout
        self.batch_size = batch_size

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            vectors.extend(self._embed_batch(texts[start : start + self.batch_size]))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        payload = {
            "model": self.model,
            "input": {"contents": [{"text": text} for text in texts]},
            "parameters": {"dimension": self.dimension},
        }
        response = requests.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise RuntimeError(f"DashScope embedding 请求失败：{response.text}") from exc
        return self.parse_embeddings(response.json(), expected_count=len(texts))

    @staticmethod
    def parse_embeddings(payload: dict, expected_count: int | None = None) -> list[list[float]]:
        embeddings = payload.get("output", {}).get("embeddings", [])
        if not embeddings:
            raise RuntimeError(f"DashScope embedding 响应中没有向量：{payload}")

        ordered = [
            item
            for _, item in sorted(
                enumerate(embeddings),
                key=lambda pair: pair[1].get("index", pair[1].get("text_index", pair[0])),
            )
        ]
        vectors = [item.get("embedding") for item in ordered]
        if any(not isinstance(vector, list) for vector in vectors):
            raise RuntimeError(f"DashScope embedding 响应格式异常：{payload}")
        if expected_count is not None and len(vectors) != expected_count:
            raise RuntimeError(
                f"DashScope embedding 返回数量不匹配：期望 {expected_count}，实际 {len(vectors)}"
            )
        return vectors


class RagAssistant:
    def __init__(self, config: RagConfig | None = None):
        self.config = config or RagConfig()
        self.config.docs_dir.mkdir(parents=True, exist_ok=True)
        self.config.upload_dir.mkdir(parents=True, exist_ok=True)
        self.config.resume_upload_dir.mkdir(parents=True, exist_ok=True)
        self.config.job_upload_dir.mkdir(parents=True, exist_ok=True)
        self.config.chroma_dir.mkdir(parents=True, exist_ok=True)
        self.config.history_path.parent.mkdir(parents=True, exist_ok=True)

    def save_upload(self, filename: str, content: bytes) -> Path:
        safe_name = Path(filename).name
        target = self.config.upload_dir / safe_name
        target.write_bytes(content)
        return target

    def extract_resume_upload(self, filename: str, content: bytes) -> ResumeProfileExtraction:
        safe_name = Path(filename).name
        target = self.config.resume_upload_dir / safe_name
        if target.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise ValueError("仅支持 PDF、Markdown 或 TXT 简历。")
        target.write_bytes(content)
        text = "\n\n".join(doc.page_content for doc in self._load_document(target))
        if not text.strip():
            raise ValueError("未能从简历中读取到文本内容。")
        return self.extract_resume_text(text)

    def extract_resume_text(self, text: str) -> ResumeProfileExtraction:
        if not text.strip():
            raise ValueError("简历文本不能为空。")
        self._require_api_key()
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是严谨的简历信息提取助手。只从原文中提取明确存在的信息，不补充或推断。"
                    "只输出 JSON 对象且不要包含 Markdown，字段固定为：name、phone、email、city、"
                    "target_role、preferred_locations、homepage、summary、education、skill、project、"
                    "award、availability。所有值均为字符串；原文没有的字段使用空字符串。"
                    "education、skill、project、award、availability 应保留适合人工复核的事实描述。",
                ),
                ("human", "简历原文：\n{text}"),
            ]
        )
        response = self._llm().invoke(prompt.format_messages(text=text.strip()))
        return self.parse_resume_profile_response(response.content)

    def extract_job_upload(self, filename: str, content: bytes) -> JobPostingExtraction:
        safe_name = Path(filename).name
        target = self.config.job_upload_dir / safe_name
        if target.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise ValueError("仅支持 PDF、Markdown 或 TXT 岗位文件。")
        target.write_bytes(content)
        text = "\n\n".join(doc.page_content for doc in self._load_document(target))
        if not text.strip():
            raise ValueError("未能从岗位文件中读取到文本内容。")
        return self.extract_job_posting_text(text)

    def extract_job_posting_text(self, raw_description: str) -> JobPostingExtraction:
        if not raw_description.strip():
            raise ValueError("请先输入 JD 原文。")
        self._require_api_key()
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是严谨的招聘 JD 信息提取助手。只提取原文明确写出的内容，不推断或补充。"
                    "只输出 JSON 对象且不要包含 Markdown，字段固定为：company、title、location、"
                    "required_skills、preferred_skills、internship_requirements。"
                    "company、title、location 必须是字符串，原文没有时使用空字符串；"
                    "后三个字段必须是字符串数组，没有明确内容时使用空数组。"
                    "required_skills 仅填写明确要求掌握的技术或能力；preferred_skills 仅填写优先或"
                    "加分能力；internship_requirements 填写到岗时间、持续时长、每周天数、学历/年级"
                    "等条件。技能项尽量保持简短，例如 Python、RAG、FastAPI。",
                ),
                ("human", "岗位 JD 原文：\n{raw_description}"),
            ]
        )
        response = self._llm().invoke(
            prompt.format_messages(raw_description=raw_description.strip())
        )
        return self.parse_job_posting_response(response.content, raw_description.strip())

    def delete_document(self, path: Path) -> bool:
        target = Path(path).resolve()
        roots = [self.config.docs_dir.resolve(), self.config.upload_dir.resolve()]
        if not any(self._is_within(target, root) for root in roots):
            raise ValueError("只能删除资料库目录中的文件。")
        if not target.is_file() or target.suffix.lower() not in SUPPORTED_SUFFIXES:
            return False
        target.unlink()
        return True

    def clear_uploads(self) -> int:
        removed = 0
        for path in self.config.upload_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
                path.unlink()
                removed += 1
        return removed

    def is_configured(self) -> bool:
        return bool(dashscope_api_key())

    def list_documents(self) -> list[Path]:
        roots = [self.config.docs_dir, self.config.upload_dir]
        files: list[Path] = []
        for root in roots:
            if root.exists():
                files.extend(
                    path
                    for path in root.rglob("*")
                    if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
                )
        return sorted(files)

    def ingest_all(self) -> int:
        return self.ingest_paths(self.list_documents())

    def ingest_paths(self, paths: Iterable[Path]) -> int:
        self._require_api_key()
        docs: list[Document] = []
        for path in paths:
            docs.extend(self._load_document(path))

        if not docs:
            return 0

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", ". ", " ", ""],
        )
        chunks = splitter.split_documents(docs)
        for index, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = index
            chunk.metadata["source_name"] = Path(chunk.metadata.get("source", "")).name

        # Add to vector store
        vectorstore = self._vectorstore()
        vectorstore.add_documents(chunks)

        # Build BM25 index if enabled
        if self.config.enable_bm25:
            bm25_index = self._load_bm25_index()
            # Get all documents from vector store for BM25 index
            all_docs = vectorstore.get()["documents"]
            all_metas = vectorstore.get()["metadatas"]
            all_chunks = [
                Document(page_content=doc, metadata=meta)
                for doc, meta in zip(all_docs, all_metas)
            ]
            bm25_index.build(all_chunks)
            self._save_bm25_index(bm25_index)

        return len(chunks)

    def reset_index(self) -> None:
        self.config.chroma_dir.mkdir(parents=True, exist_ok=True)
        vectorstore = self._vectorstore()
        try:
            vectorstore.delete_collection()
        finally:
            self._close_vectorstore(vectorstore)

        # Clean BM25 index
        import shutil
        if self.config.bm25_dir.exists():
            shutil.rmtree(self.config.bm25_dir, ignore_errors=True)

    def search(self, question: str, top_k: int | None = None) -> list[dict]:
        scored_docs = self._retrieve(question, top_k, apply_threshold=False)
        results = []

        for doc, score in scored_docs:
            score = self._safe_score(score)
            item = self._source_payload(doc)
            item["score"] = score
            item["accepted"] = score >= self.config.min_relevance_score
            results.append(item)

        return results

    def ask(self, question: str, top_k: int | None = None) -> dict:
        self._require_api_key()
        scored_docs = self._retrieve(question, top_k)

        if not scored_docs:
            return {
                "question": question,
                "answer": "资料中未找到相关信息。",
                "sources": [],
            }

        docs = [doc for doc, score in scored_docs]
        context = self._format_context(docs)

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个严谨的资料问答助手。只根据给定资料回答。"
                    "如果资料里没有答案，明确说“资料中未找到相关信息”。"
                    "先用一句话回答，再列出最多三个要点，最后列出引用来源。",
                ),
                (
                    "human",
                    "问题：{question}\n\n资料片段：\n{context}\n\n"
                    "请用中文回答，并附上引用来源。",
                ),
            ]
        )
        response = self._llm().invoke(prompt.format_messages(question=question, context=context))
        answer = response.content
        sources = [self._source_payload(doc) for doc in docs]
        record = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "question": question,
            "answer": answer,
            "sources": sources,
        }
        self._append_history(record)
        return record

    def summarize(self, top_k: int = 12) -> dict:
        self._require_api_key()
        docs = self.list_sources(limit=top_k)
        if not docs:
            return {
                "time": datetime.now().isoformat(timespec="seconds"),
                "question": "总结资料库",
                "answer": "资料库为空，请先上传或放入资料后再索引。",
                "sources": [],
            }

        context = "\n\n".join(
            f"[{idx}] {item['source']} chunk={item['chunk_index']}\n{item['content']}"
            for idx, item in enumerate(docs, start=1)
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个学习型资料整理助手。根据资料片段提炼核心主题、关键概念和可继续追问的问题。",
                ),
                ("human", "资料片段：\n{context}\n\n请用中文输出一份结构化摘要。"),
            ]
        )
        response = self._llm().invoke(prompt.format_messages(context=context))
        record = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "question": "总结资料库",
            "answer": response.content,
            "sources": docs,
        }
        self._append_history(record)
        return record

    def extract_job_requirements(self, raw_description: str) -> JobRequirementsExtraction:
        if not raw_description.strip():
            raise ValueError("请先输入 JD 原文。")
        self._require_api_key()
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是严谨的招聘 JD 信息提取助手。只提取 JD 原文明确写出的内容，不推断候选人能力，"
                    "不补充行业常识。输出一个 JSON 对象且不要包含 Markdown，字段固定为："
                    '"required_skills"、"preferred_skills"、"internship_requirements"。'
                    "三个字段的值都必须是字符串数组；没有明确内容时使用空数组。"
                    "required_skills 仅填写必须、要求、岗位职责中明确需要掌握的技术或能力；"
                    "preferred_skills 仅填写优先、加分、熟悉更佳的技术或能力；"
                    "internship_requirements 填写到岗时间、持续时长、每周天数、学历/年级、地点等条件。"
                    "技能项尽量保持简短，例如 Python、RAG、FastAPI。",
                ),
                ("human", "JD 原文：\n{raw_description}"),
            ]
        )
        response = self._llm().invoke(
            prompt.format_messages(raw_description=raw_description.strip())
        )
        return self.parse_job_requirements_response(response.content)

    @staticmethod
    def parse_resume_profile_response(content: str) -> ResumeProfileExtraction:
        if not isinstance(content, str):
            raise RuntimeError("简历解析响应不是文本格式。")
        payload_text = content.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", payload_text, flags=re.DOTALL)
        if fenced:
            payload_text = fenced.group(1)
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("简历解析结果不是有效 JSON，请重试。") from exc
        fields = (
            "name",
            "phone",
            "email",
            "city",
            "target_role",
            "preferred_locations",
            "homepage",
            "summary",
            "education",
            "skill",
            "project",
            "award",
            "availability",
        )
        if not isinstance(payload, dict) or any(
            not isinstance(payload.get(field, ""), str) for field in fields
        ):
            raise RuntimeError("简历解析结果格式异常，请重试。")
        return ResumeProfileExtraction(
            **{field: payload.get(field, "").strip() for field in fields}
        )

    def analyze_semantic_match(
        self,
        *,
        job_description: str,
        evidence: list[tuple[str, str]],
        keyword_summary: str,
    ) -> SemanticMatchResult:
        if not job_description.strip() or not evidence:
            raise ValueError("混合匹配需要岗位 JD 与已确认履历。")
        self._require_api_key()
        evidence_texts = [content for _, content in evidence]
        vectors = self._embeddings().embed_documents([job_description.strip(), *evidence_texts])
        job_vector = vectors[0]
        ranked = sorted(
            (
                (evidence_id, content, self._cosine_similarity(job_vector, vector))
                for (evidence_id, content), vector in zip(evidence, vectors[1:])
            ),
            key=lambda item: item[2],
            reverse=True,
        )
        top = ranked[: min(3, len(ranked))]
        semantic_score = round(
            max(0.0, min(100.0, sum(item[2] for item in top) / len(top) * 100)), 1
        )
        semantic_context = "\n".join(
            f"[{evidence_id}] 语义相似度={score:.3f} 内容={content}"
            for evidence_id, content, score in top
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是岗位匹配审查助手。只依据提供的履历证据和 JD 输出简短中文分析。"
                    "不得把未被证据支持的技能说成候选人已经具备。"
                    "请分别说明：已支持的匹配点、尚缺证据的要求、投递建议。",
                ),
                (
                    "human",
                    "岗位 JD：\n{job_description}\n\n关键词基线：\n{keyword_summary}\n\n"
                    "语义召回证据：\n{semantic_context}",
                ),
            ]
        )
        response = self._llm().invoke(
            prompt.format_messages(
                job_description=job_description.strip(),
                keyword_summary=keyword_summary,
                semantic_context=semantic_context,
            )
        )
        return SemanticMatchResult(
            semantic_score=semantic_score,
            evidence_ids=[item[0] for item in top],
            model_explanation=response.content,
        )

    def tailor_resume(
        self,
        *,
        job_description: str,
        evidence: list[str],
        current_text: str = "",
        request: str = "",
    ) -> ResumeTailoringResult:
        if not job_description.strip():
            raise ValueError("请先选择包含 JD 的岗位。")
        if not evidence:
            raise ValueError("至少选择一条已确认的个人履历证据。")
        self._require_api_key()
        evidence_context = "\n".join(
            f"[证据{index}] {content}" for index, content in enumerate(evidence, start=1)
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是严谨的简历定制助手。你只能使用候选人的已确认证据，不得虚构项目、"
                    "技术、职责、结果或数据。根据岗位 JD 优化表达，语言具体、简洁、适合中文简历。"
                    "如果岗位要求在证据中没有支持，必须放在 gap_notes 中，而不能写入 "
                    "recommended_text。只输出 JSON 对象且不要包含 Markdown，字段固定为："
                    '"fit_assessment"、"recommended_text"、"evidence_basis"、"gap_notes"。'
                    "四个字段的值都必须是字符串；recommended_text 只能包含可直接放入简历的表述，"
                    "不能包含判断、依据、解释或缺口。",
                ),
                (
                    "human",
                    "岗位 JD：\n{job_description}\n\n"
                    "已确认证据：\n{evidence_context}\n\n"
                    "当前表述（可能为空）：\n{current_text}\n\n"
                    "本次要求（可能为空）：\n{request}\n\n"
                    "请生成针对该岗位的简历建议。",
                ),
            ]
        )
        response = self._llm().invoke(
            prompt.format_messages(
                job_description=job_description.strip(),
                evidence_context=evidence_context,
                current_text=current_text.strip() or "未提供，请从证据生成建议。",
                request=request.strip() or "优化项目或技能表述。",
            )
        )
        return self.parse_resume_tailoring_response(response.content)

    @staticmethod
    def parse_resume_tailoring_response(content: str) -> ResumeTailoringResult:
        if not isinstance(content, str):
            raise RuntimeError("简历定制响应不是文本格式。")
        payload_text = content.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", payload_text, flags=re.DOTALL)
        if fenced:
            payload_text = fenced.group(1)
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("简历定制结果格式异常，请重新生成。") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("简历定制结果格式异常，请重新生成。")
        fields = ("fit_assessment", "recommended_text", "evidence_basis", "gap_notes")
        if any(not isinstance(payload.get(field), str) for field in fields):
            raise RuntimeError("简历定制结果缺少可用字段，请重新生成。")
        if not payload["recommended_text"].strip():
            raise RuntimeError("简历定制结果没有可写入的推荐表述，请重新生成。")
        return ResumeTailoringResult(
            fit_assessment=payload["fit_assessment"].strip(),
            recommended_text=payload["recommended_text"].strip(),
            evidence_basis=payload["evidence_basis"].strip(),
            gap_notes=payload["gap_notes"].strip(),
        )

    @classmethod
    def parse_job_posting_response(
        cls, content: str, raw_description: str
    ) -> JobPostingExtraction:
        if not isinstance(content, str):
            raise RuntimeError("JD 提取响应不是文本格式。")
        payload_text = content.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", payload_text, flags=re.DOTALL)
        if fenced:
            payload_text = fenced.group(1)
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("JD 提取结果不是有效 JSON，请重试。") from exc
        if not isinstance(payload, dict) or any(
            not isinstance(payload.get(field, ""), str)
            for field in ("company", "title", "location")
        ):
            raise RuntimeError("JD 提取结果格式异常，请重试。")
        return JobPostingExtraction(
            company=payload.get("company", "").strip(),
            title=payload.get("title", "").strip(),
            location=payload.get("location", "").strip(),
            raw_description=raw_description,
            required_skills=cls._parse_extracted_items(payload, "required_skills"),
            preferred_skills=cls._parse_extracted_items(payload, "preferred_skills"),
            internship_requirements=cls._parse_extracted_items(
                payload, "internship_requirements"
            ),
        )

    @classmethod
    def parse_job_requirements_response(cls, content: str) -> JobRequirementsExtraction:
        if not isinstance(content, str):
            raise RuntimeError("JD 提取响应不是文本格式。")
        payload_text = content.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", payload_text, flags=re.DOTALL)
        if fenced:
            payload_text = fenced.group(1)
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("JD 提取结果不是有效 JSON，请重试。") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("JD 提取结果格式异常，请重试。")
        return JobRequirementsExtraction(
            required_skills=cls._parse_extracted_items(payload, "required_skills"),
            preferred_skills=cls._parse_extracted_items(payload, "preferred_skills"),
            internship_requirements=cls._parse_extracted_items(
                payload, "internship_requirements"
            ),
        )

    def list_sources(self, limit: int = 50) -> list[dict]:
        self._require_api_key()
        vectorstore = self._vectorstore()
        data = vectorstore.get(limit=limit, include=["documents", "metadatas"])
        documents = data.get("documents", []) or []
        metadatas = data.get("metadatas", []) or []
        sources = []
        for content, metadata in zip(documents, metadatas):
            sources.append(
                {
                    "source": metadata.get("source_name") or Path(metadata.get("source", "")).name,
                    "chunk_index": metadata.get("chunk_index", 0),
                    "content": self._trim(content),
                }
            )
        return sources

    def load_history(self, limit: int | None = 20) -> list[dict]:
        records = self._read_history_records()
        if limit is None:
            return records
        return records[-limit:]

    def delete_history_record(self, history_id: str) -> bool:
        records = self._read_history_records()
        kept = [record for record in records if record.get("history_id") != history_id]
        if len(kept) == len(records):
            return False
        self._write_history_records(kept)
        return True

    def clear_history(self) -> int:
        records = self._read_history_records()
        if records:
            self._write_history_records([])
        return len(records)

    def _load_document(self, path: Path) -> list[Document]:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            loader = PyPDFLoader(str(path))
        elif suffix in {".md", ".markdown", ".txt"}:
            loader = TextLoader(str(path), encoding="utf-8", autodetect_encoding=True)
        else:
            return []

        docs = loader.load()
        for doc in docs:
            doc.metadata["source"] = str(path)
        return docs

    def _require_api_key(self) -> None:
        if not self.is_configured():
            raise RuntimeError("请先在 .env 中设置 DASHSCOPE_API_KEY，再执行索引、检索或问答。")

    def _retrieve(
        self,
        question: str,
        top_k: int | None = None,
        apply_threshold: bool = True,
    ) -> list[tuple[Document, float]]:
        k = top_k or self.config.top_k
        vectorstore = self._vectorstore()

        # Vector retrieval
        vector_results = vectorstore.similarity_search_with_relevance_scores(
            question,
            k=k * 2,
        )

        def vector_only() -> list[tuple[Document, float]]:
            # Pure vector retrieval
            safe_results = [
                (doc, self._safe_score(score))
                for doc, score in vector_results[:k]
            ]
            if not apply_threshold:
                return safe_results
            return [
                (doc, score)
                for doc, score in safe_results
                if score >= self.config.min_relevance_score
            ]

        if not self.config.enable_bm25:
            return vector_only()

        # BM25 retrieval
        bm25_index = self._load_bm25_index()
        bm25_results = bm25_index.search(question, top_k=k * 2)
        if not bm25_results:
            return vector_only()

        # RRF fusion
        rrf_scores: dict[str, float] = {}
        doc_map: dict[str, Document] = {}
        vector_score_map: dict[str, float] = {}  # 原始向量分数，用于阈值过滤

        # Add vector results
        for rank, (doc, score) in enumerate(vector_results):
            score = self._safe_score(score)
            rrf_key = doc.page_content
            rrf_scores[rrf_key] = rrf_scores.get(rrf_key, 0) + (
                self.config.vector_weight / (self.config.rrf_k + rank + 1)
            )
            doc_map[rrf_key] = doc
            vector_score_map[rrf_key] = score

        # Add BM25 results
        for rank, (doc, score) in enumerate(bm25_results):
            score = self._safe_score(score)
            rrf_key = doc.page_content
            rrf_scores[rrf_key] = rrf_scores.get(rrf_key, 0) + (
                self.config.bm25_weight / (self.config.rrf_k + rank + 1)
            )
            if rrf_key not in doc_map:
                doc_map[rrf_key] = doc
            # BM25-only 文档无向量分数，设为 0
            if rrf_key not in vector_score_map:
                vector_score_map[rrf_key] = 0.0

        # Sort by RRF score (RRF 只负责排序)
        sorted_keys = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)
        scored_docs = [(doc_map[key], rrf_scores[key]) for key in sorted_keys[:k]]

        # Apply threshold — 用原始向量分数过滤，不用 RRF 归一化分数
        if apply_threshold:
            scored_docs = [
                (doc, vector_score_map.get(doc.page_content, 0.0))
                for doc, _score in scored_docs
                if vector_score_map.get(doc.page_content, 0.0) >= self.config.min_relevance_score
            ]

        # Apply rerank if enabled
        if self.config.enable_rerank and scored_docs:
            scored_docs = self._rerank(question, scored_docs, k)

        return scored_docs

    def _rerank(
        self,
        query: str,
        candidates: list[tuple[Document, float]],
        top_k: int,
    ) -> list[tuple[Document, float]]:
        """使用 DashScope Rerank API 对候选结果重排序。"""
        if not self._require_api_key_for_rerank():
            return candidates[:top_k]

        docs = [doc for doc, _ in candidates]
        contents = [doc.page_content for doc in docs]

        try:
            reranked = self._dashscope_rerank(query, contents)
            # Reranked returns (index, score) pairs
            results = []
            for idx, score in reranked[:top_k]:
                if idx < len(docs):
                    results.append((docs[idx], self._safe_score(score)))
            return results
        except Exception:
            # Fallback to original order if rerank fails
            return candidates[:top_k]

    def _require_api_key_for_rerank(self) -> bool:
        """检查是否有 API key 用于 rerank。"""
        return bool(dashscope_api_key())

    @staticmethod
    def _safe_score(score: object, default: float = 0.0) -> float:
        if score is None:
            return default
        try:
            return float(score)
        except (TypeError, ValueError):
            return default

    def _dashscope_rerank(
        self, query: str, documents: list[str], top_n: int = 10
    ) -> list[tuple[int, float]]:
        """调用 DashScope Rerank API。"""
        api_key = dashscope_api_key()
        if not api_key:
            return [(i, 0.0) for i in range(len(documents))]

        url = "https://dashscope.aliyuncs.com/api/v1/services/reranker/text-reranking/text-reranking"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "gte-rerank",
            "input": {
                "query": query,
                "documents": documents,
            },
            "parameters": {
                "top_n": top_n,
                "return_documents": False,
            },
        }

        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()

        results = response.json().get("output", {}).get("results", [])
        return [(r["index"], r["relevance_score"]) for r in results]

    def _load_bm25_index(self) -> BM25Index:
        """加载 BM25 索引。"""
        bm25_dir = self.config.bm25_dir
        if bm25_dir.exists() and (bm25_dir / "bm25.pkl").exists():
            return BM25Index.load(bm25_dir)
        return BM25Index()

    def _save_bm25_index(self, index: BM25Index) -> None:
        """保存 BM25 索引。"""
        index.save(self.config.bm25_dir)

    def _llm(self) -> ChatOpenAI:
        return ChatOpenAI(
            api_key=dashscope_api_key(),
            base_url=dashscope_base_url(),
            model=os.getenv("OPENAI_MODEL", DEFAULT_CHAT_MODEL),
            temperature=0,
        )

    def _embeddings(self) -> DashScopeMultimodalEmbeddings:
        return DashScopeMultimodalEmbeddings(
            api_key=dashscope_api_key(),
            model=os.getenv("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
            endpoint=os.getenv("DASHSCOPE_EMBEDDING_URL", DEFAULT_DASHSCOPE_EMBEDDING_URL),
            dimension=int(os.getenv("DASHSCOPE_EMBEDDING_DIMENSION", "768")),
        )

    def _vectorstore(self) -> Chroma:
        return Chroma(
            collection_name=self.config.collection_name,
            embedding_function=self._embeddings(),
            persist_directory=str(self.config.chroma_dir),
        )

    @staticmethod
    def _close_vectorstore(vectorstore: Chroma) -> None:
        client = getattr(vectorstore, "_client", None)
        if client and hasattr(client, "clear_system_cache"):
            client.clear_system_cache()

    def _append_history(self, record: dict) -> None:
        record.setdefault("history_id", f"history_{uuid4().hex[:12]}")
        with self.config.history_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _read_history_records(self) -> list[dict]:
        if not self.config.history_path.exists():
            return []
        lines = self.config.history_path.read_text(encoding="utf-8").splitlines()
        records = [json.loads(line) for line in lines if line.strip()]
        changed = False
        for record in records:
            if not record.get("history_id"):
                record["history_id"] = f"history_{uuid4().hex[:12]}"
                changed = True
        if changed:
            self._write_history_records(records)
        return records

    def _write_history_records(self, records: list[dict]) -> None:
        content = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
        self.config.history_path.write_text(content, encoding="utf-8")

    def _format_context(self, docs: list[Document]) -> str:
        if not docs:
            return "没有检索到相关资料。"
        blocks = []
        for idx, doc in enumerate(docs, start=1):
            source = doc.metadata.get("source_name") or Path(doc.metadata.get("source", "")).name
            page = doc.metadata.get("page")
            page_text = f", page={page + 1}" if isinstance(page, int) else ""
            blocks.append(f"[{idx}] source={source}{page_text}\n{doc.page_content}")
        return "\n\n".join(blocks)

    def _source_payload(self, doc: Document) -> dict:
        source = doc.metadata.get("source_name") or Path(doc.metadata.get("source", "")).name
        page = doc.metadata.get("page")
        return {
            "source": source,
            "page": page + 1 if isinstance(page, int) else None,
            "chunk_index": doc.metadata.get("chunk_index"),
            "content": self._trim(doc.page_content),
        }

    @staticmethod
    def _parse_extracted_items(payload: dict, field_name: str) -> list[str]:
        values = payload.get(field_name, [])
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            raise RuntimeError(f"JD 提取结果中的 {field_name} 不是字符串数组。")
        cleaned = [item.strip() for item in values if item.strip()]
        return list(dict.fromkeys(cleaned))

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
        except ValueError:
            return False
        return True

    @staticmethod
    def _trim(text: str, max_length: int = 420) -> str:
        cleaned = " ".join(text.split())
        return cleaned if len(cleaned) <= max_length else cleaned[:max_length] + "..."

    @staticmethod
    def _cosine_similarity(first: list[float], second: list[float]) -> float:
        denominator = math.sqrt(sum(value * value for value in first)) * math.sqrt(
            sum(value * value for value in second)
        )
        if denominator == 0:
            return 0.0
        return sum(a * b for a, b in zip(first, second)) / denominator
