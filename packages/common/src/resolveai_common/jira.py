"""Modular Jira Cloud API client service."""

from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx

from resolveai_common.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class JiraError(Exception):
    """Base exception for Jira client operations."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class JiraNotConfiguredError(JiraError):
    """Raised when Jira credentials or base URL are missing."""


class JiraAuthenticationError(JiraError):
    """Raised on HTTP 401 or 403."""


class JiraNotFoundError(JiraError):
    """Raised on HTTP 404."""


@dataclass
class JiraComment:
    id: str
    author: str
    body: str
    created: str


@dataclass
class JiraIssue:
    key: str
    summary: str
    description: str
    status: str
    priority: str
    created: str
    updated: str
    reporter: str
    assignee: str | None
    project_key: str
    comments: list[JiraComment] = field(default_factory=list)
    raw_fields: dict[str, Any] = field(default_factory=dict)


def _extract_text_from_adf(node: Any) -> str:
    """Recursively extract plain text from Atlassian Document Format (ADF)."""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "\n".join(_extract_text_from_adf(item) for item in node if item)
    if isinstance(node, dict):
        text = node.get("text", "")
        children = node.get("content", [])
        if children:
            child_text = "\n".join(_extract_text_from_adf(c) for c in children if c)
            return f"{text}\n{child_text}".strip()
        return text
    return ""


def sanitize_untrusted_text(text: str) -> str:
    """Sanitize external ticket content to prevent prompt injection and control character abuse.
    Strips dangerous override directives while preserving diagnostic details.
    """
    if not text:
        return ""
    # Strip null bytes and non-printable control characters (except newline/tab)
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    # Neutralize common prompt injection prefixes without deleting technical error messages
    injection_patterns = [
        r"(?i)ignore\s+(all\s+)?(previous|above)\s+instructions?",
        r"(?i)you\s+are\s+now\s+in\s+developer\s+mode",
        r"(?i)system\s*:\s*override",
    ]
    for pattern in injection_patterns:
        cleaned = re.sub(pattern, "[DISARMED_DIRECTIVE]", cleaned)
    return cleaned.strip()


class JiraClient:
    """Modular, secure client for Jira Cloud REST API."""

    def __init__(
        self,
        base_url: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
        project_key: str | None = None,
        timeout: float = 30.0,
        settings: Settings | None = None,
    ) -> None:
        cfg = settings or get_settings()
        self.base_url = (base_url or cfg.jira_base_url or "").rstrip("/")
        self.email = email or cfg.jira_email or ""
        self.api_token = api_token or cfg.jira_api_token or ""
        self.project_key = project_key or cfg.jira_project_key or ""
        self.timeout = timeout or cfg.http_timeout_seconds

    @property
    def is_configured(self) -> bool:
        """Check whether minimum Jira Cloud credentials and endpoint are present."""
        return bool(
            self.base_url
            and self.email
            and self.api_token
            and "your-domain" not in self.base_url
        )

    @property
    def sanitized_base_url(self) -> str:
        """Return base URL hostname without secrets or query parameters for display."""
        if not self.base_url:
            return ""
        parsed = urlparse(self.base_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _get_headers(self) -> dict[str, str]:
        if not self.is_configured:
            raise JiraNotConfiguredError(
                "Jira Cloud credentials are not configured. "
                "Set JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN in your environment."
            )
        auth_str = f"{self.email}:{self.api_token}"
        encoded_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        return {
            "Authorization": f"Basic {encoded_auth}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "ResolveAI-JiraIntegration/1.0",
        }

    def test_connection(self) -> dict[str, Any]:
        """Verify Jira Cloud credentials against the /rest/api/3/myself endpoint."""
        if not self.is_configured:
            return {
                "ok": False,
                "configured": False,
                "message": "Jira is not configured. Set JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN.",
            }

        url = f"{self.base_url}/rest/api/3/myself"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=self._get_headers())
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "ok": True,
                    "configured": True,
                    "account_id": data.get("accountId"),
                    "display_name": data.get("displayName"),
                    "email": data.get("emailAddress") or self.email,
                    "base_url": self.sanitized_base_url,
                }
            if resp.status_code in (401, 403):
                return {
                    "ok": False,
                    "configured": True,
                    "message": "Authentication failed. Check your JIRA_EMAIL and JIRA_API_TOKEN.",
                    "status_code": resp.status_code,
                }
            return {
                "ok": False,
                "configured": True,
                "message": f"Jira returned HTTP {resp.status_code}: {resp.text[:200]}",
                "status_code": resp.status_code,
            }
        except Exception as exc:
            logger.warning("jira_connection_test_failed", extra={"error": str(exc)})
            return {
                "ok": False,
                "configured": True,
                "message": f"Connection error reaching Jira: {exc}",
            }

    def get_issue(self, issue_key: str) -> JiraIssue:
        """Fetch Jira issue details and comments by issue key (e.g., 'SUP-101')."""
        issue_key = issue_key.strip().upper()
        if not re.match(r"^[A-Z0-9]+-\d+$", issue_key):
            raise JiraError(f"Invalid Jira issue key format: '{issue_key}'. Expected format like 'PROJ-123'.")

        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
        params = {"fields": "summary,description,status,priority,created,updated,reporter,assignee,project,comment"}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=self._get_headers(), params=params)
        except httpx.TimeoutException as exc:
            raise JiraError(f"Request timeout while connecting to Jira ({self.timeout}s)", status_code=504) from exc
        except httpx.RequestError as exc:
            raise JiraError(f"Network error connecting to Jira: {exc}") from exc

        if resp.status_code == 404:
            raise JiraNotFoundError(f"Jira issue '{issue_key}' not found.", status_code=404)
        if resp.status_code in (401, 403):
            raise JiraAuthenticationError(
                f"Unauthorized access to Jira issue '{issue_key}'. Verify API token permissions.",
                status_code=resp.status_code,
            )
        if resp.status_code >= 400:
            raise JiraError(f"Jira API error ({resp.status_code}): {resp.text[:300]}", status_code=resp.status_code)

        try:
            payload = resp.json()
        except Exception as exc:
            raise JiraError(f"Malformed JSON response from Jira for issue '{issue_key}'") from exc

        fields = payload.get("fields") or {}

        # Extract description safely (handles ADF or string)
        desc_raw = fields.get("description")
        description = _extract_text_from_adf(desc_raw) if desc_raw else ""

        # Extract comments
        comments_data = (fields.get("comment") or {}).get("comments") or []
        parsed_comments: list[JiraComment] = []
        for c in comments_data:
            c_body_raw = c.get("body")
            c_body = _extract_text_from_adf(c_body_raw) if c_body_raw else ""
            parsed_comments.append(
                JiraComment(
                    id=str(c.get("id", "")),
                    author=(c.get("author") or {}).get("displayName") or "Unknown",
                    body=sanitize_untrusted_text(c_body),
                    created=str(c.get("created", "")),
                )
            )

        status_obj = fields.get("status") or {}
        priority_obj = fields.get("priority") or {}
        reporter_obj = fields.get("reporter") or {}
        assignee_obj = fields.get("assignee") or {}
        project_obj = fields.get("project") or {}

        return JiraIssue(
            key=payload.get("key", issue_key),
            summary=sanitize_untrusted_text(fields.get("summary") or ""),
            description=sanitize_untrusted_text(description),
            status=status_obj.get("name") or "Open",
            priority=priority_obj.get("name") or "Medium",
            created=fields.get("created") or "",
            updated=fields.get("updated") or "",
            reporter=reporter_obj.get("displayName") or "Unknown",
            assignee=assignee_obj.get("displayName") if assignee_obj else None,
            project_key=project_obj.get("key") or self.project_key,
            comments=parsed_comments,
            raw_fields=fields,
        )

    def add_comment(self, issue_key: str, comment_text: str) -> dict[str, Any]:
        """Publish a sanitized comment to a Jira issue.
        Does NOT change ticket status or assign tickets.
        Includes duplicate comment prevention.
        """
        issue_key = issue_key.strip().upper()
        clean_text = sanitize_untrusted_text(comment_text)
        if not clean_text:
            raise JiraError("Comment text cannot be empty.")

        # Check existing issue comments to prevent accidental duplicate posts
        try:
            issue = self.get_issue(issue_key)
            for existing in issue.comments[-5:]:  # Check last 5 comments
                if existing.body.strip() == clean_text.strip():
                    logger.info("jira_duplicate_comment_prevented", extra={"issue_key": issue_key})
                    return {
                        "ok": True,
                        "comment_id": existing.id,
                        "duplicate_prevented": True,
                        "message": "Identical comment was already posted recently.",
                    }
        except Exception:
            # If issue lookup check fails, proceed with posting
            pass

        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/comment"

        # Build Atlassian Document Format (ADF) body
        # Convert plain paragraphs to ADF paragraph nodes
        paragraphs = [p for p in clean_text.split("\n\n") if p.strip()]
        adf_content = []
        for p in paragraphs:
            adf_content.append(
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": p.strip(),
                        }
                    ],
                }
            )

        payload = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": adf_content or [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": clean_text}],
                    }
                ],
            }
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, headers=self._get_headers(), json=payload)
        except httpx.TimeoutException as exc:
            raise JiraError(f"Timeout while posting comment to Jira ({self.timeout}s)", status_code=504) from exc
        except httpx.RequestError as exc:
            raise JiraError(f"Network error posting comment to Jira: {exc}") from exc

        if resp.status_code in (401, 403):
            raise JiraAuthenticationError(
                "Unauthorized: lacked permission to comment on Jira issue.",
                status_code=resp.status_code,
            )
        if resp.status_code == 404:
            raise JiraNotFoundError(f"Jira issue '{issue_key}' not found.", status_code=404)
        if resp.status_code >= 400:
            raise JiraError(f"Failed to post Jira comment ({resp.status_code}): {resp.text[:300]}", status_code=resp.status_code)

        res_data = resp.json()
        logger.info("jira_comment_published", extra={"issue_key": issue_key, "comment_id": res_data.get("id")})
        return {
            "ok": True,
            "comment_id": str(res_data.get("id")),
            "duplicate_prevented": False,
            "message": "Comment successfully published to Jira.",
        }

    def get_transitions(self, issue_key: str) -> list[dict[str, str]]:
        """Fetch available workflow transitions for an issue from Jira."""
        issue_key = issue_key.strip().upper()
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/transitions"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=self._get_headers())
        except httpx.TimeoutException as exc:
            raise JiraError(f"Timeout fetching transitions from Jira ({self.timeout}s)", status_code=504) from exc
        except httpx.RequestError as exc:
            raise JiraError(f"Network error fetching transitions from Jira: {exc}") from exc

        if resp.status_code == 404:
            raise JiraNotFoundError(f"Jira issue '{issue_key}' not found.", status_code=404)
        if resp.status_code in (401, 403):
            raise JiraAuthenticationError(f"Unauthorized to view transitions for '{issue_key}'.", status_code=resp.status_code)
        if resp.status_code >= 400:
            raise JiraError(f"Failed to fetch transitions ({resp.status_code}): {resp.text[:200]}", status_code=resp.status_code)

        transitions = resp.json().get("transitions") or []
        return [
            {
                "id": str(t.get("id")),
                "name": str(t.get("name")),
                "to_status": (t.get("to") or {}).get("name", t.get("name")),
            }
            for t in transitions
        ]

    def transition_issue(self, issue_key: str, transition_id_or_name: str) -> dict[str, Any]:
        """Perform a workflow status transition on an issue in Jira."""
        issue_key = issue_key.strip().upper()
        transitions = self.get_transitions(issue_key)
        matched_id = None
        target_name = transition_id_or_name.strip().lower()

        for t in transitions:
            if t["id"] == transition_id_or_name or t["name"].lower() == target_name or t["to_status"].lower() == target_name:
                matched_id = t["id"]
                target_name = t["name"]
                break

        if not matched_id:
            available = [f"{t['name']} (id={t['id']})" for t in transitions]
            raise JiraError(
                f"Transition '{transition_id_or_name}' not available for '{issue_key}'. Available: {', '.join(available)}",
                status_code=400,
            )

        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/transitions"
        payload = {"transition": {"id": matched_id}}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, headers=self._get_headers(), json=payload)
        except httpx.TimeoutException as exc:
            raise JiraError(f"Timeout transitioning Jira issue ({self.timeout}s)", status_code=504) from exc
        except httpx.RequestError as exc:
            raise JiraError(f"Network error transitioning Jira issue: {exc}") from exc

        if resp.status_code in (401, 403):
            raise JiraAuthenticationError("Unauthorized to transition Jira issue.", status_code=resp.status_code)
        if resp.status_code == 404:
            raise JiraNotFoundError(f"Jira issue '{issue_key}' not found.", status_code=404)
        if resp.status_code >= 400:
            raise JiraError(f"Failed to transition issue ({resp.status_code}): {resp.text[:200]}", status_code=resp.status_code)

        logger.info("jira_issue_transitioned", extra={"issue_key": issue_key, "transition": target_name})
        return {
            "ok": True,
            "issue_key": issue_key,
            "transition_id": matched_id,
            "transition_name": target_name,
            "message": f"Successfully transitioned '{issue_key}' via '{target_name}'.",
        }

