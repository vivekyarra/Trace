"""
GitLab API client wrapper for LORE. All GitLab operations go through this module.
"""

import logging
import re
from typing import Any

import gitlab
from gitlab import exceptions as gitlab_exc

from config import (
    GITLAB_PROJECT_ID,
    GITLAB_TOKEN,
    GITLAB_URL,
)

logger = logging.getLogger("lore.gitlab_client")


class GitLabClient:
    """
    Wraps python-gitlab to provide a stable interface for MRs, issues, and wiki.
    All methods raise RuntimeError on failure with descriptive messages.
    """

    def __init__(self) -> None:
        """
        Initialise python-gitlab and load the project using config (GITLAB_URL,
        GITLAB_TOKEN, GITLAB_PROJECT_ID).
        """
        try:
            self._gl = gitlab.Gitlab(GITLAB_URL, private_token=GITLAB_TOKEN)
            self._gl.auth()
            self._project = self._gl.projects.get(GITLAB_PROJECT_ID)
        except gitlab_exc.GitlabAuthenticationError as e:
            logger.exception("GitLab authentication failed")
            raise RuntimeError(f"GitLab authentication failed: {e}") from e
        except gitlab_exc.GitlabGetError as e:
            logger.exception("Failed to get GitLab project %s", GITLAB_PROJECT_ID)
            raise RuntimeError(f"Failed to get project {GITLAB_PROJECT_ID}: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error initialising GitLab client")
            raise RuntimeError(f"GitLab client init failed: {e}") from e

    def get_mr(self, mr_iid: int) -> dict:
        """
        Return MR object with title, description, author, created_at.
        """
        try:
            mr = self._project.mergerequests.get(mr_iid)
            attrs = mr.attributes
            author = attrs.get("author") or {}
            return {
                "title": attrs.get("title", ""),
                "description": attrs.get("description") or "",
                "author": author.get("username", ""),
                "created_at": attrs.get("created_at", ""),
            }
        except gitlab_exc.GitlabGetError as e:
            logger.exception("Failed to get MR !%s", mr_iid)
            raise RuntimeError(f"Failed to get MR !{mr_iid}: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error getting MR !%s", mr_iid)
            raise RuntimeError(f"Failed to get MR !{mr_iid}: {e}") from e

    def get_mr_discussions(self, mr_iid: int) -> list[dict]:
        """
        Return all discussion notes on an MR. Each item has: author (username),
        body, created_at, resolvable, resolved.
        """
        try:
            mr = self._project.mergerequests.get(mr_iid)
            discussions = mr.discussions.list(get_all=True)
            result: list[dict] = []
            for disc in discussions:
                disc_attrs = disc.attributes
                resolvable = disc_attrs.get("resolvable", False)
                resolved = disc_attrs.get("resolved", False)
                for note in disc.notes.list(get_all=True):
                    note_attrs = note.attributes
                    author_obj = note_attrs.get("author") or {}
                    result.append({
                        "author": author_obj.get("username", ""),
                        "body": note_attrs.get("body", ""),
                        "created_at": note_attrs.get("created_at", ""),
                        "resolvable": resolvable,
                        "resolved": resolved,
                    })
            return result
        except gitlab_exc.GitlabGetError as e:
            logger.exception("Failed to get MR !%s discussions", mr_iid)
            raise RuntimeError(f"Failed to get MR !{mr_iid} discussions: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error getting MR !%s discussions", mr_iid)
            raise RuntimeError(f"Failed to get MR !{mr_iid} discussions: {e}") from e

    def get_mr_changes(self, mr_iid: int) -> list[str]:
        """
        Return list of file paths changed in the MR.
        """
        try:
            mr = self._project.mergerequests.get(mr_iid)
            data = mr.changes()
            if isinstance(data, dict):
                changes_list = data.get("changes", [])
            else:
                changes_list = []
            paths: list[str] = []
            seen: set[str] = set()
            for c in changes_list:
                for key in ("new_path", "old_path"):
                    p = c.get(key)
                    if p and p not in seen:
                        seen.add(p)
                        paths.append(p)
            return paths
        except gitlab_exc.GitlabGetError as e:
            logger.exception("Failed to get MR !%s changes", mr_iid)
            raise RuntimeError(f"Failed to get MR !{mr_iid} changes: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error getting MR !%s changes", mr_iid)
            raise RuntimeError(f"Failed to get MR !{mr_iid} changes: {e}") from e

    def get_mr_diff(self, mr_iid: int) -> str:
        """
        Return the full unified diff of the MR as a single string (for GUARDKEEPER).
        """
        try:
            mr = self._project.mergerequests.get(mr_iid)
            data = mr.changes()
            if not isinstance(data, dict):
                return ""
            changes_list = data.get("changes", [])
            parts: list[str] = []
            for c in changes_list:
                new_path = c.get("new_path") or c.get("old_path") or "?"
                old_path = c.get("old_path") or new_path
                diff = (c.get("diff") or "").strip()
                if diff:
                    parts.append(f"--- a/{old_path}\n+++ b/{new_path}\n{diff}")
            return "\n".join(parts) if parts else ""
        except gitlab_exc.GitlabGetError as e:
            logger.exception("Failed to get MR !%s diff", mr_iid)
            raise RuntimeError(f"Failed to get MR !{mr_iid} diff: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error getting MR !%s diff", mr_iid)
            raise RuntimeError(f"Failed to get MR !{mr_iid} diff: {e}") from e

    def get_mr_linked_issue_iids(self, mr_iid: int) -> list[int]:
        """
        Return issue IIDs linked from the MR (e.g. Closes #123, Fixes #456). Parses description.
        """
        try:
            mr = self._project.mergerequests.get(mr_iid)
            desc = (mr.attributes.get("description") or "").strip()
            if not desc:
                return []
            # Match #123 or # 123 (issue references)
            iids = re.findall(r"#\s*(\d+)", desc)
            seen: set[int] = set()
            result: list[int] = []
            for s in iids:
                iid = int(s)
                if iid not in seen:
                    seen.add(iid)
                    result.append(iid)
            return result
        except gitlab_exc.GitlabGetError as e:
            logger.exception("Failed to get MR !%s for linked issues", mr_iid)
            raise RuntimeError(f"Failed to get MR !{mr_iid}: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error getting MR !%s linked issues", mr_iid)
            return []

    def post_mr_comment(self, mr_iid: int, body: str) -> None:
        """
        Post a comment on an MR.
        """
        try:
            mr = self._project.mergerequests.get(mr_iid)
            mr.notes.create({"body": body})
        except gitlab_exc.GitlabCreateError as e:
            logger.exception("Failed to post comment on MR !%s", mr_iid)
            raise RuntimeError(f"Failed to post comment on MR !{mr_iid}: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error posting comment on MR !%s", mr_iid)
            raise RuntimeError(f"Failed to post comment on MR !{mr_iid}: {e}") from e

    def get_issue(self, issue_iid: int) -> dict:
        """
        Return issue with title, description, author, created_at.
        """
        try:
            issue = self._project.issues.get(issue_iid)
            attrs = issue.attributes
            author = attrs.get("author") or {}
            return {
                "title": attrs.get("title", ""),
                "description": attrs.get("description") or "",
                "author": author.get("username", ""),
                "created_at": attrs.get("created_at", ""),
            }
        except gitlab_exc.GitlabGetError as e:
            logger.exception("Failed to get issue #%s", issue_iid)
            raise RuntimeError(f"Failed to get issue #{issue_iid}: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error getting issue #%s", issue_iid)
            raise RuntimeError(f"Failed to get issue #{issue_iid}: {e}") from e

    def post_issue_comment(self, issue_iid: int, body: str) -> None:
        """
        Post a comment on an issue.
        """
        try:
            issue = self._project.issues.get(issue_iid)
            issue.notes.create({"body": body})
        except gitlab_exc.GitlabCreateError as e:
            logger.exception("Failed to post comment on issue #%s", issue_iid)
            raise RuntimeError(f"Failed to post comment on issue #{issue_iid}: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error posting comment on issue #%s", issue_iid)
            raise RuntimeError(f"Failed to post comment on issue #{issue_iid}: {e}") from e

    def get_issue_notes(self, issue_iid: int) -> list[dict]:
        """
        Return all notes (comments) on an issue. Each item: body, author (username), created_at.
        """
        try:
            issue = self._project.issues.get(issue_iid)
            notes = issue.notes.list(get_all=True)
            return [
                {
                    "body": (n.attributes.get("body") or "").strip(),
                    "author": (n.attributes.get("author") or {}).get("username", ""),
                    "created_at": n.attributes.get("created_at", ""),
                }
                for n in notes
            ]
        except gitlab_exc.GitlabGetError as e:
            logger.exception("Failed to get issue #%s notes", issue_iid)
            raise RuntimeError(f"Failed to get issue #{issue_iid} notes: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error getting issue #%s notes", issue_iid)
            raise RuntimeError(f"Failed to get issue #{issue_iid} notes: {e}") from e

    def set_issue_labels(self, issue_iid: int, labels: list[str]) -> None:
        """
        Set the issue's labels to the given list (replaces existing).
        """
        try:
            issue = self._project.issues.get(issue_iid)
            issue.labels = labels
            issue.save()
        except gitlab_exc.GitlabGetError as e:
            logger.exception("Failed to get issue #%s for label update", issue_iid)
            raise RuntimeError(f"Failed to get issue #{issue_iid}: {e}") from e
        except gitlab_exc.GitlabUpdateError as e:
            logger.exception("Failed to update issue #%s labels", issue_iid)
            raise RuntimeError(f"Failed to update issue #{issue_iid} labels: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error updating issue #%s labels", issue_iid)
            raise RuntimeError(f"Failed to update issue #{issue_iid} labels: {e}") from e

    def get_issue_labels(self, issue_iid: int) -> list[str]:
        """
        Return the list of label names on the issue.
        """
        try:
            issue = self._project.issues.get(issue_iid)
            return list(issue.attributes.get("labels") or [])
        except gitlab_exc.GitlabGetError as e:
            logger.exception("Failed to get issue #%s", issue_iid)
            raise RuntimeError(f"Failed to get issue #{issue_iid}: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error getting issue #%s labels", issue_iid)
            raise RuntimeError(f"Failed to get issue #{issue_iid} labels: {e}") from e

    def add_issue_label(self, issue_iid: int, label: str) -> None:
        """
        Add a label to the issue if not already present. Preserves existing labels.
        """
        try:
            issue = self._project.issues.get(issue_iid)
            labels = list(issue.attributes.get("labels") or [])
            if label not in labels:
                labels.append(label)
                issue.labels = labels
                issue.save()
        except (gitlab_exc.GitlabGetError, gitlab_exc.GitlabUpdateError) as e:
            logger.exception("Failed to add label to issue #%s", issue_iid)
            raise RuntimeError(f"Failed to add label to issue #{issue_iid}: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error adding label to issue #%s", issue_iid)
            raise RuntimeError(f"Failed to add label to issue #{issue_iid}: {e}") from e

    def create_issue(self, title: str, description: str, labels: list[str] | None = None) -> dict:
        """
        Create a new issue. Returns the created issue as dict with at least iid.
        """
        try:
            data: dict[str, Any] = {"title": title, "description": description}
            if labels is not None:
                data["labels"] = labels
            issue = self._project.issues.create(data)
            attrs = issue.attributes
            return {"iid": attrs.get("iid"), "title": attrs.get("title", title)}
        except gitlab_exc.GitlabCreateError as e:
            logger.exception("Failed to create issue %s", title)
            raise RuntimeError(f"Failed to create issue: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error creating issue")
            raise RuntimeError(f"Failed to create issue: {e}") from e

    def get_wiki_page(self, slug: str) -> str | None:
        """
        Return wiki page content as string, or None if page does not exist.
        """
        try:
            page = self._project.wikis.get(slug)
            return (page.attributes.get("content") or "") if page else None
        except gitlab_exc.GitlabGetError:
            logger.debug("Wiki page %s does not exist", slug)
            return None
        except Exception as e:
            logger.exception("Error getting wiki page %s", slug)
            raise RuntimeError(f"Failed to get wiki page {slug}: {e}") from e

    def create_wiki_page(self, slug: str, title: str, content: str) -> None:
        """
        Create a new wiki page. Uses slug as the page identifier (GitLab derives slug from title).
        """
        try:
            self._project.wikis.create({"title": slug, "content": content})
        except gitlab_exc.GitlabCreateError as e:
            logger.exception("Failed to create wiki page %s", slug)
            raise RuntimeError(f"Failed to create wiki page {slug}: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error creating wiki page %s", slug)
            raise RuntimeError(f"Failed to create wiki page {slug}: {e}") from e

    def update_wiki_page(self, slug: str, content: str) -> None:
        """
        Update existing wiki page content.
        """
        try:
            page = self._project.wikis.get(slug)
            page.content = content
            page.save()
        except gitlab_exc.GitlabGetError as e:
            logger.exception("Wiki page %s not found for update", slug)
            raise RuntimeError(f"Wiki page {slug} not found: {e}") from e
        except gitlab_exc.GitlabUpdateError as e:
            logger.exception("Failed to update wiki page %s", slug)
            raise RuntimeError(f"Failed to update wiki page {slug}: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error updating wiki page %s", slug)
            raise RuntimeError(f"Failed to update wiki page {slug}: {e}") from e

    def list_wiki_pages(self) -> list[str]:
        """
        Return list of all wiki page slugs.
        """
        try:
            pages = self._project.wikis.list(get_all=True)
            return [p.attributes.get("slug", "") for p in pages if p.attributes.get("slug")]
        except gitlab_exc.GitlabListError as e:
            logger.exception("Failed to list wiki pages")
            raise RuntimeError(f"Failed to list wiki pages: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error listing wiki pages")
            raise RuntimeError(f"Failed to list wiki pages: {e}") from e

    def get_recent_mrs(self, count: int = 20) -> list[dict]:
        """
        Return the most recent merged MRs with mr_iid, title, merged_at.
        """
        try:
            mrs = self._project.mergerequests.list(
                state="merged",
                order_by="updated_at",
                sort="desc",
                get_all=False,
                per_page=count,
            )
            return [
                {
                    "mr_iid": mr.attributes.get("iid"),
                    "title": mr.attributes.get("title", ""),
                    "merged_at": mr.attributes.get("merged_at", ""),
                }
                for mr in mrs
            ]
        except gitlab_exc.GitlabListError as e:
            logger.exception("Failed to list recent MRs")
            raise RuntimeError(f"Failed to list recent MRs: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error listing recent MRs")
            raise RuntimeError(f"Failed to list recent MRs: {e}") from e

    def get_project_wiki_url(self) -> str:
        """
        Return the project wiki URL for linking in comments (e.g. project/-/wikis/home).
        """
        try:
            web_url = self._project.attributes.get("web_url", "").rstrip("/")
            return f"{web_url}/-/wikis/home" if web_url else ""
        except Exception as e:
            logger.warning("Could not get project wiki URL: %s", e)
            return ""
