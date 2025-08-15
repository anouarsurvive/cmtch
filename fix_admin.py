#!/usr/bin/env python3
"""
Script pour corriger les problèmes d'administration CMTCH
"""

import sqlite3
import os
import hashlib
from datetime import datetime

def get_db_connection():
    """Crée une connexion à la base de données."""
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(BASE_DIR, "cmtch.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    """Retourne l'empreinte SHA‑256 d'un mot de passe en clair."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def fix_admin_user():
    """Corrige l'utilisateur admin et vérifie les permissions."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        print("🔧 Correction des problèmes d'administration CMTCH")
        print("=" * 60)
        
        # Vérifier si l'utilisateur admin existe
        cur.execute("SELECT * FROM users WHERE username = 'admin'")
        admin_user = cur.fetchone()
        
        if admin_user:
            print(f"✅ Utilisateur admin trouvé: ID {admin_user['id']}")
            print(f"   Nom: {admin_user['full_name']}")
            print(f"   Email: {admin_user['email']}")
            print(f"   Admin: {bool(admin_user['is_admin'])}")
            print(f"   Validé: {bool(admin_user['validated'])}")
            
            # Vérifier et corriger les permissions admin
            if not admin_user['is_admin']:
                print("⚠️  L'utilisateur admin n'a pas les droits d'administrateur. Correction...")
                cur.execute("UPDATE users SET is_admin = 1 WHERE username = 'admin'")
                print("✅ Droits d'administrateur ajoutés")
            
            if not admin_user['validated']:
                print("⚠️  L'utilisateur admin n'est pas validé. Correction...")
                cur.execute("UPDATE users SET validated = 1 WHERE username = 'admin'")
                print("✅ Statut validé ajouté")
            
            # Mettre à jour le mot de passe si nécessaire
            admin_password = "admin"
            admin_password_hash = hash_password(admin_password)
            
            if admin_user['password_hash'] != admin_password_hash:
                print("⚠️  Mise à jour du mot de passe admin...")
                cur.execute("UPDATE users SET password_hash = ? WHERE username = 'admin'", (admin_password_hash,))
                print("✅ Mot de passe admin mis à jour")
            
        else:
            print("❌ Utilisateur admin non trouvé. Création...")
            admin_password = "admin"
            admin_password_hash = hash_password(admin_password)
            
            cur.execute("""
                INSERT INTO users (username, password_hash, full_name, email, phone, ijin_number, birth_date, is_admin, validated, is_trainer)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ("admin", admin_password_hash, "Administrateur", "admin@cmtch.tn", "+21612345678", "ADMIN001", "1990-01-01", 1, 1, 0))
            
            print("✅ Utilisateur admin créé avec succès")
            print("   Identifiants: admin / admin")
        
        # Vérifier tous les utilisateurs
        print("\n📊 Vérification de tous les utilisateurs:")
        cur.execute("SELECT id, username, full_name, email, is_admin, validated FROM users ORDER BY id")
        users = cur.fetchall()
        
        for user in users:
            status = "✅" if user['validated'] else "⏳"
            admin = "👑" if user['is_admin'] else "👤"
            print(f"   {status} {admin} ID {user['id']}: {user['username']} ({user['full_name']})")
        
        # Vérifier les articles
        print("\n📰 Vérification des articles:")
        cur.execute("SELECT COUNT(*) FROM articles")
        article_count = cur.fetchone()[0]
        print(f"   Articles dans la base: {article_count}")
        
        if article_count == 0:
            print("⚠️  Aucun article trouvé. Création d'articles de test...")
            from datetime import timedelta
            
            test_articles = [
                {
                    "title": "Ouverture de la saison 2025",
                    "content": "Le Club Municipal de Tennis Chihia est ravi d'annoncer l'ouverture de la saison 2025. Cette année promet d'être exceptionnelle avec de nouveaux équipements et des programmes d'entraînement améliorés pour tous les niveaux.",
                    "created_at": (datetime.now() - timedelta(days=2)).isoformat()
                },
                {
                    "title": "Nouveau programme pour les jeunes",
                    "content": "Nous lançons un nouveau programme spécialement conçu pour les jeunes de 8 à 16 ans. Ce programme combine technique, tactique et plaisir pour développer la passion du tennis chez nos futurs champions.",
                    "created_at": (datetime.now() - timedelta(days=5)).isoformat()
                },
                {
                    "title": "Tournoi interne du mois",
                    "content": "Le tournoi interne du mois de janvier aura lieu le week-end prochain. Tous les membres sont invités à participer. Inscriptions ouvertes jusqu'à vendredi soir.",
                    "created_at": (datetime.now() - timedelta(days=8)).isoformat()
                }
            ]
            
            for article in test_articles:
                cur.execute("""
                    INSERT INTO articles (title, content, created_at)
                    VALUES (?, ?, ?)
                """, (article["title"], article["content"], article["created_at"]))
            
            print(f"✅ {len(test_articles)} articles de test créés")
        
        # Commit des changements
        conn.commit()
        
        print("\n🎯 Résumé des corrections:")
        print("   ✅ Utilisateur admin vérifié/corrrigé")
        print("   ✅ Permissions d'administration vérifiées")
        print("   ✅ Articles vérifiés/créés")
        print("\n🔑 Identifiants de connexion admin:")
        print("   Username: admin")
        print("   Password: admin")
        print("\n🌐 URLs d'administration:")
        print("   Membres: https://cmtch.onrender.com/admin/membres")
        print("   Réservations: https://cmtch.onrender.com/admin/reservations")
        print("   Articles: https://cmtch.onrender.com/admin/articles")
        
    except Exception as e:
        print(f"❌ Erreur lors de la correction: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    fix_admin_user()
    print("=" * 60)
    print("✅ Correction terminée")
