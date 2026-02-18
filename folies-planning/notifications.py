from flask_mail import Mail, Message
from flask import render_template_string, render_template
from datetime import datetime, timedelta, date
from threading import Thread

mail = Mail()

def send_async_email(app, msg):
    """Envoyer email en arrière-plan"""
    with app.app_context():
        try:
            mail.send(msg)
            print(f"✅ Email envoyé: {msg.subject}")
        except Exception as e:
            print(f"❌ Erreur envoi email: {str(e)}")

def send_email(app, subject, recipient, html_body):
    """Fonction générique pour envoyer un email"""
    from config import Config
    
    if not Config.SEND_EMAIL_NOTIFICATIONS:
        print(f"📧 Email désactivé: {subject} -> {recipient}")
        return
    
    msg = Message(
        subject=subject,
        recipients=[recipient],
        html=html_body
    )
    
    Thread(target=send_async_email, args=(app, msg)).start()

# Templates Email
def get_assignment_email_template(dj_name, date_str, notes=None):
    """Template email pour assignation"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background: #06060c; padding: 20px; color: #eeeef0; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #0a0a14, #1a1a2e); padding: 40px 30px; text-align: center; border-bottom: 2px solid #c8ff00; }}
            .header h1 {{ margin: 0; font-size: 28px; color: #c8ff00; letter-spacing: 0.1em; font-weight: 800; }}
            .header p {{ color: #8888a0; margin: 8px 0 0; font-size: 14px; }}
            .content {{ background: #111120; padding: 30px; }}
            .date-box {{ background: #1a1a2e; border-left: 3px solid #c8ff00; padding: 15px; margin: 20px 0; border-radius: 0 8px 8px 0; }}
            .date-box h2 {{ margin: 0 0 10px 0; color: #c8ff00; font-size: 22px; }}
            .footer {{ background: #06060c; color: #555566; padding: 20px; text-align: center; font-size: 11px; border-top: 1px solid rgba(255,255,255,0.06); }}
            .btn {{ display: inline-block; background: #c8ff00; color: #0a0a14; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 700; margin: 10px 0; }}
            p {{ color: #eeeef0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>LES FOLIES</h1>
                <p>Nouvelle assignation</p>
            </div>
            <div class="content">
                <p>Salut <strong style="color: #c8ff00;">{dj_name}</strong>,</p>
                <p>Tu as ete assigne pour un set a LES FOLIES !</p>

                <div class="date-box">
                    <h2>{date_str}</h2>
                    {f'<p style="color: #8888a0; font-style: italic;">{notes}</p>' if notes else ''}
                </div>

                <p>Check ton dashboard :</p>
                <a href="https://planning.tbhone.uk/login" class="btn">Acceder au Planning</a>

                <p style="margin-top: 30px; color: #8888a0; font-size: 14px;">
                    Prepare tes meilleures tracks !
                </p>
            </div>
            <div class="footer">
                &copy; 2026 LES FOLIES &mdash; Planning DJ
            </div>
        </div>
    </body>
    </html>
    """

def get_reminder_email_template(dj_name, date_str, days_left):
    """Template email pour rappel"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background: #06060c; padding: 20px; color: #eeeef0; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #0a0a14, #1a1a2e); padding: 40px 30px; text-align: center; border-bottom: 2px solid #ffab00; }}
            .header h1 {{ margin: 0; font-size: 28px; color: #ffab00; letter-spacing: 0.1em; font-weight: 800; }}
            .header p {{ color: #8888a0; margin: 8px 0 0; font-size: 14px; }}
            .content {{ background: #111120; padding: 30px; }}
            .reminder-box {{ background: rgba(255, 171, 0, 0.1); border-left: 3px solid #ffab00; padding: 15px; margin: 20px 0; border-radius: 0 8px 8px 0; }}
            .reminder-box h2 {{ color: #ffab00; margin: 0 0 8px; font-size: 20px; }}
            .footer {{ background: #06060c; color: #555566; padding: 20px; text-align: center; font-size: 11px; border-top: 1px solid rgba(255,255,255,0.06); }}
            p {{ color: #eeeef0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>LES FOLIES</h1>
                <p>Rappel &mdash; Ton set approche</p>
            </div>
            <div class="content">
                <p>Salut <strong style="color: #c8ff00;">{dj_name}</strong>,</p>

                <div class="reminder-box">
                    <h2>Set dans {days_left} jours</h2>
                    <p><strong style="color: #8888a0;">Date :</strong> {date_str}</p>
                </div>

                <p>Prepare tes tracks pour LES FOLIES !</p>
                <p style="color: #8888a0; font-size: 14px;">
                    En cas d'empechement, previens au plus vite.
                </p>
            </div>
            <div class="footer">
                &copy; 2026 LES FOLIES &mdash; Planning DJ
            </div>
        </div>
    </body>
    </html>
    """

