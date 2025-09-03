#!/usr/bin/env python3
"""
Script pour tester les URLs directes HostGator.
"""

import requests
import sys
import os

# Ajouter le répertoire courant au path pour importer database
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

def test_hostgator_direct_urls():
    """Teste les URLs directes HostGator"""
    print("🔧 TEST DES URLs DIRECTES HOSTGATOR:")
    
    try:
        conn = get_db_connection()
        
        if not hasattr(conn, '_is_mysql'):
            print("❌ Connexion SQLite établie (pas MySQL)")
            return False
        
        cur = conn.cursor()
        
        # Récupérer les articles avec leurs nouvelles URLs
        print("\n📊 ARTICLES AVEC URLs HOSTGATOR:")
        cur.execute("SELECT id, title, image_path FROM articles ORDER BY id")
        articles = cur.fetchall()
        
        accessible_count = 0
        total_count = len(articles)
        
        for article in articles:
            article_id, title, image_path = article
            print(f"\n   Article {article_id}: {title}")
            print(f"     URL: {image_path}")
            
            # Tester l'accessibilité de l'image
            try:
                response = requests.head(image_path, timeout=10)
                if response.status_code == 200:
                    print(f"     ✅ {response.status_code} - Image accessible")
                    accessible_count += 1
                else:
                    print(f"     ❌ {response.status_code} - Image non accessible")
            except Exception as e:
                print(f"     ❌ Erreur: {e}")
        
        conn.close()
        
        # Résumé
        print(f"\n📊 RÉSUMÉ:")
        print(f"   📋 Total articles: {total_count}")
        print(f"   ✅ Images accessibles: {accessible_count}")
        print(f"   ❌ Images non accessibles: {total_count - accessible_count}")
        
        if accessible_count == total_count:
            print(f"\n🎉 SUCCÈS COMPLET!")
            print(f"   ✅ Toutes les images sont accessibles via HostGator")
            print(f"   ✅ La solution URL directe fonctionne")
            return True
        elif accessible_count > 0:
            print(f"\n⚠️ SUCCÈS PARTIEL!")
            print(f"   ✅ {accessible_count}/{total_count} images accessibles")
            print(f"   ⚠️ Certaines images ne sont pas accessibles")
            return False
        else:
            print(f"\n❌ ÉCHEC!")
            print(f"   ❌ Aucune image accessible")
            print(f"   💡 Vérifier la configuration HostGator")
            return False
        
    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")
        return False

def test_new_upload_with_hostgator():
    """Teste l'upload avec le nouveau service HostGator"""
    print(f"\n🔧 TEST D'UPLOAD AVEC SERVICE HOSTGATOR:")
    
    try:
        # Import dynamique pour éviter les problèmes de résolution
        import importlib.util
        import sys
        
        # Chemin vers le module
        module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'photo_upload_service_hostgator.py')
        
        if not os.path.exists(module_path):
            print(f"   ❌ Module non trouvé: {module_path}")
            return False
        
        # Charger le module dynamiquement
        spec = importlib.util.spec_from_file_location("photo_upload_service_hostgator", module_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["photo_upload_service_hostgator"] = module
        spec.loader.exec_module(module)
        
        # Utiliser la fonction du module
        upload_photo_to_hostgator = module.upload_photo_to_hostgator
        
        # Créer un contenu de test
        test_content = b"Test content for HostGator direct URL - " + str(int(__import__('time').time())).encode()
        test_filename = "test_hostgator_direct.jpg"
        
        print(f"   📁 Test d'upload: {test_filename}")
        print(f"   📄 Contenu: {len(test_content)} bytes")
        
        # Test d'upload
        success, message, public_url = upload_photo_to_hostgator(test_content, test_filename)
        
        if success:
            print(f"   ✅ Upload réussi!")
            print(f"   📝 Message: {message}")
            print(f"   🔗 URL: {public_url}")
            
            # Tester l'accessibilité
            try:
                response = requests.head(public_url, timeout=10)
                if response.status_code == 200:
                    print(f"   ✅ {response.status_code} - Image accessible")
                    print(f"   🎉 Service d'upload HostGator fonctionne!")
                    return True
                else:
                    print(f"   ❌ {response.status_code} - Image non accessible")
                    return False
            except Exception as e:
                print(f"   ❌ Erreur test accessibilité: {e}")
                return False
        else:
            print(f"   ❌ Échec de l'upload: {message}")
            return False
            
    except Exception as e:
        print(f"   ❌ Erreur import service: {e}")
        return False

def main():
    """Fonction principale"""
    print("🚀 TEST DES URLs DIRECTES HOSTGATOR")
    print("=" * 60)
    
    print("📋 Ce script teste:")
    print("   1. Accessibilité des images via URLs directes HostGator")
    print("   2. Fonctionnement du service d'upload HostGator")
    print()
    
    # Test des URLs directes
    urls_ok = test_hostgator_direct_urls()
    
    # Test d'upload
    upload_ok = test_new_upload_with_hostgator()
    
    # Résumé final
    print(f"\n📊 RÉSUMÉ FINAL:")
    print(f"   📋 URLs directes: {'✅ OK' if urls_ok else '❌ Problème'}")
    print(f"   📋 Upload service: {'✅ OK' if upload_ok else '❌ Problème'}")
    
    if urls_ok and upload_ok:
        print(f"\n🎉 SOLUTION COMPLÈTE RÉUSSIE!")
        print(f"   ✅ URLs directes HostGator fonctionnent")
        print(f"   ✅ Service d'upload fonctionne")
        print(f"   ✅ Site web entièrement fonctionnel")
        print(f"   ✅ Plus d'erreurs 404 sur les images")
    elif urls_ok:
        print(f"\n⚠️ SOLUTION PARTIELLE!")
        print(f"   ✅ URLs directes fonctionnent")
        print(f"   ❌ Service d'upload a des problèmes")
        print(f"   💡 Vérifier la configuration d'upload")
    else:
        print(f"\n❌ SOLUTION INCOMPLÈTE!")
        print(f"   ❌ URLs directes ne fonctionnent pas")
        print(f"   💡 Vérifier la configuration HostGator")
    
    print(f"\n✅ Test terminé!")

if __name__ == "__main__":
    main()
