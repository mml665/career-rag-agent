from __future__ import annotations

import json
import pickle
from pathlib import Path

import jieba
from rank_bm25 import BM25Okapi
from langchain_core.documents import Document


class BM25Index:
    """BM25 索引，用于关键词检索。"""

    def __init__(self) -> None:
        self.documents: list[Document] = []
        self.tokenized_corpus: list[list[str]] = []
        self.bm25: BM25Okapi | None = None

    def build(self, documents: list[Document]) -> None:
        """从文档列表构建 BM25 索引。"""
        self.documents = documents
        self.tokenized_corpus = [self._tokenize(doc.page_content) for doc in documents]
        self.bm25 = BM25Okapi(self.tokenized_corpus)

    def search(self, query: str, top_k: int = 10) -> list[tuple[Document, float]]:
        """检索与查询最相关的文档。"""
        if self.bm25 is None or not self.documents:
            return []

        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        # 获取 top_k 索引（按分数降序）
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)
        top_indices = [idx for idx, _ in indexed_scores[:top_k]]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # 过滤掉得分为 0 的结果
                results.append((self.documents[idx], float(scores[idx])))

        return results

    def save(self, path: Path) -> None:
        """保存索引到文件。"""
        path.mkdir(parents=True, exist_ok=True)

        # 保存文档列表
        docs_data = []
        for doc in self.documents:
            docs_data.append({
                "page_content": doc.page_content,
                "metadata": doc.metadata,
            })
        (path / "documents.json").write_text(
            json.dumps(docs_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # 保存 BM25 模型
        with open(path / "bm25.pkl", "wb") as f:
            pickle.dump(self.bm25, f)

    @classmethod
    def load(cls, path: Path) -> BM25Index:
        """从文件加载索引。"""
        index = cls()

        # 加载文档列表
        docs_file = path / "documents.json"
        if docs_file.exists():
            docs_data = json.loads(docs_file.read_text(encoding="utf-8"))
            index.documents = [
                Document(page_content=d["page_content"], metadata=d["metadata"])
                for d in docs_data
            ]
            index.tokenized_corpus = [index._tokenize(doc.page_content) for doc in index.documents]

        # 加载 BM25 模型
        bm25_file = path / "bm25.pkl"
        if bm25_file.exists():
            with open(bm25_file, "rb") as f:
                index.bm25 = pickle.load(f)

        return index

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """使用 jieba 分词。"""
        return list(jieba.cut_for_search(text))
