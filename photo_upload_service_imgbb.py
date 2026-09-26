import requests
import base64
import os
from typing import Dict, Any


class ImgBBPhotoStorage:
    """Service de stockage de photos utilisant ImgBB."""

    def __init__(self):
        # Clé API uniquement via variable d'environnement (jamais en dur)
        self.api_key = os.getenv("IMGBB_API_KEY", "").strip()
        self.base_url = "https://api.imgbb.com/1/upload"

    def upload_photo(self, file_data: bytes, filename: str) -> Dict[str, Any]:
        """Upload une photo vers ImgBB."""
        if not self.api_key:
            return {
                "success": False,
                "error": "IMGBB_API_KEY non configurée (variable d'environnement requise)",
            }
        try:
            image_base64 = base64.b64encode(file_data).decode("utf-8")
            payload = {
                "key": self.api_key,
                "image": image_base64,
                "name": filename,
            }
            response = requests.post(self.base_url, data=payload, timeout=30)

            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    return {
                        "success": True,
                        "url": result["data"]["url"],
                        "delete_url": result["data"]["delete_url"],
                        "message": "Image uploadée avec succès vers ImgBB",
                    }
                return {
                    "success": False,
                    "error": result.get("error", {}).get(
                        "message", "Erreur inconnue ImgBB"
                    ),
                }
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text[:200]}",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def check_image_exists(self, url: str) -> bool:
        """Vérifie si une image existe (toujours True pour ImgBB)."""
        return bool(url)


imgbb_storage = ImgBBPhotoStorage()


def upload_photo_to_imgbb(file_data: bytes, filename: str) -> Dict[str, Any]:
    """Fonction d'upload vers ImgBB."""
    return imgbb_storage.upload_photo(file_data, filename)


def test_imgbb_system() -> Dict[str, Any]:
    """Test du système ImgBB."""
    try:
        if not imgbb_storage.api_key:
            return {
                "status": "error",
                "message": "IMGBB_API_KEY non configurée",
                "imgbb_working": False,
            }
        # Petite image PNG 1x1
        test_image_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        result = upload_photo_to_imgbb(test_image_data, "test_image.png")
        return {
            "status": "success" if result.get("success") else "error",
            "message": result.get("message", result.get("error", "Test ImgBB")),
            "imgbb_working": bool(result.get("success")),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur test ImgBB: {str(e)}",
            "imgbb_working": False,
        }
