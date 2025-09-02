#!/usr/bin/env python3
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
