import unittest

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

    def test_parse_embeddings_rejects_missing_vectors(self):
        with self.assertRaises(RuntimeError):
            DashScopeMultimodalEmbeddings.parse_embeddings({"output": {}}, expected_count=1)


if __name__ == "__main__":
    unittest.main()
