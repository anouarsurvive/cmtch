#!/usr/bin/env python3
"""
Script pour tester les permissions d'upload avec la nouvelle configuration.
"""

import requests
import time
from hostgator_photo_storage import HostGatorPhotoStorage

def test_upload_permissions():
    """Teste les permissions d'upload avec la nouvelle configuration"""
    print("🔧 TEST DES PERMISSIONS D'UPLOAD:")
    
    # Créer une instance du stockage
    storage = HostGatorPhotoStorage()
    
    # Créer un contenu de test (simulation d'une image)
    test_content = b"Test content for upload permissions - " + str(int(time.time())).encode()
    test_filename = "test_upload.jpg"
    
    print(f"📁 Test d'upload: {test_filename}")
    print(f"   Contenu: {len(test_content)} bytes")
    
    # Test d'upload
    success, message, public_url = storage.upload_photo(test_content, test_filename)
    
    if success:
        print(f"✅ Upload réussi!")
        print(f"   Message: {message}")
        print(f"   URL publique: {public_url}")
        
        # Attendre la synchronisation
        print(f"\n⏳ Attente de 10 secondes pour la synchronisation...")
        time.sleep(10)
        
        # Test d'accessibilité
        print(f"\n🌐 TEST D'ACCESSIBILITÉ:")
        print(f"   URL: {public_url}")
        
        try:
            response = requests.head(public_url, timeout=10)
            if response.status_code == 200:
                print(f"   ✅ {response.status_code} - Image accessible")
                print(f"   ✅ Les permissions d'upload fonctionnent correctement!")
                return True
            else:
                print(f"   ❌ {response.status_code} - Image non accessible")
                print(f"   ❌ Problème de permissions ou restriction HostGator")
                return False
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
            return False
    else:
        print(f"❌ Échec de l'upload: {message}")
        return False

def test_existing_images():
    """Teste l'accessibilité des images existantes"""
    print(f"\n🔍 TEST DES IMAGES EXISTANTES:")
    
    # Images à tester
    existing_images = [
        "default_article.jpg",
        "default_article.html",
        "default_article.svg"
    ]
    
    base_url = "https://www.cmtch.online/static/article_images/"
    
    accessible_count = 0
    
    for image_name in existing_images:
        image_url = f"{base_url}{image_name}"
        print(f"   🔍 Test de {image_name}...")
        
        try:
            response = requests.head(image_url, timeout=10)
            if response.status_code == 200:
                print(f"     ✅ {response.status_code} - Accessible")
                accessible_count += 1
            else:
                print(f"     ❌ {response.status_code} - Non accessible")
        except Exception as e:
            print(f"     ❌ Erreur: {e}")
    
    print(f"\n📊 RÉSULTAT: {accessible_count}/{len(existing_images)} images accessibles")
    return accessible_count == len(existing_images)

def main():
    """Fonction principale"""
    print("🚀 TEST DES PERMISSIONS D'UPLOAD")
    print("=" * 60)
    
    print("📋 Ce script teste:")
    print("   1. Upload avec noms simples (img_timestamp.jpg)")
    print("   2. Application des permissions 644")
    print("   3. Accessibilité des nouvelles images")
    print("   4. Accessibilité des images existantes")
    print()
    
    # Test des images existantes
    existing_ok = test_existing_images()
    
    # Test d'upload
    upload_ok = test_upload_permissions()
    
    # Résumé
    print(f"\n📊 RÉSUMÉ DES TESTS:")
    print(f"   📋 Images existantes: {'✅ OK' if existing_ok else '❌ Problème'}")
    print(f"   📋 Upload nouveau: {'✅ OK' if upload_ok else '❌ Problème'}")
    
    if existing_ok and upload_ok:
        print(f"\n🎉 TOUS LES TESTS RÉUSSIS!")
        print(f"   ✅ Les permissions d'upload sont correctement configurées")
        print(f"   ✅ Les nouvelles images seront accessibles")
        print(f"   ✅ Le système d'upload fonctionne parfaitement")
    elif existing_ok and not upload_ok:
        print(f"\n⚠️ PROBLÈME D'UPLOAD DÉTECTÉ!")
        print(f"   ✅ Les images existantes sont accessibles")
        print(f"   ❌ Les nouveaux uploads ne sont pas accessibles")
        print(f"   💡 Problème probable: restriction temporelle HostGator")
    else:
        print(f"\n❌ PROBLÈMES DÉTECTÉS!")
        print(f"   ❌ Images existantes non accessibles")
        print(f"   ❌ Upload non fonctionnel")
        print(f"   💡 Vérifier la configuration du serveur")
    
    print(f"\n✅ Test terminé!")

if __name__ == "__main__":
    main()
