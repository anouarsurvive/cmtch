#!/usr/bin/env python3
"""
Script pour tester la configuration d'upload corrigée vers HostGator.
"""

def test_upload_configuration():
    """Teste la configuration d'upload vers HostGator"""
    print("🧪 TEST DE LA CONFIGURATION D'UPLOAD:")
    
    try:
        from hostgator_photo_storage import HostGatorPhotoStorage
        
        # Créer une instance du service
        storage = HostGatorPhotoStorage()
        
        print(f"🌐 Configuration FTP:")
        print(f"   Serveur: {storage.ftp_host}")
        print(f"   Utilisateur: {storage.ftp_user}")
        print(f"   Dossier distant: {storage.remote_photos_dir}")
        print(f"   URL de base: {storage.base_url}")
        
        # Vérifier la configuration
        if "/static/article_images" in storage.remote_photos_dir:
            print("   ✅ Configuration CORRECTE - Upload vers /static/article_images/")
        else:
            print("   ❌ Configuration INCORRECTE - Upload vers mauvais dossier")
            return False
        
        if "/static/article_images" in storage.base_url:
            print("   ✅ URL de base CORRECTE - /static/article_images/")
        else:
            print("   ❌ URL de base INCORRECTE")
            return False
        
        print(f"\n🔍 Test de connexion FTP...")
        
        # Tester la connexion FTP
        try:
            import ftplib
            ftp = ftplib.FTP(storage.ftp_host)
            ftp.login(storage.ftp_user, storage.ftp_password)
            print("   ✅ Connexion FTP réussie")
            
            # Vérifier que le dossier existe
            try:
                ftp.cwd(storage.remote_photos_dir)
                print(f"   ✅ Dossier accessible: {storage.remote_photos_dir}")
                
                # Lister le contenu
                files = ftp.nlst()
                print(f"   📋 Contenu du dossier ({len(files)} fichiers):")
                for file in sorted(files):
                    if file not in {'.', '..'}:
                        print(f"     - {file}")
                
            except Exception as e:
                print(f"   ❌ Erreur accès dossier: {e}")
                return False
            
            ftp.quit()
            
        except Exception as e:
            print(f"   ❌ Erreur connexion FTP: {e}")
            return False
        
        print(f"\n🎯 RÉSUMÉ DE LA CONFIGURATION:")
        print(f"   ✅ Dossier d'upload: {storage.remote_photos_dir}")
        print(f"   ✅ URL publique: {storage.base_url}")
        print(f"   ✅ Structure FTP: /public_html/static/article_images/")
        print(f"   ✅ URL web: https://www.cmtch.online/static/article_images/")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")
        return False

def main():
    """Fonction principale"""
    print("🚀 TEST DE LA CONFIGURATION D'UPLOAD HOSTGATOR")
    print("=" * 60)
    
    success = test_upload_configuration()
    
    if success:
        print(f"\n🎉 SUCCÈS! La configuration d'upload est maintenant correcte.")
        print(f"   Maintenant, quand vous uploadez une image depuis:")
        print(f"   https://www.cmtch.online/admin/articles/modifier/3")
        print(f"   Elle sera stockée dans le BON dossier: /static/article_images/")
        print(f"   Et accessible via: https://www.cmtch.online/static/article_images/[nom_fichier]")
    else:
        print(f"\n❌ ÉCHEC! La configuration d'upload a des problèmes.")
    
    print(f"\n✅ Test terminé!")

if __name__ == "__main__":
    main()
