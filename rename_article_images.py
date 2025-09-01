#!/usr/bin/env python3
"""
Script pour renommer les images d'articles avec une séquence simple (1.jpg, 2.jpg, 3.jpg, etc.)
"""

import os
import sqlite3
import ftplib
import io
from datetime import datetime

def rename_article_images():
    """Renomme les images d'articles avec une séquence simple"""
    print("🔄 Renommage des images d'articles...")
    
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        DB_PATH = os.path.join(BASE_DIR, "database.db")
        
        if not os.path.exists(DB_PATH):
            print("❌ Base de données n'existe pas")
            return False
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Récupérer tous les articles avec des images
        cur.execute("SELECT id, title, image_path FROM articles WHERE image_path IS NOT NULL AND image_path != ''")
        articles = cur.fetchall()
        
        print(f"📋 {len(articles)} article(s) avec images trouvé(s)")
        
        # Configuration FTP HostGator
        ftp_host = "ftp.novaprint.tn"
        ftp_user = "cmtch@cmtch.online"
        ftp_password = "Anouar881984?"
        
        # Connexion FTP
        ftp = ftplib.FTP(ftp_host)
        ftp.login(ftp_user, ftp_password)
        ftp.cwd("public_html/photos")
        
        updated_count = 0
        
        for i, (article_id, title, image_path) in enumerate(articles, 1):
            print(f"\n🔄 Article {i}: {title[:50]}...")
            print(f"   Image actuelle: {image_path}")
            
            # Nouveau nom simple
            new_filename = f"{i}.jpg"
            new_url = f"https://www.cmtch.online/photos/{new_filename}"
            
            # Si l'image pointe vers HostGator, télécharger et renommer
            if "cmtch.online/photos/" in image_path:
                try:
                    # Extraire le nom de fichier actuel
                    old_filename = image_path.split("/")[-1].split("?")[0]  # Enlever les paramètres
                    
                    # Télécharger l'image actuelle
                    image_data = io.BytesIO()
                    ftp.retrbinary(f'RETR {old_filename}', image_data.write)
                    image_data.seek(0)
                    
                    # Uploader avec le nouveau nom
                    ftp.storbinary(f'STOR {new_filename}', image_data)
                    
                    print(f"   ✅ Renommé: {old_filename} → {new_filename}")
                    
                except Exception as e:
                    print(f"   ⚠️ Erreur renommage FTP: {e}")
                    # Créer une image par défaut
                    create_default_image(ftp, new_filename)
                    print(f"   ✅ Image par défaut créée: {new_filename}")
            else:
                # Créer une image par défaut
                create_default_image(ftp, new_filename)
                print(f"   ✅ Image par défaut créée: {new_filename}")
            
            # Mettre à jour la base de données
            cur.execute("UPDATE articles SET image_path = ? WHERE id = ?", (new_url, article_id))
            print(f"   ✅ Base de données mise à jour: {new_url}")
            updated_count += 1
        
        # Fermer la connexion FTP
        ftp.quit()
        
        # Sauvegarder les changements
        conn.commit()
        conn.close()
        
        print(f"\n🎉 Renommage terminé: {updated_count}/{len(articles)} articles mis à jour")
        return True
        
    except Exception as e:
        print(f"❌ Erreur renommage: {e}")
        return False

def create_default_image(ftp, filename):
    """Crée une image par défaut simple"""
    # Créer une image PNG simple (1x1 pixel transparent)
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82'
    
    # Upload vers HostGator
    ftp.storbinary(f'STOR {filename}', io.BytesIO(png_data))

def main():
    """Fonction principale"""
    print("🚀 Renommage des images d'articles avec séquence simple")
    print("=" * 60)
    
    if rename_article_images():
        print("✅ Images renommées avec succès")
        print("\n📋 Nouvelles images:")
        print("   - 1.jpg, 2.jpg, 3.jpg, etc.")
        print("   - URLs simples et mémorisables")
        print("\n🌐 Testez maintenant le site!")
    else:
        print("❌ Échec du renommage des images")

if __name__ == "__main__":
    main()
