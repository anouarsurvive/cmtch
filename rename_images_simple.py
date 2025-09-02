#!/usr/bin/env python3
"""
Script pour renommer les images avec des noms simples.
"""

import ftplib
import io
import sys
import os

# Ajouter le répertoire courant au path pour importer database
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

def rename_images_simple():
    """Renomme les images avec des noms simples"""
    print("🔧 RENOMMAGE DES IMAGES AVEC DES NOMS SIMPLES:")
    
    # Configuration FTP
    ftp_host = "ftp.novaprint.tn"
    ftp_user = "cmtch@cmtch.online"
    ftp_password = "Anouar881984?"
    
    try:
        # Connexion FTP
        ftp = ftplib.FTP(ftp_host)
        ftp.login(ftp_user, ftp_password)
        ftp.cwd('/public_html/static/article_images')
        
        # Connexion base de données
        conn = get_db_connection()
        if not hasattr(conn, '_is_mysql'):
            print("❌ Connexion SQLite établie (pas MySQL)")
            return False
        
        cur = conn.cursor()
        
        # Récupérer les articles avec leurs images
        print("\n📋 ARTICLES AVEC IMAGES:")
        cur.execute("SELECT id, title, image_path FROM articles WHERE image_path IS NOT NULL AND image_path != '' ORDER BY id")
        articles = cur.fetchall()
        
        if not articles:
            print("   Aucun article avec image trouvé")
            return False
        
        # Mapping des anciens noms vers les nouveaux noms
        name_mapping = {}
        
        for i, (article_id, title, image_path) in enumerate(articles, 1):
            if image_path and '/static/article_images/' in image_path:
                old_filename = image_path.split('/')[-1]
                
                # Créer un nouveau nom simple
                new_filename = f"article_{article_id}.jpg"
                name_mapping[old_filename] = new_filename
                
                print(f"   Article {article_id}: {title}")
                print(f"     Ancien: {old_filename}")
                print(f"     Nouveau: {new_filename}")
        
        print(f"\n🔄 RENOMMAGE DES FICHIERS:")
        
        # Renommer les fichiers sur le serveur FTP
        for old_name, new_name in name_mapping.items():
            print(f"   🔄 Renommage: {old_name} → {new_name}")
            
            try:
                # Vérifier que le fichier existe
                files = ftp.nlst()
                if old_name not in files:
                    print(f"     ⚠️ Fichier {old_name} non trouvé, ignoré")
                    continue
                
                # Lire le fichier
                file_data = []
                ftp.retrbinary(f"RETR {old_name}", file_data.append)
                file_content = b''.join(file_data)
                
                # Supprimer l'ancien fichier
                ftp.delete(old_name)
                
                # Créer le nouveau fichier
                ftp.storbinary(f'STOR {new_name}', io.BytesIO(file_content))
                
                print(f"     ✅ Renommé avec succès")
                
            except Exception as e:
                print(f"     ❌ Erreur: {e}")
        
        print(f"\n🔄 MISE À JOUR DE LA BASE DE DONNÉES:")
        
        # Mettre à jour la base de données
        for old_name, new_name in name_mapping.items():
            new_path = f"/static/article_images/{new_name}"
            
            # Mettre à jour l'article correspondant
            cur.execute("UPDATE articles SET image_path = %s WHERE image_path LIKE %s", 
                       (new_path, f"%{old_name}"))
            
            if cur.rowcount > 0:
                print(f"   ✅ Base de données mise à jour: {old_name} → {new_path}")
            else:
                print(f"   ⚠️ Aucun article trouvé pour: {old_name}")
        
        # Valider les changements
        conn.commit()
        print("💾 Changements validés en base de données")
        
        ftp.quit()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du renommage: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

def main():
    """Fonction principale"""
    print("🚀 RENOMMAGE DES IMAGES AVEC DES NOMS SIMPLES")
    print("=" * 60)
    
    print("📋 Ce script va renommer les images avec des noms simples")
    print("   pour contourner les restrictions du serveur HostGator.")
    print()
    
    # Demander confirmation
    confirm = input("❓ Continuer avec le renommage? (o/n): ").strip().lower()
    if not confirm.startswith('o'):
        print("❌ Renommage annulé")
        return
    
    # Effectuer le renommage
    success = rename_images_simple()
    
    if success:
        print(f"\n🎉 Renommage terminé!")
        print(f"   - Images renommées avec des noms simples")
        print(f"   - Base de données mise à jour")
        print(f"   - Les images devraient maintenant être accessibles")
        print(f"\n📝 Prochaine étape: Tester l'accessibilité des nouvelles images")
    else:
        print(f"\n❌ Échec du renommage")
    
    print(f"\n✅ Opération terminée!")

if __name__ == "__main__":
    main()
