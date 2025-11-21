import os
from pathlib import Path

DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '',  # Leave empty if no password set in XAMPP
    'database': 'college_erp'
}

SECRET_KEY = 'your-secret-key-change-in-production'
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'Frontend', 'uploads')

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
WORKSPACE_ROOT = PROJECT_ROOT.parent

FRONTEND_ROOT = (WORKSPACE_ROOT / ".vscode" / "Frontend").resolve()
FRONTEND_INDEX = FRONTEND_ROOT / "index.html"

ALLOWED_FRONTEND_EXTENSIONS = {
    ".html", ".css", ".js", ".json",
    ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".ico", ".woff", ".woff2", ".ttf", ".map"
}
