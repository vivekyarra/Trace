from datetime import datetime, timezone
from uuid import UUID, uuid4

from trace_memory.agents import Guardkeeper
from trace_memory.ai.bedrock import EmbeddingResult
from trace_memory.runtime.automation import GitHubAutomation


class Embedder:
    model_id = "amazon.titan-embed-text-v2:0"

    def embed(self, text: str) -> EmbeddingResult:
        assert text.strip()
        return EmbeddingResult([0.01] * 1024, self.model_id, "v2", 1024, datetime.now(timezone.utc))


class Reasoner:
    model_id = "anthropic.test"

    def reason_json(self, *, output_type, **kwargs):
        if output_type.__name__ == "RerankEnvelope":
            return output_type.model_validate({
                "selections": [{"memory_id": "TRACE-MEMORY-00701", "score": 0.97,
                                "reason": "The proposed auth cache recreates the recorded revocation risk."}],
                "final_action": "cite memory and block until revocation is preserved",
            })
        if output_type.__name__ == "AutomationEnvelope" and "Extract durable" in str(kwargs.get("system", "")):
            return output_type.model_validate({
                "comment": "Captured the authorization revocation invariant.",
                "decisions": [{
                    "title": "Preserve authorization revocation",
                    "decision": "Authorization caches must be invalidated immediately when access is revoked.",
                    "rationale": "A stale cache previously allowed revoked users to retain access.",
                    "future_implication": "Every authorization cache must include revocation invalidation.",
                    "security_relevant": True,
                    "confidence": 0.98,
                }],
            })
        return output_type.model_validate({"comment": "Guardkeeper found a relevant prior decision.", "decisions": []})


class Store:
    def __init__(self) -> None:
        self.memories = []
        self.sources = []
        self.retrievals = []

    def create_with_provenance(self, memory, *, sources, scopes, **kwargs):
        self.memories.append(memory)
        self.sources.extend(sources)
        return True

    def vector_candidates(self, **kwargs):
        memory = self.memories[0]
        source = self.sources[0]
        return [{
            "id": memory.id, "display_id": memory.display_id, "decision": memory.decision,
            "rationale": memory.rationale, "confidence": memory.confidence,
            "security_relevant": memory.security_relevant, "vector_distance": 0.03,
            "scopes": ["src/api/auth.py"], "feedback_score": 1.0, "relationships": [],
            "sources": [{"source_url": source.source_url, "source_excerpt": source.source_excerpt}],
        }]

    def record_retrieval(self, **kwargs):
        self.retrievals.append(kwargs)
        return UUID("00000000-0000-0000-0000-000000000123")


class Effects:
    def checkpoint_task(self, *args, **kwargs):
        pass

    def record_external_effect(self, *args, **kwargs):
        pass


class GitHub:
    def __init__(self) -> None:
        self.comments = []

    def pull_request(self, number):
        if number == 7:
            return {"id": 700, "title": "Fix authorization revocation cache", "body": "Invalidate on revoke",
                    "merged_at": "2026-08-11T10:00:00Z", "merge_commit_sha": "a" * 40,
                    "html_url": "https://github.com/acme/trace/pull/7", "user": {"id": 1, "login": "alice"}}
        return {"id": 800, "title": "Add a faster authorization cache",
                "body": "We will cache permissions", "merged_at": None,
                "html_url": "https://github.com/acme/trace/pull/8", "user": {"id": 2, "login": "bob"}}

    def pull_request_files(self, number):
        return [{"filename": "src/api/auth.py", "patch": "+cache permissions for ten minutes"}]

    def complete_pull_request_diff(self, number, files):
        return files[0]["patch"], True

    def post_comment_once(self, number, task_id, body):
        self.comments.append((number, body))
        return {"id": 9000 + number, "body": body}


def test_merge_remember_retrieve_and_cite_source_loop() -> None:
    github, store, reasoner = GitHub(), Store(), Reasoner()
    automation = GitHubAutomation(
        github=github, reasoner=reasoner, embedder=Embedder(),
        guardkeeper=Guardkeeper(store, reasoner=reasoner), memories=store,
        organization_id=uuid4(), repository_id=uuid4(), effects=Effects(),
    )

    automation({"aggregate_id": str(uuid4()), "payload": {"pull_request_number": 7, "delivery_id": "A"}})
    assert len(store.memories[0].embedding) == 1024
    assert store.memories[0].embedding_model == "amazon.titan-embed-text-v2:0"
    assert store.sources[0].source_url == "https://github.com/acme/trace/pull/7"

    automation({"aggregate_id": str(uuid4()), "payload": {"pull_request_number": 8, "delivery_id": "B"}})
    assert store.retrievals[0]["selected_ids"] == {"TRACE-MEMORY-00701"}
    assert store.retrievals[0]["llm_scores"] == {"TRACE-MEMORY-00701": 0.97}
    assert store.retrievals[0]["ranked"][0].semantic_score == 0.97
    assert "https://github.com/acme/trace/pull/7" in github.comments[-1][1]
    assert "00000000-0000-0000-0000-000000000123" in github.comments[-1][1]
    assert "## Memory consequence receipt" in github.comments[-1][1]
    assert "**Memory changed this review:** yes" in github.comments[-1][1]
    assert "**Governing memories:** TRACE-MEMORY-00701" in github.comments[-1][1]
    assert "Without the selected institutional memory" in github.comments[-1][1]
