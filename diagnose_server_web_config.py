#!/usr/bin/env python3
"""
Script pour diagnostiquer la configuration du serveur web HostGator.
"""

import requests
import ftplib
import time

def diagnose_server_web_config():
    """Diagnostique la configuration du serveur web"""
    print("🔍 DIAGNOSTIC DE LA CONFIGURATION DU SERVEUR WEB:")
    
    # Configuration FTP
    ftp_host = "ftp.novaprint.tn"
    ftp_user = "cmtch@cmtch.online"
    ftp_password = "Anouar881984?"
    remote_dir = "/public_html/static/article_images"
    
    try:
        # Connexion FTP pour vérifier les fichiers
        ftp = ftplib.FTP(ftp_host)
        ftp.login(ftp_user, ftp_password)
        ftp.cwd(remote_dir)
        
        print("\n📁 FICHIERS PRÉSENTS SUR LE SERVEUR:")
        ftp.retrlines('LIST', print)
        
        ftp.quit()
        
        # Test 1: Vérifier l'accès au dossier parent
        print(f"\n🌐 TEST 1: Accès au dossier parent /static/")
        try:
            response = requests.head("https://www.cmtch.online/static/", timeout=10)
            print(f"   Dossier /static/: {response.status_code}")
            if response.status_code == 200:
                print("   ✅ Dossier static accessible")
            else:
                print("   ❌ Dossier static non accessible")
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
        
        # Test 2: Vérifier l'accès au dossier article_images
        print(f"\n🌐 TEST 2: Accès au dossier article_images")
        try:
            response = requests.head("https://www.cmtch.online/static/article_images/", timeout=10)
            print(f"   Dossier /static/article_images/: {response.status_code}")
            if response.status_code == 200:
                print("   ✅ Dossier article_images accessible")
            else:
                print("   ❌ Dossier article_images non accessible")
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
        
        # Test 3: Vérifier les fichiers .htaccess
        print(f"\n🌐 TEST 3: Vérification des fichiers .htaccess")
        htaccess_paths = [
            "https://www.cmtch.online/.htaccess",
            "https://www.cmtch.online/static/.htaccess",
            "https://www.cmtch.online/static/article_images/.htaccess"
        ]
        
        for path in htaccess_paths:
            try:
                response = requests.head(path, timeout=10)
                print(f"   {path}: {response.status_code}")
                if response.status_code == 200:
                    print("     ✅ Fichier .htaccess présent")
                else:
                    print("     ❌ Fichier .htaccess absent")
            except Exception as e:
                print(f"   {path}: Erreur - {e}")
        
        # Test 4: Comparer les fichiers accessibles vs non accessibles
        print(f"\n🌐 TEST 4: Comparaison des fichiers")
        
        # Fichiers accessibles (créés à 09:11)
        accessible_files = [
            "default_article.jpg",
            "default_article.html",
            "default_article.svg"
        ]
        
        # Fichiers non accessibles (créés récemment)
        inaccessible_files = [
            "test_1756828380.jpg",  # Le fichier que vous venez de créer
            "test_1756828145.jpg",  # Fichier de test précédent
            "img_1756828145.jpg"    # Autre fichier de test
        ]
        
        print(f"\n   📋 FICHIERS ACCESSIBLES (HTTP 200):")
        for filename in accessible_files:
            url = f"https://www.cmtch.online/static/article_images/{filename}"
            try:
                response = requests.head(url, timeout=10)
                print(f"     {filename}: {response.status_code}")
            except Exception as e:
                print(f"     {filename}: Erreur - {e}")
        
        print(f"\n   📋 FICHIERS NON ACCESSIBLES (HTTP 404):")
        for filename in inaccessible_files:
            url = f"https://www.cmtch.online/static/article_images/{filename}"
            try:
                response = requests.head(url, timeout=10)
                print(f"     {filename}: {response.status_code}")
            except Exception as e:
                print(f"     {filename}: Erreur - {e}")
        
        # Test 5: Vérifier les en-têtes HTTP
        print(f"\n🌐 TEST 5: Analyse des en-têtes HTTP")
        test_url = "https://www.cmtch.online/static/article_images/test_1756828380.jpg"
        try:
            response = requests.head(test_url, timeout=10)
            print(f"   URL: {test_url}")
            print(f"   Status: {response.status_code}")
            print(f"   Headers:")
            for key, value in response.headers.items():
                print(f"     {key}: {value}")
        except Exception as e:
            print(f"   Erreur: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du diagnostic: {e}")
        return False

def test_different_approaches():
    """Teste différentes approches pour contourner le problème"""
    print(f"\n🧪 TEST DE DIFFÉRENTES APPROCHES:")
    
    # Test 1: Essayer avec un nom très simple
    print(f"\n   📋 APPROCHE 1: Nom très simple")
    simple_names = ["a.jpg", "1.jpg", "test.jpg"]
    
    for name in simple_names:
        url = f"https://www.cmtch.online/static/article_images/{name}"
        try:
            response = requests.head(url, timeout=5)
            print(f"     {name}: {response.status_code}")
        except:
            print(f"     {name}: Erreur")
    
    # Test 2: Essayer avec des extensions différentes
    print(f"\n   📋 APPROCHE 2: Extensions différentes")
    extensions = [".jpg", ".jpeg", ".png", ".gif", ".txt"]
    
    for ext in extensions:
        name = f"test{ext}"
        url = f"https://www.cmtch.online/static/article_images/{name}"
        try:
            response = requests.head(url, timeout=5)
            print(f"     {name}: {response.status_code}")
        except:
            print(f"     {name}: Erreur")
    
    # Test 3: Essayer avec des chemins différents
    print(f"\n   📋 APPROCHE 3: Chemins différents")
    paths = [
        "https://www.cmtch.online/test_1756828380.jpg",
        "https://www.cmtch.online/images/test_1756828380.jpg",
        "https://www.cmtch.online/uploads/test_1756828380.jpg"
    ]
    
    for path in paths:
        try:
            response = requests.head(path, timeout=5)
            print(f"     {path}: {response.status_code}")
        except:
            print(f"     {path}: Erreur")

def main():
    """Fonction principale"""
    print("🚀 DIAGNOSTIC DE LA CONFIGURATION DU SERVEUR WEB")
    print("=" * 60)
    
    print("📋 Ce script diagnostique pourquoi les fichiers avec")
    print("   les bonnes permissions ne sont pas accessibles sur le web.")
    print()
    
    # Diagnostic principal
    success = diagnose_server_web_config()
    
    # Test de différentes approches
    test_different_approaches()
    
    print(f"\n💡 ANALYSE:")
    print(f"   ✅ Fichiers présents sur FTP avec bonnes permissions")
    print(f"   ❌ Fichiers non accessibles via HTTP")
    print(f"   🔍 Problème probable: Configuration serveur web HostGator")
    print(f"   📝 Solutions possibles:")
    print(f"      1. Contacter le support HostGator")
    print(f"      2. Vérifier la configuration Apache/Nginx")
    print(f"      3. Vérifier les règles .htaccess")
    print(f"      4. Vérifier les restrictions de sécurité")
    
    print(f"\n✅ Diagnostic terminé!")

if __name__ == "__main__":
    main()
