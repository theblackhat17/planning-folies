from flask_mail import Mail, Message
from flask import render_template_string
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
            body {{ font-family: 'Poppins', Arial, sans-serif; background: #f8fafc; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; padding: 30px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 28px; }}
            .content {{ padding: 30px; }}
            .date-box {{ background: #f0f4ff; border-left: 4px solid #6366f1; padding: 15px; margin: 20px 0; border-radius: 8px; }}
            .date-box h2 {{ margin: 0 0 10px 0; color: #6366f1; font-size: 24px; }}
            .footer {{ background: #1e293b; color: #94a3b8; padding: 20px; text-align: center; font-size: 12px; }}
            .btn {{ display: inline-block; background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; padding: 12px 30px; text-decoration: none; border-radius: 8px; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎵 LES FOLIES</h1>
                <p>Nouveau Set Assigné</p>
            </div>
            <div class="content">
                <p>Bonjour <strong>{dj_name}</strong>,</p>
                <p>Vous avez été assigné pour mixer à LES FOLIES !</p>
                
                <div class="date-box">
                    <h2>📅 {date_str}</h2>
                    {f'<p><em>{notes}</em></p>' if notes else ''}
                </div>
                
                <p>Connectez-vous à votre espace pour voir tous vos sets à venir :</p>
                <a href="https://planning.tbhone.uk/login" class="btn">Accéder au Planning</a>
                
                <p style="margin-top: 30px; color: #64748b; font-size: 14px;">
                    Préparez vos meilleures tracks ! 🔥
                </p>
            </div>
            <div class="footer">
                &copy; 2026 LES FOLIES - Planning DJ<br>
                Cet email a été envoyé automatiquement, merci de ne pas répondre.
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
            body {{ font-family: 'Poppins', Arial, sans-serif; background: #f8fafc; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #f59e0b, #ef4444); color: white; padding: 30px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 28px; }}
            .content {{ padding: 30px; }}
            .reminder-box {{ background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0; border-radius: 8px; }}
            .footer {{ background: #1e293b; color: #94a3b8; padding: 20px; text-align: center; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>⏰ RAPPEL</h1>
                <p>Votre set approche !</p>
            </div>
            <div class="content">
                <p>Bonjour <strong>{dj_name}</strong>,</p>
                
                <div class="reminder-box">
                    <h2>🎧 Set dans {days_left} jours</h2>
                    <p><strong>Date :</strong> {date_str}</p>
                </div>
                
                <p>N'oubliez pas de préparer votre set pour LES FOLIES ! 🔥</p>
                <p style="color: #64748b; font-size: 14px;">
                    En cas d'empêchement, merci de prévenir au plus vite.
                </p>
            </div>
            <div class="footer">
                &copy; 2026 LES FOLIES - Planning DJ
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
            body {{ font-family: 'Poppins', Arial, sans-serif; background: #f8fafc; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #ef4444, #dc2626); color: white; padding: 30px; text-align: center; }}
            .content {{ padding: 30px; }}
            .alert-box {{ background: #fee2e2; border-left: 4px solid #ef4444; padding: 15px; margin: 20px 0; border-radius: 8px; }}
            .footer {{ background: #1e293b; color: #94a3b8; padding: 20px; text-align: center; font-size: 12px; }}
            .btn {{ display: inline-block; background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; padding: 12px 30px; text-decoration: none; border-radius: 8px; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>⚠️ ALERTE PLANNING</h1>
            </div>
            <div class="content">
                <p>Bonjour Admin,</p>
                
                <div class="alert-box">
                    <h2>Aucun DJ disponible</h2>
                    <p><strong>Date :</strong> {date_str}</p>
                    <p><strong>DJs disponibles :</strong> {available_count}</p>
                </div>
                
                <p>Cette date n'a aucun DJ disponible. Veuillez contacter les DJs pour trouver une solution.</p>
                
                <a href="https://planning.tbhone.uk/admin/dashboard" class="btn">Voir le Planning</a>
            </div>
            <div class="footer">
                &copy; 2026 LES FOLIES - Planning DJ
            </div>
        </div>
    </body>
    </html>
    """

def send_assignment_notification(app, dj, assignment):
    """Envoyer notification d'assignation à un DJ"""
    date_str = assignment.date.strftime('%A %d %B %Y')
    subject = f"🎵 Nouveau Set - {date_str}"
    
    html = get_assignment_email_template(
        dj_name=dj.dj_name,
        date_str=date_str,
        notes=assignment.notes
    )
    
    send_email(app, subject, dj.email, html)

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