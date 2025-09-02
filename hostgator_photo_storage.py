#!/usr/bin/env python3
"""
Système de stockage des photos sur HostGator via FTP
"""

import os
import ftplib
import io
import uuid
import time
from typing import Optional, Tuple
import urllib.parse

class HostGatorPhotoStorage:
    """Gestionnaire de stockage des photos sur HostGator"""
    
    def __init__(self):
        # Configuration HostGator avec vos vrais paramètres
        self.ftp_host = "ftp.novaprint.tn"
        self.ftp_user = "cmtch@cmtch.online"  # Votre nom d'utilisateur FTP
        self.ftp_password = "Anouar881984?"  # Votre mot de passe FTP
        # ✅ CORRIGÉ: Upload vers le bon dossier /static/article_images/
        self.remote_photos_dir = "/public_html/static/article_images"  # Dossier sur HostGator
        self.base_url = "https://www.cmtch.online/static/article_images"  # URL publique
        
    def upload_photo(self, file_content: bytes, filename: str) -> Tuple[bool, str, str]:
        """
        Upload une photo sur HostGator
        
        Args:
            file_content: Contenu binaire du fichier
            filename: Nom original du fichier
            
        Returns:
            Tuple[success, message, public_url]
        """
        try:
            # ✅ CORRIGÉ: Générer un nom simple avec timestamp au lieu d'UUID
            ext = os.path.splitext(filename)[1] or ".jpg"
            timestamp = int(time.time())
            unique_name = f"img_{timestamp}{ext}"
            
            # Connexion FTP
            ftp = ftplib.FTP(self.ftp_host)
            ftp.login(self.ftp_user, self.ftp_password)
            
            # Créer le dossier s'il n'existe pas
            try:
                # Essayer de créer le dossier complet
                ftp.mkd(self.remote_photos_dir)
                print(f"✅ Dossier créé: {self.remote_photos_dir}")
            except ftplib.error_perm as e:
                if "exists" in str(e).lower():
                    print(f"ℹ️ Dossier existe déjà: {self.remote_photos_dir}")
                else:
                    print(f"⚠️ Erreur création dossier: {e}")
                    # Essayer de créer le dossier parent d'abord
                    try:
                        ftp.mkd("/public_html")
                        ftp.mkd("/public_html/static")
                        ftp.mkd(self.remote_photos_dir)
                        print(f"✅ Dossier créé avec parents: {self.remote_photos_dir}")
                    except:
                        pass
            
            # Changer vers le dossier article_images
            try:
                ftp.cwd(self.remote_photos_dir)
            except ftplib.error_perm:
                # Si on ne peut pas changer de dossier, utiliser le répertoire racine
                print("⚠️ Utilisation du répertoire racine pour l'upload")
            
            # Upload du fichier
            ftp.storbinary(f'STOR {unique_name}', 
                          io.BytesIO(file_content))
            
            # ✅ CORRIGÉ: Appliquer les permissions 644 après upload
            try:
                ftp.sendcmd(f"SITE CHMOD 644 {unique_name}")
                print(f"✅ Permissions 644 appliquées à {unique_name}")
            except:
                print(f"⚠️ Impossible d'appliquer les permissions à {unique_name}")
            
            # Fermer la connexion
            ftp.quit()
            
            # URL publique de la photo
            public_url = f"{self.base_url}/{unique_name}"
            
            return True, f"Photo uploadée avec succès: {unique_name}", public_url
            
        except Exception as e:
            return False, f"Erreur lors de l'upload: {str(e)}", ""
    
    def delete_photo(self, filename: str) -> Tuple[bool, str]:
        """
        Supprime une photo de HostGator
        
        Args:
            filename: Nom du fichier à supprimer
            
        Returns:
            Tuple[success, message]
        """
        try:
            # Connexion FTP
            ftp = ftplib.FTP(self.ftp_host)
            ftp.login(self.ftp_user, self.ftp_password)
            
            # Changer vers le dossier article_images
            ftp.cwd(self.remote_photos_dir)
            
            # Supprimer le fichier
            ftp.delete(filename)
            
            # Fermer la connexion
            ftp.quit()
            
            return True, f"Photo supprimée avec succès: {filename}"
            
        except Exception as e:
            return False, f"Erreur lors de la suppression: {str(e)}"
    
    def list_photos(self) -> Tuple[bool, list, str]:
        """
        Liste toutes les photos sur HostGator
        
        Returns:
            Tuple[success, photo_list, message]
        """
        try:
            # Connexion FTP
            ftp = ftplib.FTP(self.ftp_host)
            ftp.login(self.ftp_user, self.ftp_password)
            
            # Changer vers le dossier article_images
            ftp.cwd(self.remote_photos_dir)
            
            # Lister les fichiers
            files = ftp.nlst()
            
            # Filtrer les fichiers d'images
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp'}
            photos = []
            
            for file in files:
                if file in {'.', '..'}:
                    continue
                ext = os.path.splitext(file)[1].lower()
                if ext in image_extensions:
                    photos.append({
                        'filename': file,
                        'url': f"{self.base_url}/{file}",
                        'size': ftp.size(file) if ftp.size(file) else 0
                    })
            
            # Fermer la connexion
            ftp.quit()
            
            return True, photos, f"{len(photos)} photos trouvées"
            
        except Exception as e:
            return False, [], f"Erreur lors de la liste: {str(e)}"
    
    def get_photo_url(self, filename: str) -> str:
        """
        Retourne l'URL publique d'une photo
        
        Args:
            filename: Nom du fichier
            
        Returns:
            URL publique de la photo
        """
        return f"{self.base_url}/{filename}"
    
    def photo_exists(self, filename: str) -> bool:
        """
        Vérifie si une photo existe sur HostGator
        
        Args:
            filename: Nom du fichier
            
        Returns:
            True si la photo existe, False sinon
        """
        try:
            # Connexion FTP
            ftp = ftplib.FTP(self.ftp_host)
            ftp.login(self.ftp_user, self.ftp_password)
            
            # Changer vers le dossier article_images
            ftp.cwd(self.remote_photos_dir)
            
            # Vérifier si le fichier existe
            try:
                ftp.size(filename)
                exists = True
            except:
                exists = False
            
            # Fermer la connexion
            ftp.quit()
            
            return exists
            
        except Exception as e:
            print(f"❌ Erreur vérification existence: {e}")
            return False

