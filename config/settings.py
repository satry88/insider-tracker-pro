import os

class Config:
    SECRET_KEY         = os.getenv("SECRET_KEY", "insider-tracker-secret-2026")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///insider_tracker.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    FINNHUB_API_KEY    = os.getenv("FINNHUB_API_KEY", "")
