#!/usr/bin/env python3
"""
Script pour diagnostiquer la configuration du serveur web HostGator.
"""

import requests
import ftplib
import os

def diagnose_server_config():
    """Diagnostique la configuration du serveur web"""
    print("🔍 DIAGNOSTIC DE LA CONFIGURATION DU SERVEUR:")
    
    # Test 1: Vérifier l'accès au dossier static
    print("\n📁 TEST 1: Accès au dossier static")
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
    print("\n📁 TEST 2: Accès au dossier article_images")
    try:
        response = requests.head("https://www.cmtch.online/static/article_images/", timeout=10)
        print(f"   Dossier /static/article_images/: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Dossier article_images accessible")
        else:
            print("   ❌ Dossier article_images non accessible")
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
    
    # Test 3: Vérifier l'accès à un fichier .htaccess
    print("\n📁 TEST 3: Vérification .htaccess")
    try:
        response = requests.head("https://www.cmtch.online/static/.htaccess", timeout=10)
        print(f"   Fichier .htaccess: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Fichier .htaccess présent")
        else:
            print("   ❌ Fichier .htaccess absent ou non accessible")
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
    
    # Test 4: Vérifier l'accès à un fichier index
    print("\n📁 TEST 4: Vérification index")
    try:
        response = requests.head("https://www.cmtch.online/static/index.html", timeout=10)
        print(f"   Fichier index.html: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Fichier index.html présent")
        else:
            print("   ❌ Fichier index.html absent")
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
    
    # Test 5: Vérifier les permissions via FTP
    print("\n📁 TEST 5: Vérification des permissions via FTP")
    try:
        ftp = ftplib.FTP("ftp.novaprint.tn")
        ftp.login("cmtch@cmtch.online", "Anouar881984?")
        
        # Aller dans le dossier article_images
        ftp.cwd('/public_html/static/article_images')
        
        # Lister avec détails
        print("   📋 Contenu du dossier avec détails:")
        ftp.retrlines('LIST', print)
        
        ftp.quit()
        
    except Exception as e:
        print(f"   ❌ Erreur FTP: {e}")
    
    # Test 6: Tester différents types de fichiers
    print("\n📁 TEST 6: Test de différents types de fichiers")
    test_files = [
        "default_article.jpg",
        "default_article.html", 
        "default_article.svg",
        "test_permissions.txt"
    ]
    
    for file_name in test_files:
        try:
            url = f"https://www.cmtch.online/static/article_images/{file_name}"
            response = requests.head(url, timeout=10)
            print(f"   {file_name}: {response.status_code}")
        except Exception as e:
            print(f"   {file_name}: Erreur - {e}")

def main():
    """Fonction principale"""
    print("🚀 DIAGNOSTIC DE LA CONFIGURATION DU SERVEUR")
    print("=" * 60)
    
    print("📋 Ce script va diagnostiquer pourquoi les images ne sont pas accessibles")
    print("   malgré leur présence dans le dossier FTP.")
    print()
    
    diagnose_server_config()
    
    print(f"\n💡 ANALYSE:")
    print(f"   - Si seul default_article.jpg est accessible, c'est un problème de configuration")
    print(f"   - Si aucun fichier n'est accessible, c'est un problème de permissions")
    print(f"   - Si tous les fichiers sont accessibles, le problème est résolu")
    
    print(f"\n✅ Diagnostic terminé!")

if __name__ == "__main__":
    main()
