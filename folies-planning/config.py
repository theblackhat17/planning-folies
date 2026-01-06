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
    
    # Email Configuration (Gmail)
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'votre-email@gmail.com'  # À configurer
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'votre-mot-de-passe-app'  # À configurer
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'LES FOLIES <noreply@lesfolies.com>'
    
    # Notification Settings
    SEND_EMAIL_NOTIFICATIONS = os.environ.get('SEND_EMAIL_NOTIFICATIONS', 'false').lower() in ['true', 'on', '1']
    NOTIFICATION_REMINDER_DAYS = 7  # Rappel X jours avant un set
