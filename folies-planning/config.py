import os
from datetime import timedelta

class Config:
    # Secret key pour les sessions
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'folies_secret_key_2026_super_secure'
    
    # Database
    SQLALCHEMY_DATABASE_URI = 'sqlite:///folies_planning.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Upload
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max
    
    # Admin par défaut
    DEFAULT_ADMIN_USERNAME = 'admin'
    DEFAULT_ADMIN_PASSWORD = 'Folies2026!'  # À changer en production
