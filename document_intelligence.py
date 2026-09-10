from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from pypdf import PdfReader


TEXT_DENSITY_GOOD = 300
TEXT_DENSITY_LOW = 80


@dataclass
class DocumentInspectionReport:
    filename: str
    suffix: str
    file_type: str
    document_type: str
    parser_strategy: str
    page_count: int = 0
    text_chars: int = 0
    avg_chars_per_page: float = 0.0
    image_count: int = 0
    image_pages: int = 0
    image_page_ratio: float = 0.0
    rotated_pages: list[int] = field(default_factory=list)
    has_text_layer: bool = False
    needs_ocr: bool = False
    requires_visual_review: bool = False
    quality_score: float = 1.0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_metadata(self) -> dict[str, Any]:
        return {
            "document_type": self.document_type,
            "parser_strategy": self.parser_strategy,
            "page_count": self.page_count,
            "text_chars": self.text_chars,
            "avg_chars_per_page": self.avg_chars_per_page,
            "image_count": self.image_count,
            "image_page_ratio": self.image_page_ratio,
            "has_text_layer": self.has_text_layer,
            "needs_ocr": self.needs_ocr,
            "requires_visual_review": self.requires_visual_review,
            "quality_score": self.quality_score,
            "inspection_warnings": "; ".join(self.warnings),
        }


def inspect_document(path: Path) -> DocumentInspectionReport:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return inspect_pdf(path)
    if suffix in {".md", ".markdown"}:
        return DocumentInspectionReport(
            filename=path.name,
            suffix=suffix,
            file_type="markdown",
            document_type="structured_text",
            parser_strategy="heading_aware_text",
            text_chars=_safe_text_length(path),
            has_text_layer=True,
        )
    if suffix == ".txt":
        return DocumentInspectionReport(
            filename=path.name,
            suffix=suffix,
            file_type="text",
            document_type="plain_text",
            parser_strategy="paragraph_recursive_text",
            text_chars=_safe_text_length(path),
            has_text_layer=True,
        )
    return DocumentInspectionReport(
        filename=path.name,
        suffix=suffix,
        file_type="unsupported",
        document_type="unsupported",
        parser_strategy="unsupported",
        quality_score=0.0,
        warnings=["unsupported_suffix"],
    )


def inspect_pdf(path: Path) -> DocumentInspectionReport:
    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        return DocumentInspectionReport(
            filename=path.name,
            suffix=".pdf",
            file_type="pdf",
            document_type="damaged_pdf",
            parser_strategy="reject",
            quality_score=0.0,
            requires_visual_review=True,
            warnings=[f"open_failed:{type(exc).__name__}"],
        )

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            return DocumentInspectionReport(
                filename=path.name,
                suffix=".pdf",
                file_type="pdf",
                document_type="encrypted_pdf",
                parser_strategy="reject",
                quality_score=0.0,
                requires_visual_review=True,
                warnings=["encrypted_pdf_requires_password"],
            )

    page_count = len(reader.pages)
    page_text_lengths: list[int] = []
    image_count = 0
    image_pages = 0
    rotated_pages: list[int] = []

    for page_index, page in enumerate(reader.pages, start=1):
        text = ""
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text_length = len(_normalize_text(text))
        page_text_lengths.append(text_length)

        page_image_count = _count_page_images(page)
        image_count += page_image_count
        if page_image_count:
            image_pages += 1

        rotation = int(page.get("/Rotate", 0) or 0) % 360
        if rotation:
            rotated_pages.append(page_index)

    text_chars = sum(page_text_lengths)
    avg_chars_per_page = round(text_chars / page_count, 1) if page_count else 0.0
    image_page_ratio = round(image_pages / page_count, 3) if page_count else 0.0
    has_text_layer = text_chars > 0

    document_type, parser_strategy, needs_ocr = _classify_pdf(
        avg_chars_per_page=avg_chars_per_page,
        image_page_ratio=image_page_ratio,
        has_text_layer=has_text_layer,
    )
    warnings = _pdf_warnings(
        document_type=document_type,
        avg_chars_per_page=avg_chars_per_page,
        image_page_ratio=image_page_ratio,
        rotated_pages=rotated_pages,
        needs_ocr=needs_ocr,
    )
    quality_score = _quality_score(
        avg_chars_per_page=avg_chars_per_page,
        image_page_ratio=image_page_ratio,
        rotated_pages=rotated_pages,
        needs_ocr=needs_ocr,
    )

    return DocumentInspectionReport(
        filename=path.name,
        suffix=".pdf",
        file_type="pdf",
        document_type=document_type,
        parser_strategy=parser_strategy,
        page_count=page_count,
        text_chars=text_chars,
        avg_chars_per_page=avg_chars_per_page,
        image_count=image_count,
        image_pages=image_pages,
        image_page_ratio=image_page_ratio,
        rotated_pages=rotated_pages,
        has_text_layer=has_text_layer,
        needs_ocr=needs_ocr,
        requires_visual_review=needs_ocr or bool(rotated_pages),
        quality_score=quality_score,
        warnings=warnings,
    )


