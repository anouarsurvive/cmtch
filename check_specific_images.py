#!/usr/bin/env python3
"""
Script pour vérifier les images spécifiques qui causent des erreurs 404
"""

import os
import sqlite3

def check_specific_images():
    """Vérifie les images spécifiques qui causent des erreurs 404"""
    print("🔍 Vérification des images spécifiques...")
    
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        DB_PATH = os.path.join(BASE_DIR, "database.db")
        
        if not os.path.exists(DB_PATH):
            print("❌ Base de données n'existe pas")
            return False
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Images problématiques
        problematic_images = [
            "94b7d52068c24d4f8919889670831bfb.jpg",
            "1fb035de3f394ec3ba127e56d4b42119.jpg",
            "c30ed102110f439a808f140839182ed9.jpg"
        ]
        
        for image_name in problematic_images:
            print(f"\n🔍 Recherche de: {image_name}")
            
            # Chercher dans les articles
            cur.execute("SELECT id, title, image_path FROM articles WHERE image_path LIKE ?", (f"%{image_name}%",))
            articles = cur.fetchall()
            
            if articles:
                print(f"   📄 Trouvé dans {len(articles)} article(s):")
                for article_id, title, image_path in articles:
                    print(f"      - ID: {article_id}, Titre: {title}")
                    print(f"      - Image: {image_path}")
            else:
                print(f"   ❌ Pas trouvé dans la base de données")
        
        # Vérifier tous les articles avec des chemins locaux
        print(f"\n🔍 Tous les articles avec des chemins locaux:")
        cur.execute("SELECT id, title, image_path FROM articles WHERE image_path LIKE '/static/article_images/%'")
        local_articles = cur.fetchall()
        
        if local_articles:
            print(f"   ⚠️ {len(local_articles)} article(s) avec chemins locaux:")
            for article_id, title, image_path in local_articles:
                print(f"      - ID: {article_id}, Titre: {title}")
                print(f"      - Image: {image_path}")
        else:
            print(f"   ✅ Aucun article avec chemin local")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Erreur vérification: {e}")
        return False

def main():
    """Fonction principale"""
    print("🚀 Vérification des images spécifiques")
    print("=" * 60)
    
    check_specific_images()

if __name__ == "__main__":
    main()
