from app import app, db
from models import Availability, Assignment, calculate_tarif

with app.app_context():
    # Ajouter les colonnes manquantes
    try:
        db.session.execute(db.text('ALTER TABLE availabilities ADD COLUMN time_slot VARCHAR(20) DEFAULT "complete"'))
        print("✅ Colonne time_slot ajoutée à availabilities")
    except Exception as e:
        print(f"⚠️ Colonne time_slot existe déjà dans availabilities: {e}")
    
    try:
        db.session.execute(db.text('ALTER TABLE assignments ADD COLUMN time_slot VARCHAR(20) DEFAULT "complete"'))
        print("✅ Colonne time_slot ajoutée à assignments")
    except Exception as e:
        print(f"⚠️ Colonne time_slot existe déjà dans assignments: {e}")
    
    try:
        db.session.execute(db.text('ALTER TABLE assignments ADD COLUMN tarif INTEGER DEFAULT 0'))
        print("✅ Colonne tarif ajoutée à assignments")
    except Exception as e:
        print(f"⚠️ Colonne tarif existe déjà dans assignments: {e}")
    
    db.session.commit()
    
    # Mettre à jour les tarifs existants
    assignments = Assignment.query.all()
    for assignment in assignments:
        if not assignment.time_slot:
            assignment.time_slot = 'complete'
        if not assignment.tarif:
            assignment.tarif = calculate_tarif(assignment.date, assignment.time_slot)
    
    db.session.commit()
    print(f"✅ Migration terminée ! {len(assignments)} assignments mis à jour.")
