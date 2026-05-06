import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    DATABASE_PATH = DATA_DIR / "database.sqlite"
    IMPORT_PATH = DATA_DIR / "import_data.pkl"
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@cosmos.local")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin12345")
