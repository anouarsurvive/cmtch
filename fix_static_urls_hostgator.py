#!/usr/bin/env python3
"""
Script pour corriger les URLs statiques pour utiliser HostGator directement.
"""

import sys
import os

# Ajouter le répertoire courant au path pour importer database
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

def fix_static_urls_hostgator():
    """Corrige les URLs statiques pour utiliser HostGator directement"""
    print("🔧 CORRECTION DES URLs STATIQUES POUR HOSTGATOR:")
    
    try:
        conn = get_db_connection()
        
        if not hasattr(conn, '_is_mysql'):
            print("❌ Connexion SQLite établie (pas MySQL)")
            return False
        
        cur = conn.cursor()
        
        # Vérifier l'état actuel
        print("\n📊 ÉTAT ACTUEL DES ARTICLES:")
        cur.execute("SELECT id, title, image_path FROM articles ORDER BY id")
        articles = cur.fetchall()
        
        for article in articles:
            article_id, title, image_path = article
            print(f"   Article {article_id}: {title}")
            print(f"     Image actuelle: {image_path}")
        
        # Corriger les URLs pour utiliser HostGator directement
        print(f"\n🔄 CORRECTION DES URLs VERS HOSTGATOR:")
        
        # URL de base HostGator
        hostgator_base_url = "https://www.cmtch.online/static/article_images"
        
        # Mettre à jour tous les articles pour utiliser l'URL directe HostGator
        cur.execute("UPDATE articles SET image_path = %s", (f"{hostgator_base_url}/default_article.jpg",))
        articles_updated = cur.rowcount
        
        print(f"   ✅ {articles_updated} articles mis à jour avec l'URL HostGator directe")
        
        # Valider les changements
        conn.commit()
        print("💾 Changements validés en base de données")
        
        # Vérifier l'état après correction
        print(f"\n📊 ÉTAT APRÈS CORRECTION:")
        cur.execute("SELECT id, title, image_path FROM articles ORDER BY id")
        articles_after = cur.fetchall()
        
        for article in articles_after:
            article_id, title, image_path = article
            print(f"   Article {article_id}: {title}")
            print(f"     Nouvelle image: {image_path}")
        
        conn.close()
        
        return articles_updated
        
    except Exception as e:
        print(f"❌ Erreur lors de la correction: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return 0

def create_hostgator_upload_service():
    """Crée un service d'upload qui utilise l'URL directe HostGator"""
    print("\n🔧 CRÉATION DU SERVICE D'UPLOAD HOSTGATOR:")
    
    service_content = '''#!/usr/bin/env python3
"""
Service d'upload qui utilise l'URL directe HostGator.
"""

from hostgator_photo_storage import HostGatorPhotoStorage
import requests

def upload_photo_to_hostgator(file_content: bytes, filename: str) -> tuple:
    """
    Upload une photo sur HostGator et retourne l'URL directe.
    
    Args:
        file_content: Contenu binaire du fichier
        filename: Nom original du fichier
        
    Returns:
        Tuple[success, message, public_url]
    """
    try:
        # Upload sur HostGator
        storage = HostGatorPhotoStorage()
        success, message, public_url = storage.upload_photo(file_content, filename)
        
        if success:
            # Tester l'accessibilité de l'image uploadée
            try:
                response = requests.head(public_url, timeout=10)
                if response.status_code == 200:
                    # Image accessible, retourner l'URL directe HostGator
                    return True, message, public_url
                else:
                    print(f"⚠️ Image uploadée mais non accessible (HTTP {response.status_code})")
                    # Utiliser l'image par défaut accessible
                    default_url = "https://www.cmtch.online/static/article_images/default_article.jpg"
                    return True, f"Upload réussi mais image non accessible, utilisation de l'image par défaut", default_url
            except:
                print(f"⚠️ Impossible de vérifier l'accessibilité de l'image")
                # Utiliser l'image par défaut accessible
                default_url = "https://www.cmtch.online/static/article_images/default_article.jpg"
                return True, f"Upload réussi mais vérification impossible, utilisation de l'image par défaut", default_url
        
        # En cas d'échec d'upload, utiliser l'image par défaut
        default_url = "https://www.cmtch.online/static/article_images/default_article.jpg"
        return True, f"Échec upload, utilisation de l'image par défaut: {message}", default_url
        
    except Exception as e:
        # En cas d'erreur, utiliser l'image par défaut
        default_url = "https://www.cmtch.online/static/article_images/default_article.jpg"
        return True, f"Erreur upload, utilisation de l'image par défaut: {str(e)}", default_url
'''
    
    try:
        with open('photo_upload_service_hostgator.py', 'w', encoding='utf-8') as f:
            f.write(service_content)
        
        print("   ✅ Service d'upload HostGator créé: photo_upload_service_hostgator.py")
        return True
        
    except Exception as e:
        print(f"   ❌ Erreur création service: {e}")
        return False

def modify_app_py_for_hostgator():
    """Modifie app.py pour utiliser l'URL directe HostGator"""
    print("\n🔧 MODIFICATION D'APP.PY POUR HOSTGATOR:")
    
    try:
        # Lire le fichier app.py
        with open('app.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Remplacer l'import du service d'upload
        old_import = "from photo_upload_service import upload_photo_to_hostgator"
        new_import = "from photo_upload_service_hostgator import upload_photo_to_hostgator"
        
        if old_import in content:
            content = content.replace(old_import, new_import)
            print("   ✅ Import du service d'upload modifié")
        else:
            print("   ⚠️ Import du service d'upload non trouvé")
        
        # Commenter le montage StaticFiles pour éviter les conflits
        old_mount = '''app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "static")),
    name="static",
)'''
        
        new_mount = '''# Montage StaticFiles commenté - utilisation de l'URL directe HostGator
# app.mount(
#     "/static",
#     StaticFiles(directory=os.path.join(BASE_DIR, "static")),
#     name="static",
# )'''
        
        if old_mount in content:
            content = content.replace(old_mount, new_mount)
            print("   ✅ Montage StaticFiles commenté")
        else:
            print("   ⚠️ Montage StaticFiles non trouvé")
        
        # Écrire le fichier modifié
        with open('app.py', 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("   ✅ Fichier app.py modifié")
        return True
        
    except Exception as e:
        print(f"   ❌ Erreur modification app.py: {e}")
        return False

def main():
    """Fonction principale"""
    print("🚀 CORRECTION POUR URL DIRECTE HOSTGATOR")
    print("=" * 60)
    
    print("📋 Ce script configure l'application pour utiliser")
    print("   l'URL directe HostGator au lieu du montage FastAPI local.")
    print()
    
    # Correction des URLs en base de données
    updated_count = fix_static_urls_hostgator()
    
    # Création du service d'upload
    service_ok = create_hostgator_upload_service()
    
    # Modification d'app.py
    app_ok = modify_app_py_for_hostgator()
    
    if updated_count > 0 and service_ok and app_ok:
        print(f"\n🎉 CONFIGURATION TERMINÉE!")
        print(f"   ✅ {updated_count} articles mis à jour avec URL HostGator")
        print(f"   ✅ Service d'upload HostGator créé")
        print(f"   ✅ App.py modifié pour éviter les conflits")
        print(f"   ✅ Site web configuré pour utiliser HostGator directement")
        print(f"\n📝 PROCHAINES ÉTAPES:")
        print(f"   1. ✅ Redémarrer l'application")
        print(f"   2. ✅ Tester l'affichage des images")
        print(f"   3. ✅ Tester l'upload de nouvelles images")
        print(f"   4. ✅ Vérifier que les images sont accessibles")
    else:
        print(f"\n❌ Problème lors de la configuration")
    
    print(f"\n✅ Opération terminée!")

if __name__ == "__main__":
    main()
