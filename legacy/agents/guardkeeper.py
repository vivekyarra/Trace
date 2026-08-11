"""
GUARDKEEPER agent: triggered on MR open or on reply to a GUARDKEEPER comment.
Checks MR against Trace memories and posts conflict notice or green check;
handles intentional/accidental/discuss replies.
"""

import json
import logging
import re
from datetime import datetime

from core.gitlab_client import GitLabClient
from core.claude_client import ClaudeClient
from core.memory import MemoryStore

logger = logging.getLogger("trace.guardkeeper")


def _get_memory_by_id(memories: list[dict], memory_id: str) -> dict:
    """
    Find a memory from the list by its id field. Return empty dict if not found.
    Matches ids with or without leading zeros (e.g. 1, 01, 001).
    """
    target = str(memory_id).strip().zfill(3)
    for m in memories:
        if str(m.get("id", "")).strip().zfill(3) == target:
            return m
    return {}


def _parse_conflict_memory_ids_from_discussions(discussions: list[dict]) -> list[str]:
    """
    Find the GUARDKEEPER conflict comment in MR discussions and extract Memory #ids.
    Returns list of memory ids (e.g. ['047', '048']).
    """
    memory_ids: list[str] = []
    for note in discussions:
        body = (note.get("body") or "").strip()
        if "Decision Conflict Detected" not in body or "Memory #" not in body:
            continue
        # Match "Memory #047" or "Memory #47"
        for match in re.finditer(r"Memory\s*#\s*(\d+)", body, re.IGNORECASE):
            mid = match.group(1).lstrip("0") or "0"
            if mid not in memory_ids:
                memory_ids.append(mid)
    return memory_ids


