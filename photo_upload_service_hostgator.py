#!/usr/bin/env python3
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
