from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config
from models import db, User, Availability, Assignment
from datetime import datetime, timedelta, date
import calendar as cal

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

# Helper function pour générer le calendrier
def generate_calendar(year, month, user_id):
    today = date.today()
    
    # Obtenir le calendrier du mois
    month_calendar = cal.monthcalendar(year, month)
    
    # Récupérer les disponibilités de l'utilisateur
    availabilities = Availability.query.filter_by(user_id=user_id).filter(
        db.extract('month', Availability.date) == month,
        db.extract('year', Availability.date) == year
    ).all()
    
    avail_dict = {a.date: a for a in availabilities}
    
    # Récupérer les assignments
    assignments = Assignment.query.filter_by(user_id=user_id).filter(
        db.extract('month', Assignment.date) == month,
        db.extract('year', Assignment.date) == year
    ).all()
    
    assign_dict = {a.date: a for a in assignments}
    
    # Construire les données du calendrier
    calendar_data = []
    for week in month_calendar:
        week_data = []
        for day in week:
            if day == 0:
                week_data.append(None)
            else:
                day_date = date(year, month, day)
                is_past = day_date < today
                is_assigned = day_date in assign_dict
                
                availability = avail_dict.get(day_date)
                is_available = availability.is_available if availability else False
                
                status = 'past' if is_past else ('assigned' if is_assigned else ('available' if is_available else 'unavailable'))
                
                week_data.append({
                    'day': day,
                    'date': day_date.isoformat(),
                    'is_available': is_available,
                    'is_assigned': is_assigned,
                    'is_past': is_past,
                    'status': status
                })
        calendar_data.append(week_data)
    
    return calendar_data

# Routes principales
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('dj_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('auth/login.html')

@app.route('/login', methods=['POST'])
def do_login():
    username = request.form.get('username')
    password = request.form.get('password')
    remember = request.form.get('remember', False)
    
    user = User.query.filter_by(username=username).first()
    
    if user and user.check_password(password):
        if not user.is_active:
            flash('Votre compte est désactivé. Contactez l\'administrateur.', 'danger')
            return redirect(url_for('login'))
        
        login_user(user, remember=remember)
        flash(f'Bienvenue {user.dj_name} !', 'success')
        
        if user.is_admin:
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('dj_dashboard'))
    else:
        flash('Identifiants incorrects.', 'danger')
        return redirect(url_for('login'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Déconnexion réussie.', 'success')
    return redirect(url_for('login'))

# Routes DJ
@app.route('/dj/dashboard')
@login_required
def dj_dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    # Paramètres de date
    month = request.args.get('month', type=int, default=datetime.now().month)
    year = request.args.get('year', type=int, default=datetime.now().year)
    
    # Stats
    today = date.today()
    first_day = date(year, month, 1)
    last_day = date(year, month, cal.monthrange(year, month)[1])
    
    disponibilites = Availability.query.filter(
        Availability.user_id == current_user.id,
        Availability.date >= first_day,
        Availability.date <= last_day,
        Availability.is_available == True
    ).count()
    
    assignments = Assignment.query.filter_by(user_id=current_user.id).filter(
        Assignment.date >= today
    ).count()
    
    upcoming_sets = Assignment.query.filter_by(user_id=current_user.id).filter(
        Assignment.date >= today
    ).order_by(Assignment.date).limit(5).all()
    
    stats = {
        'disponibilites': disponibilites,
        'assignments': assignments,
        'prochains_sets': len(upcoming_sets)
    }
    
    # Calendrier
    calendar_data = generate_calendar(year, month, current_user.id)
    
    months = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
              'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
    
    return render_template('dj/dashboard.html',
                         stats=stats,
                         calendar_data=calendar_data,
                         upcoming_sets=upcoming_sets,
                         current_month=month,
                         current_year=year,
                         months=months,
                         today=today)

@app.route('/dj/toggle-availability', methods=['POST'])
@login_required
def toggle_availability():
    if current_user.is_admin:
        return jsonify({'success': False, 'error': 'Admin ne peut pas modifier les disponibilités'})
    
    data = request.get_json()
    date_str = data.get('date')
    is_available = data.get('is_available')
    
    try:
        day_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Vérifier que ce n'est pas une date passée
        if day_date < date.today():
            return jsonify({'success': False, 'error': 'Cannot modify past dates'})
        
        # Vérifier qu'il n'y a pas d'assignment
        existing_assignment = Assignment.query.filter_by(
            user_id=current_user.id,
            date=day_date
        ).first()
        
        if existing_assignment:
            return jsonify({'success': False, 'error': 'Date already assigned'})
        
        # Créer ou mettre à jour la disponibilité
        availability = Availability.query.filter_by(
            user_id=current_user.id,
            date=day_date
        ).first()
        
        if availability:
            availability.is_available = is_available
            availability.updated_at = datetime.utcnow()
        else:
            availability = Availability(
                user_id=current_user.id,
                date=day_date,
                is_available=is_available
            )
            db.session.add(availability)
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

# Routes Admin
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Accès refusé.', 'danger')
        return redirect(url_for('dj_dashboard'))
    return render_template('admin/dashboard.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3000)