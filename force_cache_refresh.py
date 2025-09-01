#!/usr/bin/env python3
"""
Script pour forcer le rechargement du cache en ajoutant un paramètre de version
"""

import os
import sqlite3

def force_cache_refresh():
    """Ajoute un paramètre de version aux URLs d'images pour forcer le rechargement"""
    print("🔄 Forçage du rechargement du cache...")
    
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        DB_PATH = os.path.join(BASE_DIR, "database.db")
        
        if not os.path.exists(DB_PATH):
            print("❌ Base de données n'existe pas")
            return False
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Récupérer tous les articles avec des images HostGator
        cur.execute("SELECT id, title, image_path FROM articles WHERE image_path LIKE '%cmtch.online/photos/%'")
        articles = cur.fetchall()
        
        print(f"📋 {len(articles)} article(s) avec images HostGator trouvé(s)")
        
        updated_count = 0
        
        for article_id, title, image_path in articles:
            print(f"\n🔄 Article: {title}")
            print(f"   Image actuelle: {image_path}")
            
            # Ajouter un paramètre de version pour forcer le rechargement
            if "?" not in image_path:
                new_url = f"{image_path}?v=20250901"
            else:
                # Remplacer le paramètre existant
                base_url = image_path.split("?")[0]
                new_url = f"{base_url}?v=20250901"
            
            # Mettre à jour la base de données
            cur.execute("UPDATE articles SET image_path = ? WHERE id = ?", (new_url, article_id))
            print(f"   ✅ Mis à jour vers: {new_url}")
            updated_count += 1
        
        # Sauvegarder les changements
        conn.commit()
        conn.close()
        
        print(f"\n🎉 Cache refresh forcé: {updated_count}/{len(articles)} articles mis à jour")
        return True
        
    except Exception as e:
        print(f"❌ Erreur cache refresh: {e}")
        return False

def main():
    """Fonction principale"""
    print("🚀 Forçage du rechargement du cache")
    print("=" * 60)
    
    if force_cache_refresh():
        print("✅ Cache refresh forcé avec succès")
    else:
        print("❌ Échec du cache refresh")

if __name__ == "__main__":
    main()
