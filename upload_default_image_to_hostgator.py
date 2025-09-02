#!/usr/bin/env python3
"""
Script pour uploader l'image par défaut sur HostGator via FTP.
Cette image sera utilisée pour les articles qui n'ont pas d'images.
"""

import os
import ftplib
from pathlib import Path

def upload_to_hostgator():
    """Upload l'image par défaut sur HostGator via FTP"""
    print("📤 UPLOAD DE L'IMAGE PAR DÉFAUT SUR HOSTGATOR:")
    
    # Vérifier que l'image par défaut existe
    default_image_path = Path("static/article_images/default_article.svg")
    if not default_image_path.exists():
        print("❌ Image par défaut non trouvée. Créons-la d'abord...")
        create_default_svg()
        default_image_path = Path("static/article_images/default_article.svg")
    
    # Récupérer les informations de connexion FTP depuis les variables d'environnement
    ftp_host = os.getenv('FTP_HOST')
    ftp_user = os.getenv('FTP_USER')
    ftp_password = os.getenv('FTP_PASSWORD')
    ftp_path = os.getenv('FTP_PATH', '/public_html/static/article_images/')
    
    if not all([ftp_host, ftp_user, ftp_password]):
        print("❌ Variables d'environnement FTP manquantes:")
        print("   - FTP_HOST: serveur FTP HostGator")
        print("   - FTP_USER: nom d'utilisateur FTP")
        print("   - FTP_PASSWORD: mot de passe FTP")
        print("   - FTP_PATH: chemin sur le serveur (optionnel)")
        return False
    
    try:
        print(f"🔌 Connexion à {ftp_host}...")
        
        # Connexion FTP
        ftp = ftplib.FTP(ftp_host)
        ftp.login(ftp_user, ftp_password)
        print("✅ Connexion FTP établie")
        
        # Créer la structure de dossiers étape par étape
        print("📁 Création de la structure de dossiers...")
        
        # Aller d'abord à la racine
        ftp.cwd('/')
        print(f"   📂 Dossier actuel: {ftp.pwd()}")
        
        # Créer et aller dans public_html
        try:
            ftp.cwd('public_html')
            print("   ✅ Dossier public_html accessible")
        except:
            print("   📁 Création du dossier public_html...")
            ftp.mkd('public_html')
            ftp.cwd('public_html')
            print("   ✅ Dossier public_html créé")
        
        # Créer et aller dans static
        try:
            ftp.cwd('static')
            print("   ✅ Dossier static accessible")
        except:
            print("   📁 Création du dossier static...")
            ftp.mkd('static')
            ftp.cwd('static')
            print("   ✅ Dossier static créé")
        
        # Créer et aller dans article_images
        try:
            ftp.cwd('article_images')
            print("   ✅ Dossier article_images accessible")
        except:
            print("   📁 Création du dossier article_images...")
            ftp.mkd('article_images')
            ftp.cwd('article_images')
            print("   ✅ Dossier article_images créé")
        
        print(f"📂 Dossier final: {ftp.pwd()}")
        
        # Upload de l'image SVG par défaut
        print(f"📤 Upload de {default_image_path.name}...")
        with open(default_image_path, 'rb') as file:
            ftp.storbinary(f'STOR {default_image_path.name}', file)
        print("   ✅ Image SVG uploadée")
        
        # Upload également de l'image HTML par défaut si elle existe
        html_image_path = Path("static/article_images/default_article.html")
        if html_image_path.exists():
            print(f"📤 Upload de {html_image_path.name}...")
            with open(html_image_path, 'rb') as file:
                ftp.storbinary(f'STOR {html_image_path.name}', file)
            print("   ✅ Image HTML uploadée")
        
        # Créer et upload une image JPG par défaut (plus compatible)
        jpg_image_path = create_default_jpg()
        if jpg_image_path:
            print(f"📤 Upload de {jpg_image_path.name}...")
            with open(jpg_image_path, 'rb') as file:
                ftp.storbinary(f'STOR {jpg_image_path.name}', file)
            print("   ✅ Image JPG uploadée")
        
        # Lister les fichiers uploadés
        print(f"\n📋 Fichiers dans le dossier actuel:")
        files = ftp.nlst()
        for file in sorted(files):
            print(f"   - {file}")
        
        ftp.quit()
        print("\n✅ Upload terminé avec succès!")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'upload: {e}")
        return False

