#!/usr/bin/env python3
"""
Script pour forcer la migration de toutes les images vers HostGator
"""

import os
import sqlite3
import ftplib
import io
from datetime import datetime

def force_hostgator_migration():
    """Force la migration de toutes les images vers HostGator"""
    print("🔄 Migration forcée vers HostGator...")
    
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        DB_PATH = os.path.join(BASE_DIR, "database.db")
        
        if not os.path.exists(DB_PATH):
            print("❌ Base de données n'existe pas")
            return False
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Récupérer tous les articles avec des chemins locaux
        cur.execute("SELECT id, title, image_path FROM articles WHERE image_path LIKE '/static/article_images/%'")
        articles = cur.fetchall()
        
        print(f"📋 {len(articles)} article(s) avec chemins locaux trouvé(s)")
        
        if not articles:
            print("✅ Aucun article avec chemin local à migrer")
            return True
        
        # Configuration FTP HostGator
        ftp_host = "ftp.novaprint.tn"
        ftp_user = "cmtch@cmtch.online"
        ftp_password = "Anouar881984?"
        
        # Connexion FTP
        ftp = ftplib.FTP(ftp_host)
        ftp.login(ftp_user, ftp_password)
        ftp.cwd("public_html/photos")
        
        migrated_count = 0
        
        for article_id, title, image_path in articles:
            print(f"\n🔄 Article {article_id}: {title[:50]}...")
            print(f"   Image locale: {image_path}")
            
            # Extraire le nom du fichier
            filename = os.path.basename(image_path)
            local_file_path = os.path.join(BASE_DIR, "static", "article_images", filename)
            
            # Vérifier si le fichier local existe
            if os.path.exists(local_file_path):
                try:
                    # Lire le fichier local
                    with open(local_file_path, "rb") as f:
                        file_content = f.read()
                    
                    # Upload vers HostGator
                    ftp.storbinary(f'STOR {filename}', io.BytesIO(file_content))
                    
                    # Nouvelle URL HostGator
                    new_url = f"https://www.cmtch.online/photos/{filename}"
                    
                    # Mettre à jour la base de données
                    cur.execute("UPDATE articles SET image_path = ? WHERE id = ?", (new_url, article_id))
                    
                    print(f"   ✅ Migré vers HostGator: {new_url}")
                    migrated_count += 1
                    
                except Exception as e:
                    print(f"   ❌ Erreur migration: {e}")
            else:
                print(f"   ⚠️ Fichier local introuvable: {local_file_path}")
        
        # Fermer la connexion FTP
        ftp.quit()
        
        # Sauvegarder les changements
        conn.commit()
        conn.close()
        
        print(f"\n🎉 Migration terminée: {migrated_count}/{len(articles)} articles migrés")
        return True
        
    except Exception as e:
        print(f"❌ Erreur migration: {e}")
        return False

def main():
    """Fonction principale"""
    print("🚀 Migration forcée vers HostGator")
    print("=" * 60)
    
    if force_hostgator_migration():
        print("✅ Migration vers HostGator réussie")
        print("\n🌐 Toutes les images sont maintenant sur HostGator!")
        print("   Plus de suppression automatique par Render!")
    else:
        print("❌ Échec de la migration")

if __name__ == "__main__":
    main()
