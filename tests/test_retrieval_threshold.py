import tempfile
import unittest
from pathlib import Path

from langchain_core.documents import Document

from rag_agent import RagAssistant, RagConfig


class FakeVectorStore:
    def similarity_search_with_relevance_scores(self, question: str, k: int):
        return [
            (Document(page_content="high", metadata={"source_name": "high.md"}), 0.8),
            (Document(page_content="low", metadata={"source_name": "low.md"}), 0.3),
        ][:k]


class RetrievalThresholdTests(unittest.TestCase):
    def build_assistant(self, root: Path) -> RagAssistant:
        assistant = RagAssistant(
            RagConfig(
                docs_dir=root / "documents",
                upload_dir=root / "uploads",
                chroma_dir=root / "chroma",
                history_path=root / "history.jsonl",
                min_relevance_score=0.45,
            )
        )
        assistant._vectorstore = lambda: FakeVectorStore()
        return assistant

    def test_retrieve_filters_chunks_below_threshold_for_answering(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            assistant = self.build_assistant(Path(temp_dir))

            results = assistant._retrieve("query", top_k=2)

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0][0].page_content, "high")

    def test_search_exposes_all_candidates_and_threshold_decision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            assistant = self.build_assistant(Path(temp_dir))

            results = assistant.search("query", top_k=2)

            self.assertEqual(len(results), 2)
            self.assertTrue(results[0]["accepted"])
            self.assertFalse(results[1]["accepted"])
            self.assertEqual(results[1]["score"], 0.3)


if __name__ == "__main__":
    unittest.main()
