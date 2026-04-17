from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config
from models import db, User, Availability, Assignment, calculate_tarif
from notifications import mail, send_assignment_notification, send_reminder_notification, send_admin_alert
from datetime import datetime, timedelta, date
import calendar as cal
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)
app.config.from_object(Config)

# Initialisation
db.init_app(app)
mail.init_app(app)  # ← AJOUTER CETTE LIGNE
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Connectez-vous pour accéder à cette page.'

if not app.debug:
    file_handler = RotatingFileHandler(
        '/var/log/folies-planning-auth.log',
        maxBytes=10240000,
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('LES FOLIES Planning startup')
    
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
                time_slot = availability.time_slot if availability else 'complete'
                
                status = 'past' if is_past else ('assigned' if is_assigned else ('available' if is_available else 'unavailable'))
                
                week_data.append({
                    'day': day,
                    'date': day_date.isoformat(),
                    'is_available': is_available,
                    'time_slot': time_slot,
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dj_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Votre compte est en attente d\'activation par l\'administrateur.', 'warning')
                app.logger.warning(f'Login attempt for inactive user: {username} from {request.remote_addr}')
                return redirect(url_for('login'))
            
            login_user(user, remember=True)
            app.logger.info(f'Successful login: {username} from {request.remote_addr}')
            
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                next_page = url_for('admin_dashboard') if user.is_admin else url_for('dj_dashboard')
            return redirect(next_page)
        
        # ⚠️ LOGGER L'ÉCHEC POUR FAIL2BAN
        app.logger.warning(f'Login failed for user: {request.remote_addr}')
        flash('Nom d\'utilisateur ou mot de passe incorrect', 'danger')
    
    return render_template('auth/login.html')
# Route inscription GET
@app.route('/register', methods=['GET'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('auth/register.html')

# Route inscription POST
@app.route('/register', methods=['POST'])
def do_register():
    dj_name = request.form.get('dj_name')
    username = request.form.get('username')
    email = request.form.get('email')
    phone = request.form.get('phone')
    password = request.form.get('password')
    password_confirm = request.form.get('password_confirm')
    
    # Validation
    if password != password_confirm:
        flash('Les mots de passe ne correspondent pas.', 'danger')
        return redirect(url_for('register'))
    
    if User.query.filter_by(username=username).first():
        flash('Ce nom d\'utilisateur existe déjà.', 'danger')
        return redirect(url_for('register'))
    
    if User.query.filter_by(email=email).first():
        flash('Cet email existe déjà.', 'danger')
        return redirect(url_for('register'))
    
    try:
        # Créer le compte INACTIF (en attente de validation)
        new_dj = User(
            username=username,
            email=email,
            dj_name=dj_name,
            phone=phone,
            is_admin=False,
            is_active=False
        )
        new_dj.set_password(password)
        
        db.session.add(new_dj)
        db.session.commit()
        
        flash('Inscription réussie ! Votre compte sera activé par l\'administrateur.', 'success')
        return redirect(url_for('login'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de l\'inscription: {str(e)}', 'danger')
        return redirect(url_for('register'))

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
    time_slot = data.get('time_slot', 'complete')  # Nouveau paramètre
    
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
            availability.time_slot = time_slot if is_available else None
            availability.updated_at = datetime.utcnow()
        else:
            availability = Availability(
                user_id=current_user.id,
                date=day_date,
                is_available=is_available,
                time_slot=time_slot if is_available else None
            )
            db.session.add(availability)
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

# Helper function pour le calendrier admin
def generate_admin_calendar(year, month):
        today = date.today()
        month_calendar = cal.monthcalendar(year, month)
        
        # Récupérer tous les assignments du mois
        assignments = Assignment.query.filter(
            db.extract('month', Assignment.date) == month,
            db.extract('year', Assignment.date) == year
        ).all()
        
        # Grouper les assignments par date
        assign_by_date = {}
        for a in assignments:
            if a.date not in assign_by_date:
                assign_by_date[a.date] = []
            assign_by_date[a.date].append(a)
        
        # Récupérer toutes les disponibilités du mois
        availabilities = Availability.query.filter(
            db.extract('month', Availability.date) == month,
            db.extract('year', Availability.date) == year,
            Availability.is_available == True
        ).all()
        
        # Grouper par date et créneau
        avail_by_date = {}
        for avail in availabilities:
            key = (avail.date, avail.time_slot)
            if key not in avail_by_date:
                avail_by_date[key] = []
            avail_by_date[key].append(avail)
        
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
                    
                    assignments_list = assign_by_date.get(day_date, [])
                    
                    # Compter les dispos par créneau
                    warmup_count = len(avail_by_date.get((day_date, 'warmup'), []))
                    peaktime_count = len(avail_by_date.get((day_date, 'peaktime'), []))
                    complete_count = len(avail_by_date.get((day_date, 'complete'), []))
                    peaktime_duo_count = len(avail_by_date.get((day_date, 'peaktime_duo'), []))

                    total_avail = warmup_count + peaktime_count + complete_count + peaktime_duo_count

                    # Déterminer le statut
                    if assignments_list:
                        status = 'assigned'
                    elif is_past:
                        status = 'past'
                    elif total_avail > 1:
                        status = 'multiple'
                    elif total_avail == 1:
                        status = 'single'
                    else:
                        status = 'none'

                    week_data.append({
                        'day': day,
                        'date': day_date.isoformat(),
                        'assignments': assignments_list,
                        'is_past': is_past,
                        'warmup_count': warmup_count,
                        'peaktime_count': peaktime_count,
                        'complete_count': complete_count,
                        'peaktime_duo_count': peaktime_duo_count,
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
        
        dj.assignments_count = Assignment.query.filter_by(user_id=dj.id).filter(  # ← ERREUR ICI
            Assignment.date >= today
        ).count()
    
    months = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
              'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
    
    # Demandes d'inscription en attente
    pending_djs = User.query.filter_by(is_admin=False, is_active=False).all()
    pending_count = len(pending_djs)
    
    return render_template('admin/dashboard.html',
                         stats=stats,
                         calendar_data=calendar_data,
                         conflicts_data=conflicts_data,
                         all_djs=all_djs,
                         pending_djs=pending_djs,
                         pending_count=pending_count,
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
        
        original_time_slot = availability.time_slot

        # Récupérer tous les assignments existants pour cette date
        existing_assignments = Assignment.query.filter_by(date=day_date).all()
        assigned_slots = {a.time_slot for a in existing_assignments}

        has_complete = 'complete' in assigned_slots
        has_warmup = 'warmup' in assigned_slots
        has_peaktime = 'peaktime' in assigned_slots
        has_peaktime_duo = 'peaktime_duo' in assigned_slots
        peaktime_duo_count = sum(1 for a in existing_assignments if a.time_slot == 'peaktime_duo')

        # Déterminer le créneau à assigner
        actual_time_slot = original_time_slot

        # Si déjà une soirée complète assignée → impossible
        if has_complete:
            return jsonify({'success': False, 'error': 'Complete night already assigned'})

        # Compter le total de DJs sur le créneau peak (solo + duo)
        total_peak_djs = peaktime_duo_count + (1 if has_peaktime else 0)

        # Peaktime duo : compatible avec peaktime solo existant
        if original_time_slot == 'peaktime_duo':
            if total_peak_djs >= 2:
                return jsonify({'success': False, 'error': 'Peak time déjà plein (2 DJs max)'})
            actual_time_slot = 'peaktime_duo'
        elif original_time_slot == 'peaktime':
            # Si un peaktime_duo existe, ce DJ rejoint en duo
            if has_peaktime_duo:
                if total_peak_djs >= 2:
                    return jsonify({'success': False, 'error': 'Peak time déjà plein (2 DJs max)'})
                actual_time_slot = 'peaktime_duo'
            elif has_peaktime:
                return jsonify({'success': False, 'error': 'Peak time already assigned'})
            else:
                actual_time_slot = 'peaktime'
        else:
            peak_occupied = has_peaktime or has_peaktime_duo

            # Si warmup déjà pris
            if has_warmup:
                if original_time_slot == 'warmup':
                    return jsonify({'success': False, 'error': 'Warmup already assigned'})
                elif original_time_slot == 'complete':
                    if peak_occupied:
                        return jsonify({'success': False, 'error': 'Soirée déjà complète'})
                    actual_time_slot = 'peaktime'

            # Si peak déjà pris
            elif peak_occupied:
                if original_time_slot == 'complete':
                    actual_time_slot = 'warmup'

            # Vérifier que le créneau final n'est pas déjà pris (sauf peaktime_duo)
            if actual_time_slot != 'peaktime_duo' and actual_time_slot in assigned_slots:
                return jsonify({'success': False, 'error': f'{actual_time_slot.capitalize()} already assigned'})
        
        # Créer l'assignment avec le créneau adapté
        assignment = Assignment(
            user_id=dj_id,
            date=day_date,
            time_slot=actual_time_slot,
            tarif=calculate_tarif(day_date, actual_time_slot),
            created_by=current_user.id
        )
        
        db.session.add(assignment)
        db.session.commit()
        
        # ✉️ ENVOI EMAIL DE CONFIRMATION
        # ✉️ ENVOI EMAIL DE CONFIRMATION
        if app.config.get('SEND_EMAIL_NOTIFICATIONS', False):
            try:
                dj = User.query.get(dj_id)
                send_assignment_notification(app, dj, assignment)
                print(f"✅ Email de confirmation envoyé à {dj.email}")
            except Exception as email_error:
                print(f"⚠️ Erreur envoi email à {dj.email}: {email_error}")
                import traceback
                traceback.print_exc()
        
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
# Route pour approuver un DJ
@app.route('/admin/approve-dj', methods=['POST'])
@login_required
def admin_approve_dj():
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    dj_id = data.get('dj_id')
    
    try:
        dj = User.query.get(dj_id)
        if not dj or dj.is_admin:
            return jsonify({'success': False, 'error': 'DJ not found'})
        
        dj.is_active = True
        db.session.commit()
        
        flash(f'DJ {dj.dj_name} approuvé avec succès !', 'success')
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

# Route pour refuser un DJ
@app.route('/admin/reject-dj', methods=['POST'])
@login_required
def admin_reject_dj():
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    dj_id = data.get('dj_id')
    
    try:
        dj = User.query.get(dj_id)
        if not dj or dj.is_admin:
            return jsonify({'success': False, 'error': 'DJ not found'})
        
        db.session.delete(dj)
        db.session.commit()
        
        flash(f'Demande de {dj.dj_name} refusée.', 'info')
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/day-details')
@login_required
def admin_day_details():
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    date_str = request.args.get('date')
    day_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    # Assignments existants
    assignments = Assignment.query.filter_by(date=day_date).all()

    # Déterminer quels créneaux sont encore disponibles
    assigned_slots = {a.time_slot for a in assignments}
    has_complete = 'complete' in assigned_slots
    has_warmup = 'warmup' in assigned_slots
    has_peaktime = 'peaktime' in assigned_slots
    has_peaktime_duo = 'peaktime_duo' in assigned_slots
    peaktime_duo_count = sum(1 for a in assignments if a.time_slot == 'peaktime_duo')

    # DJs disponibles
    availabilities = Availability.query.filter_by(
        date=day_date,
        is_available=True
    ).all()

    html = f'<h6 class="mb-3">Date : {day_date.strftime("%A %d %B %Y")}</h6>'

    slot_emoji = {'warmup': '🌅', 'peaktime': '🔥', 'complete': '🌙', 'peaktime_duo': '👥'}
    slot_name = {'warmup': 'Warm-up', 'peaktime': 'Peak time', 'complete': 'Complète', 'peaktime_duo': 'Peak à 2'}

    # Afficher les assignments existants
    if assignments:
        html += '<h6>Déjà assignés :</h6><div class="mb-3">'
        for assignment in assignments:
            html += f'''
            <div class="alert alert-info d-flex justify-content-between align-items-center mb-2">
                <strong>
                    {slot_emoji.get(assignment.time_slot, '')}
                    {assignment.user.dj_name} - {slot_name.get(assignment.time_slot, '')}
                    ({assignment.tarif}€)
                </strong>
                <button class="btn btn-sm btn-danger" onclick="unassignDJById({assignment.id})">
                    <i class="fas fa-times"></i> Retirer
                </button>
            </div>
            '''
        html += '</div>'

    # Si soirée complète déjà assignée, on ne peut plus rien faire
    if has_complete:
        html += '<div class="alert alert-warning">Soirée complète déjà assignée, aucune autre assignation possible.</div>'
        return jsonify({
            'success': True,
            'date_formatted': day_date.strftime('%A %d %B %Y'),
            'html': html
        })

    # Filtrer les DJs disponibles selon ce qui reste à assigner
    available_djs = []
    for avail in availabilities:
        # Vérifier si ce DJ est déjà assigné ce jour
        already_assigned = any(a.user_id == avail.user_id for a in assignments)
        if already_assigned:
            continue

        # Peaktime duo : peut rejoindre si pas encore 2 DJs sur le créneau 2h-6h
        # Compatible avec peaktime solo (le solo devient duo à 100€ chacun)
        if avail.time_slot == 'peaktime_duo':
            total_peak_slots = peaktime_duo_count + (1 if has_peaktime else 0)
            if total_peak_slots < 2 and not has_complete:
                avail.assignable_as = 'peaktime_duo'
                available_djs.append(avail)
            continue

        # Peaktime solo : compatible avec peaktime_duo existant (rejoint comme duo)
        if avail.time_slot == 'peaktime':
            if has_peaktime_duo:
                total_peak_slots = peaktime_duo_count
                if total_peak_slots < 2 and not has_complete:
                    avail.assignable_as = 'peaktime_duo'
                    available_djs.append(avail)
            elif not has_peaktime and not has_complete:
                available_djs.append(avail)
            continue

        # Si warmup ET créneau peak déjà pris
        peak_occupied = has_peaktime or has_peaktime_duo
        if has_warmup and peak_occupied:
            if avail.time_slot == 'complete':
                available_djs.append(avail)
        elif has_warmup:
            if avail.time_slot == 'complete':
                avail.assignable_as = 'peaktime'
                available_djs.append(avail)
        elif peak_occupied:
            if avail.time_slot == 'warmup':
                available_djs.append(avail)
            elif avail.time_slot == 'complete':
                avail.assignable_as = 'warmup'
                available_djs.append(avail)
        else:
            available_djs.append(avail)

    if available_djs:
        html += '<h6>DJs Disponibles :</h6><div class="list-group mb-3">'
        for avail in available_djs:
            display_slot = getattr(avail, 'assignable_as', avail.time_slot)
            display_name = slot_name.get(display_slot, display_slot)
            display_emoji = slot_emoji.get(display_slot, '')

            html += f'''
            <div class="list-group-item d-flex justify-content-between align-items-center">
                <span>
                    <i class="fas fa-user me-2"></i>{avail.user.dj_name}
                    <span class="badge bg-secondary ms-2">{display_emoji} {display_name}</span>
                </span>
                <button class="btn btn-sm btn-primary" onclick="assignDJ('{date_str}', {avail.user.id})">
                    Assigner
                </button>
            </div>
            '''
        html += '</div>'
    else:
        html += '<div class="alert alert-warning">Aucun DJ disponible pour les créneaux restants</div>'

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

# Route pour retirer un assignment par ID (supporte peaktime_duo)
@app.route('/admin/unassign-dj-by-id', methods=['POST'])
@login_required
def admin_unassign_dj_by_id():
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    data = request.get_json()
    assignment_id = data.get('assignment_id')

    try:
        assignment = Assignment.query.get(assignment_id)
        if not assignment:
            return jsonify({'success': False, 'error': 'No assignment found'})

        db.session.delete(assignment)
        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

# Route auto-assignation équitable
@app.route('/admin/auto-assign', methods=['POST'])
@login_required
def admin_auto_assign():
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    import random
    from calendar import monthrange

    data = request.get_json()
    year = data.get('year', datetime.now().year)
    month = data.get('month', datetime.now().month)

    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])
    today = date.today()

    # 1. Récupérer les dates futures non-assignées du mois
    existing_assignments = Assignment.query.filter(
        Assignment.date >= first_day,
        Assignment.date <= last_day
    ).all()

    # Dates déjà assignées (avec leurs slots occupés)
    assigned_by_date = {}
    for a in existing_assignments:
        assigned_by_date.setdefault(a.date, set()).add(a.time_slot)

    # Compter peaktime_duo par date
    duo_count_by_date = {}
    for a in existing_assignments:
        if a.time_slot == 'peaktime_duo':
            duo_count_by_date[a.date] = duo_count_by_date.get(a.date, 0) + 1

    # Compter les assignments existants par DJ ce mois
    dj_assignment_count = {}
    for a in existing_assignments:
        dj_assignment_count[a.user_id] = dj_assignment_count.get(a.user_id, 0) + 1

    # 2. Récupérer toutes les disponibilités du mois
    availabilities = Availability.query.filter(
        Availability.date >= first_day,
        Availability.date <= last_day,
        Availability.is_available == True
    ).all()

    # Organiser les dispos par date
    avail_by_date = {}
    for av in availabilities:
        avail_by_date.setdefault(av.date, []).append(av)

    # 3. Identifier les dates à remplir (futures, avec des dispos, pas complètement assignées)
    dates_to_fill = []
    current = max(first_day, today + timedelta(days=1))  # Que les dates futures
    while current <= last_day:
        assigned_slots = assigned_by_date.get(current, set())
        # Si 'complete' est déjà assigné, la date est pleine
        if 'complete' in assigned_slots:
            current += timedelta(days=1)
            continue
        # Si warmup ET peak plein (solo ou duo avec 2 DJs), la date est pleine
        total_peak = duo_count_by_date.get(current, 0) + (1 if 'peaktime' in assigned_slots else 0)
        peaktime_full = total_peak >= 2
        if 'warmup' in assigned_slots and peaktime_full:
            current += timedelta(days=1)
            continue
        # S'il y a des DJs disponibles
        if current in avail_by_date:
            dates_to_fill.append(current)
        current += timedelta(days=1)

    # 4. Trier par contrainte (dates avec le moins de DJs disponibles en premier)
    dates_to_fill.sort(key=lambda d: len(avail_by_date.get(d, [])))

    # 5. Algorithme greedy d'assignation
    suggestions = []
    sim_assigned = {d: set(slots) for d, slots in assigned_by_date.items()}
    sim_counts = dict(dj_assignment_count)
    sim_dj_by_date = {}
    sim_duo_count = dict(duo_count_by_date)
    for a in existing_assignments:
        sim_dj_by_date.setdefault(a.date, set()).add(a.user_id)

    for d in dates_to_fill:
        assigned_slots = sim_assigned.get(d, set())
        assigned_djs = sim_dj_by_date.get(d, set())
        cur_duo_count = sim_duo_count.get(d, 0)

        # Filtrer les DJs disponibles et non déjà assignés ce jour
        candidates = []
        has_peak_solo = 'peaktime' in assigned_slots
        has_peak_duo = 'peaktime_duo' in assigned_slots
        total_peak_djs = cur_duo_count + (1 if has_peak_solo else 0)
        peak_occupied = has_peak_solo or has_peak_duo

        for av in avail_by_date.get(d, []):
            if av.user_id in assigned_djs:
                continue
            slot = av.time_slot
            if 'complete' in assigned_slots:
                continue
            if slot == 'peaktime_duo':
                if total_peak_djs < 2:
                    candidates.append(av)
                continue
            if slot == 'peaktime':
                # Peaktime solo compatible avec duo existant (rejoint en duo)
                if has_peak_duo and total_peak_djs < 2:
                    candidates.append(av)
                elif not peak_occupied:
                    candidates.append(av)
                continue
            if slot == 'warmup' and 'warmup' in assigned_slots:
                continue
            if slot == 'complete' and 'warmup' in assigned_slots and peak_occupied:
                continue
            candidates.append(av)

        if not candidates:
            continue

        random.shuffle(candidates)
        candidates.sort(key=lambda av: sim_counts.get(av.user_id, 0))

        best = candidates[0]

        actual_slot = best.time_slot
        # Peaktime solo rejoint un duo existant → devient duo
        if best.time_slot == 'peaktime' and has_peak_duo:
            actual_slot = 'peaktime_duo'
        elif best.time_slot == 'complete':
            if 'warmup' in assigned_slots:
                actual_slot = 'peaktime'
            elif peak_occupied:
                actual_slot = 'warmup'

        tarif = calculate_tarif(d, actual_slot)

        # Build alternatives list for this date
        alternatives = []
        for c in candidates:
            c_slot = c.time_slot
            if c.time_slot == 'peaktime' and has_peak_duo:
                c_slot = 'peaktime_duo'
            elif c.time_slot == 'complete':
                if 'warmup' in assigned_slots:
                    c_slot = 'peaktime'
                elif peak_occupied:
                    c_slot = 'warmup'
            c_tarif = calculate_tarif(d, c_slot)
            alternatives.append({
                'dj_id': c.user_id,
                'dj_name': c.user.dj_name,
                'tarif': c_tarif,
                'count': sim_counts.get(c.user_id, 0)
            })

        suggestions.append({
            'date': d.strftime('%Y-%m-%d'),
            'date_formatted': d.strftime('%A %d/%m'),
            'dj_id': best.user_id,
            'dj_name': best.user.dj_name,
            'time_slot': actual_slot,
            'original_slot': best.time_slot,
            'tarif': tarif,
            'alternatives': alternatives
        })

        sim_counts[best.user_id] = sim_counts.get(best.user_id, 0) + 1
        sim_assigned.setdefault(d, set()).add(actual_slot)
        sim_dj_by_date.setdefault(d, set()).add(best.user_id)
        if actual_slot == 'peaktime_duo':
            sim_duo_count[d] = sim_duo_count.get(d, 0) + 1

    # 6. Calculer le résumé par DJ
    dj_summary = {}
    for s in suggestions:
        dj_id = s['dj_id']
        if dj_id not in dj_summary:
            dj_summary[dj_id] = {
                'dj_name': s['dj_name'],
                'existing': dj_assignment_count.get(dj_id, 0),
                'suggested': 0,
                'total_tarif': 0
            }
        dj_summary[dj_id]['suggested'] += 1
        dj_summary[dj_id]['total_tarif'] += s['tarif']

    return jsonify({
        'success': True,
        'suggestions': suggestions,
        'dj_summary': list(dj_summary.values()),
        'total_dates': len(dates_to_fill),
        'filled_dates': len(suggestions)
    })


# Route validation bulk des suggestions
@app.route('/admin/bulk-assign', methods=['POST'])
@login_required
def admin_bulk_assign():
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    data = request.get_json()
    assignments_data = data.get('assignments', [])

    created = 0
    errors = []

    for item in assignments_data:
        try:
            day_date = datetime.strptime(item['date'], '%Y-%m-%d').date()
            dj_id = item['dj_id']
            time_slot = item['time_slot']

            # Vérifier que le DJ a bien une dispo
            avail = Availability.query.filter_by(
                user_id=dj_id,
                date=day_date,
                is_available=True
            ).first()
            if not avail:
                errors.append(f"{item['date']}: DJ non disponible")
                continue

            # Vérifier pas de conflit de slot
            existing = Assignment.query.filter_by(
                date=day_date,
                time_slot=time_slot
            ).all()
            if time_slot == 'peaktime_duo':
                if len(existing) >= 2:
                    errors.append(f"{item['date']}: Slot peaktime_duo déjà plein")
                    continue
            elif existing:
                errors.append(f"{item['date']}: Slot {time_slot} déjà pris")
                continue

            # Vérifier que le DJ n'est pas déjà assigné ce jour
            dj_existing = Assignment.query.filter_by(
                date=day_date,
                user_id=dj_id
            ).first()
            if dj_existing:
                errors.append(f"{item['date']}: DJ déjà assigné")
                continue

            tarif = calculate_tarif(day_date, time_slot)
            assignment = Assignment(
                user_id=dj_id,
                date=day_date,
                time_slot=time_slot,
                tarif=tarif,
                created_by=current_user.id
            )
            db.session.add(assignment)
            created += 1

        except Exception as e:
            errors.append(f"{item.get('date', '?')}: {str(e)}")

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'Erreur DB: {str(e)}'})

    return jsonify({
        'success': True,
        'created': created,
        'errors': errors
    })


# Route calendrier DJ individuel (admin)
@app.route('/admin/dj-calendar/<int:dj_id>')
@login_required
def admin_dj_calendar(dj_id):
    if not current_user.is_admin:
        flash('Accès refusé.', 'danger')
        return redirect(url_for('dj_dashboard'))
    
    dj = User.query.get_or_404(dj_id)
    if dj.is_admin:
        flash('Impossible d\'afficher le calendrier d\'un admin.', 'warning')
        return redirect(url_for('admin_dashboard'))
    
    # Paramètres de date
    month = request.args.get('month', type=int, default=datetime.now().month)
    year = request.args.get('year', type=int, default=datetime.now().year)
    
    today = date.today()
    first_day = date(year, month, 1)
    last_day = date(year, month, cal.monthrange(year, month)[1])
    
    # Stats du DJ
    disponibilites_mois = Availability.query.filter_by(
        user_id=dj_id,
        is_available=True
    ).filter(
        Availability.date >= first_day,
        Availability.date <= last_day
    ).count()
    
    sets_venir = Assignment.query.filter_by(user_id=dj_id).filter(
        Assignment.date >= today
    ).count()
    
    sets_passes = Assignment.query.filter_by(user_id=dj_id).filter(
        Assignment.date < today
    ).count()
    
    # Taux de disponibilité (sur les 30 derniers jours)
    thirty_days_ago = today - timedelta(days=30)
    total_days = 30
    days_available = Availability.query.filter_by(
        user_id=dj_id,
        is_available=True
    ).filter(
        Availability.date >= thirty_days_ago,
        Availability.date < today
    ).count()
    
    taux_dispo = int((days_available / total_days) * 100) if total_days > 0 else 0
    
    stats = {
        'disponibilites_mois': disponibilites_mois,
        'sets_venir': sets_venir,
        'sets_passes': sets_passes,
        'taux_dispo': taux_dispo
    }
    
    # Calendrier
    calendar_data = generate_calendar(year, month, dj_id)
    
    # Prochains sets
    upcoming_sets = Assignment.query.filter_by(user_id=dj_id).filter(
        Assignment.date >= today
    ).order_by(Assignment.date).limit(5).all()
    
    # Sets passés
    past_sets = Assignment.query.filter_by(user_id=dj_id).filter(
        Assignment.date < today
    ).order_by(Assignment.date.desc()).limit(5).all()
    
    months = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
              'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
    
    return render_template('admin/dj_calendar.html',
                         dj=dj,
                         stats=stats,
                         calendar_data=calendar_data,
                         upcoming_sets=upcoming_sets,
                         past_sets=past_sets,
                         current_month=month,
                         current_year=year,
                         months=months,
                         today=today)

def generate_planning_pdf(year, month):
    """Générer un PDF du planning mensuel"""
    buffer = BytesIO()
    
    # Créer le document PDF en paysage
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#6366f1'),
        spaceAfter=30,
        alignment=1  # Centré
    )
    
    # Titre
    months_fr = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
    title = Paragraph(f"🎵 LES FOLIES - Planning {months_fr[month-1]} {year}", title_style)
    elements.append(title)
    elements.append(Spacer(1, 1*cm))
    
    # Récupérer les assignments du mois
    first_day = date(year, month, 1)
    last_day = date(year, month, cal.monthrange(year, month)[1])
    
    assignments = Assignment.query.filter(
        Assignment.date >= first_day,
        Assignment.date <= last_day
    ).order_by(Assignment.date).all()
    
    # Créer le tableau
    data = [['Date', 'Jour', 'DJ', 'Notes']]
    
    for assignment in assignments:
        date_str = assignment.date.strftime('%d/%m/%Y')
        jour = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'][assignment.date.weekday()]
        dj_name = assignment.user.dj_name
        notes = assignment.notes or '-'
        
        data.append([date_str, jour, dj_name, notes])
    
    if len(data) == 1:
        data.append(['Aucun set assigné', '', '', ''])
    
    # Style du tableau
    table = Table(data, colWidths=[3*cm, 3*cm, 5*cm, 8*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6366f1')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 1*cm))
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=1
    )
    footer = Paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')} - © 2026 LES FOLIES", footer_style)
    elements.append(footer)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    return buffer

# Route pour export PDF du planning
@app.route('/admin/export-planning-pdf')
@login_required
def admin_export_planning_pdf():
    if not current_user.is_admin:
        flash('Accès refusé.', 'danger')
        return redirect(url_for('dj_dashboard'))
    
    month = request.args.get('month', type=int, default=datetime.now().month)
    year = request.args.get('year', type=int, default=datetime.now().year)
    
    try:
        pdf_buffer = generate_planning_pdf(year, month)
        
        months_fr = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                     'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        filename = f"Planning_LES_FOLIES_{months_fr[month-1]}_{year}.pdf"
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'Erreur lors de la génération du PDF: {str(e)}', 'danger')
        return redirect(url_for('admin_dashboard'))
@app.route('/planning-mensuel')
@login_required
def planning_mensuel():
    """Planning mensuel en lecture seule pour les DJs"""
    from datetime import datetime, date as date_obj
    from calendar import monthrange

    # Récupérer le mois demandé (ou mois actuel)
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)

    # Calculer les dates du mois (utiliser date, pas datetime, pour matcher le type db.Date)
    first_day = date_obj(year, month, 1)
    last_day_num = monthrange(year, month)[1]
    last_day = date_obj(year, month, last_day_num)
    
    # Récupérer UNIQUEMENT les assignments (pas les disponibilités)
    assignments = Assignment.query.filter(
        Assignment.date >= first_day,
        Assignment.date <= last_day
    ).order_by(Assignment.date, Assignment.time_slot).all()
    
    # Organiser par date
    planning_by_date = {}
    current_date = first_day
    while current_date <= last_day:
        date_str = current_date.strftime('%Y-%m-%d')
        day_assignments = [a for a in assignments if a.date == current_date]
        planning_by_date[date_str] = {
            'date': current_date,
            'assignments': day_assignments,
            'day_name': current_date.strftime('%A'),
            'is_weekend': current_date.weekday() in [3, 4, 5]  # Jeu/Ven/Sam
        }
        current_date = current_date + timedelta(days=1)

    # Organiser par semaines (lundi = début de semaine)
    weeks = []
    current_date = first_day
    # Remplir les jours vides avant le 1er du mois
    first_weekday = first_day.weekday()  # 0=lundi
    current_week = [None] * first_weekday

    while current_date <= last_day:
        date_str = current_date.strftime('%Y-%m-%d')
        current_week.append(planning_by_date[date_str])
        if len(current_week) == 7:
            weeks.append(current_week)
            current_week = []
        current_date = current_date + timedelta(days=1)

    # Remplir les jours vides après la fin du mois
    if current_week:
        while len(current_week) < 7:
            current_week.append(None)
        weeks.append(current_week)

    # Mois suivant/précédent
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    return render_template('planning_mensuel.html',
                         planning_by_date=planning_by_date,
                         weeks=weeks,
                         current_month=datetime(year, month, 1),
                         prev_month=prev_month,
                         prev_year=prev_year,
                         next_month=next_month,
                         next_year=next_year)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
