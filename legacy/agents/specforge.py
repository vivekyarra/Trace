"""
SPECFORGE agent: triggered when @trace is mentioned in a GitLab issue. Reads the
issue, finds relevant Trace memories, and generates a full engineering spec
posted as a structured comment. Also handles spec approval and MR spec compliance.
"""

import json
import logging
import re

from config import TRACE_SPEC_SLUG_PREFIX
from core.gitlab_client import GitLabClient
from core.claude_client import ClaudeClient
from core.memory import MemoryStore

logger = logging.getLogger("trace.specforge")

# Stop words for keyword extraction (Step 4).
_STOP_WORDS = frozenset([
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "and", "or", "but", "if", "then", "that", "this", "it", "its", "we",
    "i", "you", "he", "she", "they", "what", "which", "who", "when",
    "where", "how", "all", "any", "both", "each", "few", "more", "most",
    "other", "some", "such", "no", "not", "only", "same", "so", "than",
    "too", "very", "just", "new", "add", "update", "change", "get", "use",
])


def _extract_keywords(text: str) -> set[str]:
    """
    Extracts meaningful keywords from text for memory relevance matching.
    Lowercases, splits on non-alphanumeric characters, removes stop words
    and short tokens.
    """
    tokens = re.split(r"[^a-z0-9]+", text.lower())
    return {
        t for t in tokens
        if len(t) > 3 and t not in _STOP_WORDS
    }


async def run_specforge(payload: dict) -> None:
    """
    Run SPECFORGE: read issue, find relevant memories, generate engineering
    spec via Claude, and post as issue comments.
    """
    issue_iid: int | None = None
    try:
        # — Step 1: Extract data from webhook payload —
        issue_iid = int(payload["object_attributes"]["iid"])
        issue_title = payload["object_attributes"]["title"]
        issue_description = payload["object_attributes"]["description"] or ""
        issue_author = payload["user"]["username"]
        issue_url = payload["object_attributes"]["url"]

        # — Step 2: Initialise clients —
        gitlab = GitLabClient()
        claude = ClaudeClient()
        memory_store = MemoryStore(gitlab)

        # — Step 3: Post immediate acknowledgement comment (before any heavy work) —
        gitlab.post_issue_comment(
            issue_iid,
            f"🧠 Trace — SPECFORGE\n\n"
            f"*@{issue_author} — Analysing your issue and generating an engineering "
            "specification. This will take about 30 seconds...*",
        )

        # — Step 4: Find relevant memories —
        all_memories = memory_store.get_all_memories()
        if not all_memories:
            relevant_memories: list[dict] = []
        else:
            combined_issue_text = f"{issue_title} {issue_description}"
            issue_keywords = _extract_keywords(combined_issue_text)
            relevant_memories = []
            for mem in all_memories:
                decision_lower = (mem.get("decision") or "").lower()
                implication_lower = (mem.get("future_implication") or "").lower()
                governs_lower = [ (p or "").lower() for p in (mem.get("governs_files") or []) ]
                searchable = f"{decision_lower} {implication_lower} {' '.join(governs_lower)}"
                if any(kw in searchable for kw in issue_keywords):
                    relevant_memories.append(mem)
            relevant_memories = relevant_memories[:10]

        # — Step 5: Build the user message for Claude —
        if not relevant_memories:
            relevant_block = (
                "None found. Generate the spec based on the issue description alone."
            )
        else:
            parts = []
            for m in relevant_memories:
                governs = ", ".join(m.get("governs_files") or [])
                parts.append(
                    f"---\n"
                    f"Memory #{m.get('id', '')}\n"
                    f"Decision: {m.get('decision', '')}\n"
                    f"Future implication: {m.get('future_implication', '')}\n"
                    f"Governs files: {governs}\n"
                    f"---"
                )
            relevant_block = "\n\n".join(parts)

        user_message = (
            f"ISSUE TITLE: {issue_title}\n"
            f"ISSUE AUTHOR: @{issue_author}\n"
            f"ISSUE DESCRIPTION:\n{issue_description}\n\n"
            f"RELEVANT MEMORIES:\n{relevant_block}"
        )

        # — Step 6: Call Claude —
        system_prompt = claude.load_prompt("specforge")
        response = claude.call(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=3000,
        )

        # — Step 7: Validate the response —
        if len(response) <= 100 or "Acceptance Criteria" not in response:
            gitlab.post_issue_comment(
                issue_iid,
                "🧠 Trace — SPECFORGE\n\n"
                "*Spec generation produced an incomplete result. "
                "Please try again by editing the issue description with more detail.*",
            )
            return

        # — Step 8: Post the spec and then the summary comment —
        gitlab.post_issue_comment(issue_iid, response)

        gitlab.add_issue_label(issue_iid, "trace-spec-pending")

        mem_ids_str = "none" if not relevant_memories else ", ".join(
            f"#{m.get('id', '')}" for m in relevant_memories
        )
        gitlab.post_issue_comment(
            issue_iid,
            f"🧠 Trace — SPECFORGE\n\n"
            f"✅ Spec generated. {len(relevant_memories)} relevant memories considered.\n\n"
            "**Next step:** Review the spec above, make any edits needed, then reply "
            "`trace: spec approved` or `approved` to lock this as the implementation contract.\n\n"
            f"*Relevant memories: {mem_ids_str}*",
        )

    except Exception as e:
        logger.error("SPECFORGE failed: %s", e, exc_info=True)
        try:
            if issue_iid is not None:
                gitlab = GitLabClient()
                gitlab.post_issue_comment(
                    issue_iid,
                    "🧠 Trace — SPECFORGE\n\n"
                    "*An error occurred during spec generation. Check server logs.*",
                )
            else:
                issue_iid = payload.get("object_attributes", {}).get("iid")
                if issue_iid is not None:
                    gitlab = GitLabClient()
                    gitlab.post_issue_comment(
                        int(issue_iid),
                        "🧠 Trace — SPECFORGE\n\n"
                        "*An error occurred during spec generation. Check server logs.*",
                    )
        except Exception:
            pass


