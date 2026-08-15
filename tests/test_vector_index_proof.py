from scripts.seed_vector_index_proof import analyzed_latencies, duration_ms, latency_summary


def test_duration_parser_normalizes_explain_units() -> None:
    assert duration_ms("execution time: 63µs") == 0.063
    assert duration_ms("execution time: 2ms") == 2
    assert duration_ms("execution time: 0.5s") == 500


def test_analyzed_plan_separates_database_and_vector_operator_time() -> None:
    plan = [
        "execution time: 102ms",
        "• vector search",
        "execution time: 21ms",
    ]
    assert analyzed_latencies(plan) == (102, 21)


def test_latency_summary_uses_nearest_rank_p95() -> None:
    assert latency_summary([float(value) for value in range(1, 21)]) == {
        "min": 1.0,
        "median": 10.5,
        "p95": 19.0,
        "max": 20.0,
    }
