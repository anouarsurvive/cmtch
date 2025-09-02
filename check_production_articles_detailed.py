#!/usr/bin/env python3
"""
Script pour examiner en détail les articles de production MySQL.
"""

import sys
import os

# Ajouter le répertoire courant au path pour importer database
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

def check_production_articles_detailed():
    """Vérifie en détail les articles de production"""
    print("🔍 VÉRIFICATION DÉTAILLÉE DES ARTICLES DE PRODUCTION:")
    
    try:
        conn = get_db_connection()
        
        if hasattr(conn, '_is_mysql'):
            print("🔌 Connexion MySQL établie")
        else:
            print("❌ Connexion SQLite établie (pas MySQL)")
            return
        
        cur = conn.cursor()
        
        # Afficher tous les articles avec leurs détails
        print("\n📝 ARTICLES EN PRODUCTION:")
        cur.execute("SELECT id, title, image_path, created_at FROM articles ORDER BY id")
        articles = cur.fetchall()
        
        for article in articles:
            article_id, title, image_path, created_at = article
            print(f"\n   Article {article_id}: {title}")
            print(f"     Image: {image_path}")
            print(f"     Créé: {created_at}")
            
            # Vérifier si l'image existe sur le serveur
            if image_path:
                if image_path.startswith('http'):
                    print(f"     ⚠️  URL externe (problématique)")
                elif image_path.startswith('/static/'):
                    print(f"     ✅ Chemin local valide")
                else:
                    print(f"     ❓ Format inconnu")
            else:
                print(f"     ❌ Aucune image")
        
        # Vérifier les URLs externes spécifiquement
        print(f"\n🔍 VÉRIFICATION DES URLs EXTERNES:")
        cur.execute("SELECT id, title, image_path FROM articles WHERE image_path LIKE 'http%'")
        external_urls = cur.fetchall()
        
        if external_urls:
            print(f"   🚫 {len(external_urls)} articles avec URLs externes:")
            for article in external_urls:
                article_id, title, image_path = article
                print(f"     Article {article_id}: {title}")
                print(f"       URL: {image_path}")
        else:
            print("   ✅ Aucune URL externe trouvée")
        
        # Vérifier les articles sans images
        print(f"\n🔍 VÉRIFICATION DES ARTICLES SANS IMAGES:")
        cur.execute("SELECT id, title FROM articles WHERE image_path IS NULL OR image_path = ''")
        articles_without_images = cur.fetchall()
        
        if articles_without_images:
            print(f"   ❌ {len(articles_without_images)} articles sans images:")
            for article in articles_without_images:
                article_id, title = article
                print(f"     Article {article_id}: {title}")
        else:
            print("   ✅ Tous les articles ont des images")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur lors de la vérification: {e}")

def main():
    """Fonction principale"""
    print("🚀 VÉRIFICATION DÉTAILLÉE - ARTICLES DE PRODUCTION")
    print("=" * 60)
    
    check_production_articles_detailed()
    
    print("\n✅ Vérification terminée!")

if __name__ == "__main__":
    main()
