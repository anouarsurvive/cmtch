#!/usr/bin/env python3
"""
Script pour uploader une nouvelle image vers le dossier FTP.
"""

import ftplib
import os
from pathlib import Path

def upload_new_image(image_path):
    """Upload une nouvelle image vers le dossier FTP"""
    print(f"📤 UPLOAD DE L'IMAGE: {image_path}")
    
    # Configuration FTP depuis les variables d'environnement
    ftp_host = os.getenv('FTP_HOST', 'ftp.novaprint.tn')
    ftp_user = os.getenv('FTP_USER', 'cmtch@cmtch.online')
    ftp_password = os.getenv('FTP_PASSWORD', 'Anouar881984?')
    
    print(f"🌐 Connexion à: {ftp_host}")
    print(f"👤 Utilisateur: {ftp_user}")
    
    # Vérifier que l'image existe localement
    if not os.path.exists(image_path):
        print(f"❌ Erreur: L'image {image_path} n'existe pas localement")
        return False
    
    try:
        # Connexion FTP
        ftp = ftplib.FTP(ftp_host)
        ftp.login(ftp_user, ftp_password)
        print("✅ Connexion FTP établie")
        
        # Naviguer vers le dossier article_images
        print("📁 Navigation vers le dossier article_images...")
        
        # Aller à la racine
        ftp.cwd('/')
        print(f"   📂 Racine: {ftp.pwd()}")
        
        # Aller dans public_html
        ftp.cwd('public_html')
        print(f"   📂 public_html: {ftp.pwd()}")
        
        # Aller dans static
        ftp.cwd('static')
        print(f"   📂 static: {ftp.pwd()}")
        
        # Aller dans article_images
        ftp.cwd('article_images')
        print(f"   📂 article_images: {ftp.pwd()}")
        
        # Lister le contenu actuel
        print("📋 Contenu actuel du dossier:")
        files_before = ftp.nlst()
        for file in sorted(files_before):
            print(f"   - {file}")
        
        # Upload de la nouvelle image
        image_name = os.path.basename(image_path)
        print(f"\n📤 Upload de {image_name}...")
        
        with open(image_path, 'rb') as file:
            ftp.storbinary(f'STOR {image_name}', file)
        
        print(f"   ✅ {image_name} uploadé avec succès!")
        
        # Lister le contenu après upload
        print("\n📋 Contenu après upload:")
        files_after = ftp.nlst()
        for file in sorted(files_after):
            print(f"   - {file}")
        
        # Vérifier que l'image est accessible
        print(f"\n🔍 VÉRIFICATION:")
        print(f"   Image uploadée: {image_name}")
        print(f"   Chemin complet: /public_html/static/article_images/{image_name}")
        print(f"   URL web: https://www.cmtch.online/static/article_images/{image_name}")
        
        ftp.quit()
        print("\n✅ Upload terminé avec succès!")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'upload: {e}")
        return False

def main():
    """Fonction principale"""
    print("🚀 UPLOAD D'UNE NOUVELLE IMAGE")
    print("=" * 50)
    
    # Demander le chemin de l'image
    print("📝 INSTRUCTIONS:")
    print("   1. Placez votre image (ex: 1.jpg) dans le répertoire courant")
    print("   2. Entrez le nom du fichier à uploader")
    print()
    
    # Vérifier les images disponibles localement
    current_dir = Path(".")
    image_files = list(current_dir.glob("*.jpg")) + list(current_dir.glob("*.png")) + list(current_dir.glob("*.jpeg"))
    
    if image_files:
        print("📸 Images disponibles localement:")
        for i, img in enumerate(image_files, 1):
            print(f"   {i}. {img.name}")
        print()
    
    # Demander le nom de l'image
    image_name = input("📁 Nom de l'image à uploader (ex: 1.jpg): ").strip()
    
    if not image_name:
        print("❌ Aucun nom d'image fourni")
        return
    
    # Vérifier que l'image existe
    if not os.path.exists(image_name):
        print(f"❌ L'image {image_name} n'existe pas dans le répertoire courant")
        print("💡 Assurez-vous que l'image est dans le même dossier que ce script")
        return
    
    # Effectuer l'upload
    print(f"\n🚀 Début de l'upload de {image_name}...")
    success = upload_new_image(image_name)
    
    if success:
        print(f"\n🎉 SUCCÈS! L'image {image_name} est maintenant accessible sur:")
        print(f"   https://www.cmtch.online/static/article_images/{image_name}")
    else:
        print(f"\n❌ Échec de l'upload de {image_name}")

if __name__ == "__main__":
    main()
