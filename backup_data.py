#!/usr/bin/env python3
"""
Script de sauvegarde des données avant migration vers PostgreSQL
"""

import sqlite3
import json
import os
from datetime import datetime

def backup_sqlite_data():
    """Sauvegarde toutes les données de la base SQLite"""
    
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(BASE_DIR, "database.db")
    
    if not os.path.exists(DB_PATH):
        print("❌ Base de données SQLite non trouvée")
        return
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Récupérer tous les utilisateurs
        cur.execute("SELECT * FROM users")
        users = cur.fetchall()
        
        # Récupérer toutes les réservations
        cur.execute("SELECT * FROM reservations")
        reservations = cur.fetchall()
        
        # Récupérer tous les articles
        cur.execute("SELECT * FROM articles")
        articles = cur.fetchall()
        
        conn.close()
        
        # Créer la sauvegarde
        backup_data = {
            "timestamp": datetime.now().isoformat(),
            "users": [
                {
                    "id": user[0],
                    "username": user[1],
                    "password_hash": user[2],
                    "full_name": user[3],
                    "email": user[4],
                    "phone": user[5],
                    "ijin_number": user[6] if len(user) > 6 else None,
                    "birth_date": user[7] if len(user) > 7 else None,
                    "photo_path": user[8] if len(user) > 8 else None,
                    "is_admin": bool(user[9]) if len(user) > 9 else False,
                    "validated": bool(user[10]) if len(user) > 10 else False,
                    "is_trainer": bool(user[11]) if len(user) > 11 else False
                }
                for user in users
            ],
            "reservations": [
                {
                    "id": res[0],
                    "user_id": res[1],
                    "court_number": res[2],
                    "date": res[3],
                    "start_time": res[4],
                    "end_time": res[5]
                }
                for res in reservations
            ],
            "articles": [
                {
                    "id": art[0],
                    "title": art[1],
                    "content": art[2],
                    "image_path": art[3],
                    "created_at": art[4]
                }
                for art in articles
            ]
        }
        
        # Sauvegarder dans un fichier JSON
        backup_filename = f"backup_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        backup_path = os.path.join(BASE_DIR, backup_filename)
        
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Sauvegarde créée : {backup_filename}")
        print(f"📊 Données sauvegardées :")
        print(f"   - {len(users)} utilisateurs")
        print(f"   - {len(reservations)} réservations")
        print(f"   - {len(articles)} articles")
        print(f"💾 Fichier : {backup_path}")
        
        return backup_data
        
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde : {e}")
        return None

def restore_from_backup(backup_file):
    """Restaure les données depuis un fichier de sauvegarde"""
    
    if not os.path.exists(backup_file):
        print(f"❌ Fichier de sauvegarde non trouvé : {backup_file}")
        return
    
    try:
        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        print(f"📖 Lecture de la sauvegarde du {backup_data['timestamp']}")
        print(f"📊 Données à restaurer :")
        print(f"   - {len(backup_data['users'])} utilisateurs")
        print(f"   - {len(backup_data['reservations'])} réservations")
        print(f"   - {len(backup_data['articles'])} articles")
        
        return backup_data
        
    except Exception as e:
        print(f"❌ Erreur lors de la lecture de la sauvegarde : {e}")
        return None

if __name__ == "__main__":
    print("🔄 Création de la sauvegarde des données...")
    backup_data = backup_sqlite_data()
    
    if backup_data:
        print("\n✅ Sauvegarde terminée avec succès !")
        print("💡 Vous pouvez maintenant déployer sur Render avec PostgreSQL")
        print("🔗 Vos données seront automatiquement migrées au premier démarrage")
    else:
        print("\n❌ Échec de la sauvegarde")
