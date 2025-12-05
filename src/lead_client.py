import logging
from typing import List, Optional

import gspread
from google.oauth2.service_account import Credentials

from .config import Config
from .models import Lead

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

class GSheetClient:
    def __init__(self):
        if not Config.GSHEET_SERVICE_ACCOUNT_JSON:
            raise RuntimeError("GSHEET_SERVICE_ACCOUNT_JSON not configured")
        if not Config.GSHEET_SPREADSHEET_ID:
            raise RuntimeError("GSHEET_SPREADSHEET_ID not configured")

        creds = Credentials.from_service_account_file(
            Config.GSHEET_SERVICE_ACCOUNT_JSON, scopes=SCOPES
        )
        gc = gspread.authorize(creds)
        self.sheet = gc.open_by_key(Config.GSHEET_SPREADSHEET_ID).sheet1

        self.header = [c.strip() for c in self.sheet.row_values(1)]
        self.header_lower = [c.lower() for c in self.header]
        logger.info("Sheet headers: %s", self.header)

    # --- internal helpers ---

    def _col_index(self, col_name: str) -> Optional[int]:
        """Return 1-based column index for given header name (case-insensitive)."""
        col_name = col_name.lower()
        try:
            return self.header_lower.index(col_name) + 1
        except ValueError:
            return None

    def _row_to_dict(self, values: list) -> dict:
        d = {}
        for i, h in enumerate(self.header):
            d[h.lower()] = values[i].strip() if i < len(values) else ""
        return d

    # --- public API ---

    def list_leads(self) -> List[Lead]:
        all_values = self.sheet.get_all_values()
        if len(all_values) < 2:
            return []

        rows = all_values[1:]  # skip header
        leads: List[Lead] = []

        for idx, row in enumerate(rows, start=2):
            data = self._row_to_dict(row)

            # lead_id = id column if present, else jira_issue_id, else 'row:X'
            lead_id = data.get("id") or data.get("jira_issue_id") or f"row:{idx}"

            def parse_int(val: str) -> Optional[int]:
                val = (val or "").strip()
                if not val:
                    return None
                return int(val) if val.isdigit() else None

            lead = Lead(
                lead_id=str(lead_id),
                row_index=idx,
                title=data.get("title") or data.get("name") or "",
                description=data.get("description") or None,
                status=(data.get("status") or "").upper() or None,
                priority=data.get("priority") or None,
                story_points=parse_int(data.get("story_points") or ""),
                jira_issue_id=data.get("jira_issue_id") or None,
                updated_at=data.get("updated_at") or None,
            )
            leads.append(lead)

        return leads

    def get_lead_by_row(self, row_index: int) -> Optional[Lead]:
        vals = self.sheet.row_values(row_index)
        if not vals:
            return None
        data = self._row_to_dict(vals)
        lead_id = data.get("id") or data.get("jira_issue_id") or f"row:{row_index}"

        def parse_int(val: str) -> Optional[int]:
            val = (val or "").strip()
            if not val:
                return None
            return int(val) if val.isdigit() else None

        return Lead(
            lead_id=str(lead_id),
            row_index=row_index,
            title=data.get("title") or data.get("name") or "",
            description=data.get("description") or None,
            status=(data.get("status") or "").upper() or None,
            priority=data.get("priority") or None,
            story_points=parse_int(data.get("story_points") or ""),
            jira_issue_id=data.get("jira_issue_id") or None,
            updated_at=data.get("updated_at") or None,
        )

    def write_jira_issue_id(self, row_index: int, issue_key: str):
        col = self._col_index("jira_issue_id")
        if not col:
            # add column at end if missing
            self.header.append("jira_issue_id")
            self.header_lower.append("jira_issue_id")
            self.sheet.insert_row(self.header, 1)
            col = self._col_index("jira_issue_id")
        self.sheet.update_cell(row_index, col, issue_key)
        logger.info("Wrote Jira issue key %s to row %s", issue_key, row_index)

    def update_lead_status(self, row_index: int, new_status: str):
        col = self._col_index("status")
        if not col:
            raise RuntimeError("No 'status' header in sheet")
        self.sheet.update_cell(row_index, col, new_status)
        logger.info("Updated row %s status -> %s", row_index, new_status)
