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
    
    # Email configuration - ProtonMail SMTP Direct
    MAIL_SERVER = 'smtp.protonmail.ch'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = 'serveur@tbhone.uk'
    MAIL_PASSWORD = 'V5HX212B66QBEYLT'
    MAIL_DEFAULT_SENDER = ('Planning Folies Lille', 'serveur@tbhone.uk')
    
    # Notification settings
    SEND_EMAIL_NOTIFICATIONS = os.environ.get('SEND_EMAIL_NOTIFICATIONS', 'true').lower() in ['true', 'on', '1']
    NOTIFICATION_REMINDER_DAYS = 7  # Rappel 7 jours avant
    ADMIN_EMAIL = 'tbhone.pro@protonmail.com'  # Email de l'admin
