#!/usr/bin/env python3
"""
Script pour vérifier la cohérence entre les URLs en base de données et les fichiers FTP.
"""

import sys
import os
import ftplib

# Ajouter le répertoire courant au path pour importer database
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

def verify_ftp_vs_database_urls():
    """Vérifie la cohérence entre les URLs en base de données et les fichiers FTP"""
    print("🔍 VÉRIFICATION DE LA COHÉRENCE FTP vs BASE DE DONNÉES:")
    
    try:
        # Connexion à la base de données
        conn = get_db_connection()
        
        if not hasattr(conn, '_is_mysql'):
            print("❌ Connexion SQLite établie (pas MySQL)")
            return False
        
        cur = conn.cursor()
        
        # Récupérer tous les articles avec leurs images
        print("\n📊 ARTICLES EN BASE DE DONNÉES:")
        cur.execute("SELECT id, title, image_path FROM articles ORDER BY id")
        articles = cur.fetchall()
        
        for article in articles:
            article_id, title, image_path = article
            print(f"   Article {article_id}: {title}")
            print(f"     Image path: {image_path}")
        
        # Connexion FTP
        print(f"\n📁 CONNEXION FTP:")
        ftp_host = "ftp.novaprint.tn"
        ftp_user = "cmtch@cmtch.online"
        ftp_password = "Anouar881984?"
        remote_dir = "/public_html/static/article_images"
        
        ftp = ftplib.FTP(ftp_host)
        ftp.login(ftp_user, ftp_password)
        ftp.cwd(remote_dir)
        
        print(f"   ✅ Connexion FTP réussie")
        print(f"   📂 Répertoire: {remote_dir}")
        
        # Lister les fichiers sur le FTP
        print(f"\n📋 FICHIERS SUR LE FTP:")
        ftp_files = []
        ftp.retrlines('LIST', lambda line: ftp_files.append(line))
        
        for file_info in ftp_files:
            print(f"   {file_info}")
        
        # Extraire les noms de fichiers
        file_names = []
        for file_info in ftp_files:
            parts = file_info.split()
            if len(parts) >= 9:
                file_name = parts[-1]
                file_names.append(file_name)
        
        print(f"\n📋 NOMS DE FICHIERS FTP:")
        for file_name in file_names:
            print(f"   - {file_name}")
        
        # Analyser les URLs de la base de données
        print(f"\n🔍 ANALYSE DES URLs DE LA BASE DE DONNÉES:")
        db_urls = []
        for article in articles:
            article_id, title, image_path = article
            if image_path:
                # Extraire le nom de fichier de l'URL
                if '/' in image_path:
                    filename = image_path.split('/')[-1]
                    db_urls.append((article_id, filename, image_path))
                    print(f"   Article {article_id}: {filename}")
        
        # Vérifier la cohérence
        print(f"\n🔍 VÉRIFICATION DE LA COHÉRENCE:")
        mismatches = []
        
        for article_id, db_filename, full_url in db_urls:
            if db_filename in file_names:
                print(f"   ✅ Article {article_id}: {db_filename} - Fichier trouvé sur FTP")
            else:
                print(f"   ❌ Article {article_id}: {db_filename} - Fichier NON trouvé sur FTP")
                mismatches.append((article_id, db_filename, full_url))
        
        # Analyser les fichiers FTP non référencés
        print(f"\n🔍 FICHIERS FTP NON RÉFÉRENCÉS:")
        referenced_files = [url[1] for url in db_urls]
        unreferenced_files = [f for f in file_names if f not in referenced_files]
        
        for file_name in unreferenced_files:
            print(f"   📁 {file_name} - Présent sur FTP mais non référencé en base")
        
        ftp.quit()
        conn.close()
        
        # Résumé
        print(f"\n📊 RÉSUMÉ:")
        print(f"   📋 Articles en base: {len(articles)}")
        print(f"   📁 Fichiers sur FTP: {len(file_names)}")
        print(f"   ✅ Fichiers cohérents: {len(db_urls) - len(mismatches)}")
        print(f"   ❌ Incohérences: {len(mismatches)}")
        print(f"   📁 Fichiers non référencés: {len(unreferenced_files)}")
        
        if mismatches:
            print(f"\n⚠️ INCOHÉRENCES DÉTECTÉES:")
            for article_id, filename, url in mismatches:
                print(f"   Article {article_id}: {filename} ({url})")
        
        return len(mismatches) == 0
        
    except Exception as e:
        print(f"❌ Erreur lors de la vérification: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Fonction principale"""
    print("🚀 VÉRIFICATION DE LA COHÉRENCE FTP vs BASE DE DONNÉES")
    print("=" * 60)
    
    print("📋 Ce script vérifie que les URLs d'images en base de données")
    print("   correspondent aux fichiers présents sur le FTP HostGator.")
    print()
    
    # Vérification de la cohérence
    success = verify_ftp_vs_database_urls()
    
    if success:
        print(f"\n🎉 COHÉRENCE PARFAITE!")
        print(f"   ✅ Tous les fichiers en base correspondent aux fichiers FTP")
        print(f"   ✅ Aucune incohérence détectée")
    else:
        print(f"\n⚠️ INCOHÉRENCES DÉTECTÉES!")
        print(f"   ❌ Certains fichiers en base ne correspondent pas aux fichiers FTP")
        print(f"   💡 Il faut corriger les URLs en base de données")
    
    print(f"\n✅ Vérification terminée!")

if __name__ == "__main__":
    main()
