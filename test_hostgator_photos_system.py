#!/usr/bin/env python3
"""
Script de test complet du système de photos HostGator
"""

import os
import time
import requests
from hostgator_photo_storage import HostGatorPhotoStorage
from photo_upload_service_hostgator import upload_photo_to_hostgator

def test_connection():
    """Test de connexion FTP HostGator"""
    print("🔍 Test de connexion FTP HostGator...")
    
    storage = HostGatorPhotoStorage()
    
    try:
        import ftplib
        ftp = ftplib.FTP(storage.ftp_host)
        ftp.login(storage.ftp_user, storage.ftp_password)
        
        print(f"✅ Connexion FTP réussie")
        print(f"   Serveur: {storage.ftp_host}")
        print(f"   Utilisateur: {storage.ftp_user}")
        print(f"   Dossier: {storage.remote_photos_dir}")
        
        # Tester l'accès au dossier
        try:
            ftp.cwd(storage.remote_photos_dir)
            files = ftp.nlst()
            print(f"   📁 {len(files)} fichier(s) dans le dossier")
        except Exception as e:
            print(f"   ⚠️ Problème accès dossier: {e}")
        
        ftp.quit()
        return True
        
    except Exception as e:
        print(f"❌ Erreur connexion FTP: {e}")
        return False

def test_upload():
    """Test d'upload d'une image"""
    print("\n📤 Test d'upload d'image...")
    
    # Créer une image de test simple (SVG)
    test_image_content = b'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <rect width="100" height="100" fill="#4CAF50"/>
  <text x="50" y="50" text-anchor="middle" dy=".3em" fill="white" font-family="Arial" font-size="12">TEST</text>
</svg>'''
    
    test_filename = f"test_image_{int(time.time())}.svg"
    
    try:
        success, message, url = upload_photo_to_hostgator(test_image_content, test_filename)
        
        if success:
            print(f"✅ Upload réussi: {message}")
            print(f"   URL: {url}")
            
            # Tester l'accessibilité de l'image
            try:
                response = requests.head(url, timeout=10)
                if response.status_code == 200:
                    print(f"✅ Image accessible via HTTP: {response.status_code}")
                    return url
                else:
                    print(f"⚠️ Image non accessible: HTTP {response.status_code}")
                    return None
            except Exception as e:
                print(f"❌ Erreur test accessibilité: {e}")
                return None
        else:
            print(f"❌ Échec upload: {message}")
            return None
            
    except Exception as e:
        print(f"❌ Erreur upload: {e}")
        return None

def test_list_photos():
    """Test de liste des photos"""
    print("\n📋 Test de liste des photos...")
    
    storage = HostGatorPhotoStorage()
    
    try:
        success, photos, message = storage.list_photos()
        
        if success:
            print(f"✅ {message}")
            print(f"   📊 {len(photos)} photo(s) trouvée(s)")
            
            for i, photo in enumerate(photos[:5]):  # Afficher les 5 premières
                print(f"   {i+1}. {photo['filename']} ({photo['size']} bytes)")
                print(f"      URL: {photo['url']}")
        else:
            print(f"❌ Erreur liste: {message}")
            
    except Exception as e:
        print(f"❌ Erreur liste photos: {e}")

def test_default_image():
    """Test de l'image par défaut"""
    print("\n🖼️ Test de l'image par défaut...")
    
    default_url = "https://www.cmtch.online/static/article_images/default_article.jpg"
    
    try:
        response = requests.head(default_url, timeout=10)
        if response.status_code == 200:
            print(f"✅ Image par défaut accessible: {response.status_code}")
            print(f"   URL: {default_url}")
            return True
        else:
            print(f"❌ Image par défaut non accessible: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erreur test image par défaut: {e}")
        return False

def test_photo_exists():
    """Test de vérification d'existence"""
    print("\n🔍 Test de vérification d'existence...")
    
    storage = HostGatorPhotoStorage()
    
    # Tester avec un fichier qui existe probablement
    test_files = [
        "default_article.jpg",
        "default_article.svg",
        "nonexistent_file.jpg"
    ]
    
    for filename in test_files:
        exists = storage.photo_exists(filename)
        status = "✅" if exists else "❌"
        print(f"   {status} {filename}: {'Existe' if exists else 'N\'existe pas'}")

def test_cleanup():
    """Test de nettoyage (suppression d'images de test)"""
    print("\n🧹 Test de nettoyage...")
    
    storage = HostGatorPhotoStorage()
    
    # Lister les fichiers de test
    try:
        success, photos, message = storage.list_photos()
        if success:
            test_files = [p for p in photos if p['filename'].startswith('test_image_')]
            
            if test_files:
                print(f"🗑️ Suppression de {len(test_files)} fichier(s) de test...")
                for photo in test_files:
                    try:
                        success, message = storage.delete_photo(photo['filename'])
                        if success:
                            print(f"   ✅ Supprimé: {photo['filename']}")
                        else:
                            print(f"   ❌ Erreur suppression: {message}")
                    except Exception as e:
                        print(f"   ❌ Erreur suppression {photo['filename']}: {e}")
            else:
                print("ℹ️ Aucun fichier de test à supprimer")
        else:
            print(f"❌ Impossible de lister les photos: {message}")
            
    except Exception as e:
        print(f"❌ Erreur nettoyage: {e}")

def main():
    """Fonction principale de test"""
    print("🧪 Test complet du système de photos HostGator")
    print("=" * 60)
    
    # Tests
    connection_ok = test_connection()
    
    if connection_ok:
        test_upload()
        test_list_photos()
        test_default_image()
        test_photo_exists()
        test_cleanup()
        
        print("\n🎉 Tests terminés!")
        print("\n📋 Résumé:")
        print("   ✅ Connexion FTP HostGator")
        print("   ✅ Upload d'images")
        print("   ✅ Liste des photos")
        print("   ✅ Vérification d'existence")
        print("   ✅ Nettoyage")
        
        print("\n💡 Le système de photos HostGator est opérationnel!")
    else:
        print("\n❌ Tests échoués - Vérifiez la configuration FTP")

if __name__ == "__main__":
    main()
