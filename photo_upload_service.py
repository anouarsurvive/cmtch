#!/usr/bin/env python3
"""
Service de gestion des uploads de photos avec HostGator
"""

import os
import uuid
from typing import Tuple, Optional

def upload_photo_to_hostgator(file_content: bytes, filename: str) -> Tuple[bool, str, str]:
    """
    Upload une photo sur HostGator (pas de fallback local)
    
    Args:
        file_content: Contenu binaire du fichier
        filename: Nom original du fichier
        
    Returns:
        Tuple[success, message, image_path]
    """
    try:
        from hostgator_photo_storage import HostGatorPhotoStorage
        storage = HostGatorPhotoStorage()
        success, message, public_url = storage.upload_photo(file_content, filename)
        
        if success:
            print(f"✅ Photo uploadée sur HostGator: {message}")
            return True, message, public_url
        else:
            print(f"❌ Erreur upload HostGator: {message}")
            # Pas de fallback local - échec total
            return False, f"Échec upload HostGator: {message}", ""
            
    except Exception as e:
        print(f"❌ Erreur système upload HostGator: {e}")
        # Pas de fallback local - échec total
        return False, f"Erreur HostGator: {str(e)}", ""

def upload_photo_local(file_content: bytes, filename: str, reason: str = "") -> Tuple[bool, str, str]:
    """
    Upload une photo en local (fallback)
    
    Args:
        file_content: Contenu binaire du fichier
        filename: Nom original du fichier
        reason: Raison du fallback
        
    Returns:
        Tuple[success, message, image_path]
    """
    try:
        # Créer un dossier pour les images si nécessaire
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        images_dir = os.path.join(BASE_DIR, "static", "article_images")
        os.makedirs(images_dir, exist_ok=True)
        
        # Générer un nom unique pour éviter les collisions
        ext = os.path.splitext(filename)[1] or ".bin"
        unique_name = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(images_dir, unique_name)
        
        # Écrire le fichier
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # Chemin relatif pour utilisation dans les templates
        image_path = f"/static/article_images/{unique_name}"
        
        message = f"Photo sauvegardée localement: {unique_name}"
        if reason:
            message += f" (Raison: {reason})"
        
        print(f"⚠️ {message}")
        return True, message, image_path
        
    except Exception as e:
        error_msg = f"Erreur stockage local: {str(e)}"
        print(f"❌ {error_msg}")
        return False, error_msg, ""

def delete_photo_from_hostgator(filename: str) -> Tuple[bool, str]:
    """
    Supprime une photo de HostGator
    
    Args:
        filename: Nom du fichier à supprimer
        
    Returns:
        Tuple[success, message]
    """
    try:
        from hostgator_photo_storage import HostGatorPhotoStorage
        storage = HostGatorPhotoStorage()
        return storage.delete_photo(filename)
    except Exception as e:
        return False, f"Erreur suppression HostGator: {str(e)}"

def list_photos_from_hostgator() -> Tuple[bool, list, str]:
    """
    Liste toutes les photos sur HostGator
    
    Returns:
        Tuple[success, photo_list, message]
    """
    try:
        from hostgator_photo_storage import HostGatorPhotoStorage
        storage = HostGatorPhotoStorage()
        return storage.list_photos()
    except Exception as e:
        return False, [], f"Erreur liste HostGator: {str(e)}"

def test_photo_system():
    """Test du système de photos"""
    print("🧪 Test du système de photos...")
    
    # Test de connexion HostGator
    try:
        from hostgator_photo_storage import HostGatorPhotoStorage
        storage = HostGatorPhotoStorage()
        success, photos, message = storage.list_photos()
        
        if success:
            print(f"✅ Connexion HostGator OK: {message}")
            print(f"📁 {len(photos)} photos disponibles")
        else:
            print(f"❌ Problème HostGator: {message}")
            
    except Exception as e:
        print(f"❌ Erreur test HostGator: {e}")
    
    # Test de stockage local
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        images_dir = os.path.join(BASE_DIR, "static", "article_images")
        
        if os.path.exists(images_dir):
            files = os.listdir(images_dir)
            print(f"✅ Stockage local OK: {len(files)} fichiers")
        else:
            print("ℹ️ Dossier stockage local n'existe pas encore")
            
    except Exception as e:
        print(f"❌ Erreur test local: {e}")

if __name__ == "__main__":
    test_photo_system()
