from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

def calculate_tarif(date, time_slot):
    """Calculer le tarif selon le jour et le créneau"""
    day_of_week = date.weekday()  # 0=Lundi, 3=Jeudi, 4=Vendredi, 5=Samedi
    
    # Jeudi (3)
    if day_of_week == 3:
        if time_slot == 'complete':
            return 120
        elif time_slot == 'warmup':
            return 40
        elif time_slot == 'peaktime':
            return 80
    
    # Vendredi (4) et Samedi (5)
    elif day_of_week in [4, 5]:
        if time_slot == 'complete':
            return 200
        elif time_slot == 'warmup':
            return 50
        elif time_slot == 'peaktime':
            return 150
    
    # Autres jours (Dimanche à Mercredi)
    else:
        if time_slot == 'complete':
            return 100
        elif time_slot == 'warmup':
            return 30
        elif time_slot == 'peaktime':
            return 70
    
    return 0

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    dj_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations - AJOUTER foreign_keys
    availabilities = db.relationship('Availability', backref='user', lazy=True, cascade='all, delete-orphan')
    assignments = db.relationship('Assignment', 
                                  foreign_keys='Assignment.user_id',
                                  backref='user', 
                                  lazy=True, 
                                  cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username} - {self.dj_name}>'

class Availability(db.Model):
            __tablename__ = 'availabilities'
            
            id = db.Column(db.Integer, primary_key=True)
            user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
            date = db.Column(db.Date, nullable=False)
            is_available = db.Column(db.Boolean, default=True)
            time_slot = db.Column(db.String(20), default='complete')  # 'complete', 'warmup', 'peaktime'
            notes = db.Column(db.String(200))
            created_at = db.Column(db.DateTime, default=datetime.utcnow)
            updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
            
            # Index et contraintes
            __table_args__ = (
                db.UniqueConstraint('user_id', 'date', name='unique_user_date_availability'),
                db.Index('idx_availability_date', 'date'),
            )
            
            def __repr__(self):
                return f'<Availability {self.user.dj_name} - {self.date} - {self.time_slot}>'

class Assignment(db.Model):
            __tablename__ = 'assignments'
            
            id = db.Column(db.Integer, primary_key=True)
            user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
            date = db.Column(db.Date, nullable=False)
            time_slot = db.Column(db.String(20), default='complete')  # 'complete', 'warmup', 'peaktime'
            tarif = db.Column(db.Integer, default=0)  # Tarif calculé automatiquement
            notes = db.Column(db.String(200))
            created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
            created_at = db.Column(db.DateTime, default=datetime.utcnow)
            updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
            
            # Index
            __table_args__ = (
                db.UniqueConstraint('date', 'time_slot', name='unique_date_timeslot_assignment'),
                db.Index('idx_assignment_date', 'date'),
            )
            
            def __repr__(self):
                return f'<Assignment {self.user.dj_name} - {self.date} - {self.time_slot} - {self.tarif}€>'