async def run_guardkeeper(payload: dict, reply_type: str | None = None) -> None:
    """
    Run GUARDKEEPER: Mode 1 (reply_type None) checks MR against memories and posts
    result; Mode 2 (intentional/accidental/discuss) handles developer reply.
    """
    mr_iid: int | None = None
    try:
        if reply_type is not None:
            # — MODE 2: Reply handling —
            mr_iid = int(payload["merge_request"]["iid"])
            note_body = payload["object_attributes"]["note"]
            note_author = payload["user"]["username"]

            gitlab = GitLabClient()

            if reply_type == "intentional":
                # — Step 2: Handle "intentional" — extract reasoning and update memories
                body_lower = (note_body or "").strip().lower()
                idx = body_lower.find("trace: intentional")
                if idx >= 0:
                    reasoning = (note_body or "")[idx + len("trace: intentional") :].strip()
                    reasoning = reasoning.lstrip(" —").lstrip(" -").lstrip()
                else:
                    reasoning = ""
                if not reasoning:
                    reasoning = "No reasoning provided."

                # Find our conflict comment and update each conflicted memory
                memory_store = MemoryStore(gitlab)
                discussions = gitlab.get_mr_discussions(mr_iid)
                conflict_memory_ids = _parse_conflict_memory_ids_from_discussions(discussions)
                override_note = (
                    f"Overridden on {datetime.utcnow().strftime('%Y-%m-%d')} by @{note_author}: {reasoning}"
                )
                for mid in conflict_memory_ids:
                    try:
                        memory_store.update_memory_status(
                            mid, "Superseded", append_note=override_note
                        )
                    except RuntimeError as e:
                        logger.warning("Could not update memory %s: %s", mid, e)

                gitlab.post_mr_comment(
                    mr_iid,
                    f"🧠 Trace — GUARDKEEPER\n\n"
                    f"Acknowledged @{note_author}. This override has been recorded.\n\n"
                    f"**Your reasoning:** {reasoning}\n\n"
                    f"Institutional memory updated for memory/ies: {', '.join('#' + m for m in conflict_memory_ids) or 'N/A'}. "
                    f"Future developers will see both the original constraint and your override reasoning.",
                )
                return

            if reply_type == "accidental":
                # — Step 3: Handle "accidental" —
                gitlab.post_mr_comment(
                    mr_iid,
                    "🧠 Trace — GUARDKEEPER\n\n"
                    f"Understood @{note_author}. This conflict appears to be unintentional.\n\n"
                    "**Next step:** Please revise the implementation to align with the existing "
                    "architectural decision before merging.\n\n"
                    "If you believe the original decision should be revisited, reply with "
                    "`trace: discuss` to loop in the original decision makers.",
                )
                return

            if reply_type == "discuss":
                # — Step 4: Handle "discuss" —
                memory_store = MemoryStore(gitlab)
                changed_files = gitlab.get_mr_changes(mr_iid)
                memories = memory_store.get_memories_for_files(changed_files)
                usernames: set[str] = set()
                for m in memories:
                    for handle in m.get("decided_by") or []:
                        u = (handle.strip().lstrip("@") or "").strip()
                        if u and u != note_author:
                            usernames.add(u)
                mention_str = " ".join(f"@{u}" for u in sorted(usernames))

                gitlab.post_mr_comment(
                    mr_iid,
                    f"🧠 Trace — GUARDKEEPER\n\n"
                    f"Looping in the original decision makers as requested by @{note_author}.\n\n"
                    f"{mention_str}\n\n"
                    "A decision conflict has been flagged on this MR. Your institutional context "
                    "is needed before this merges. Please review the conflict details above "
                    "and share your perspective.",
                )
                return

        # — MODE 1: MR opened — reply_type is None —

        # — Step 1: Extract data from webhook payload —
        mr_iid = int(payload["object_attributes"]["iid"])
        mr_title = payload["object_attributes"]["title"]
        mr_description = payload["object_attributes"]["description"] or ""
        mr_author = payload["user"]["username"]
        mr_url = payload["object_attributes"]["url"]

        # — Step 2: Initialise clients —
        gitlab = GitLabClient()
        claude = ClaudeClient()
        memory_store = MemoryStore(gitlab)

        # — Step 3: Get changed files and full diff —
        changed_files = gitlab.get_mr_changes(mr_iid)
        if not changed_files:
            logger.info("GUARDKEEPER: MR !%s has no changed files, skipping", mr_iid)
            return

        try:
            full_diff = gitlab.get_mr_diff(mr_iid)
        except RuntimeError as e:
            logger.warning("GUARDKEEPER: Could not get MR diff: %s. Proceeding with file list only.", e)
            full_diff = "(Diff unavailable; only file paths were checked.)"

        # — Step 4: Load relevant memories —
        memories = memory_store.get_memories_for_files(changed_files)
        if not memories:
            gitlab.post_mr_comment(
                mr_iid,
                "✅ Trace — GUARDKEEPER\n\n"
                "**0 memories** found for files in this MR. "
                "No institutional memory to check against yet.\n\n"
                f"*Files scanned: {', '.join(changed_files)}*",
            )
            return

        # — Step 5: Build the user message for Claude (include full diff) —
        changed_files_block = "\n".join(changed_files)
        past_decisions_parts = []
        for m in memories:
            governs = ", ".join(m.get("governs_files") or [])
            past_decisions_parts.append(
                f"---\n"
                f"Memory #{m.get('id', '')}\n"
                f"Decision: {m.get('decision', '')}\n"
                f"Rejected: {m.get('rejected', '')}\n"
                f"Reason: {m.get('reason', '')}\n"
                f"Future implication: {m.get('future_implication', '')}\n"
                f"Governs files: {governs}\n"
                f"Memory ID: {m.get('id', '')}\n"
                f"---"
            )
        past_decisions_block = "\n\n".join(past_decisions_parts)

        user_message = (
            f"MR TITLE: {mr_title}\n"
            f"MR AUTHOR: @{mr_author}\n"
            f"MR DESCRIPTION:\n{mr_description}\n\n"
            f"CHANGED FILES:\n{changed_files_block}\n\n"
            f"DIFF (full):\n```\n{full_diff[:50000]}\n```\n\n"
            f"PAST DECISIONS:\n{past_decisions_block}"
        )

        # — Step 6: Call Claude —
        system_prompt = claude.load_prompt("guardkeeper")
        response_str = claude.call(system_prompt=system_prompt, user_message=user_message)

        # — Step 7: Parse Claude response —
        try:
            result = json.loads(response_str)
        except json.JSONDecodeError as e:
            logger.error("GUARDKEEPER: Failed to parse Claude JSON: %s", e, exc_info=True)
            gitlab.post_mr_comment(
                mr_iid,
                "🧠 Trace — GUARDKEEPER\n\n*Could not parse conflict analysis. Check server logs.*",
            )
            return

        has_conflict = result.get("has_conflict", False)
        conflicts = result.get("conflicts") or []
        checked_memories = result.get("checked_memories") or []
        clean_files = result.get("clean_files") or []

        # — Step 8: Post result comment —
        if not has_conflict:
            ids_str = ", ".join(f"#{mid}" for mid in checked_memories)
            clean_files_str = ", ".join(clean_files)
            gitlab.post_mr_comment(
                mr_iid,
                f"✅ Trace — GUARDKEEPER\n\n"
                f"**{len(checked_memories)} memories checked. No decision conflicts detected.**\n\n"
                "This MR is clean against your team's institutional memory.\n\n"
                f"*Memories checked: {ids_str}*\n"
                f"*Files scanned: {clean_files_str}*",
            )
            return

        # Build conflict comment with all conflicts
        n = len(conflicts)
        conflict_parts = [
            "🧠 Trace — GUARDKEEPER — ⚠️ Decision Conflict Detected",
            "",
            f"This MR conflicts with {n} stored architectural decision(s).",
            "",
        ]
        for c in conflicts:
            mem_id = c.get("memory_id", "")
            severity = c.get("severity", "MEDIUM")
            conflict_desc = c.get("conflict_description", "")
            code_location = c.get("conflicting_code_location", "")
            reasoning = c.get("reasoning", "")

            mem = _get_memory_by_id(memories, mem_id)
            decision_text = mem.get("decision", "")
            reason_text = mem.get("reason", "")
            decided_by = mem.get("decided_by") or []
            decided_by_str = " ".join(decided_by)
            source_mr = mem.get("source_mr_number", "")

            conflict_parts.append("---")
            conflict_parts.append(f"### Conflict with Memory #{mem_id} — {severity} severity")
            conflict_parts.append("")
            conflict_parts.append(f"**What conflicts:** {conflict_desc}")
            conflict_parts.append(f"**Where:** {code_location}")
            conflict_parts.append("")
            conflict_parts.append("**Trace's reasoning:**")
            conflict_parts.append(reasoning)
            conflict_parts.append("")
            conflict_parts.append("**The original decision:**")
            conflict_parts.append(f"> {decision_text}")
            conflict_parts.append("")
            conflict_parts.append("**Why it was decided:**")
            conflict_parts.append(f"> {reason_text}")
            conflict_parts.append("")
            conflict_parts.append(f"**Original decision makers:** {decided_by_str}")
            conflict_parts.append(f"**Original MR:** !{source_mr}")
            conflict_parts.append("---")
            conflict_parts.append("")

        conflict_parts.append("**Three paths forward — reply to this comment:**")
        conflict_parts.append("")
        conflict_parts.append("💬 `trace: intentional — [your reasoning]`")
        conflict_parts.append("The new approach is deliberate. Trace will update institutional memory with your reasoning.")
        conflict_parts.append("")
        conflict_parts.append("💬 `trace: accidental`")
        conflict_parts.append("You were unaware of this constraint. Please revise before merging.")
        conflict_parts.append("")
        conflict_parts.append("💬 `trace: discuss`")
        conflict_parts.append("Loop in the original decision makers before proceeding.")
        conflict_parts.append("")
        conflict_parts.append(f"*Trace checked {len(checked_memories)} memories across {len(changed_files)} files.*")

        gitlab.post_mr_comment(mr_iid, "\n".join(conflict_parts))

    except Exception as e:
        logger.error("GUARDKEEPER failed: %s", e, exc_info=True)
        if mr_iid is None:
            try:
                mr_iid = payload.get("object_attributes", {}).get("iid")
                if mr_iid is None:
                    mr_iid = payload.get("merge_request", {}).get("iid")
                if mr_iid is not None:
                    gitlab = GitLabClient()
                    gitlab.post_mr_comment(
                        int(mr_iid),
                        "🧠 Trace — GUARDKEEPER\n\n*An error occurred during conflict analysis. Check server logs.*",
                    )
            except Exception:
                pass
        else:
            try:
                gitlab = GitLabClient()
                gitlab.post_mr_comment(
                    mr_iid,
                    "🧠 Trace — GUARDKEEPER\n\n*An error occurred during conflict analysis. Check server logs.*",
                )
            except Exception:
                pass
