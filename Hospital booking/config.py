# config.py

import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = "offline-ai-hospital-secret"
    
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "database.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    TTS_FOLDER = os.path.join(BASE_DIR, "static", "tts")

    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
