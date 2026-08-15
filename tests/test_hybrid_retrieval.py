from trace_memory.retrieval import HybridRanker


def test_hybrid_ranker_explains_and_prioritizes_security_scoped_memory() -> None:
    ranked = HybridRanker().rank([
        {"display_id": "TRACE-MEMORY-001", "vector_distance": 0.1, "confidence": 0.8,
         "security_relevant": True, "scopes": ["src/auth.py"], "feedback_score": 0.2},
        {"display_id": "TRACE-MEMORY-002", "vector_distance": 0.1, "confidence": 0.8,
         "security_relevant": False, "scopes": [], "feedback_score": 0.2},
    ], changed_paths=["src/auth.py"])
    assert ranked[0].memory_id == "TRACE-MEMORY-001"
    assert "security_boost=0.15" in ranked[0].explanation
