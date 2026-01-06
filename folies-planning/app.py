from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config
from models import db, User, Availability, Assignment
from datetime import datetime, timedelta
import calendar

app = Flask(__name__)
app.config.from_object(Config)

# Initialisation
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Connectez-vous pour accéder à cette page.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Création de la base de données et admin par défaut
with app.app_context():
    db.create_all()
    
    # Créer l'admin si inexistant
    if not User.query.filter_by(username=Config.DEFAULT_ADMIN_USERNAME).first():
        admin = User(
            username=Config.DEFAULT_ADMIN_USERNAME,
            email='admin@lesfolies.com',
            dj_name='Administrateur',
            is_admin=True,
            phone='+33 6 00 00 00 00'
        )
        admin.set_password(Config.DEFAULT_ADMIN_PASSWORD)
        db.session.add(admin)
        db.session.commit()
        print(f"✅ Admin créé : {Config.DEFAULT_ADMIN_USERNAME} / {Config.DEFAULT_ADMIN_PASSWORD}")

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('dj_dashboard'))
    return redirect(url_for('login'))

@app.route('/login')
def login():
    return render_template('auth/login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Déconnexion réussie.', 'success')
    return redirect(url_for('login'))

@app.route('/dj/dashboard')
@login_required
def dj_dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    return render_template('dj/dashboard.html')

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Accès refusé.', 'danger')
        return redirect(url_for('dj_dashboard'))
    return render_template('admin/dashboard.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3000)
