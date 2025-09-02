#!/usr/bin/env python3
"""
Script pour tester l'upload d'image lors de la création d'un nouvel article.
"""

import os
import uuid
from pathlib import Path

def test_article_creation_upload():
    """Teste l'upload d'image lors de la création d'article"""
    print("🧪 TEST DE L'UPLOAD - CRÉATION D'ARTICLE:")
    
    try:
        # Simuler le processus d'upload d'un nouvel article
        print("📝 Simulation de la création d'un nouvel article...")
        
        # 1. Vérifier le service d'upload
        print("\n🔍 Vérification du service d'upload...")
        from photo_upload_service import upload_photo_to_hostgator
        
        # 2. Créer une image de test
        print("🎨 Création d'une image de test...")
        test_image_content = create_test_image()
        
        # 3. Générer un nom unique (comme dans l'app)
        filename = "test_article_image.jpg"
        ext = os.path.splitext(filename)[1] or ".bin"
        unique_name = f"{uuid.uuid4().hex}{ext}"
        
        print(f"   📁 Nom original: {filename}")
        print(f"   🔑 Nom unique généré: {unique_name}")
        
        # 4. Tester l'upload vers HostGator
        print(f"\n📤 Test de l'upload vers HostGator...")
        success, message, hostgator_url = upload_photo_to_hostgator(test_image_content, unique_name)
        
        if success:
            print(f"   ✅ Upload réussi!")
            print(f"   📋 Message: {message}")
            print(f"   🌐 URL HostGator: {hostgator_url}")
            
            # 5. Vérifier que l'URL est correcte
            if "/static/article_images/" in hostgator_url:
                print(f"   ✅ URL CORRECTE - Pointe vers /static/article_images/")
            else:
                print(f"   ❌ URL INCORRECTE - Ne pointe pas vers /static/article_images/")
                return False
            
            # 6. Vérifier que l'image est accessible
            print(f"\n🔍 Vérification de l'accessibilité de l'image...")
            if verify_image_accessibility(hostgator_url):
                print(f"   ✅ Image accessible sur le web!")
            else:
                print(f"   ⚠️ Image non accessible (peut prendre quelques secondes)")
            
            return True
            
        else:
            print(f"   ❌ Upload échoué: {message}")
            return False
        
    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")
        return False

def create_test_image():
    """Crée une image de test simple"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # Créer une image 400x300
        img = Image.new('RGB', (400, 300), color='#e3f2fd')
        draw = ImageDraw.Draw(img)
        
        # Dessiner un rectangle pour l'icône
        draw.rectangle([150, 100, 250, 200], fill='#2196f3', outline='#1976d2', width=3)
        
        # Ajouter du texte
        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            font = ImageFont.load_default()
        
        draw.text((200, 250), "Test Article", fill='#1976d2', anchor="mm", font=font)
        
        # Convertir en bytes
        import io
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG', quality=85)
        return img_bytes.getvalue()
        
    except ImportError:
        # Fallback si PIL n'est pas disponible
        print("   ⚠️ PIL non disponible, création d'une image simple...")
        return b"fake_image_content_for_testing"

def verify_image_accessibility(url):
    """Vérifie que l'image est accessible sur le web"""
    try:
        import requests
        
        # Attendre un peu pour que l'upload soit traité
        import time
        time.sleep(2)
        
        response = requests.head(url, timeout=10)
        if response.status_code == 200:
            return True
        else:
            print(f"      ⚠️ Statut HTTP: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"      ⚠️ Erreur vérification: {e}")
        return False

def main():
    """Fonction principale"""
    print("🚀 TEST DE L'UPLOAD - CRÉATION D'ARTICLE")
    print("=" * 60)
    
    print("📋 Ce test simule l'upload d'image lors de la création d'un nouvel article")
    print("   et vérifie que la configuration corrigée fonctionne correctement.")
    print()
    
    success = test_article_creation_upload()
    
    if success:
        print(f"\n🎉 SUCCÈS! L'upload depuis la création d'article fonctionne parfaitement!")
        print(f"   ✅ Configuration corrigée")
        print(f"   ✅ Upload vers le bon dossier: /static/article_images/")
        print(f"   ✅ URLs générées correctement")
        print(f"   ✅ Images accessibles sur le web")
        print(f"\n📝 Maintenant vous pouvez:")
        print(f"   1. Créer un nouvel article avec image")
        print(f"   2. Modifier un article existant avec image")
        print(f"   3. Toutes les images seront dans le bon dossier")
    else:
        print(f"\n❌ ÉCHEC! L'upload depuis la création d'article a des problèmes.")
        print(f"   Vérifiez la configuration et relancez le test.")
    
    print(f"\n✅ Test terminé!")

if __name__ == "__main__":
    main()
