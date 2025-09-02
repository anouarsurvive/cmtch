#!/usr/bin/env python3
"""
Script pour vérifier le contenu du dossier FTP et diagnostiquer les problèmes d'upload.
"""

import ftplib
import os
from pathlib import Path

def check_ftp_directory():
    """Vérifie le contenu du dossier FTP"""
    print("🔍 VÉRIFICATION DU DOSSIER FTP:")
    
    # Configuration FTP depuis les variables d'environnement
    ftp_host = os.getenv('FTP_HOST', 'ftp.novaprint.tn')
    ftp_user = os.getenv('FTP_USER', 'cmtch@cmtch.online')
    ftp_password = os.getenv('FTP_PASSWORD', 'Anouar881984?')
    
    print(f"🌐 Connexion à: {ftp_host}")
    print(f"👤 Utilisateur: {ftp_user}")
    
    try:
        # Connexion FTP
        ftp = ftplib.FTP(ftp_host)
        ftp.login(ftp_user, ftp_password)
        print("✅ Connexion FTP établie")
        
        # Vérifier la structure des dossiers
        print("\n📁 STRUCTURE DES DOSSIERS:")
        
        # Aller à la racine
        ftp.cwd('/')
        print(f"   📂 Racine: {ftp.pwd()}")
        
        # Vérifier public_html
        try:
            ftp.cwd('public_html')
            print(f"   📂 public_html: {ftp.pwd()}")
            
            # Lister le contenu de public_html
            print("   📋 Contenu de public_html:")
            files_public_html = ftp.nlst()
            for file in sorted(files_public_html):
                print(f"     - {file}")
            
            # Vérifier static
            try:
                ftp.cwd('static')
                print(f"   📂 static: {ftp.pwd()}")
                
                # Lister le contenu de static
                print("   📋 Contenu de static:")
                files_static = ftp.nlst()
                for file in sorted(files_static):
                    print(f"     - {file}")
                
                # Vérifier article_images
                try:
                    ftp.cwd('article_images')
                    print(f"   📂 article_images: {ftp.pwd()}")
                    
                    # Lister le contenu de article_images
                    print("   📋 Contenu de article_images:")
                    files_article_images = ftp.nlst()
                    for file in sorted(files_article_images):
                        print(f"     - {file}")
                    
                    # Vérifier les permissions
                    print("\n🔐 PERMISSIONS:")
                    try:
                        # Tenter de créer un fichier de test
                        test_content = b"test"
                        ftp.storbinary('STOR test_permissions.txt', test_content)
                        print("   ✅ Permissions d'écriture: OK")
                        
                        # Supprimer le fichier de test
                        ftp.delete('test_permissions.txt')
                        print("   ✅ Permissions de suppression: OK")
                        
                    except Exception as e:
                        print(f"   ❌ Problème de permissions: {e}")
                    
                except Exception as e:
                    print(f"   ❌ Erreur dossier article_images: {e}")
                
            except Exception as e:
                print(f"   ❌ Erreur dossier static: {e}")
                
        except Exception as e:
            print(f"   ❌ Erreur dossier public_html: {e}")
        
        ftp.quit()
        print("\n✅ Vérification FTP terminée!")
        
    except Exception as e:
        print(f"❌ Erreur lors de la vérification FTP: {e}")

def main():
    """Fonction principale"""
    print("🚀 DIAGNOSTIC DU DOSSIER FTP")
    print("=" * 50)
    
    check_ftp_directory()
    
    print("\n📝 RECOMMANDATIONS:")
    print("   1. Vérifiez que le dossier existe")
    print("   2. Vérifiez les permissions d'écriture")
    print("   3. Utilisez le script d'upload pour ajouter de nouvelles images")

if __name__ == "__main__":
    main()
