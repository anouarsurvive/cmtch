#!/usr/bin/env python3
"""
Script pour créer une favicon à partir du logo du club
"""

from PIL import Image
import os

def create_favicon():
    """Crée une favicon à partir du logo du club"""
    
    # Chemin vers le logo
    logo_path = "static/images/logo.jpg"
    favicon_path = "static/favicon.ico"
    
    try:
        # Vérifier si le logo existe
        if not os.path.exists(logo_path):
            print(f"❌ Logo non trouvé : {logo_path}")
            return False
        
        # Ouvrir l'image du logo
        logo = Image.open(logo_path)
        print(f"✅ Logo chargé : {logo.size} pixels")
        
        # Créer différentes tailles de favicon
        sizes = [16, 32, 48, 64, 128, 256]
        favicon_images = []
        
        for size in sizes:
            # Redimensionner en gardant les proportions
            resized = logo.resize((size, size), Image.Resampling.LANCZOS)
            favicon_images.append(resized)
            print(f"✅ Taille {size}x{size} créée")
        
        # Créer le fichier ICO avec toutes les tailles
        favicon_images[0].save(
            favicon_path,
            format='ICO',
            sizes=[(img.width, img.height) for img in favicon_images],
            append_images=favicon_images[1:]
        )
        
        print(f"🎉 Favicon créée avec succès : {favicon_path}")
        
        # Créer aussi des versions PNG pour les navigateurs modernes
        for size in [16, 32, 180, 192, 512]:
            png_path = f"static/favicon-{size}x{size}.png"
            resized = logo.resize((size, size), Image.Resampling.LANCZOS)
            resized.save(png_path, format='PNG')
            print(f"✅ PNG {size}x{size} créé : {png_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la création de la favicon : {e}")
        return False

if __name__ == "__main__":
    print("🎨 Création de la favicon du Club Municipal de Tennis Chihia")
    print("=" * 60)
    
    success = create_favicon()
    
    if success:
        print("\n🎉 Favicon créée avec succès !")
        print("📁 Fichiers créés :")
        print("   - static/favicon.ico (favicon principale)")
        print("   - static/favicon-16x16.png")
        print("   - static/favicon-32x32.png")
        print("   - static/favicon-180x180.png (Apple Touch Icon)")
        print("   - static/favicon-192x192.png (Android)")
        print("   - static/favicon-512x512.png (Android)")
    else:
        print("\n❌ Échec de la création de la favicon")
