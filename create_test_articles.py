#!/usr/bin/env python3
"""
Script pour créer des articles de test dans la base de données CMTCH
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

def create_test_articles():
    """Crée des articles de test dans la base de données."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Vérifier si la table articles existe
        cur.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='articles'
        """)
        
        if not cur.fetchone():
            print("❌ Table 'articles' non trouvée. Création...")
            cur.execute("""
                CREATE TABLE articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    image_path TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("✅ Table 'articles' créée")
        
        # Vérifier s'il y a déjà des articles
        cur.execute("SELECT COUNT(*) FROM articles")
        count = cur.fetchone()[0]
        print(f"📰 Articles existants: {count}")
        
        if count == 0:
            print("🆕 Création d'articles de test...")
            
            # Articles de test
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
                },
                {
                    "title": "Maintenance des courts",
                    "content": "Nos courts de tennis ont été entièrement rénovés pendant les vacances. Nouvelle surface, filets neufs et éclairage amélioré pour une expérience de jeu optimale.",
                    "created_at": (datetime.now() - timedelta(days=12)).isoformat()
                },
                {
                    "title": "Bienvenue aux nouveaux membres",
                    "content": "Nous souhaitons la bienvenue à tous nos nouveaux membres qui ont rejoint le club ce mois-ci. N'hésitez pas à participer aux activités et à vous intégrer dans notre communauté tennis.",
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
            
            conn.commit()
            print(f"🎉 {len(test_articles)} articles de test créés avec succès!")
            
        else:
            print("ℹ️  Des articles existent déjà dans la base")
            
        # Afficher tous les articles
        print("\n📋 Liste des articles dans la base:")
        cur.execute("SELECT id, title, created_at FROM articles ORDER BY datetime(created_at) DESC")
        articles = cur.fetchall()
        
        for article in articles:
            print(f"  ID {article['id']}: {article['title']} ({article['created_at']})")
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("🚀 Script de création d'articles de test CMTCH")
    print("=" * 50)
    create_test_articles()
    print("=" * 50)
    print("✅ Script terminé")
