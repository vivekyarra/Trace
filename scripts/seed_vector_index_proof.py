"""Seed and measure a tenant-isolated CockroachDB vector-index proof corpus.

The benchmark deliberately uses the production ``memories`` table and its
tenant-prefixed 1024-dimensional vector index.  Rows live in a separate
organization/repository, so they cannot be retrieved by the public Trace demo.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
import statistics
from datetime import datetime, timezone
from time import perf_counter
from uuid import UUID, uuid5

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

NAMESPACE = UUID("9111f801-56b3-4f30-867b-1f577abfb20f")
ORGANIZATION_ID = uuid5(NAMESPACE, "trace-vector-index-proof-organization")
REPOSITORY_ID = uuid5(NAMESPACE, "trace-vector-index-proof-repository")
DEFAULT_ROWS = 10_000
DIMENSIONS = 1_024
_DURATION = re.compile(r"^execution time:\s*([0-9.]+)(µs|ms|s)$")


def deterministic_vector(seed: int) -> list[float]:
    """Return a repeatable, normalized Titan-sized vector."""
    generator = random.Random(seed)
    values = [generator.uniform(-1.0, 1.0) for _ in range(DIMENSIONS)]
    magnitude = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / magnitude for value in values]


def serialize_vector(values: list[float]) -> str:
    return "[" + ",".join(format(value, ".9g") for value in values) + "]"


def duration_ms(line: str) -> float | None:
    """Parse CockroachDB EXPLAIN ANALYZE duration lines into milliseconds."""
    match = _DURATION.match(line.strip())
    if match is None:
        return None
    value = float(match.group(1))
    return value * {"µs": 0.001, "ms": 1.0, "s": 1_000.0}[match.group(2)]


def analyzed_latencies(plan: list[str]) -> tuple[float, float]:
    """Return total query and vector-operator execution from an analyzed plan."""
    total = next((duration for line in plan if (duration := duration_ms(line)) is not None), None)
    vector = None
    for index, line in enumerate(plan):
        if "vector search" not in line.lower():
            continue
        vector = next(
            (duration for item in plan[index + 1 :] if (duration := duration_ms(item)) is not None),
            None,
        )
        break
    if total is None or vector is None:
        raise RuntimeError("CockroachDB analyzed plan did not expose execution timings")
    return total, vector


def latency_summary(latencies: list[float]) -> dict[str, float]:
    ordered = sorted(latencies)
    return {
        "min": round(min(latencies), 2),
        "median": round(statistics.median(latencies), 2),
        "p95": round(ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)], 2),
        "max": round(max(latencies), 2),
    }


def seed(database: Engine, target_rows: int) -> int:
    now = datetime.now(timezone.utc)
    with database.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE organizations
                SET name = 'Trace Production Evidence 2026-08-15'
                WHERE name = 'Trace Live Evidence 2026-08-11'
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO organizations (id, name)
                VALUES (:id, 'Trace Vector Index Proof 2026-08-15')
                ON CONFLICT (name) DO NOTHING
                """
            ),
            {"id": ORGANIZATION_ID},
        )
        connection.execute(
            text(
                """
                INSERT INTO repositories (
                    id, organization_id, provider, external_project_id, name, default_branch
                ) VALUES (
                    :id, :organization_id, 'benchmark', 'trace-vector-index-proof-v1',
                    'Trace Vector Index Proof', 'main'
                ) ON CONFLICT (provider, external_project_id) DO NOTHING
                """
            ),
            {"id": REPOSITORY_ID, "organization_id": ORGANIZATION_ID},
        )
        existing = int(
            connection.execute(
                text("SELECT count(*) FROM memories WHERE repository_id = :repository_id"),
                {"repository_id": REPOSITORY_ID},
            ).scalar_one()
        )

    insert_sql = text(
        """
        INSERT INTO memories (
            id, organization_id, repository_id, display_id, memory_type, title, decision,
            rationale, rejected_alternative, future_implication, status, confidence,
            confidence_basis, security_relevant, severity, content_hash, semantic_key,
            embedding, embedding_model, embedding_version, embedded_at, valid_from,
            version, created_by_actor_type, created_by_actor_id, created_at, updated_at
        ) VALUES (
            :id, :organization_id, :repository_id, :display_id, 'ARCHITECTURAL_DECISION',
            :title, :decision, :rationale, :rejected_alternative, :future_implication,
            'ACTIVE', 0.80, 'deterministic vector-index benchmark corpus', false, NULL,
            :content_hash, :semantic_key, CAST(:embedding AS VECTOR),
            'amazon.titan-embed-text-v2:0', 'v2-1024', :now, :now, 1, 'SYSTEM',
            'vector-index-proof', :now, :now
        ) ON CONFLICT (repository_id, content_hash) DO NOTHING
        """
    )
    # CockroachDB's vector index is maintained transactionally. Small batches
    # avoid long transactions and partition-split retry storms while seeding.
    batch_size = 10
    for start in range(existing, target_rows, batch_size):
        rows = []
        for number in range(start, min(start + batch_size, target_rows)):
            topic = number % 40
            body = f"benchmark memory {number} for service-{topic} architectural policy"
            rows.append(
                {
                    "id": uuid5(NAMESPACE, f"memory-{number}"),
                    "organization_id": ORGANIZATION_ID,
                    "repository_id": REPOSITORY_ID,
                    "display_id": f"TRACE-MEMORY-{900000 + number}",
                    "title": f"Service {topic} production decision {number}",
                    "decision": f"Route service-{topic} work through the durable production path.",
                    "rationale": f"Historical operational evidence for corpus row {number}.",
                    "rejected_alternative": "An unbounded synchronous request path.",
                    "future_implication": f"Changes touching service-{topic} must preserve durability.",
                    "content_hash": hashlib.sha256(body.encode()).hexdigest(),
                    "semantic_key": f"benchmark/service-{topic}/{number}",
                    "embedding": serialize_vector(deterministic_vector(number)),
                    "now": now,
                }
            )
        with database.begin() as connection:
            connection.execute(insert_sql, rows)

    with database.begin() as connection:
        connection.execute(text("CREATE STATISTICS vector_index_proof_stats FROM memories"))
        return int(
            connection.execute(
                text("SELECT count(*) FROM memories WHERE repository_id = :repository_id"),
                {"repository_id": REPOSITORY_ID},
            ).scalar_one()
        )


