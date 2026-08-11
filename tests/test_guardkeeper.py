from lore.agents.guardkeeper import FindingLayer, Guardkeeper


class Candidates:
    def vector_candidates(self, **_: object) -> list[dict[str, object]]:
        return [{"display_id": "LORE-MEMORY-001", "decision": "Use parameterized SQL queries", "security_relevant": True}]


def test_guardkeeper_always_detects_direct_security_regressions() -> None:
    review = Guardkeeper(Candidates()).review(organization_id="org", repository_id="repo", embedding="[0,0,1]", diff="password=token\neval(user_input)")
    assert {finding.layer for finding in review.findings} >= {FindingLayer.SECURITY}


def test_guardkeeper_records_unfulfilled_promises_and_memory_conflicts() -> None:
    review = Guardkeeper(Candidates()).review(organization_id="org", repository_id="repo", embedding="[0,0,1]", diff="use parameterized query = 'SELECT'", promises=["add retries"])
    assert any(finding.layer is FindingLayer.PROMISE for finding in review.findings)
    assert any(finding.layer is FindingLayer.MEMORY_CONFLICT for finding in review.findings)
