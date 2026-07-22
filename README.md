# Google Sheets ↔ Jira Two-Way Sync

A reliable, bi-directional synchronization engine built with Python that keeps **Google Sheets** rows (Leads / Tasks) in sync with **Jira** issues (Tasks / Stories). It uses a fingerprint-based state tracking strategy backed by SQLite to ensure **idempotency**, prevent feedback loops, and accurately detect changes on either platform.

---

## 🚀 Features

- **Bi-Directional Synchronization**: Pushes changes from Google Sheets to Jira and pulls updates from Jira back into Google Sheets.
- **Fingerprint-Based State Tracking**: Calculates checksums (`status|title|priority|story_points`) to detect actual modifications on either side, eliminating unnecessary API calls and avoiding infinite update loops.
- **Automated Issue Creation**: Automatically creates a corresponding Jira issue for any new row added to the Google Sheet and writes back the assigned Jira Issue Key.
- **Status Mapping**: Seamlessly translates workflow statuses between Google Sheets and Jira.
- **Configurable Polling Loop**: Periodically polls for modifications at customizable intervals.
- **Robust Error Handling & Logging**: Logs sync events, field updates, and transition failures gracefully.

---

## 📁 Project Structure

```text
two_way_sync/
├── .env.example           # Template for required environment variables
├── requirements.txt       # Python package dependencies
├── README.md              # Project documentation
├── data/                  # Storage directory for local SQLite mapping database
├── src/
│   ├── config.py          # Environment configuration loader & validator
│   ├── db.py              # SQLite database manager for lead <-> issue mappings
│   ├── lead_client.py     # Google Sheets API client (gspread)
│   ├── task_client.py     # Jira REST API client
│   ├── models.py          # Data models for Lead and Task objects
│   ├── sync_logic.py      # Core two-way sync engine & fingerprint logic
│   ├── main.py            # CLI entry point for initial sync & polling runner
│   └── api.py            # API module placeholder
└── tests/
    ├── test_idempotency.py # Tests for sync idempotency
    └── test_mapping.py     # Unit tests for mapping database logic
```

---

## 🔄 Status Mapping Matrix

The sync engine maps workflow statuses between Google Sheets and Jira as follows:

| Google Sheet Status | Jira Issue Status |
| :--- | :--- |
| `NEW` | `To Do` |
| `IN_PROGRESS` | `In Progress` |
| `IN_REVIEW` | `In Review` |
| `DONE` | `Done` |

---

## ⚙️ Configuration & Environment Variables

Copy `.env.example` to `.env` and fill in your credentials and configuration options:

```bash
cp .env.example .env
```

### Environment Variables

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `GSHEET_SERVICE_ACCOUNT_JSON` | Path to Google Cloud Service Account JSON key file | `./auth.json` |
| `GSHEET_SPREADSHEET_ID` | Spreadsheet ID from your Google Sheet URL | `1A2b3C4d5E...` |
| `JIRA_BASE_URL` | Base URL of your Jira instance | `https://your-domain.atlassian.net` |
| `JIRA_EMAIL` | Jira user email for HTTP Basic Auth | `user@company.com` |
| `JIRA_API_TOKEN` | Jira API Token generated from Atlassian Account | `ATATT3xFfGF0...` |
| `JIRA_PROJECT_KEY` | Jira Project Key where issues are created | `PROJ` |
| `JIRA_STORY_POINTS_FIELD` | Custom field ID for Story Points in Jira | `customfield_10016` |
| `POLL_INTERVAL_SECONDS` | Sync loop polling interval in seconds | `20` |
| `LOG_LEVEL` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `info` |
| `SQLITE_DB_PATH` | Path to SQLite database file for tracking mappings | `./data/database.db` |

---

## 🛠️ Setup & Installation

### Prerequisites

- **Python 3.8+**
- A **Google Cloud Service Account** with Google Sheets API scope enabled.
- A **Google Sheet** shared with your service account email (Editor access).
- A **Jira Cloud/Server account** with access to create & update issues in the target project.

### 1. Clone & Setup Virtual Environment

```bash
git clone <repository-url>
cd two_way_sync

# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Activate virtual environment (macOS/Linux)
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 🏁 Running the Application

### 1. Run Initial Sync

To map existing rows in the Google Sheet to Jira issues (or create missing Jira issues for unmapped rows):

```bash
python -m src.main initial
```

### 2. Run Continuous Polling Sync

To start the continuous polling loop that periodically syncs changes between Google Sheets and Jira:

```bash
python -m src.main run
```

Or simply run without arguments (defaults to `run`):

```bash
python -m src.main
```

---

## 🧠 Architecture & How Sync Works

1. **Fingerprint Computation**:
   - `lead_fingerprint` = `STATUS|TITLE|PRIORITY|STORY_POINTS` (computed from Sheet row)
   - `task_fingerprint` = `STATUS|SUMMARY|PRIORITY|STORY_POINTS` (computed from Jira issue)
2. **Sheet to Jira Sync (`sync_leads_to_jira`)**:
   - Reads sheet rows and compares their current fingerprint with the stored `lead_updated_at` fingerprint in SQLite.
   - If changed, updates Jira fields/status and saves the updated fingerprints for both sides in SQLite.
3. **Jira to Sheet Sync (`sync_jira_to_leads`)**:
   - Queries mapped Jira issues and compares their current fingerprint with the stored `task_updated_at` fingerprint.
   - If changed, updates the Google Sheet row status/fields and updates the stored fingerprints in SQLite.

---

## 🧪 Testing

To run the unit and integration tests:

```bash
pytest
```
