#!/usr/bin/env python3
"""
Script de diagnostic rapide pour vérifier l'état de la production.
Ce script vérifie si les erreurs 404 sont toujours présentes.
"""

import requests
import time
from urllib.parse import urljoin

def check_production_images():
    """Vérifie l'état des images d'articles en production"""
    print("🔍 DIAGNOSTIC RAPIDE DE LA PRODUCTION")
    print("=" * 50)
    
    # URL de base du site
    base_url = "https://www.cmtch.online"
    
    # Images problématiques identifiées
    problematic_images = [
        "cbc7855d212240fc826e2447c73df415.jpg",
        "c14411214c364170879184ede9a97290.jpg",
        "2091bc799bf744c1aeababd53563657c.jpg"
    ]
    
    print(f"🌐 Vérification de {base_url}")
    print(f"📸 Test de {len(problematic_images)} images problématiques")
    print()
    
    # Vérifier chaque image
    working_images = 0
    broken_images = 0
    
    for image_name in problematic_images:
        image_url = urljoin(base_url, f"/static/article_images/{image_name}")
        
        try:
            print(f"🔍 Test de {image_name}...", end=" ")
            response = requests.get(image_url, timeout=10)
            
            if response.status_code == 200:
                print("✅ OK")
                working_images += 1
            elif response.status_code == 404:
                print("❌ 404 - Image manquante")
                broken_images += 1
            else:
                print(f"⚠️ {response.status_code}")
                broken_images += 1
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur: {e}")
            broken_images += 1
        
        # Pause entre les requêtes pour éviter la surcharge
        time.sleep(1)
    
    # Résumé
    print(f"\n📊 RÉSUMÉ:")
    print(f"   Images fonctionnelles: {working_images}")
    print(f"   Images cassées: {broken_images}")
    
    if broken_images == 0:
        print("🎉 Toutes les images fonctionnent correctement!")
    else:
        print(f"⚠️ {broken_images} images sont encore cassées")
        print("\n📝 Actions nécessaires:")
        print("   1. Vérifier la base de données MySQL sur HostGator")
        print("   2. Exécuter: python fix_production_mysql_images.py")
        print("   3. Uploader les images par défaut si nécessaire")
    
    return broken_images

def check_articles_page():
    """Vérifie que la page des articles est accessible"""
    print(f"\n📄 Vérification de la page des articles...")
    
    try:
        response = requests.get("https://www.cmtch.online/articles", timeout=10)
        
        if response.status_code == 200:
            print("✅ Page des articles accessible")
            
            # Vérifier s'il y a des erreurs d'images dans le contenu
            content = response.text.lower()
            if "404" in content or "image not found" in content:
                print("⚠️ Possibles erreurs d'images détectées dans le contenu")
            else:
                print("✅ Aucune erreur d'image détectée dans le contenu")
        else:
            print(f"❌ Erreur {response.status_code} sur la page des articles")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur lors de l'accès à la page: {e}")

def main():
    """Fonction principale"""
    print("🚀 DIAGNOSTIC RAPIDE - SITE CMTCH EN PRODUCTION")
    print("=" * 60)
    
    # Vérifier les images
    broken_count = check_production_images()
    
    # Vérifier la page des articles
    check_articles_page()
    
    # Recommandations
    print(f"\n📋 RECOMMANDATIONS:")
    
    if broken_count == 0:
        print("✅ Aucune action nécessaire - tout fonctionne!")
    else:
        print("🔧 Actions recommandées:")
        print("   1. Configurer les variables FTP (voir FTP_CONFIG.md)")
        print("   2. Uploader les images par défaut: python upload_default_image_to_hostgator.py")
        print("   3. Corriger la base MySQL: python fix_production_mysql_images.py")
        print("   4. Relancer ce diagnostic pour vérifier")
    
    print("\n✅ Diagnostic terminé!")

if __name__ == "__main__":
    main()
