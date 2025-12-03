# Models for Lead and Task
from dataclasses import dataclass
from typing import Optional

@dataclass
class Lead:
    lead_id: str
    row_index: int
    title: str
    description: Optional[str]
    status: Optional[str]
    priority: Optional[str]
    story_points: Optional[int]
    jira_issue_id: Optional[str]
    updated_at: Optional[str]

@dataclass
class Task:
    issue_key: str
    summary: str
    status: str
    priority: Optional[str]
    story_points: Optional[int]