def create_default_svg():
    """Crée une image SVG par défaut si elle n'existe pas"""
    print("🎨 Création de l'image SVG par défaut...")
    
    images_dir = Path("static/article_images")
    images_dir.mkdir(exist_ok=True)
    
    svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="400" height="300" viewBox="0 0 400 300" xmlns="http://www.w3.org/2000/svg">
  <!-- Fond -->
  <rect width="400" height="300" fill="#f8f9fa" stroke="#dee2e6" stroke-width="2"/>
  
  <!-- Icône d'article -->
  <g transform="translate(200, 150)">
    <!-- Document -->
    <rect x="-40" y="-50" width="80" height="100" fill="#007bff" rx="5"/>
    
    <!-- Lignes de texte -->
    <rect x="-30" y="-35" width="60" height="3" fill="white" rx="1"/>
    <rect x="-30" y="-25" width="45" height="3" fill="white" rx="1"/>
    <rect x="-30" y="-15" width="55" height="3" fill="white" rx="1"/>
    <rect x="-30" y="-5" width="40" height="3" fill="white" rx="1"/>
    <rect x="-30" y="5" width="50" height="3" fill="white" rx="1"/>
    <rect x="-30" y="15" width="35" height="3" fill="white" rx="1"/>
    <rect x="-30" y="25" width="60" height="3" fill="white" rx="1"/>
    <rect x="-30" y="35" width="42" height="3" fill="white" rx="1"/>
  </g>
  
  <!-- Texte -->
  <text x="200" y="250" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" fill="#6c757d">
    Image par défaut
  </text>
</svg>'''
    
    svg_path = images_dir / "default_article.svg"
    with open(svg_path, 'w', encoding='utf-8') as f:
        f.write(svg_content)
    
    print(f"✅ Image SVG créée: {svg_path}")

def create_default_jpg():
    """Crée une image JPG simple par défaut (plus compatible)"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        print("🎨 Création de l'image JPG par défaut...")
        
        # Créer une image 400x300
        img = Image.new('RGB', (400, 300), color='#f8f9fa')
        draw = ImageDraw.Draw(img)
        
        # Dessiner un rectangle pour l'icône
        draw.rectangle([160, 100, 240, 200], fill='#007bff', outline='#0056b3', width=2)
        
        # Ajouter du texte
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except:
            font = ImageFont.load_default()
        
        draw.text((200, 250), "Image par défaut", fill='#6c757d', anchor="mm", font=font)
        
        # Sauvegarder
        images_dir = Path("static/article_images")
        jpg_path = images_dir / "default_article.jpg"
        img.save(jpg_path, 'JPEG', quality=85)
        
        print(f"✅ Image JPG créée: {jpg_path}")
        return jpg_path
        
    except ImportError:
        print("⚠️ PIL/Pillow non disponible, impossible de créer l'image JPG")
        return None
    except Exception as e:
        print(f"❌ Erreur lors de la création de l'image JPG: {e}")
        return None

def main():
    """Fonction principale"""
    print("🚀 UPLOAD DE L'IMAGE PAR DÉFAUT SUR HOSTGATOR")
    print("=" * 60)
    
    # Vérifier les prérequis
    print("📋 PRÉREQUIS:")
    print("   - Variables d'environnement FTP configurées")
    print("   - Connexion internet active")
    print("   - Accès FTP à HostGator")
    
    # Demander confirmation
    confirm = input("\n❓ Continuer avec l'upload? (o/n): ").strip().lower()
    if not confirm.startswith('o'):
        print("❌ Upload annulé")
        return
    
    # Effectuer l'upload
    success = upload_to_hostgator()
    
    if success:
        print("\n🎉 Upload réussi!")
        print("📝 Prochaines étapes:")
        print("   1. Exécuter le script de correction MySQL: python fix_production_mysql_images.py")
        print("   2. Vérifier que les erreurs 404 sont résolues sur le site")
    else:
        print("\n❌ Upload échoué")
        print("📝 Vérifiez:")
        print("   - Vos informations de connexion FTP")
        print("   - Votre connexion internet")
        print("   - Les permissions sur HostGator")

if __name__ == "__main__":
    main()