def test_hostgator_connection():
    """Test de connexion à HostGator"""
    print("🔍 Test de connexion à HostGator...")
    
    storage = HostGatorPhotoStorage()
    
    try:
        # Test de connexion
        ftp = ftplib.FTP(storage.ftp_host)
        ftp.login(storage.ftp_user, storage.ftp_password)
        
        print("✅ Connexion FTP réussie !")
        
        # Test de création de dossier
        try:
            ftp.mkd(storage.remote_photos_dir)
            print(f"✅ Dossier créé: {storage.remote_photos_dir}")
        except ftplib.error_perm:
            print(f"ℹ️ Dossier existe déjà: {storage.remote_photos_dir}")
        
        # Lister le contenu
        ftp.cwd(storage.remote_photos_dir)
        files = ftp.nlst()
        print(f"📁 {len(files)} fichier(s) dans le dossier photos")
        
        ftp.quit()
        return True
        
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        return False

def main():
    """Fonction principale de test"""
    print("🚀 Test du système de stockage HostGator")
    print("=" * 50)
    
    if test_hostgator_connection():
        print("\n🎉 Configuration HostGator OK !")
        print("💡 Vous pouvez maintenant utiliser le stockage des photos sur HostGator")
    else:
        print("\n❌ Problème de configuration HostGator")
        print("💡 Vérifiez vos paramètres FTP dans le fichier")

if __name__ == "__main__":
    main()