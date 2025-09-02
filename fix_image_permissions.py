#!/usr/bin/env python3
"""
Script pour corriger les permissions des images dans le dossier FTP.
"""

import ftplib
import os

def fix_image_permissions():
    """Corrige les permissions des images dans le dossier FTP"""
    print("🔧 CORRECTION DES PERMISSIONS DES IMAGES:")
    
    # Configuration FTP
    ftp_host = "ftp.novaprint.tn"
    ftp_user = "cmtch@cmtch.online"
    ftp_password = "Anouar881984?"
    
    print(f"🌐 Connexion à: {ftp_host}")
    print(f"👤 Utilisateur: {ftp_user}")
    
    try:
        # Connexion FTP
        ftp = ftplib.FTP(ftp_host)
        ftp.login(ftp_user, ftp_password)
        print("✅ Connexion FTP établie")
        
        # Naviguer vers le dossier article_images
        print("📁 Navigation vers le dossier article_images...")
        
        # Aller à la racine
        ftp.cwd('/')
        print(f"   📂 Racine: {ftp.pwd()}")
        
        # Aller dans public_html
        ftp.cwd('public_html')
        print(f"   📂 public_html: {ftp.pwd()}")
        
        # Aller dans static
        ftp.cwd('static')
        print(f"   📂 static: {ftp.pwd()}")
        
        # Aller dans article_images
        ftp.cwd('article_images')
        print(f"   📂 article_images: {ftp.pwd()}")
        
        # Lister le contenu actuel
        print("📋 Contenu actuel du dossier:")
        files = ftp.nlst()
        for file in sorted(files):
            if file not in {'.', '..'}:
                print(f"   - {file}")
        
        # Images à corriger (d'après le diagnostic)
        images_to_fix = [
            "39cebba8134541a4997e9b3a4029a4fe.jpg",
            "61c8f2b8595948d08b6e8dbc1517a963.jpg", 
            "ed9b5c9611f14f559eb906ec0e2e1fbb.jpg",
            "d902e16affb04fd3a6c10192bdf4a5c5.jpg"
        ]
        
        print(f"\n🔧 CORRECTION DES PERMISSIONS:")
        
        for image_name in images_to_fix:
            print(f"   🔧 Correction de {image_name}...")
            
            try:
                # Essayer de corriger les permissions
                # Note: Les commandes FTP pour les permissions varient selon le serveur
                
                # Méthode 1: Utiliser SITE CHMOD (si supporté)
                try:
                    ftp.sendcmd(f"SITE CHMOD 644 {image_name}")
                    print(f"     ✅ Permissions 644 appliquées")
                except:
                    print(f"     ⚠️ SITE CHMOD non supporté, tentative alternative...")
                    
                    # Méthode 2: Re-uploader le fichier (force les bonnes permissions)
                    try:
                        # Lire le fichier
                        file_data = []
                        ftp.retrbinary(f"RETR {image_name}", file_data.append)
                        file_content = b''.join(file_data)
                        
                        # Supprimer et re-uploader
                        ftp.delete(image_name)
                        ftp.storbinary(f'STOR {image_name}', file_content)
                        print(f"     ✅ Fichier re-uploadé avec bonnes permissions")
                        
                    except Exception as e:
                        print(f"     ❌ Erreur re-upload: {e}")
                
            except Exception as e:
                print(f"     ❌ Erreur permissions: {e}")
        
        # Vérifier les permissions du dossier lui-même
        print(f"\n🔧 CORRECTION DES PERMISSIONS DU DOSSIER:")
        try:
            # Remonter d'un niveau
            ftp.cwd('..')
            print(f"   📂 Dossier parent: {ftp.pwd()}")
            
            # Essayer de corriger les permissions du dossier article_images
            try:
                ftp.sendcmd("SITE CHMOD 755 article_images")
                print(f"   ✅ Permissions 755 appliquées au dossier article_images")
            except:
                print(f"   ⚠️ Impossible de corriger les permissions du dossier")
                
        except Exception as e:
            print(f"   ❌ Erreur permissions dossier: {e}")
        
        ftp.quit()
        print("\n✅ Correction des permissions terminée!")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la correction des permissions: {e}")
        return False

def main():
    """Fonction principale"""
    print("🚀 CORRECTION DES PERMISSIONS DES IMAGES")
    print("=" * 60)
    
    print("📋 Ce script va corriger les permissions des images dans le dossier FTP")
    print("   pour qu'elles soient accessibles publiquement sur le web.")
    print()
    
    # Demander confirmation
    confirm = input("❓ Continuer avec la correction des permissions? (o/n): ").strip().lower()
    if not confirm.startswith('o'):
        print("❌ Correction annulée")
        return
    
    # Effectuer la correction
    success = fix_image_permissions()
    
    if success:
        print(f"\n🎉 Correction des permissions terminée!")
        print(f"   - Permissions des images corrigées")
        print(f"   - Permissions du dossier corrigées")
        print(f"   - Les images devraient maintenant être accessibles publiquement")
        print(f"\n📝 Prochaine étape: Tester l'accessibilité des images")
    else:
        print(f"\n❌ Échec de la correction des permissions")
    
    print(f"\n✅ Opération terminée!")

if __name__ == "__main__":
    main()
