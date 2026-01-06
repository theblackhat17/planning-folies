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

# Helper function pour le calendrier admin
def generate_admin_calendar(year, month):
    today = date.today()
    month_calendar = cal.monthcalendar(year, month)
    
    # Récupérer tous les assignments du mois
    assignments = Assignment.query.filter(
        db.extract('month', Assignment.date) == month,
        db.extract('year', Assignment.date) == year
    ).all()
    
    assign_dict = {a.date: a for a in assignments}
    
    # Récupérer toutes les disponibilités du mois
    availabilities = Availability.query.filter(
        db.extract('month', Availability.date) == month,
        db.extract('year', Availability.date) == year,
        Availability.is_available == True
    ).all()
    
    # Grouper par date
    avail_by_date = {}
    for avail in availabilities:
        if avail.date not in avail_by_date:
            avail_by_date[avail.date] = []
        avail_by_date[avail.date].append(avail)
    
    # Construire le calendrier
    calendar_data = []
    for week in month_calendar:
        week_data = []
        for day in week:
            if day == 0:
                week_data.append(None)
            else:
                day_date = date(year, month, day)
                is_past = day_date < today
                
                assignment = assign_dict.get(day_date)
                available_djs = avail_by_date.get(day_date, [])
                available_count = len(available_djs)
                
                if assignment:
                    status = 'assigned'
                    assigned_dj = assignment.user.dj_name
                elif is_past:
                    status = 'past'
                    assigned_dj = None
                elif available_count > 1:
                    status = 'multiple'
                    assigned_dj = None
                elif available_count == 1:
                    status = 'single'
                    assigned_dj = None
                else:
                    status = 'none'
                    assigned_dj = None
                
                week_data.append({
                    'day': day,
                    'date': day_date.isoformat(),
                    'is_assigned': assignment is not None,
                    'assigned_dj': assigned_dj,
                    'is_past': is_past,
                    'available_count': available_count,
                    'status': status
                })
        calendar_data.append(week_data)
    
    return calendar_data

# Route Admin Dashboard
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Accès refusé.', 'danger')
        return redirect(url_for('dj_dashboard'))
    
    # Paramètres de date
    month = request.args.get('month', type=int, default=datetime.now().month)
    year = request.args.get('year', type=int, default=datetime.now().year)
    
    today = date.today()
    first_day = date(year, month, 1)
    last_day = date(year, month, cal.monthrange(year, month)[1])
    
    # Stats globales
    total_djs = User.query.filter_by(is_admin=False, is_active=True).count()
    
    assignments_month = Assignment.query.filter(
        Assignment.date >= first_day,
        Assignment.date <= last_day
    ).count()
    
    # Conflits = dates avec plusieurs DJs disponibles et pas encore assignées
    availabilities = Availability.query.filter(
        Availability.date >= today,
        Availability.date >= first_day,
        Availability.date <= last_day,
        Availability.is_available == True
    ).all()
    
    date_dj_count = {}
    for avail in availabilities:
        if avail.date not in date_dj_count:
            date_dj_count[avail.date] = []
        date_dj_count[avail.date].append(avail.user)
    
    # Filtrer les conflits (plus d'un DJ dispo)
    conflicts_dates = {d: djs for d, djs in date_dj_count.items() if len(djs) > 1}
    
    # Exclure les dates déjà assignées
    assigned_dates = {a.date for a in Assignment.query.filter(
        Assignment.date >= first_day,
        Assignment.date <= last_day
    ).all()}
    
    conflicts_dates = {d: djs for d, djs in conflicts_dates.items() if d not in assigned_dates}
    
    conflicts = len(conflicts_dates)
    
    # Jours non assignés (futures dates sans assignment)
    total_days_month = (last_day - max(first_day, today)).days + 1
    unassigned_days = total_days_month - Assignment.query.filter(
        Assignment.date >= max(first_day, today),
        Assignment.date <= last_day
    ).count()
    
    stats = {
        'total_djs': total_djs,
        'assignments_month': assignments_month,
        'conflicts': conflicts,
        'unassigned_days': max(0, unassigned_days)
    }
    
    # Calendrier admin
    calendar_data = generate_admin_calendar(year, month)
    
    # Conflits détaillés
    conflicts_data = [
        {'date': d, 'djs': djs}
        for d, djs in sorted(conflicts_dates.items())
    ]
    
    # Liste des DJs avec leurs stats
    all_djs = User.query.filter_by(is_admin=False).all()
    for dj in all_djs:
        dj.disponibilites = Availability.query.filter_by(
            user_id=dj.id,
            is_available=True
        ).filter(
            Availability.date >= first_day,
            Availability.date <= last_day
        ).count()
        
        dj.assignments = Assignment.query.filter_by(user_id=dj.id).filter(
            Assignment.date >= today
        ).count()
    
    months = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
              'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
    
    return render_template('admin/dashboard.html',
                         stats=stats,
                         calendar_data=calendar_data,
                         conflicts_data=conflicts_data,
                         all_djs=all_djs,
                         current_month=month,
                         current_year=year,
                         months=months)

