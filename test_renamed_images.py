#!/usr/bin/env python3
"""
Script pour tester l'accessibilité des images renommées.
"""

import requests
import time

def test_renamed_images():
    """Teste l'accessibilité des images renommées"""
    print("🔍 TEST D'ACCESSIBILITÉ DES IMAGES RENOMMÉES:")
    
    # Images renommées à tester
    renamed_images = [
        "article_1.jpg",
        "article_2.jpg", 
        "article_3.jpg"
    ]
    
    # Images de référence
    reference_images = [
        "default_article.jpg",
        "default_article.html",
        "default_article.svg"
    ]
    
    base_url = "https://www.cmtch.online/static/article_images/"
    
    print(f"🌐 Test des images sur: {base_url}")
    print()
    
    # Test des images renommées
    print("📋 TEST DES IMAGES RENOMMÉES:")
    results_renamed = []
    
    for image_name in renamed_images:
        image_url = f"{base_url}{image_name}"
        print(f"🔍 Test de {image_name}...")
        
        try:
            response = requests.head(image_url, timeout=10)
            status_code = response.status_code
            
            if status_code == 200:
                print(f"   ✅ {status_code} - Image accessible")
                results_renamed.append({"image": image_name, "status": "accessible", "code": status_code})
            else:
                print(f"   ❌ {status_code} - Image non accessible")
                results_renamed.append({"image": image_name, "status": "error", "code": status_code})
                
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Erreur: {e}")
            results_renamed.append({"image": image_name, "status": "error", "code": "exception"})
        
        time.sleep(0.5)
    
    # Test des images de référence
    print(f"\n📋 TEST DES IMAGES DE RÉFÉRENCE:")
    results_reference = []
    
    for image_name in reference_images:
        image_url = f"{base_url}{image_name}"
        print(f"🔍 Test de {image_name}...")
        
        try:
            response = requests.head(image_url, timeout=10)
            status_code = response.status_code
            
            if status_code == 200:
                print(f"   ✅ {status_code} - Image accessible")
                results_reference.append({"image": image_name, "status": "accessible", "code": status_code})
            else:
                print(f"   ❌ {status_code} - Image non accessible")
                results_reference.append({"image": image_name, "status": "error", "code": status_code})
                
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Erreur: {e}")
            results_reference.append({"image": image_name, "status": "error", "code": "exception"})
        
        time.sleep(0.5)
    
    # Résumé des résultats
    print(f"\n📊 RÉSUMÉ DES TESTS:")
    
    # Images renommées
    accessible_renamed = sum(1 for r in results_renamed if r["status"] == "accessible")
    error_renamed = sum(1 for r in results_renamed if r["status"] == "error")
    
    print(f"   📋 Images renommées:")
    print(f"     ✅ Accessibles: {accessible_renamed}")
    print(f"     ❌ Non accessibles: {error_renamed}")
    
    # Images de référence
    accessible_reference = sum(1 for r in results_reference if r["status"] == "accessible")
    error_reference = sum(1 for r in results_reference if r["status"] == "error")
    
    print(f"   📋 Images de référence:")
    print(f"     ✅ Accessibles: {accessible_reference}")
    print(f"     ❌ Non accessibles: {error_reference}")
    
    # Analyse
    if accessible_renamed == len(renamed_images):
        print(f"\n🎉 SUCCÈS COMPLET!")
        print(f"   - Toutes les images renommées sont accessibles")
        print(f"   - Le problème de filtrage des noms est résolu")
        print(f"   - Les articles devraient maintenant afficher leurs images")
    elif accessible_renamed > 0:
        print(f"\n⚠️ SUCCÈS PARTIEL!")
        print(f"   - {accessible_renamed}/{len(renamed_images)} images renommées sont accessibles")
        print(f"   - Le renommage a partiellement résolu le problème")
    else:
        print(f"\n❌ ÉCHEC!")
        print(f"   - Aucune image renommée n'est accessible")
        print(f"   - Le problème persiste malgré le renommage")
    
    return results_renamed, results_reference

def main():
    """Fonction principale"""
    print("🚀 TEST D'ACCESSIBILITÉ DES IMAGES RENOMMÉES")
    print("=" * 60)
    
    print("📋 Ce script teste l'accessibilité des images après renommage")
    print("   avec des noms simples pour contourner les restrictions HostGator.")
    print()
    
    results_renamed, results_reference = test_renamed_images()
    
    print(f"\n✅ Test terminé!")
    
    # Recommandations
    accessible_count = sum(1 for r in results_renamed if r["status"] == "accessible")
    if accessible_count == len(results_renamed):
        print(f"\n💡 RECOMMANDATIONS:")
        print(f"   1. ✅ Le problème est résolu - toutes les images sont accessibles")
        print(f"   2. ✅ Vérifier que le site web affiche correctement les images")
        print(f"   3. ✅ Tester l'upload de nouvelles images")
    else:
        print(f"\n💡 RECOMMANDATIONS:")
        print(f"   1. Vérifier les permissions du dossier /static/article_images/")
        print(f"   2. Contacter le support HostGator pour les restrictions de fichiers")
        print(f"   3. Tester d'autres formats de noms de fichiers")

if __name__ == "__main__":
    main()