def get_admin_alert_email_template(date_str, available_count):
    """Template email pour alerte admin"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background: #06060c; padding: 20px; color: #eeeef0; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #0a0a14, #1a1a2e); padding: 40px 30px; text-align: center; border-bottom: 2px solid #ff1744; }}
            .header h1 {{ margin: 0; font-size: 28px; color: #ff1744; letter-spacing: 0.1em; font-weight: 800; }}
            .content {{ background: #111120; padding: 30px; }}
            .alert-box {{ background: rgba(255, 23, 68, 0.1); border-left: 3px solid #ff1744; padding: 15px; margin: 20px 0; border-radius: 0 8px 8px 0; }}
            .alert-box h2 {{ color: #ff1744; margin: 0 0 12px; font-size: 20px; }}
            .footer {{ background: #06060c; color: #555566; padding: 20px; text-align: center; font-size: 11px; border-top: 1px solid rgba(255,255,255,0.06); }}
            .btn {{ display: inline-block; background: #ff1744; color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 700; margin: 10px 0; }}
            p {{ color: #eeeef0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>ALERTE PLANNING</h1>
            </div>
            <div class="content">
                <p>Admin,</p>

                <div class="alert-box">
                    <h2>Aucun DJ disponible</h2>
                    <p><strong style="color: #8888a0;">Date :</strong> {date_str}</p>
                    <p><strong style="color: #8888a0;">DJs disponibles :</strong> {available_count}</p>
                </div>

                <p>Cette date n'a aucun DJ dispo. Contacte l'equipe.</p>

                <a href="https://planning.tbhone.uk/admin/dashboard" class="btn">Voir le Planning</a>
            </div>
            <div class="footer">
                &copy; 2026 LES FOLIES &mdash; Planning DJ
            </div>
        </div>
    </body>
    </html>
    """

def send_assignment_notification(app, dj, assignment):
    """Envoyer notification d'assignation au DJ"""
    if not app.config.get('SEND_EMAIL_NOTIFICATIONS'):
        return
    
    with app.app_context():
        try:
            msg = Message(
                subject=f"🎵 Nouveau set à LES FOLIES - {assignment.date.strftime('%d/%m/%Y')}",
                recipients=[dj.email],  # ← EMAIL DU DJ
                html=render_template('email/assignment_notification.html', 
                                    dj=dj, 
                                    assignment=assignment)
            )
            
            thread = Thread(target=send_async_email, args=(app, msg))
            thread.start()
            
        except Exception as e:
            print(f"Erreur envoi email assignment: {e}")

def send_reminder_notification(app, dj, assignment, days_left):
    """Envoyer rappel à un DJ"""
    date_str = assignment.date.strftime('%A %d %B %Y')
    subject = f"⏰ Rappel: Set dans {days_left} jours"
    
    html = get_reminder_email_template(
        dj_name=dj.dj_name,
        date_str=date_str,
        days_left=days_left
    )
    
    send_email(app, subject, dj.email, html)

def send_admin_alert(app, admin_email, date_obj, available_count):
    """Envoyer alerte à l'admin"""
    date_str = date_obj.strftime('%A %d %B %Y')
    subject = f"⚠️ Alerte: Aucun DJ dispo - {date_str}"
    
    html = get_admin_alert_email_template(date_str, available_count)
    
    send_email(app, subject, admin_email, html)

def check_and_send_reminders(app):
    """Vérifier et envoyer les rappels (à appeler quotidiennement)"""
    from models import Assignment, User
    from config import Config
    
    with app.app_context():
        today = date.today()
        reminder_date = today + timedelta(days=Config.NOTIFICATION_REMINDER_DAYS)
        
        # Trouver les assignments dans X jours
        assignments = Assignment.query.filter_by(date=reminder_date).all()
        
        for assignment in assignments:
            dj = User.query.get(assignment.user_id)
            if dj and dj.is_active:
                send_reminder_notification(app, dj, assignment, Config.NOTIFICATION_REMINDER_DAYS)
                print(f"📧 Rappel envoyé à {dj.dj_name} pour le {reminder_date}")

def check_availability_alerts(app):
    """Vérifier les dates sans DJ et alerter l'admin (à appeler quotidiennement)"""
    from models import Availability, Assignment, User
    from datetime import timedelta
    
    with app.app_context():
        today = date.today()
        next_week = today + timedelta(days=7)
        
        # Dates de la semaine prochaine
        dates_to_check = [today + timedelta(days=i) for i in range(1, 8)]
        
        admin = User.query.filter_by(is_admin=True).first()
        if not admin:
            return
        
        for check_date in dates_to_check:
            # Vérifier si déjà assigné
            assignment = Assignment.query.filter_by(date=check_date).first()
            if assignment:
                continue
            
            # Compter les dispos
            available_count = Availability.query.filter_by(
                date=check_date,
                is_available=True
            ).count()
            
            if available_count == 0:
                send_admin_alert(app, admin.email, check_date, available_count)
                print(f"⚠️ Alerte admin: Aucun DJ dispo le {check_date}")
