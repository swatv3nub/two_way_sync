import logging
import time

from .config import Config
from .db import init_db, upsert_mapping, get_mapping_by_lead, get_all_mappings
from .lead_client import GSheetClient
from .task_client import JiraClient

logger = logging.getLogger(__name__)

SHEET_TO_JIRA_STATUS = {
    "NEW": "To Do",
    "IN_PROGRESS": "In Progress",
    "IN_REVIEW": "In Review",
    "DONE": "Done",
}

JIRA_TO_SHEET_STATUS = {
    "To Do": "NEW",
    "In Progress": "IN_PROGRESS",
    "In Review": "IN_REVIEW",
    "Done": "DONE",
}


class SyncEngine:
    """
    Two-way sync using "fingerprints":
    - lead_fingerprint = status|title|priority|story_points (from sheet)
    - task_fingerprint = status|summary|priority|story_points (from Jira)

    We store these fingerprints in the DB columns lead_updated_at and task_updated_at.
    On each poll:
      - if current lead_fingerprint != stored lead_fingerprint   -> push sheet -> Jira
      - if current task_fingerprint != stored task_fingerprint   -> pull Jira -> sheet
    """

    def __init__(self):
        Config.validate()
        init_db()
        self.sheet = GSheetClient()
        self.jira = JiraClient()

    # ---------- FINGERPRINT HELPERS ----------

    @staticmethod
    def _lead_fingerprint(lead) -> str:
        # Normalize to strings to avoid None issues
        return "|".join([
            (lead.status or "").upper(),
            (lead.title or "").strip(),
            (lead.priority or "").strip(),
            str(lead.story_points or ""),
        ])

    @staticmethod
    def _task_fingerprint(task) -> str:
        return "|".join([
            (task.status or "").strip(),
            (task.summary or "").strip(),
            (task.priority or "").strip(),
            str(task.story_points or ""),
        ])

    # ---------- INITIAL SYNC ----------

    def initial_sync(self):
        """
        One-time sync to create Jira issues for sheet rows that have no mapping yet.
        """
        logger.info("Running initial sync")
        leads = self.sheet.list_leads()
        for lead in leads:
            mapping = get_mapping_by_lead(lead.lead_id)
            if mapping and mapping.get("task_key"):
                # Already mapped
                continue

            # If you want to skip certain statuses, you can do it here.
            # Example: skip rows with empty name
            if not (lead.title or "").strip():
                logger.info("Skipping lead %s with empty title", lead.lead_id)
                continue

            try:
                issue_key = self.jira.create_issue(
                    summary=lead.title or f"Lead {lead.lead_id}",
                    issuetype="Task",
                    project_key=Config.JIRA_PROJECT_KEY,
                    description=None,
                    priority=lead.priority,
                    story_points=lead.story_points,
                )
                task = self.jira.get_issue(issue_key)
                task_fp = self._task_fingerprint(task) if task else ""

                lead_fp = self._lead_fingerprint(lead)
                upsert_mapping(
                    lead.lead_id,
                    lead.row_index,
                    issue_key,
                    lead_updated_at=lead_fp,
                    task_updated_at=task_fp,
                )

                # Write Jira key into sheet
                self.sheet.write_jira_issue_id(lead.row_index, issue_key)
                logger.info("Initial sync: mapped lead %s -> %s", lead.lead_id, issue_key)
            except Exception:
                logger.exception("Failed to create issue for lead %s", lead.lead_id)

    # ---------- MAIN LOOP ----------

    def run_polling_loop(self):
        logger.info(
            "Starting polling sync (interval = %s s)",
            Config.POLL_INTERVAL_SECONDS,
        )
        while True:
            try:
                self.sync_leads_to_jira()
                self.sync_jira_to_leads()
            except Exception:
                logger.exception("Error during sync iteration")
            time.sleep(Config.POLL_INTERVAL_SECONDS)

    # ---------- SHEET -> JIRA ----------

    def sync_leads_to_jira(self):
        """
        For each lead:
          - compute current fingerprint
          - compare with stored fingerprint (lead_updated_at)
          - if different -> push changes to Jira, then refresh Jira + update both fingerprints in DB
        """
        leads = self.sheet.list_leads()
        for lead in leads:
            mapping = get_mapping_by_lead(lead.lead_id)
            lead_fp = self._lead_fingerprint(lead)

            # No mapping: create a new Jira issue
            if not mapping:
                if not (lead.title or "").strip():
                    continue
                try:
                    issue_key = self.jira.create_issue(
                        summary=lead.title or f"Lead {lead.lead_id}",
                        issuetype="Task",
                        project_key=Config.JIRA_PROJECT_KEY,
                        description=None,
                        priority=lead.priority,
                        story_points=lead.story_points,
                    )
                    task = self.jira.get_issue(issue_key)
                    task_fp = self._task_fingerprint(task) if task else ""

                    upsert_mapping(
                        lead.lead_id,
                        lead.row_index,
                        issue_key,
                        lead_updated_at=lead_fp,
                        task_updated_at=task_fp,
                    )
                    self.sheet.write_jira_issue_id(lead.row_index, issue_key)
                    logger.info("Created and mapped lead %s -> %s", lead.lead_id, issue_key)
                except Exception:
                    logger.exception("Create failed for lead %s", lead.lead_id)
                continue

            # Mapping exists; check if sheet actually changed since last sync
            stored_lead_fp = mapping.get("lead_updated_at") or ""
            issue_key = mapping.get("task_key")

            if lead_fp == stored_lead_fp:
                # No sheet-side change; do not push anything for this row
                continue

            if not issue_key:
                logger.warning("Mapping for lead %s has no task_key", lead.lead_id)
                continue

            logger.info("Detected SHEET change for lead %s -> pushing to %s", lead.lead_id, issue_key)

            # Update fields in Jira
            try:
                self.jira.update_issue_fields(
                    issue_key,
                    summary=lead.title or None,
                    priority=lead.priority or None,
                    story_points=lead.story_points,
                )
            except Exception:
                logger.exception("Failed field update for %s", issue_key)

            # Try status transition based on sheet status
            desired_jira_status = SHEET_TO_JIRA_STATUS.get((lead.status or "").upper())
            if desired_jira_status:
                try:
                    self.jira.transition_issue(issue_key, desired_jira_status)
                except Exception as e:
                    logger.debug(
                        "Transition not available/failed for %s -> %s: %s",
                        issue_key,
                        desired_jira_status,
                        e,
                    )

            # Refresh Jira issue + update both fingerprints in DB
            try:
                task = self.jira.get_issue(issue_key)
                task_fp = self._task_fingerprint(task) if task else ""
            except Exception:
                task_fp = mapping.get("task_updated_at") or ""

            upsert_mapping(
                lead.lead_id,
                lead.row_index,
                issue_key,
                lead_updated_at=lead_fp,
                task_updated_at=task_fp,
            )

    # ---------- JIRA -> SHEET ----------

    def sync_jira_to_leads(self):
        """
        For each mapping:
          - fetch Jira issue
          - compute current task fingerprint
          - compare with stored task fingerprint (task_updated_at)
          - if different -> Jira changed -> update sheet accordingly and refresh both fingerprints
        """
        mappings = get_all_mappings()
        for m in mappings:
            lead_id = m["lead_id"]
            issue_key = m["task_key"]
            row_index = m["row_index"]
            stored_task_fp = m.get("task_updated_at") or ""

            try:
                task = self.jira.get_issue(issue_key)
            except Exception:
                logger.exception("Failed to fetch issue %s", issue_key)
                continue

            if not task:
                logger.warning("Issue %s not found (maybe deleted)", issue_key)
                continue

            current_task_fp = self._task_fingerprint(task)

            # If Jira hasn't changed according to fingerprint, do NOT overwrite the sheet
            if current_task_fp == stored_task_fp:
                continue

            logger.info("Detected JIRA change for %s -> updating sheet row %s", issue_key, row_index)

            # Pull Jira status into sheet
            new_sheet_status = JIRA_TO_SHEET_STATUS.get(task.status)
            lead = self.sheet.get_lead_by_row(row_index)
            if not lead:
                logger.warning("Lead row %s not found", row_index)
                continue

            # Only update sheet status if we have a mapped status and it's actually different
            if new_sheet_status and (lead.status or "").upper() != new_sheet_status:
                try:
                    self.sheet.update_lead_status(row_index, new_sheet_status)
                except Exception:
                    logger.exception(
                        "Failed to update sheet status for lead %s / issue %s",
                        lead_id,
                        issue_key,
                    )

            # Re-read lead to build its current fingerprint
            lead = self.sheet.get_lead_by_row(row_index)
            lead_fp = self._lead_fingerprint(lead) if lead else ""

            # Update fingerprints in DB so next loop knows both sides are in sync
            try:
                upsert_mapping(
                    lead_id,
                    row_index,
                    issue_key,
                    lead_updated_at=lead_fp,
                    task_updated_at=current_task_fp,
                )
            except Exception:
                logger.exception(
                    "Failed to update mapping fingerprints for lead %s / issue %s",
                    lead_id,
                    issue_key,
                )
