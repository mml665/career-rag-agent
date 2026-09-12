import unittest
from unittest.mock import MagicMock, patch

from rag_agent import DashScopeMultimodalEmbeddings


class DashScopeEmbeddingTests(unittest.TestCase):
    def test_parse_embeddings_orders_by_index(self):
        payload = {
            "output": {
                "embeddings": [
                    {"index": 1, "embedding": [0.3, 0.4], "type": "text"},
                    {"index": 0, "embedding": [0.1, 0.2], "type": "text"},
                ]
            }
        }

        vectors = DashScopeMultimodalEmbeddings.parse_embeddings(payload, expected_count=2)

        self.assertEqual(vectors, [[0.1, 0.2], [0.3, 0.4]])

    def test_parse_embeddings_orders_by_text_index(self):
        payload = {
            "output": {
                "embeddings": [
                    {"text_index": 1, "embedding": [0.7, 0.8], "type": "text"},
                    {"text_index": 0, "embedding": [0.5, 0.6], "type": "text"},
                ]
            }
        }

        vectors = DashScopeMultimodalEmbeddings.parse_embeddings(payload, expected_count=2)

        self.assertEqual(vectors, [[0.5, 0.6], [0.7, 0.8]])

    def test_parse_embeddings_accepts_openai_compatible_data(self):
        payload = {
            "data": [
                {"index": 1, "embedding": [0.3, 0.4], "object": "embedding"},
                {"index": 0, "embedding": [0.1, 0.2], "object": "embedding"},
            ],
            "model": "qwen3.7-text-embedding",
            "object": "list",
        }

        vectors = DashScopeMultimodalEmbeddings.parse_embeddings(payload, expected_count=2)

        self.assertEqual(vectors, [[0.1, 0.2], [0.3, 0.4]])

    def test_text_embedding_request_uses_texts_payload(self):
        embedding = DashScopeMultimodalEmbeddings(
            api_key="test-key",
            model="qwen3.7-text-embedding",
            endpoint="https://example.com/embeddings",
            dimension=768,
        )
        response = MagicMock()
        response.json.return_value = {
            "output": {
                "embeddings": [
                    {"index": 0, "embedding": [0.1, 0.2], "type": "text"},
                ]
            }
        }

        with patch("rag_agent.requests.post", return_value=response) as post:
            vectors = embedding.embed_documents(["hello"])

        self.assertEqual(vectors, [[0.1, 0.2]])
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "qwen3.7-text-embedding")
        self.assertEqual(payload["input"], {"texts": ["hello"]})

    def test_parse_embeddings_rejects_missing_vectors(self):
        with self.assertRaises(RuntimeError):
            DashScopeMultimodalEmbeddings.parse_embeddings({"output": {}}, expected_count=1)


if __name__ == "__main__":
    unittest.main()
