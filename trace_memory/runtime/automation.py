"""Execute admitted GitHub tasks against Bedrock and canonical memory."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from trace_memory.agents import Guardkeeper
from trace_memory.ai.bedrock import BedrockEmbedder, BedrockReasoner
from trace_memory.domain import ActorType, Memory, MemoryStatus, MemoryType
from trace_memory.runtime.github import GitHubClient


class MemoryWriter(Protocol):
    def create(self, memory: Memory) -> None: ...


class AutomationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=300)
    decision: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    future_implication: str = Field(min_length=1)
    rejected_alternative: str | None = None
    security_relevant: bool = False
    confidence: float = Field(ge=0, le=1)


class AutomationEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    comment: str = Field(min_length=1, max_length=60_000)
    decisions: list[AutomationDecision] = Field(default_factory=list, max_length=10)


@dataclass
class GitHubAutomation:
    github: GitHubClient
    reasoner: BedrockReasoner
    embedder: BedrockEmbedder
    guardkeeper: Guardkeeper
    memories: MemoryWriter
    organization_id: UUID
    repository_id: UUID

    def __call__(self, event: dict[str, object]) -> None:
        payload = dict(event.get("payload", event))
        pr_number = payload.get("pull_request_number")
        issue_number = payload.get("issue_number")
        if pr_number:
            self._pull_request(int(pr_number), payload)
        elif issue_number:
            self._issue(int(issue_number), payload)
        elif payload.get("event") == "ping":
            return
        else:
            # Pushes are admitted for provenance but do not create noisy comments.
            return

    def _pull_request(self, number: int, payload: dict[str, object]) -> None:
        pull = self.github.pull_request(number)
        files = self.github.pull_request_files(number)
        diff = "\n".join(str(file.get("patch", "")) for file in files)[:180_000]
        if pull.get("merged_at"):
            envelope = self.reasoner.reason_json(
                system=("You are Tracekeeper. Extract only durable architectural, security, incident, "
                        "or review decisions from a merged pull request. Return JSON matching the schema."),
                user_content=f"PR: {pull.get('title')}\nBody: {pull.get('body')}\nDiff:\n{diff}",
                output_type=AutomationEnvelope, max_tokens=1800,
            )
            for index, decision in enumerate(envelope.decisions, 1):
                self.memories.create(self._memory(number, index, str(pull.get("title", "")), decision))
            if envelope.comment:
                self.github.post_comment(number, envelope.comment + "\n\n— Trace")
            return

        embedding = self.embedder.embed(diff or str(pull.get("title", "pull request")))
        vector = "[" + ",".join(str(value) for value in embedding.values) + "]"
        review = self.guardkeeper.review(
            organization_id=self.organization_id, repository_id=self.repository_id,
            embedding=vector, diff=diff, promises=_promises(str(pull.get("body", ""))),
        )
        deterministic = "\n".join(
            f"- **{finding.severity} / {finding.layer.value}:** {finding.summary} Evidence: {finding.evidence}"
            for finding in review.findings
        ) or "- No deterministic conflicts or security sentinels fired."
        envelope = self.reasoner.reason_json(
            system=("You are Trace GUARDKEEPER. Assess architectural conflicts, stated promises, code "
                    "intelligence, and security. The deterministic findings are authoritative. Return JSON."),
            user_content=f"PR: {pull.get('title')}\nBody: {pull.get('body')}\nFindings:\n{deterministic}\nDiff:\n{diff}",
            output_type=AutomationEnvelope, max_tokens=1400,
        )
        self.github.post_comment(number, envelope.comment + "\n\n" + deterministic + "\n\n— Trace")

    def _issue(self, number: int, payload: dict[str, object]) -> None:
        issue = self.github.issue(number)
        comments = self.github.issue_comments(number)
        thread = "\n".join(f"@{item.get('user', {}).get('login')}: {item.get('body', '')}" for item in comments)[-100_000:]
        envelope = self.reasoner.reason_json(
            system=("You are Trace SPECFORGE. Produce a failure pre-mortem, hard technical questions, "
                    "acceptance criteria, security precedents, and a compute/carbon estimate. Return JSON."),
            user_content=(f"Issue: {issue.get('title')}\nBody: {issue.get('body')}\n"
                          f"Event metadata: {payload}\nThread:\n{thread}"),
            output_type=AutomationEnvelope, max_tokens=1400,
        )
        self.github.post_comment(number, envelope.comment + "\n\n— Trace")

    def _memory(self, pr_number: int, index: int, pr_title: str, item: AutomationDecision) -> Memory:
        content = f"{item.decision}\n{item.rationale}\n{item.future_implication}"
        digest = hashlib.sha256(content.encode()).hexdigest()
        display = f"TRACE-MEMORY-{pr_number:03d}{index:02d}"
        return Memory(
            organization_id=self.organization_id, repository_id=self.repository_id,
            display_id=display, memory_type=(MemoryType.SECURITY_CONSTRAINT if item.security_relevant
                                             else MemoryType.ARCHITECTURAL_DECISION),
            title=item.title or pr_title, decision=item.decision, rationale=item.rationale,
            rejected_alternative=item.rejected_alternative, future_implication=item.future_implication,
            status=MemoryStatus.ACTIVE, confidence=item.confidence,
            confidence_basis=f"Bedrock extraction from merged PR #{pr_number}",
            security_relevant=item.security_relevant, content_hash=digest,
            semantic_key=hashlib.sha256(item.decision.casefold().encode()).hexdigest(),
            created_by_actor_type=ActorType.AGENT, created_by_actor_id="tracekeeper",
        )


def _promises(body: str) -> list[str]:
    return [line.strip(" -*") for line in body.splitlines()
            if any(token in line.casefold() for token in ("will ", "must ", "acceptance"))][:20]
