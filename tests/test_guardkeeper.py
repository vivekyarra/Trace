from trace_memory.agents.guardkeeper import FindingLayer, Guardkeeper


class Candidates:
    def vector_candidates(self, **_: object) -> list[dict[str, object]]:
        return [{"display_id": "TRACE-MEMORY-001", "decision": "Use parameterized SQL queries", "security_relevant": True}]


def test_guardkeeper_always_detects_direct_security_regressions() -> None:
    review = Guardkeeper(Candidates()).review(organization_id="org", repository_id="repo", embedding="[0,0,1]", diff="password=token\neval(user_input)")
    assert {finding.layer for finding in review.findings} >= {FindingLayer.SECURITY}


def test_guardkeeper_records_unfulfilled_promises_and_memory_conflicts() -> None:
    review = Guardkeeper(Candidates()).review(organization_id="org", repository_id="repo", embedding="[0,0,1]", diff="use parameterized query = 'SELECT'", promises=["add retries"])
    assert any(finding.layer is FindingLayer.PROMISE for finding in review.findings)
    assert any(finding.layer is FindingLayer.MEMORY_CONFLICT for finding in review.findings)
    assert review.memory_consequence.memory_changed_review is True
    assert review.memory_consequence.governing_memory_ids == ["TRACE-MEMORY-001"]
    assert review.memory_consequence.memory_conflict_findings == 1
    assert review.memory_consequence.independent_findings == 1
    assert "1 memory-conflict finding(s) would be absent" in review.memory_consequence.counterfactual


class NoCandidates:
    def vector_candidates(self, **_: object) -> list[dict[str, object]]:
        return []


def test_guardkeeper_proves_when_memory_did_not_change_the_review() -> None:
    review = Guardkeeper(NoCandidates()).review(
        organization_id="org", repository_id="repo", embedding="[0,0,1]", diff="password=token",
    )
    assert review.memory_consequence.memory_changed_review is False
    assert review.memory_consequence.governing_memory_ids == []
    assert review.memory_consequence.memory_conflict_findings == 0
    assert review.memory_consequence.independent_findings == 1
