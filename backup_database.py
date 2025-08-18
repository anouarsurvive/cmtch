#!/usr/bin/env python3
"""
Script de sauvegarde automatique de la base de données CMTCH.

Ce script sauvegarde la base de données PostgreSQL sur Render vers un fichier local
et peut également restaurer les données si nécessaire.
"""

import os
import json
import subprocess
import sys
from datetime import datetime
from typing import Dict, Any, Optional

def get_database_url() -> Optional[str]:
    """Récupère l'URL de la base de données depuis les variables d'environnement."""
    return os.getenv('DATABASE_URL')

def backup_postgresql_db() -> Dict[str, Any]:
    """Sauvegarde la base de données PostgreSQL."""
    database_url = get_database_url()
    
    if not database_url:
        return {
            "status": "error",
            "message": "DATABASE_URL non définie"
        }
    
    try:
        # Créer le nom du fichier de sauvegarde avec timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_cmtch_{timestamp}.sql"
        
        # Commande pg_dump pour sauvegarder
        cmd = [
            "pg_dump",
            "--clean",  # Inclure les commandes DROP
            "--if-exists",  # Ajouter IF EXISTS aux DROP
            "--no-owner",  # Ne pas inclure les propriétaires
            "--no-privileges",  # Ne pas inclure les privilèges
            "--data-only",  # Sauvegarder seulement les données
            "--dbname", database_url
        ]
        
        print(f"🔄 Sauvegarde en cours vers {backup_filename}...")
        
        with open(backup_filename, 'w') as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
        
        if result.returncode == 0:
            # Obtenir la taille du fichier
            file_size = os.path.getsize(backup_filename)
            
            return {
                "status": "success",
                "message": f"Sauvegarde créée avec succès",
                "filename": backup_filename,
                "size_bytes": file_size,
                "timestamp": timestamp
            }
        else:
            return {
                "status": "error",
                "message": f"Erreur lors de la sauvegarde: {result.stderr}"
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"Exception lors de la sauvegarde: {str(e)}"
        }

def restore_postgresql_db(backup_filename: str) -> Dict[str, Any]:
    """Restaure la base de données PostgreSQL depuis un fichier de sauvegarde."""
    database_url = get_database_url()
    
    if not database_url:
        return {
            "status": "error",
            "message": "DATABASE_URL non définie"
        }
    
    if not os.path.exists(backup_filename):
        return {
            "status": "error",
            "message": f"Fichier de sauvegarde {backup_filename} non trouvé"
        }
    
    try:
        print(f"🔄 Restauration depuis {backup_filename}...")
        
        # Commande psql pour restaurer
        cmd = [
            "psql",
            "--dbname", database_url,
            "--file", backup_filename
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return {
                "status": "success",
                "message": "Restauration terminée avec succès"
            }
        else:
            return {
                "status": "error",
                "message": f"Erreur lors de la restauration: {result.stderr}"
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"Exception lors de la restauration: {str(e)}"
        }

def list_backups() -> Dict[str, Any]:
    """Liste tous les fichiers de sauvegarde disponibles."""
    try:
        backup_files = []
        for filename in os.listdir('.'):
            if filename.startswith('backup_cmtch_') and filename.endswith('.sql'):
                file_path = os.path.join('.', filename)
                file_size = os.path.getsize(file_path)
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                backup_files.append({
                    "filename": filename,
                    "size_bytes": file_size,
                    "created_at": file_time.isoformat()
                })
        
        # Trier par date de création (plus récent en premier)
        backup_files.sort(key=lambda x: x["created_at"], reverse=True)
        
        return {
            "status": "success",
            "backups": backup_files,
            "count": len(backup_files)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur lors de la liste des sauvegardes: {str(e)}"
        }

def main():
    """Fonction principale du script."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python backup_database.py backup     # Créer une sauvegarde")
        print("  python backup_database.py restore <file>  # Restaurer depuis un fichier")
        print("  python backup_database.py list       # Lister les sauvegardes")
        return
    
    command = sys.argv[1]
    
    if command == "backup":
        result = backup_postgresql_db()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif command == "restore":
        if len(sys.argv) < 3:
            print("Erreur: nom de fichier requis pour la restauration")
            return
        backup_file = sys.argv[2]
        result = restore_postgresql_db(backup_file)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif command == "list":
        result = list_backups()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    else:
        print(f"Commande inconnue: {command}")

if __name__ == "__main__":
    main()