def _find_spec_comment_body(notes: list[dict]) -> str | None:
    """Find the first note that looks like the SPECFORGE spec (has Engineering Specification + Acceptance Criteria)."""
    for n in notes:
        body = (n.get("body") or "").strip()
        if "Engineering Specification" in body and "Acceptance Criteria" in body:
            return body
    return None


async def handle_spec_approval(payload: dict) -> None:
    """
    When someone replies 'trace: spec approved' or 'approved' on an issue, store the spec
    in the wiki and set label trace-spec-approved.
    """
    issue_iid: int | None = None
    try:
        note_body = (payload.get("object_attributes") or {}).get("note", "").strip().lower()
        if "trace: spec approved" not in note_body and "approved" != note_body.strip():
            return
        noteable_type = (payload.get("object_attributes") or {}).get("noteable_type", "")
        if noteable_type != "Issue":
            return

        # Note Hook: issue IID is in payload.issue.iid (noteable_id is internal DB id)
        issue_iid = (payload.get("issue") or {}).get("iid") or (payload.get("object_attributes") or {}).get("noteable_id")
        if issue_iid is None:
            return
        issue_iid = int(issue_iid)
        gitlab = GitLabClient()

        notes = gitlab.get_issue_notes(issue_iid)
        spec_body = _find_spec_comment_body(notes)
        if not spec_body:
            gitlab.post_issue_comment(
                issue_iid,
                "🧠 Trace — SPECFORGE\n\n*No prior spec comment found on this issue. "
                "Mention @trace in the issue description first to generate a spec.*",
            )
            return

        slug = f"{TRACE_SPEC_SLUG_PREFIX}{issue_iid}"
        existing = gitlab.get_wiki_page(slug)
        if existing is None:
            gitlab.create_wiki_page(slug, slug, spec_body)
        else:
            gitlab.update_wiki_page(slug, spec_body)

        labels = list(gitlab.get_issue_labels(issue_iid))
        if "trace-spec-pending" in labels:
            labels.remove("trace-spec-pending")
        if "trace-spec-approved" not in labels:
            labels.append("trace-spec-approved")
        gitlab.set_issue_labels(issue_iid, labels)

        gitlab.post_issue_comment(
            issue_iid,
            "🧠 Trace — SPECFORGE\n\n✅ **Spec approved and stored.** This spec will be used to check "
            "compliance when MRs linked to this issue are opened.",
        )
    except Exception as e:
        logger.error("Spec approval failed: %s", e, exc_info=True)
        if issue_iid is not None:
            try:
                gitlab = GitLabClient()
                gitlab.post_issue_comment(
                    issue_iid,
                    "🧠 Trace — SPECFORGE\n\n*Failed to store approved spec. Check server logs.*",
                )
            except Exception:
                pass


