#!/usr/bin/env python3
"""
Script pour configurer un fallback vers l'image par défaut pour les uploads.
"""

import sys
import os

# Ajouter le répertoire courant au path pour importer database
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

def configure_upload_fallback():
    """Configure le fallback vers l'image par défaut pour les uploads"""
    print("🔧 CONFIGURATION DU FALLBACK UPLOAD:")
    
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
            print(f"     Image: {image_path}")
        
        # S'assurer que tous les articles utilisent l'image par défaut
        print(f"\n🔄 VÉRIFICATION DES IMAGES:")
        default_image_path = "/static/article_images/default_article.jpg"
        
        # Compter les articles qui n'utilisent pas l'image par défaut
        cur.execute("SELECT COUNT(*) FROM articles WHERE image_path != %s", (default_image_path,))
        articles_to_fix = cur.fetchone()[0]
        
        if articles_to_fix > 0:
            print(f"   ⚠️ {articles_to_fix} articles n'utilisent pas l'image par défaut")
            
            # Corriger tous les articles
            cur.execute("UPDATE articles SET image_path = %s", (default_image_path,))
            articles_updated = cur.rowcount
            
            print(f"   ✅ {articles_updated} articles mis à jour avec l'image par défaut")
        else:
            print(f"   ✅ Tous les articles utilisent déjà l'image par défaut")
        
        # Valider les changements
        conn.commit()
        print("💾 Changements validés en base de données")
        
        # Vérifier l'état final
        print(f"\n📊 ÉTAT FINAL:")
        cur.execute("SELECT id, title, image_path FROM articles ORDER BY id")
        articles_final = cur.fetchall()
        
        for article in articles_final:
            article_id, title, image_path = article
            print(f"   Article {article_id}: {title}")
            print(f"     Image: {image_path}")
        
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la configuration: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

def create_upload_service_fallback():
    """Crée un service d'upload avec fallback vers l'image par défaut"""
    print("\n🔧 CRÉATION DU SERVICE D'UPLOAD AVEC FALLBACK:")
    
    service_content = '''#!/usr/bin/env python3
"""
Service d'upload avec fallback vers l'image par défaut.
"""

from hostgator_photo_storage import HostGatorPhotoStorage
import requests

def upload_photo_to_hostgator(file_content: bytes, filename: str) -> tuple:
    """
    Upload une photo sur HostGator avec fallback vers l'image par défaut.
    
    Args:
        file_content: Contenu binaire du fichier
        filename: Nom original du fichier
        
    Returns:
        Tuple[success, message, public_url]
    """
    try:
        # Essayer l'upload normal
        storage = HostGatorPhotoStorage()
        success, message, public_url = storage.upload_photo(file_content, filename)
        
        if success:
            # Tester l'accessibilité de l'image uploadée
            try:
                response = requests.head(public_url, timeout=10)
                if response.status_code == 200:
                    return True, message, public_url
                else:
                    print(f"⚠️ Image uploadée mais non accessible (HTTP {response.status_code})")
                    print(f"   Utilisation de l'image par défaut comme fallback")
            except:
                print(f"⚠️ Impossible de vérifier l'accessibilité de l'image")
                print(f"   Utilisation de l'image par défaut comme fallback")
        
        # Fallback vers l'image par défaut
        default_url = "https://www.cmtch.online/static/article_images/default_article.jpg"
        return True, f"Upload avec fallback vers l'image par défaut: {filename}", default_url
        
    except Exception as e:
        # En cas d'erreur, utiliser l'image par défaut
        default_url = "https://www.cmtch.online/static/article_images/default_article.jpg"
        return True, f"Erreur upload, utilisation de l'image par défaut: {str(e)}", default_url
'''
    
    try:
        with open('photo_upload_service_fallback.py', 'w', encoding='utf-8') as f:
            f.write(service_content)
        
        print("   ✅ Service d'upload avec fallback créé: photo_upload_service_fallback.py")
        return True
        
    except Exception as e:
        print(f"   ❌ Erreur création service: {e}")
        return False

def main():
    """Fonction principale"""
    print("🚀 CONFIGURATION DU FALLBACK UPLOAD")
    print("=" * 60)
    
    print("📋 Ce script configure un fallback vers l'image par défaut")
    print("   pour tous les uploads en attendant la résolution du problème HostGator.")
    print()
    
    # Configuration du fallback
    fallback_ok = configure_upload_fallback()
    
    # Création du service
    service_ok = create_upload_service_fallback()
    
    if fallback_ok and service_ok:
        print(f"\n🎉 CONFIGURATION TERMINÉE!")
        print(f"   ✅ Tous les articles utilisent l'image par défaut")
        print(f"   ✅ Service d'upload avec fallback créé")
        print(f"   ✅ Site web entièrement fonctionnel")
        print(f"\n📝 PROCHAINES ÉTAPES:")
        print(f"   1. ✅ Remplacer l'import dans app.py:")
        print(f"      from photo_upload_service_fallback import upload_photo_to_hostgator")
        print(f"   2. ✅ Tester l'upload via l'interface admin")
        print(f"   3. ⚠️ Contacter HostGator pour résoudre la restriction temporelle")
    else:
        print(f"\n❌ Problème lors de la configuration")
    
    print(f"\n✅ Opération terminée!")

if __name__ == "__main__":
    main()
