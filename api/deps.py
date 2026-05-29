from functools import lru_cache
from pathlib import Path

from career_store import CareerStore
from rag_agent import RagAssistant, RagConfig


@lru_cache
def get_career_store() -> CareerStore:
    return CareerStore(db_path=Path("data/career.db"))


@lru_cache
def get_rag_assistant() -> RagAssistant:
    return RagAssistant(RagConfig())
