#!/usr/bin/env python3
"""
Script pour tester l'accessibilité des images sur le web.
"""

import requests
import time

def test_image_accessibility():
    """Teste l'accessibilité des images sur le web"""
    print("🔍 TEST D'ACCESSIBILITÉ DES IMAGES:")
    
    # Images à tester (d'après le diagnostic FTP)
    images_to_test = [
        "39cebba8134541a4997e9b3a4029a4fe.jpg",
        "61c8f2b8595948d08b6e8dbc1517a963.jpg", 
        "ed9b5c9611f14f559eb906ec0e2e1fbb.jpg",
        "d902e16affb04fd3a6c10192bdf4a5c5.jpg",
        "default_article.jpg"
    ]
    
    base_url = "https://www.cmtch.online/static/article_images/"
    
    print(f"🌐 Test des images sur: {base_url}")
    print()
    
    results = []
    
    for image_name in images_to_test:
        image_url = f"{base_url}{image_name}"
        print(f"🔍 Test de {image_name}...")
        
        try:
            # Test avec HEAD request (plus rapide)
            response = requests.head(image_url, timeout=10)
            status_code = response.status_code
            
            if status_code == 200:
                print(f"   ✅ {status_code} - Image accessible")
                results.append({"image": image_name, "status": "accessible", "code": status_code})
            else:
                print(f"   ❌ {status_code} - Image non accessible")
                results.append({"image": image_name, "status": "error", "code": status_code})
                
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Erreur: {e}")
            results.append({"image": image_name, "status": "error", "code": "exception"})
        
        # Petite pause entre les tests
        time.sleep(0.5)
    
    # Résumé des résultats
    print(f"\n📊 RÉSUMÉ DES TESTS:")
    accessible_count = sum(1 for r in results if r["status"] == "accessible")
    error_count = sum(1 for r in results if r["status"] == "error")
    
    print(f"   ✅ Images accessibles: {accessible_count}")
    print(f"   ❌ Images avec erreur: {error_count}")
    
    if error_count > 0:
        print(f"\n🚨 IMAGES AVEC PROBLÈMES:")
        for result in results:
            if result["status"] == "error":
                print(f"   - {result['image']}: {result['code']}")
    
    return results

def main():
    """Fonction principale"""
    print("🚀 TEST D'ACCESSIBILITÉ DES IMAGES")
    print("=" * 50)
    
    print("📋 Ce script teste l'accessibilité de toutes les images")
    print("   qui sont dans le dossier FTP mais qui peuvent retourner 404.")
    print()
    
    results = test_image_accessibility()
    
    print(f"\n✅ Test terminé!")
    
    # Recommandations
    if any(r["status"] == "error" for r in results):
        print(f"\n💡 RECOMMANDATIONS:")
        print(f"   1. Vérifier les permissions du dossier /static/article_images/")
        print(f"   2. Vérifier la configuration du serveur web")
        print(f"   3. Vérifier que le dossier est bien accessible publiquement")
        print(f"   4. Tester l'accès direct via navigateur")

if __name__ == "__main__":
    main()