async def run_spec_compliance(payload: dict) -> None:
    """
    When an MR is opened, if it links to an issue with an approved spec, compare the MR diff
    to the spec and post a compliance report on the MR.
    """
    mr_iid: int | None = None
    try:
        mr_iid = int(payload.get("object_attributes", {}).get("iid"))
        gitlab = GitLabClient()
        claude = ClaudeClient()

        linked_issue_iids = gitlab.get_mr_linked_issue_iids(mr_iid)
        if not linked_issue_iids:
            return

        spec_content: str | None = None
        issue_iid_used: int | None = None
        for iid in linked_issue_iids:
            slug = f"{TRACE_SPEC_SLUG_PREFIX}{iid}"
            content = gitlab.get_wiki_page(slug)
            if content and "Acceptance Criteria" in content:
                spec_content = content
                issue_iid_used = iid
                break

        if not spec_content:
            return

        try:
            full_diff = gitlab.get_mr_diff(mr_iid)
        except RuntimeError:
            full_diff = "(Diff unavailable.)"

        mr_title = payload.get("object_attributes", {}).get("title", "")
        mr_description = payload.get("object_attributes", {}).get("description", "")

        user_message = (
            f"APPROVED SPEC (from issue #{issue_iid_used}):\n```\n{spec_content[:30000]}\n```\n\n"
            f"MR TITLE: {mr_title}\n"
            f"MR DESCRIPTION:\n{mr_description}\n\n"
            f"DIFF:\n```\n{full_diff[:40000]}\n```"
        )

        system_prompt = claude.load_prompt("spec_compliance")
        response_str = claude.call(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=2000,
        )

        try:
            result = json.loads(response_str)
        except json.JSONDecodeError:
            gitlab.post_mr_comment(
                mr_iid,
                "🧠 Trace — SPECFORGE Compliance\n\n*Compliance check could not parse result.*",
            )
            return

        criteria_met = result.get("criteria_met") or []
        criteria_missing = result.get("criteria_missing") or []
        undescribed = result.get("undescribed_changes") or []
        summary = result.get("summary", "")

        parts = [
            "🧠 Trace — SPECFORGE Compliance",
            "",
            f"*Spec from issue #{issue_iid_used}*",
            "",
            "## Acceptance criteria",
            "",
        ]
        for c in criteria_met:
            parts.append(f"- ✅ {c.get('criterion', '')} — {c.get('location', '')}")
        for c in criteria_missing:
            parts.append(f"- ❌ {c.get('criterion', '')} — {c.get('note', '')}")
        if undescribed:
            parts.append("")
            parts.append("## Undescribed changes")
            parts.append("")
            for u in undescribed:
                parts.append(f"- **{u.get('location', '')}**: {u.get('description', '')}")
                if u.get("question"):
                    parts.append(f"  *{u['question']}*")
        parts.append("")
        parts.append(f"**Summary:** {summary}")

        gitlab.post_mr_comment(mr_iid, "\n".join(parts))
    except Exception as e:
        logger.error("Spec compliance failed: %s", e, exc_info=True)
        if mr_iid is not None:
            try:
                gitlab = GitLabClient()
                gitlab.post_mr_comment(
                    mr_iid,
                    "🧠 Trace — SPECFORGE Compliance\n\n*Compliance check failed. Check server logs.*",
                )
            except Exception:
                pass
