"""
Trace memory store: wiki-backed storage and indexing of architectural decisions.
"""

import logging
import re
from typing import TYPE_CHECKING

from config import TRACE_INDEX_SLUG, MEMORY_SLUG_PREFIX

from .gitlab_client import GitLabClient

if TYPE_CHECKING:
    pass

logger = logging.getLogger("trace.memory")


def _zero_pad_id(memory_id: str) -> str:
    """Return zero-padded 3-digit id for slug."""
    try:
        n = int(memory_id)
        return f"{n:03d}"
    except (TypeError, ValueError):
        return memory_id.zfill(3) if len(memory_id) < 3 else memory_id


class MemoryStore:
    """
    Handles all Trace memory operations using GitLab wiki via GitLabClient.
    """

    def __init__(self, gitlab: GitLabClient) -> None:
        """Store the GitLab client reference for wiki operations."""
        self._gitlab = gitlab

    def _parse_memory(self, content: str) -> dict:
        """
        Parse a wiki page string into a memory dict with keys: id, source_mr_number,
        source_mr_title, date, governs_files, decision, rejected, reason,
        future_implication, decided_by, confidence, status.
        """
        lines = content.strip().split("\n")
        memory: dict = {
            "id": "",
            "source_mr_number": "",
            "source_mr_title": "",
            "date": "",
            "governs_files": [],
            "decision": "",
            "rejected": "",
            "reason": "",
            "future_implication": "",
            "decided_by": [],
            "confidence": "",
            "status": "",
        }
        for line in lines:
            line = line.strip()
            if line.startswith("Trace Memory #"):
                memory["id"] = line.replace("Trace Memory #", "").strip()
            elif line.startswith("Source MR:"):
                rest = line.replace("Source MR:", "").strip()
                match = re.match(r"!(\d+)\s*—\s*(.*)", rest)
                if match:
                    memory["source_mr_number"] = match.group(1)
                    memory["source_mr_title"] = match.group(2).strip()
            elif line.startswith("Date:"):
                memory["date"] = line.replace("Date:", "").strip()
            elif line.startswith("Governs files:"):
                raw = line.replace("Governs files:", "").strip()
                memory["governs_files"] = [p.strip() for p in raw.split(",") if p.strip()]
            elif line.startswith("Decision:"):
                memory["decision"] = line.replace("Decision:", "").strip()
            elif line.startswith("Rejected:"):
                memory["rejected"] = line.replace("Rejected:", "").strip()
            elif line.startswith("Reason:"):
                memory["reason"] = line.replace("Reason:", "").strip()
            elif line.startswith("Future implication:"):
                memory["future_implication"] = line.replace("Future implication:", "").strip()
            elif line.startswith("Decided by:"):
                raw = line.replace("Decided by:", "").strip()
                memory["decided_by"] = [h.strip() for h in raw.split(",") if h.strip()]
            elif line.startswith("Confidence:"):
                memory["confidence"] = line.replace("Confidence:", "").strip()
            elif line.startswith("Status:"):
                memory["status"] = line.replace("Status:", "").strip()
        return memory

    def _serialize_memory(self, memory: dict) -> str:
        """
        Convert a memory dict into the Trace wiki markdown format.
        """
        governs = ", ".join(memory.get("governs_files") or [])
        decided_by = ", ".join(memory.get("decided_by") or [])
        return (
            f"Trace Memory #{memory.get('id', '')}\n"
            f"Source MR: !{memory.get('source_mr_number', '')} — {memory.get('source_mr_title', '')}\n"
            f"Date: {memory.get('date', '')}\n"
            f"Governs files: {governs}\n"
            f"Decision: {memory.get('decision', '')}\n"
            f"Rejected: {memory.get('rejected', '')}\n"
            f"Reason: {memory.get('reason', '')}\n"
            f"Future implication: {memory.get('future_implication', '')}\n"
            f"Decided by: {decided_by}\n"
            f"Confidence: {memory.get('confidence', '')}\n"
            f"Status: {memory.get('status', '')}\n"
        )

    def save_memory(self, memory: dict) -> str:
        """
        Save memory to wiki, update TRACE-INDEX, and return the page slug.
        """
        try:
            memory_id = str(memory.get("id", "")).strip()
            if not memory_id:
                pad = "001"
                slugs = self._gitlab.list_wiki_pages()
                existing = [s for s in slugs if s.startswith(MEMORY_SLUG_PREFIX)]
                if existing:
                    nums = []
                    for s in existing:
                        suffix = s.replace(MEMORY_SLUG_PREFIX, "")
                        if suffix.isdigit():
                            nums.append(int(suffix))
                    pad = f"{max(nums) + 1:03d}" if nums else "001"
                memory_id = pad
                memory["id"] = memory_id
            else:
                pad = _zero_pad_id(memory_id)
            slug = f"{MEMORY_SLUG_PREFIX}{pad}"
            content = self._serialize_memory(memory)
            existing = self._gitlab.get_wiki_page(slug)
            if existing is None:
                self._gitlab.create_wiki_page(slug, slug, content)
            else:
                self._gitlab.update_wiki_page(slug, content)
            self._update_index(memory_id, memory.get("governs_files") or [])
            return slug
        except RuntimeError:
            raise
        except Exception as e:
            logger.exception("Failed to save memory")
            raise RuntimeError(f"Failed to save memory: {e}") from e

    def get_memory(self, memory_id: str) -> dict | None:
        """
        Fetch and parse a single memory by id (e.g. '001'). Returns None if not found.
        """
        try:
            pad = _zero_pad_id(memory_id)
            slug = f"{MEMORY_SLUG_PREFIX}{pad}"
            content = self._gitlab.get_wiki_page(slug)
            if content is None or not content.strip():
                return None
            return self._parse_memory(content)
        except RuntimeError:
            raise
        except Exception as e:
            logger.exception("Failed to get memory %s", memory_id)
            raise RuntimeError(f"Failed to get memory {memory_id}: {e}") from e

    def get_memories_for_files(self, file_paths: list[str]) -> list[dict]:
        """
        Read TRACE-INDEX, find all memory IDs that govern any of the given file paths,
        fetch and return those memories.
        """
        try:
            content = self._gitlab.get_wiki_page(TRACE_INDEX_SLUG)
            if not content or not file_paths:
                return []
            path_set = set(f.strip() for f in file_paths if f and f.strip())
            if not path_set:
                return []
            index = self._parse_index(content)
            memory_ids: set[str] = set()
            for path in path_set:
                for fid in index.get(path, []):
                    memory_ids.add(fid)
            result: list[dict] = []
            for mid in memory_ids:
                mem = self.get_memory(mid)
                if mem:
                    result.append(mem)
            return result
        except RuntimeError:
            raise
        except Exception as e:
            logger.exception("Failed to get memories for files")
            raise RuntimeError(f"Failed to get memories for files: {e}") from e

    def _parse_index(self, content: str) -> dict[str, list[str]]:
        """Parse TRACE-INDEX markdown table into dict: file_path -> list of memory ids."""
        index: dict[str, list[str]] = {}
        lines = content.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or "|" not in line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2 and parts[0].lower() != "file path":
                path = parts[0]
                ids_str = parts[1]
                ids = [i.strip() for i in ids_str.replace(" ", "").split(",") if i.strip()]
                if path and ids:
                    index[path] = ids
        return index

    def get_all_memories(self) -> list[dict]:
        """
        Fetch and parse every TRACE-MEMORY-* wiki page.
        """
        try:
            slugs = self._gitlab.list_wiki_pages()
            memory_slugs = sorted(s for s in slugs if s.startswith(MEMORY_SLUG_PREFIX))
            result: list[dict] = []
            for slug in memory_slugs:
                content = self._gitlab.get_wiki_page(slug)
                if content and content.strip():
                    result.append(self._parse_memory(content))
            return result
        except RuntimeError:
            raise
        except Exception as e:
            logger.exception("Failed to get all memories")
            raise RuntimeError(f"Failed to get all memories: {e}") from e

    def update_memory_status(
        self, memory_id: str, status: str, append_note: str | None = None
    ) -> None:
        """
        Update the status field of a memory; optionally append a note to the reason field.
        """
        try:
            mem = self.get_memory(memory_id)
            if not mem:
                raise RuntimeError(f"Memory {memory_id} not found")
            mem["status"] = status
            if append_note:
                mem["reason"] = (mem.get("reason") or "").strip()
                if mem["reason"]:
                    mem["reason"] += "\n" + append_note
                else:
                    mem["reason"] = append_note
            pad = _zero_pad_id(memory_id)
            slug = f"{MEMORY_SLUG_PREFIX}{pad}"
            self._gitlab.update_wiki_page(slug, self._serialize_memory(mem))
        except RuntimeError:
            raise
        except Exception as e:
            logger.exception("Failed to update memory status for %s", memory_id)
            raise RuntimeError(f"Failed to update memory status: {e}") from e

    def ensure_index_exists(self) -> None:
        """
        Create the TRACE-INDEX wiki page if it does not exist yet.
        """
        try:
            content = self._gitlab.get_wiki_page(TRACE_INDEX_SLUG)
            if content is not None:
                return
            initial = "# Trace Index\n\n| File Path | Memory IDs |\n"
            self._gitlab.create_wiki_page(TRACE_INDEX_SLUG, TRACE_INDEX_SLUG, initial)
        except RuntimeError:
            raise
        except Exception as e:
            logger.exception("Failed to ensure TRACE-INDEX exists")
            raise RuntimeError(f"Failed to ensure index exists: {e}") from e

    def _update_index(self, memory_id: str, file_paths: list[str]) -> None:
        """
        Add the memory_id -> file_paths mapping to TRACE-INDEX. Merges with existing rows.
        """
        try:
            self.ensure_index_exists()
            content = self._gitlab.get_wiki_page(TRACE_INDEX_SLUG)
            if not content:
                raise RuntimeError("TRACE-INDEX missing after ensure_index_exists")
            index = self._parse_index(content)
            pad = _zero_pad_id(memory_id)
            for path in file_paths:
                path = path.strip()
                if not path:
                    continue
                if path not in index:
                    index[path] = []
                if pad not in index[path]:
                    index[path].append(pad)
            lines = ["# Trace Index", "", "| File Path | Memory IDs |", "| --- | --- |"]
            for path in sorted(index.keys()):
                ids_str = ", ".join(sorted(index[path]))
                lines.append(f"| {path} | {ids_str} |")
            self._gitlab.update_wiki_page(TRACE_INDEX_SLUG, "\n".join(lines) + "\n")
        except RuntimeError:
            raise
        except Exception as e:
            logger.exception("Failed to update TRACE-INDEX")
            raise RuntimeError(f"Failed to update index: {e}") from e
