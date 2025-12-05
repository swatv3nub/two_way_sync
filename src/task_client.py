# src/task_client.py
import logging
from typing import Optional, Dict, Any

import requests
from requests.auth import HTTPBasicAuth

from .config import Config
from .models import Task

logger = logging.getLogger(__name__)


class JiraClient:
    def __init__(self):
        if not (Config.JIRA_BASE_URL and Config.JIRA_EMAIL and Config.JIRA_API_TOKEN):
            raise RuntimeError("Jira config missing (BASE_URL / EMAIL / API_TOKEN)")
        self.base = Config.JIRA_BASE_URL.rstrip("/")
        self.auth = HTTPBasicAuth(Config.JIRA_EMAIL, Config.JIRA_API_TOKEN)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self.story_points_field = Config.JIRA_STORY_POINTS_FIELD

    def create_issue(
        self,
        summary: str,
        issuetype: str = "Task",
        project_key: Optional[str] = None,
        description: Optional[str] = None,   # kept in signature but not used
        priority: Optional[str] = None,      # kept in signature but not used
        story_points: Optional[int] = None,
    ) -> str:
        """
        Create a Jira issue with minimal required fields.
        We *do not* send description or priority to avoid ADF / screen issues.
        """
        data: Dict[str, Any] = {
            "fields": {
                "project": {"key": project_key or Config.JIRA_PROJECT_KEY},
                "summary": summary,
                "issuetype": {"name": issuetype},
            }
        }

        if self.story_points_field and story_points is not None:
            try:
                data["fields"][self.story_points_field] = int(story_points)
            except Exception:
                logger.warning("Invalid story points value: %s", story_points)

        resp = requests.post(
            f"{self.base}/rest/api/3/issue",
            json=data,
            auth=self.auth,
            headers=self.headers,
        )
        if resp.status_code not in (200, 201):
            logger.error("Create issue failed: %s %s", resp.status_code, resp.text)
            resp.raise_for_status()

        key = resp.json()["key"]
        logger.info("Created Jira issue %s", key)
        return key

    def get_issue(self, issue_key: str) -> Optional[Task]:
        resp = requests.get(
            f"{self.base}/rest/api/3/issue/{issue_key}",
            auth=self.auth,
            headers=self.headers,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        d = resp.json()
        fields = d["fields"]
        status = fields["status"]["name"]
        summary = fields["summary"]
        priority = fields.get("priority", {}).get("name")
        story_points = None
        if self.story_points_field:
            sp = fields.get(self.story_points_field)
            if sp is not None:
                try:
                    story_points = int(sp)
                except Exception:
                    pass
        updated_at = fields.get("updated")  # Jira's last updated timestamp as string
        return Task(issue_key, summary, status, priority, story_points, updated_at)

    def update_issue_fields(
        self,
        issue_key: str,
        summary: Optional[str] = None,
        priority: Optional[str] = None,
        story_points: Optional[int] = None,
    ):
        """
        Safely update summary and (optionally) story points.
        Priority is commented out to avoid workflow/screen issues unless configured.
        """
        fields: Dict[str, Any] = {}
        if summary is not None:
            fields["summary"] = summary
        # if priority is not None:
        #     fields["priority"] = {"name": priority}
        if self.story_points_field and story_points is not None:
            fields[self.story_points_field] = int(story_points)
        if not fields:
            return

        resp = requests.put(
            f"{self.base}/rest/api/3/issue/{issue_key}",
            json={"fields": fields},
            auth=self.auth,
            headers=self.headers,
        )
        if resp.status_code not in (200, 204):
            logger.error("Update issue failed: %s %s", resp.status_code, resp.text)
            resp.raise_for_status()
        logger.info("Updated fields for %s", issue_key)

    def find_transition_id(self, issue_key: str, desired_name: str) -> Optional[str]:
        resp = requests.get(
            f"{self.base}/rest/api/3/issue/{issue_key}/transitions",
            auth=self.auth,
            headers=self.headers,
        )
        resp.raise_for_status()
        transitions = resp.json().get("transitions", [])
        for t in transitions:
            if t.get("name", "").lower() == desired_name.lower():
                return t.get("id")
        return None

    def transition_issue(self, issue_key: str, desired_transition_name: str):
        tid = self.find_transition_id(issue_key, desired_transition_name)
        if not tid:
            raise RuntimeError(
                f"Transition '{desired_transition_name}' not found for {issue_key}"
            )
        resp = requests.post(
            f"{self.base}/rest/api/3/issue/{issue_key}/transitions",
            json={"transition": {"id": tid}},
            auth=self.auth,
            headers=self.headers,
        )
        if resp.status_code not in (200, 204):
            logger.error("Transition failed: %s %s", resp.status_code, resp.text)
            resp.raise_for_status()
        logger.info("Transitioned %s -> %s", issue_key, desired_transition_name)