def split_text_document(path: Path, text: str) -> list[Document]:
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return split_markdown_by_headings(path, text)
    return [
        Document(
            page_content=text,
            metadata={
                "source": str(path),
                "heading_path": "全文",
                "section_title": "全文",
                "parser_strategy": "paragraph_recursive_text",
            },
        )
    ]


def split_markdown_by_headings(path: Path, text: str) -> list[Document]:
    lines = text.splitlines()
    sections: list[Document] = []
    heading_stack: list[tuple[int, str]] = []
    current_lines: list[str] = []
    current_heading = "全文"

    def flush() -> None:
        content = "\n".join(current_lines).strip()
        if not content:
            return
        heading_path = " > ".join(title for _, title in heading_stack) or current_heading
        sections.append(
            Document(
                page_content=content,
                metadata={
                    "source": str(path),
                    "heading_path": heading_path,
                    "section_title": heading_stack[-1][1] if heading_stack else current_heading,
                    "parser_strategy": "heading_aware_text",
                },
            )
        )

    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            flush()
            current_lines = [line]
            level = len(match.group(1))
            title = match.group(2).strip()
            heading_stack = [(lvl, name) for lvl, name in heading_stack if lvl < level]
            heading_stack.append((level, title))
            current_heading = title
        else:
            current_lines.append(line)

    flush()

    if sections:
        return sections
    return [
        Document(
            page_content=text,
            metadata={
                "source": str(path),
                "heading_path": "全文",
                "section_title": "全文",
                "parser_strategy": "heading_aware_text",
            },
        )
    ]


def _classify_pdf(
    *,
    avg_chars_per_page: float,
    image_page_ratio: float,
    has_text_layer: bool,
) -> tuple[str, str, bool]:
    if not has_text_layer and image_page_ratio > 0:
        return "scanned_or_photo_pdf", "ocr_with_preprocessing_required", True
    if avg_chars_per_page < TEXT_DENSITY_LOW and image_page_ratio >= 0.5:
        return "scanned_or_photo_pdf", "ocr_with_preprocessing_required", True
    if avg_chars_per_page < TEXT_DENSITY_LOW:
        return "low_text_pdf", "text_layer_with_manual_review", False
    if image_page_ratio > 0.3:
        return "mixed_pdf", "text_layer_plus_optional_image_ocr", False
    return "text_pdf", "text_layer", False


def _pdf_warnings(
    *,
    document_type: str,
    avg_chars_per_page: float,
    image_page_ratio: float,
    rotated_pages: list[int],
    needs_ocr: bool,
) -> list[str]:
    warnings = []
    if needs_ocr:
        warnings.append("text_layer_too_sparse_or_image_dominant")
    if rotated_pages:
        warnings.append(f"rotated_pages:{','.join(str(page) for page in rotated_pages)}")
    if document_type == "mixed_pdf":
        warnings.append("contains_text_and_images")
    if avg_chars_per_page < TEXT_DENSITY_LOW:
        warnings.append("low_text_density")
    if image_page_ratio >= 0.5:
        warnings.append("image_dominant_pages")
    if needs_ocr:
        warnings.append("deskew_blur_detection_requires_rendered_page_images")
    return warnings


def _quality_score(
    *,
    avg_chars_per_page: float,
    image_page_ratio: float,
    rotated_pages: list[int],
    needs_ocr: bool,
) -> float:
    score = 1.0
    if avg_chars_per_page < TEXT_DENSITY_GOOD:
        score -= 0.25
    if avg_chars_per_page < TEXT_DENSITY_LOW:
        score -= 0.3
    if image_page_ratio > 0.3:
        score -= 0.15
    if rotated_pages:
        score -= 0.1
    if needs_ocr:
        score -= 0.25
    return round(max(0.0, min(1.0, score)), 2)


def _count_page_images(page: Any) -> int:
    count = 0
    try:
        xobjects = page.get("/Resources", {}).get("/XObject", {})
        xobjects = xobjects.get_object() if hasattr(xobjects, "get_object") else xobjects
        for obj in xobjects.values():
            xobj = obj.get_object() if hasattr(obj, "get_object") else obj
            if xobj.get("/Subtype") == "/Image":
                count += 1
    except Exception:
        pass
    return count


def _safe_text_length(path: Path) -> int:
    try:
        return len(_normalize_text(path.read_text(encoding="utf-8")))
    except UnicodeDecodeError:
        try:
            return len(_normalize_text(path.read_text(encoding="gb18030")))
        except Exception:
            return 0
    except Exception:
        return 0


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")
