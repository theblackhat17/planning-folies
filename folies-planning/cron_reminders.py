#!/usr/bin/env python3
"""
Script cron pour envoyer les rappels automatiques
À exécuter quotidiennement via crontab
"""

from app import app, db
from models import Assignment, User, Availability
from notifications import send_reminder_notification, send_admin_alert
from datetime import date, timedelta
from config import Config

def send_reminders():
    """Envoyer les rappels aux DJs (uniquement Jeudi, Vendredi, Samedi)"""
    with app.app_context():
        today = date.today()
        reminder_date_7 = today + timedelta(days=Config.NOTIFICATION_REMINDER_DAYS)
        reminder_date_1 = today + timedelta(days=1)
        
        print(f"📅 Aujourd'hui: {today}")
        print(f"🔔 Rappels 7j pour: {reminder_date_7}")
        print(f"⏰ Rappels 24h pour: {reminder_date_1}")
        print("-" * 50)
        
        # Rappels 7 jours avant (seulement Jeudi=3, Vendredi=4, Samedi=5)
        assignments_7days = Assignment.query.filter_by(date=reminder_date_7).all()
        for assignment in assignments_7days:
            # Vérifier que c'est Jeudi, Vendredi ou Samedi
            day_of_week = assignment.date.weekday()  # 0=Lundi, 3=Jeudi, 4=Vendredi, 5=Samedi
            if day_of_week not in [3, 4, 5]:
                print(f"⏭️ Skip {assignment.user.dj_name} - {assignment.date} n'est pas Jeu/Ven/Sam")
                continue
            
            try:
                send_reminder_notification(
                    app,
                    assignment.user,
                    assignment,
                    Config.NOTIFICATION_REMINDER_DAYS
                )
                print(f"✅ Rappel 7j envoyé à {assignment.user.dj_name} ({assignment.user.email}) pour {assignment.date.strftime('%A %d/%m')}")
            except Exception as e:
                print(f"❌ Erreur rappel 7j pour {assignment.user.dj_name}: {e}")
        
        # Rappels 24h avant (seulement Jeudi, Vendredi, Samedi)
        assignments_1day = Assignment.query.filter_by(date=reminder_date_1).all()
        for assignment in assignments_1day:
            # Vérifier que c'est Jeudi, Vendredi ou Samedi
            day_of_week = assignment.date.weekday()
            if day_of_week not in [3, 4, 5]:
                print(f"⏭️ Skip {assignment.user.dj_name} - {assignment.date} n'est pas Jeu/Ven/Sam")
                continue
            
            try:
                send_reminder_notification(
                    app,
                    assignment.user,
                    assignment,
                    1
                )
                print(f"✅ Rappel 24h envoyé à {assignment.user.dj_name} ({assignment.user.email}) pour {assignment.date.strftime('%A %d/%m')}")
            except Exception as e:
                print(f"❌ Erreur rappel 24h pour {assignment.user.dj_name}: {e}")
        
        # Compter les rappels envoyés (seulement ceux des bons jours)
        rappels_7j_sent = sum(1 for a in assignments_7days if a.date.weekday() in [3, 4, 5])
        rappels_24h_sent = sum(1 for a in assignments_1day if a.date.weekday() in [3, 4, 5])
        
        print(f"🎉 Rappels terminés : {rappels_7j_sent} rappels 7j, {rappels_24h_sent} rappels 24h")

def check_availability_alerts():
    """Alerter l'admin pour dates sans DJ (uniquement Jeudi, Vendredi, Samedi)"""
    with app.app_context():
        today = date.today()
        check_until = today + timedelta(days=14)  # Vérifier les 2 prochaines semaines
        
        print(f"🔍 Vérification disponibilités jusqu'au {check_until}")
        print("-" * 50)
        
        current_date = today
        alerts_sent = 0
        
        while current_date <= check_until:
            # Vérifier uniquement Jeudi (3), Vendredi (4), Samedi (5)
            day_of_week = current_date.weekday()
            if day_of_week not in [3, 4, 5]:
                current_date += timedelta(days=1)
                continue
            
            # Vérifier si déjà assigné
            assignments = Assignment.query.filter_by(date=current_date).all()
            assigned_slots = {a.time_slot for a in assignments}
            
            # Si soirée complète assignée, pas besoin d'alerte
            if 'complete' in assigned_slots:
                current_date += timedelta(days=1)
                continue
            
            # Si warmup ET peaktime assignés, pas besoin d'alerte
            if 'warmup' in assigned_slots and 'peaktime' in assigned_slots:
                current_date += timedelta(days=1)
                continue
            
            # Compter les DJs disponibles
            availabilities = Availability.query.filter_by(
                date=current_date,
                is_available=True
            ).all()
            
            warmup_count = sum(1 for a in availabilities if a.time_slot in ['warmup', 'complete'])
            peaktime_count = sum(1 for a in availabilities if a.time_slot in ['peaktime', 'complete'])
            
            # Alerte si manque de DJs
            needs_warmup = 'warmup' not in assigned_slots and warmup_count == 0
            needs_peaktime = 'peaktime' not in assigned_slots and peaktime_count == 0
            
            if needs_warmup or needs_peaktime:
                try:
                    send_admin_alert(
                        app,
                        Config.ADMIN_EMAIL,
                        current_date,
                        len(availabilities)
                    )
                    alerts_sent += 1
                    print(f"⚠️ Alerte envoyée pour {current_date.strftime('%A %d/%m')} (warmup: {warmup_count}, peak: {peaktime_count})")
                except Exception as e:
                    print(f"❌ Erreur alerte admin pour {current_date}: {e}")
            
            current_date += timedelta(days=1)
        
        print(f"🔔 Alertes admin terminées : {alerts_sent} alertes envoyées")

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 CRON LES FOLIES PLANNING - Démarrage")
    print(f"⏰ Exécution: {date.today()}")
    print("=" * 50)
    
    send_reminders()
    print()
    check_availability_alerts()
    
    print("=" * 50)
    print("✅ Tâches terminées")
    print("=" * 50)
