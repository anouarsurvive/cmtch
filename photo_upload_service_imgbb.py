import requests
import base64
import os
from typing import Optional, Dict, Any

class ImgBBPhotoStorage:
    """Service de stockage de photos utilisant ImgBB (gratuit et fiable)"""
    
    def __init__(self):
        # Clé API ImgBB (gratuite, 32MB par image, illimitée)
        self.api_key = "e4b5d5cbeabc2e7cfb7b7202c642798f"
        self.base_url = "https://api.imgbb.com/1/upload"
    
    def upload_photo(self, file_data: bytes, filename: str) -> Dict[str, Any]:
        """Upload une photo vers ImgBB"""
        try:
            # Encoder l'image en base64
            image_base64 = base64.b64encode(file_data).decode('utf-8')
            
            # Paramètres de l'upload
            payload = {
                'key': self.api_key,
                'image': image_base64,
                'name': filename
            }
            
            # Upload vers ImgBB
            response = requests.post(self.base_url, data=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    return {
                        'success': True,
                        'url': result['data']['url'],
                        'delete_url': result['data']['delete_url'],
                        'message': 'Image uploadée avec succès vers ImgBB'
                    }
                else:
                    return {
                        'success': False,
                        'error': result.get('error', {}).get('message', 'Erreur inconnue ImgBB')
                    }
            else:
                return {
                    'success': False,
                    'error': f'Erreur HTTP {response.status_code}: {response.text}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Erreur lors de l\'upload: {str(e)}'
            }
    
    def photo_exists(self, url: str) -> bool:
        """Vérifie si une image existe (toujours True pour ImgBB)"""
        try:
            response = requests.head(url, timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def get_upload_url(self) -> str:
        """Retourne l'URL de base pour les images"""
        return "https://i.ibb.co/"

# Instance globale
imgbb_storage = ImgBBPhotoStorage()

def upload_photo_to_imgbb(file_data: bytes, filename: str) -> Dict[str, Any]:
    """Fonction d'upload vers ImgBB"""
    return imgbb_storage.upload_photo(file_data, filename)

def test_imgbb_system() -> Dict[str, Any]:
    """Test du système ImgBB"""
    try:
        # Créer une image de test simple (1x1 pixel PNG)
        test_image_data = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='
        )
        
        result = upload_photo_to_imgbb(test_image_data, "test_image.png")
        
        return {
            'status': 'success' if result['success'] else 'error',
            'message': result.get('message', result.get('error', 'Test ImgBB')),
            'test_url': result.get('url', 'N/A'),
            'imgbb_working': result['success']
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Erreur test ImgBB: {str(e)}',
            'imgbb_working': False
        }
