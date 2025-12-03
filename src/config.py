import os
from dotenv import load_dotenv;

load_dotenv()

class Config():
    GSHEET_SERVICE_ACCOUNT_JSON = os.environ.get("GSHEET_SERVICE_ACCOUNT_JSON")
    GSHEET_SPREADSHEET_ID = os.environ.get("GSHEET_SPREADSHEET_ID")
    JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL")
    JIRA_EMAIL = os.environ.get("JIRA_EMAIL")
    JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")
    JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY")
    JIRA_STORY_POINTS_FIELD= os.environ.get("JIRA_STORY_POINTS_FIELD")
    POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", 20))
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "info")
    SQLITE_DB_PATH = os.environ.get("SQLITE_DB_PATH", "./data/database.db")