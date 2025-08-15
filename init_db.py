#!/usr/bin/env python3
"""
Script pour initialiser la base de données CMTCH avec des données de test
"""

import sqlite3
import os
from datetime import datetime, timedelta

def get_db_connection():
    """Crée une connexion à la base de données."""
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(BASE_DIR, "cmtch.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialise la base de données avec toutes les tables et données de test."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        print("🚀 Initialisation de la base de données CMTCH")
        print("=" * 50)
        
        # Créer la table users si elle n'existe pas
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                ijin_number TEXT,
                birth_date TEXT,
                photo_path TEXT,
                is_admin INTEGER DEFAULT 0,
                validated INTEGER DEFAULT 0,
                is_trainer INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Table 'users' créée/vérifiée")
        
        # Créer la table articles si elle n'existe pas
        cur.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                image_path TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Table 'articles' créée/vérifiée")
        
        # Créer la table reservations si elle n'existe pas
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                court_number INTEGER NOT NULL,
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        print("✅ Table 'reservations' créée/vérifiée")
        
        # Vérifier s'il y a déjà des utilisateurs
        cur.execute("SELECT COUNT(*) FROM users")
        user_count = cur.fetchone()[0]
        
        if user_count == 0:
            print("🆕 Création de l'utilisateur admin...")
            # Créer l'utilisateur admin
            admin_password = "admin"  # En production, utiliser un hash sécurisé
            cur.execute("""
                INSERT INTO users (username, password_hash, full_name, email, phone, ijin_number, birth_date, is_admin, validated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ("admin", admin_password, "Administrateur", "admin@cmtch.tn", "+21612345678", "ADMIN001", "1990-01-01", 1, 1))
            print("  ✅ Utilisateur admin créé: admin / admin")
        
        # Vérifier s'il y a déjà des articles
        cur.execute("SELECT COUNT(*) FROM articles")
        article_count = cur.fetchone()[0]
        
        if article_count == 0:
            print("🆕 Création d'articles de test...")
            
            # Articles de test avec des dates récentes
            test_articles = [
                {
                    "title": "Ouverture de la saison 2025",
                    "content": "Le Club Municipal de Tennis Chihia est ravi d'annoncer l'ouverture de la saison 2025. Cette année promet d'être exceptionnelle avec de nouveaux équipements et des programmes d'entraînement améliorés pour tous les niveaux. Nous avons investi dans la rénovation de nos courts et l'achat de nouveaux équipements pour offrir une expérience de tennis optimale à tous nos membres.",
                    "created_at": (datetime.now() - timedelta(days=2)).isoformat()
                },
                {
                    "title": "Nouveau programme pour les jeunes",
                    "content": "Nous lançons un nouveau programme spécialement conçu pour les jeunes de 8 à 16 ans. Ce programme combine technique, tactique et plaisir pour développer la passion du tennis chez nos futurs champions. Les entraînements auront lieu les mercredis et samedis avec des groupes adaptés selon l'âge et le niveau.",
                    "created_at": (datetime.now() - timedelta(days=5)).isoformat()
                },
                {
                    "title": "Tournoi interne du mois",
                    "content": "Le tournoi interne du mois de janvier aura lieu le week-end prochain. Tous les membres sont invités à participer. Inscriptions ouvertes jusqu'à vendredi soir. Le tournoi se déroulera sur deux jours avec des catégories par niveau. Des prix seront remis aux gagnants de chaque catégorie.",
                    "created_at": (datetime.now() - timedelta(days=8)).isoformat()
                },
                {
                    "title": "Maintenance des courts",
                    "content": "Nos courts de tennis ont été entièrement rénovés pendant les vacances. Nouvelle surface, filets neufs et éclairage amélioré pour une expérience de jeu optimale. Les travaux ont duré trois semaines et nous sommes fiers du résultat. Venez tester la nouvelle surface dès maintenant !",
                    "created_at": (datetime.now() - timedelta(days=12)).isoformat()
                },
                {
                    "title": "Bienvenue aux nouveaux membres",
                    "content": "Nous souhaitons la bienvenue à tous nos nouveaux membres qui ont rejoint le club ce mois-ci. N'hésitez pas à participer aux activités et à vous intégrer dans notre communauté tennis. Des sessions d'intégration sont organisées chaque samedi matin pour vous familiariser avec les installations et rencontrer d'autres membres.",
                    "created_at": (datetime.now() - timedelta(days=15)).isoformat()
                }
            ]
            
            # Insérer les articles
            for article in test_articles:
                cur.execute("""
                    INSERT INTO articles (title, content, created_at)
                    VALUES (?, ?, ?)
                """, (article["title"], article["content"], article["created_at"]))
                print(f"  ✅ Article créé: {article['title']}")
            
            print(f"🎉 {len(test_articles)} articles de test créés avec succès!")
            
        else:
            print(f"ℹ️  {article_count} articles existent déjà dans la base")
        
        # Commit des changements
        conn.commit()
        
        # Afficher un résumé
        print("\n📊 Résumé de la base de données:")
        cur.execute("SELECT COUNT(*) FROM users")
        user_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM articles")
        article_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM reservations")
        reservation_count = cur.fetchone()[0]
        
        print(f"  👥 Utilisateurs: {user_count}")
        print(f"  📰 Articles: {article_count}")
        print(f"  📅 Réservations: {reservation_count}")
        
        # Afficher les articles récents
        print("\n📋 Articles récents:")
        cur.execute("SELECT id, title, created_at FROM articles ORDER BY datetime(created_at) DESC LIMIT 3")
        articles = cur.fetchall()
        
        for article in articles:
            print(f"  ID {article['id']}: {article['title']} ({article['created_at']})")
            
        print("\n🔑 Identifiants de connexion:")
        print("  Admin: admin / admin")
        print("  (Créez d'autres comptes via l'inscription)")
        
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    init_database()
    print("=" * 50)
    print("✅ Initialisation terminée")