# Route pour ajouter un DJ
@app.route('/admin/add-dj', methods=['POST'])
@login_required
def admin_add_dj():
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    dj_name = request.form.get('dj_name')
    username = request.form.get('username')
    email = request.form.get('email')
    phone = request.form.get('phone')
    password = request.form.get('password')
    
    # Validation
    if User.query.filter_by(username=username).first():
        flash('Ce nom d\'utilisateur existe déjà.', 'danger')
        return redirect(url_for('admin_dashboard') + '?tab=djs')
    
    if User.query.filter_by(email=email).first():
        flash('Cet email existe déjà.', 'danger')
        return redirect(url_for('admin_dashboard') + '?tab=djs')
    
    try:
        new_dj = User(
            username=username,
            email=email,
            dj_name=dj_name,
            phone=phone,
            is_admin=False,
            is_active=True
        )
        new_dj.set_password(password)
        
        db.session.add(new_dj)
        db.session.commit()
        
        flash(f'DJ {dj_name} créé avec succès !', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'danger')
    
    return redirect(url_for('admin_dashboard') + '#djs')

# Route pour assigner un DJ
@app.route('/admin/assign-dj', methods=['POST'])
@login_required
def admin_assign_dj():
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    date_str = data.get('date')
    dj_id = data.get('dj_id')
    
    try:
        day_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Vérifier que la date n'est pas dans le passé
        if day_date < date.today():
            return jsonify({'success': False, 'error': 'Cannot assign past dates'})
        
        # Vérifier que le DJ est disponible
        availability = Availability.query.filter_by(
            user_id=dj_id,
            date=day_date,
            is_available=True
        ).first()
        
        if not availability:
            return jsonify({'success': False, 'error': 'DJ not available on this date'})
        
        # Vérifier qu'il n'y a pas déjà un assignment
        existing = Assignment.query.filter_by(date=day_date).first()
        if existing:
            return jsonify({'success': False, 'error': 'Date already assigned'})
        
        # Créer l'assignment
        assignment = Assignment(
            user_id=dj_id,
            date=day_date,
            created_by=current_user.id
        )
        
        db.session.add(assignment)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

# Route pour toggle status DJ
@app.route('/admin/toggle-dj-status', methods=['POST'])
@login_required
def admin_toggle_dj_status():
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    dj_id = data.get('dj_id')
    
    try:
        dj = User.query.get(dj_id)
        if not dj or dj.is_admin:
            return jsonify({'success': False, 'error': 'DJ not found'})
        
        dj.is_active = not dj.is_active
        db.session.commit()
        
        return jsonify({'success': True, 'new_status': dj.is_active})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

# Route pour supprimer un DJ
@app.route('/admin/delete-dj', methods=['POST'])
@login_required
def admin_delete_dj():
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    dj_id = data.get('dj_id')
    
    try:
        dj = User.query.get(dj_id)
        if not dj or dj.is_admin:
            return jsonify({'success': False, 'error': 'DJ not found'})
        
        # Cascade delete via relationship
        db.session.delete(dj)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

# Route pour les détails d'un jour (modal)
@app.route('/admin/day-details')
@login_required
def admin_day_details():
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    date_str = request.args.get('date')
    day_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    # Assignment existant
    assignment = Assignment.query.filter_by(date=day_date).first()
    
    # DJs disponibles
    availabilities = Availability.query.filter_by(
        date=day_date,
        is_available=True
    ).all()
    
    html = f'<h6 class="mb-3">Date : {day_date.strftime("%A %d %B %Y")}</h6>'
    
    if assignment:
        html += f'''
        <div class="alert alert-info">
            <strong><i class="fas fa-music me-2"></i>Assigné à :</strong> {assignment.user.dj_name}
            <button class="btn btn-sm btn-danger float-end" onclick="unassignDJ('{date_str}')">
                <i class="fas fa-times me-1"></i>Retirer
            </button>
        </div>
        '''
    else:
        if availabilities:
            html += '<h6>DJs Disponibles :</h6><div class="list-group mb-3">'
            for avail in availabilities:
                html += f'''
                <div class="list-group-item d-flex justify-content-between align-items-center">
                    <span><i class="fas fa-user me-2"></i>{avail.user.dj_name}</span>
                    <button class="btn btn-sm btn-primary" onclick="assignDJ('{date_str}', {avail.user.id})">
                        Assigner
                    </button>
                </div>
                '''
            html += '</div>'
        else:
            html += '<div class="alert alert-warning">Aucun DJ disponible ce jour</div>'
    
    return jsonify({
        'success': True,
        'date_formatted': day_date.strftime('%A %d %B %Y'),
        'html': html
    })

# Route pour retirer un assignment
@app.route('/admin/unassign-dj', methods=['POST'])
@login_required
def admin_unassign_dj():
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    date_str = data.get('date')
    
    try:
        day_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        assignment = Assignment.query.filter_by(date=day_date).first()
        if not assignment:
            return jsonify({'success': False, 'error': 'No assignment found'})
        
        db.session.delete(assignment)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3000)