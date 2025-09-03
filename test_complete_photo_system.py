#!/usr/bin/env python3
"""
Test complet du système de photos avec l'application Flask
"""

import os
import time
import requests
import sqlite3
from hostgator_photo_storage import HostGatorPhotoStorage
from photo_upload_service_hostgator import upload_photo_to_hostgator

def test_app_photo_upload():
    """Test de l'upload via l'application"""
    print("🧪 Test de l'upload via l'application...")
    
    # Créer une image de test
    test_image_content = b'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="200" height="150" xmlns="http://www.w3.org/2000/svg">
  <rect width="200" height="150" fill="#2196F3"/>
  <text x="100" y="75" text-anchor="middle" dy=".3em" fill="white" font-family="Arial" font-size="16">TEST APP</text>
</svg>'''
    
    # Simuler l'upload comme le ferait l'application
    test_filename = f"app_test_{int(time.time())}.svg"
    
    try:
        success, message, url = upload_photo_to_hostgator(test_image_content, test_filename)
        
        if success:
            print(f"✅ Upload via app réussi: {message}")
            print(f"   URL générée: {url}")
            
            # Vérifier que l'URL est bien une URL HostGator
            if "cmtch.online" in url and "static/article_images" in url:
                print("✅ URL HostGator correcte")
                return url
            else:
                print("⚠️ URL non-HostGator générée")
                return None
        else:
            print(f"❌ Échec upload via app: {message}")
            return None
            
    except Exception as e:
        print(f"❌ Erreur upload via app: {e}")
        return None

def test_database_integration():
    """Test d'intégration avec la base de données"""
    print("\n🗄️ Test d'intégration base de données...")
    
    # Créer un article de test
    conn = sqlite3.connect("cmtch.db")
    cur = conn.cursor()
    
    try:
        # Insérer un article de test
        test_title = f"Test Article {int(time.time())}"
        test_content = "Ceci est un article de test pour vérifier le système de photos."
        test_image_url = "https://www.cmtch.online/static/article_images/default_article.jpg"
        
        cur.execute("""
            INSERT INTO articles (title, content, image_path) 
            VALUES (?, ?, ?)
        """, (test_title, test_content, test_image_url))
        
        article_id = cur.lastrowid
        conn.commit()
        
        print(f"✅ Article de test créé (ID: {article_id})")
        print(f"   Titre: {test_title}")
        print(f"   Image: {test_image_url}")
        
        # Vérifier l'insertion
        cur.execute("SELECT id, title, image_path FROM articles WHERE id = ?", (article_id,))
        article = cur.fetchone()
        
        if article:
            print(f"✅ Article récupéré: {article}")
            
            # Nettoyer - supprimer l'article de test
            cur.execute("DELETE FROM articles WHERE id = ?", (article_id,))
            conn.commit()
            print(f"✅ Article de test supprimé")
            
            return True
        else:
            print("❌ Article non trouvé")
            return False
            
    except Exception as e:
        print(f"❌ Erreur base de données: {e}")
        return False
    finally:
        conn.close()

def test_image_serving():
    """Test du service d'images de l'application"""
    print("\n🖼️ Test du service d'images...")
    
    # Tester l'image par défaut
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

def test_fallback_system():
    """Test du système de fallback"""
    print("\n🔄 Test du système de fallback...")
    
    # Tester avec un fichier invalide
    invalid_content = b"Ceci n'est pas une image valide"
    invalid_filename = "invalid_test.txt"
    
    try:
        success, message, url = upload_photo_to_hostgator(invalid_content, invalid_filename)
        
        if success:
            print(f"✅ Fallback fonctionne: {message}")
            print(f"   URL de fallback: {url}")
            
            # Vérifier que c'est bien l'image par défaut
            if "default_article.jpg" in url:
                print("✅ Image par défaut utilisée en fallback")
                return True
            else:
                print("⚠️ Fallback n'utilise pas l'image par défaut")
                return False
        else:
            print(f"❌ Fallback échoué: {message}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur test fallback: {e}")
        return False

def test_article_creation_workflow():
    """Test du workflow complet de création d'article"""
    print("\n📝 Test du workflow création d'article...")
    
    # Simuler la création d'un article avec image
    test_image_content = b'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="300" height="200" xmlns="http://www.w3.org/2000/svg">
  <rect width="300" height="200" fill="#4CAF50"/>
  <text x="150" y="100" text-anchor="middle" dy=".3em" fill="white" font-family="Arial" font-size="20">WORKFLOW TEST</text>
</svg>'''
    
    test_filename = f"workflow_test_{int(time.time())}.svg"
    
    try:
        # 1. Upload de l'image
        success, message, image_url = upload_photo_to_hostgator(test_image_content, test_filename)
        
        if not success:
            print("❌ Échec upload image pour workflow")
            return False
        
        print(f"✅ Image uploadée: {image_url}")
        
        # 2. Création de l'article en base
        conn = sqlite3.connect("cmtch.db")
        cur = conn.cursor()
        
        test_title = f"Workflow Test {int(time.time())}"
        test_content = "Article créé via le workflow de test complet."
        
        cur.execute("""
            INSERT INTO articles (title, content, image_path) 
            VALUES (?, ?, ?)
        """, (test_title, test_content, image_url))
        
        article_id = cur.lastrowid
        conn.commit()
        
        print(f"✅ Article créé (ID: {article_id})")
        
        # 3. Vérification
        cur.execute("SELECT id, title, image_path FROM articles WHERE id = ?", (article_id,))
        article = cur.fetchone()
        
        if article and article[2] == image_url:
            print(f"✅ Article vérifié: {article}")
            
            # 4. Nettoyage
            cur.execute("DELETE FROM articles WHERE id = ?", (article_id,))
            conn.commit()
            print(f"✅ Article de test supprimé")
            
            conn.close()
            return True
        else:
            print("❌ Vérification article échouée")
            conn.close()
            return False
            
    except Exception as e:
        print(f"❌ Erreur workflow: {e}")
        return False

def main():
    """Fonction principale de test"""
    print("🧪 Test complet du système de photos HostGator")
    print("=" * 60)
    
    tests = [
        ("Upload via application", test_app_photo_upload),
        ("Intégration base de données", test_database_integration),
        ("Service d'images", test_image_serving),
        ("Système de fallback", test_fallback_system),
        ("Workflow création article", test_article_creation_workflow)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Erreur inattendue: {e}")
            results.append((test_name, False))
    
    # Résumé
    print(f"\n{'='*60}")
    print("📊 RÉSUMÉ DES TESTS")
    print(f"{'='*60}")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSÉ" if result else "❌ ÉCHOUÉ"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Résultat: {passed}/{total} tests passés")
    
    if passed == total:
        print("🎉 Tous les tests sont passés ! Le système de photos HostGator est opérationnel.")
    else:
        print("⚠️ Certains tests ont échoué. Vérifiez la configuration.")
    
    print(f"\n💡 Prochaines étapes:")
    print("   1. Déployer l'application sur Render")
    print("   2. Tester l'upload d'images en production")
    print("   3. Vérifier l'affichage des images sur le site")

if __name__ == "__main__":
    main()