def measure(database: Engine, repetitions: int = 30) -> dict[str, object]:
    query_vector = serialize_vector(deterministic_vector(7))
    statement = text(
        """
        WITH nearest AS MATERIALIZED (
            SELECT id, embedding <-> CAST(:embedding AS VECTOR) AS vector_distance
            FROM memories
            WHERE organization_id = :organization_id
              AND repository_id = :repository_id
            ORDER BY embedding <-> CAST(:embedding AS VECTOR)
            LIMIT 100
        )
        SELECT m.id, m.display_id, nearest.vector_distance
        FROM nearest JOIN memories m ON m.id = nearest.id
        WHERE m.status = 'ACTIVE' AND m.embedding IS NOT NULL
        ORDER BY nearest.vector_distance LIMIT 20
        """
    )
    params = {
        "organization_id": ORGANIZATION_ID,
        "repository_id": REPOSITORY_ID,
        "embedding": query_vector,
    }
    latencies: list[float] = []
    with database.connect() as connection:
        connection.execute(statement, params).all()
        for _ in range(repetitions):
            started = perf_counter()
            connection.execute(statement, params).all()
            latencies.append((perf_counter() - started) * 1_000)
        plan = [str(row[0]) for row in connection.execute(text("EXPLAIN " + statement.text), params).all()]
        analyzed = [
            str(row[0])
            for row in connection.execute(
                text("EXPLAIN ANALYZE (DISTSQL) " + statement.text), params
            ).all()
        ]
        analyzed_total: list[float] = []
        analyzed_vector: list[float] = []
        for _ in range(repetitions):
            analyzed = [
                str(row[0])
                for row in connection.execute(
                    text("EXPLAIN ANALYZE (DISTSQL) " + statement.text), params
                ).all()
            ]
            total_ms, vector_ms = analyzed_latencies(analyzed)
            analyzed_total.append(total_ms)
            analyzed_vector.append(vector_ms)
    return {
        "organization_id": str(ORGANIZATION_ID),
        "repository_id": str(REPOSITORY_ID),
        "dimensions": DIMENSIONS,
        "repetitions": repetitions,
        "client_round_trip_latency_ms": latency_summary(latencies),
        "database_execution_latency_ms": latency_summary(analyzed_total),
        "vector_operator_latency_ms": latency_summary(analyzed_vector),
        "plan": plan,
        "analyzed_plan": analyzed,
        "vector_index_used": any("memories_embedding_vector_idx" in line for line in plan),
        "full_scan": any("FULL SCAN" in line.upper() for line in plan),
    }


def main() -> int:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    for scheme in ("postgresql://", "postgres://"):
        if database_url.startswith(scheme):
            database_url = database_url.replace(scheme, "cockroachdb://", 1)
            break
    database = create_engine(database_url, pool_pre_ping=True)
    target_rows = int(os.environ.get("TRACE_VECTOR_PROOF_ROWS", str(DEFAULT_ROWS)))
    count = seed(database, target_rows)
    result = measure(database)
    result["seeded_rows"] = count
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["vector_index_used"] and not result["full_scan"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
