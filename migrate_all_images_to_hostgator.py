#!/usr/bin/env python3
"""
Script pour migrer toutes les images d'articles vers HostGator
et mettre à jour la base de données avec les URLs HostGator.
"""

import os
import sqlite3
import requests
from hostgator_photo_storage import HostGatorPhotoStorage
from pathlib import Path

def get_db_connection():
    """Connexion à la base de données SQLite"""
    return sqlite3.connect("cmtch.db")

def download_image_from_url(url: str) -> tuple:
    """
    Télécharge une image depuis une URL
    
    Returns:
        Tuple[success, content, filename]
    """
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            # Extraire le nom de fichier de l'URL
            filename = os.path.basename(url.split('?')[0])
            if not filename or '.' not in filename:
                filename = f"migrated_image_{int(time.time())}.jpg"
            return True, response.content, filename
        else:
            return False, None, None
    except Exception as e:
        print(f"❌ Erreur téléchargement {url}: {e}")
        return False, None, None

def migrate_local_image_to_hostgator(local_path: str) -> tuple:
    """
    Migre une image locale vers HostGator
    
    Returns:
        Tuple[success, hostgator_url, message]
    """
    try:
        # Lire le fichier local
        with open(local_path, 'rb') as f:
            file_content = f.read()
        
        # Extraire le nom de fichier
        filename = os.path.basename(local_path)
        
        # Upload vers HostGator
        storage = HostGatorPhotoStorage()
        success, message, hostgator_url = storage.upload_photo(file_content, filename)
        
        return success, hostgator_url, message
        
    except Exception as e:
        return False, "", f"Erreur migration locale: {e}"

def migrate_article_images():
    """Migre toutes les images d'articles vers HostGator"""
    print("🚀 Migration des images d'articles vers HostGator")
    print("=" * 60)
    
    # Connexion à la base de données
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Récupérer tous les articles avec des images
    cur.execute("SELECT id, title, image_path FROM articles WHERE image_path IS NOT NULL AND image_path != ''")
    articles = cur.fetchall()
    
    print(f"📊 {len(articles)} articles avec images trouvés")
    
    storage = HostGatorPhotoStorage()
    migrated_count = 0
    error_count = 0
    
    for article_id, title, image_path in articles:
        print(f"\n📝 Article {article_id}: {title[:50]}...")
        print(f"   Image actuelle: {image_path}")
        
        # Vérifier si c'est déjà une URL HostGator
        if "cmtch.online" in image_path and "static/article_images" in image_path:
            print("   ✅ Déjà sur HostGator, ignoré")
            continue
        
        new_url = ""
        success = False
        
        # Cas 1: URL externe
        if image_path.startswith("http"):
            print("   🔄 Téléchargement depuis URL externe...")
            success_download, content, filename = download_image_from_url(image_path)
            if success_download:
                success, new_url, message = storage.upload_photo(content, filename)
                print(f"   📤 Upload HostGator: {'✅' if success else '❌'} {message}")
            else:
                print("   ❌ Échec téléchargement")
        
        # Cas 2: Chemin local
        elif image_path.startswith("/"):
            local_path = f"static{image_path}"
            if os.path.exists(local_path):
                print("   🔄 Migration depuis fichier local...")
                success, new_url, message = migrate_local_image_to_hostgator(local_path)
                print(f"   📤 Upload HostGator: {'✅' if success else '❌'} {message}")
            else:
                print("   ❌ Fichier local introuvable")
        
        # Cas 3: Autres cas
        else:
            print("   ❌ Format d'URL non reconnu")
        
        # Mettre à jour la base de données si succès
        if success and new_url:
            try:
                cur.execute("UPDATE articles SET image_path = ? WHERE id = ?", (new_url, article_id))
                conn.commit()
                print(f"   ✅ Base de données mise à jour: {new_url}")
                migrated_count += 1
            except Exception as e:
                print(f"   ❌ Erreur mise à jour DB: {e}")
                error_count += 1
        else:
            # Utiliser l'image par défaut en cas d'échec
            default_url = "https://www.cmtch.online/static/article_images/default_article.jpg"
            try:
                cur.execute("UPDATE articles SET image_path = ? WHERE id = ?", (default_url, article_id))
                conn.commit()
                print(f"   🔄 Image par défaut assignée: {default_url}")
                migrated_count += 1
            except Exception as e:
                print(f"   ❌ Erreur assignation défaut: {e}")
                error_count += 1
    
    conn.close()
    
    print(f"\n🎉 Migration terminée!")
    print(f"   ✅ {migrated_count} articles migrés")
    print(f"   ❌ {error_count} erreurs")
    print(f"   📊 {len(articles)} articles traités au total")

def verify_migration():
    """Vérifie que toutes les images pointent vers HostGator"""
    print("\n🔍 Vérification de la migration...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Vérifier les URLs non-HostGator
    cur.execute("""
        SELECT id, title, image_path 
        FROM articles 
        WHERE image_path IS NOT NULL 
        AND image_path != '' 
        AND image_path NOT LIKE '%cmtch.online%'
    """)
    non_hostgator = cur.fetchall()
    
    if non_hostgator:
        print(f"⚠️ {len(non_hostgator)} articles avec URLs non-HostGator:")
        for article_id, title, url in non_hostgator:
            print(f"   - Article {article_id}: {url}")
    else:
        print("✅ Tous les articles utilisent des URLs HostGator")
    
    # Vérifier les URLs HostGator
    cur.execute("""
        SELECT COUNT(*) 
        FROM articles 
        WHERE image_path LIKE '%cmtch.online%'
    """)
    hostgator_count = cur.fetchone()[0]
    print(f"✅ {hostgator_count} articles avec URLs HostGator")
    
    conn.close()

def main():
    """Fonction principale"""
    print("🖼️ Migration des images d'articles vers HostGator")
    print("=" * 60)
    
    # Test de connexion HostGator
    print("🔍 Test de connexion HostGator...")
    storage = HostGatorPhotoStorage()
    try:
        import ftplib
        ftp = ftplib.FTP(storage.ftp_host)
        ftp.login(storage.ftp_user, storage.ftp_password)
        ftp.quit()
        print("✅ Connexion HostGator OK")
    except Exception as e:
        print(f"❌ Erreur connexion HostGator: {e}")
        return
    
    # Migration
    migrate_article_images()
    
    # Vérification
    verify_migration()
    
    print("\n🎯 Prochaines étapes:")
    print("   1. Tester l'affichage des images sur le site")
    print("   2. Vérifier qu'il n'y a plus d'erreurs 404")
    print("   3. Supprimer les anciens fichiers locaux si nécessaire")

if __name__ == "__main__":
    import time
    main()
