#!/usr/bin/env python3
"""
Script de sauvegarde automatique pour CMTCH
Sauvegarde la base de données au démarrage et restaure si nécessaire
"""

import os
import sys
import subprocess
import json
from datetime import datetime
from pathlib import Path

def get_db_url():
    """Récupère l'URL de la base de données depuis les variables d'environnement."""
    return os.getenv('DATABASE_URL')

def backup_database():
    """Sauvegarde la base de données PostgreSQL."""
    db_url = get_db_url()
    if not db_url:
        print("❌ DATABASE_URL non trouvée")
        return False
    
    try:
        # Créer le dossier de sauvegarde
        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)
        
        # Nom du fichier de sauvegarde
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"cmtch_auto_backup_{timestamp}.sql"
        
        # Commande de sauvegarde
        cmd = [
            "pg_dump",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "--dbname", db_url,
            "--file", str(backup_file)
        ]
        
        print(f"🔄 Sauvegarde automatique en cours...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Sauvegarde créée: {backup_file}")
            return str(backup_file)
        else:
            print(f"❌ Erreur lors de la sauvegarde: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde: {e}")
        return False

def restore_database(backup_file):
    """Restaure la base de données depuis un fichier de sauvegarde."""
    db_url = get_db_url()
    if not db_url:
        print("❌ DATABASE_URL non trouvée")
        return False
    
    try:
        # Commande de restauration
        cmd = [
            "psql",
            "--dbname", db_url,
            "--file", backup_file
        ]
        
        print(f"🔄 Restauration depuis {backup_file}...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Base de données restaurée avec succès")
            return True
        else:
            print(f"❌ Erreur lors de la restauration: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur lors de la restauration: {e}")
        return False

def check_database_empty():
    """Vérifie si la base de données est vide."""
    db_url = get_db_url()
    if not db_url:
        return True
    
    try:
        import psycopg2
        
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # Vérifier si la table users existe et contient des données
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_name = 'users'
        """)
        
        if cur.fetchone()[0] == 0:
            # La table n'existe pas
            conn.close()
            return True
        
        # Vérifier le nombre d'utilisateurs
        cur.execute("SELECT COUNT(*) FROM users")
        users_count = cur.fetchone()[0]
        
        conn.close()
        return users_count == 0
        
    except Exception as e:
        print(f"❌ Erreur lors de la vérification: {e}")
        return True

def find_latest_backup():
    """Trouve la sauvegarde la plus récente."""
    backup_dir = Path("backups")
    if not backup_dir.exists():
        return None
    
    backup_files = list(backup_dir.glob("cmtch_auto_backup_*.sql"))
    if not backup_files:
        return None
    
    # Retourner le fichier le plus récent
    return str(max(backup_files, key=lambda x: x.stat().st_mtime))

def main():
    """Fonction principale du script de sauvegarde automatique."""
    print("🔄 Démarrage du script de sauvegarde automatique...")
    
    # Vérifier si la base de données est vide
    if check_database_empty():
        print("📭 Base de données vide détectée")
        
        # Chercher une sauvegarde à restaurer
        latest_backup = find_latest_backup()
        if latest_backup:
            print(f"🔄 Tentative de restauration depuis {latest_backup}")
            if restore_database(latest_backup):
                print("✅ Restauration réussie")
                return True
            else:
                print("❌ Échec de la restauration")
        else:
            print("📭 Aucune sauvegarde trouvée")
    else:
        print("✅ Base de données contient des données - Sauvegarde uniquement")
        
        # Créer une sauvegarde (sans toucher aux données existantes)
        backup_file = backup_database()
        if backup_file:
            print("✅ Sauvegarde automatique créée")
            
            # Nettoyer les anciennes sauvegardes (garder seulement les 5 plus récentes)
            cleanup_old_backups()
            
            return True
        else:
            print("❌ Échec de la sauvegarde")
    
    return False

def cleanup_old_backups():
    """Nettoie les anciennes sauvegardes, garde seulement les 5 plus récentes."""
    backup_dir = Path("backups")
    if not backup_dir.exists():
        return
    
    backup_files = list(backup_dir.glob("cmtch_auto_backup_*.sql"))
    if len(backup_files) <= 5:
        return
    
    # Trier par date de modification (plus récent en premier)
    backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    # Supprimer les anciens fichiers
    for old_file in backup_files[5:]:
        try:
            old_file.unlink()
            print(f"🗑️ Ancienne sauvegarde supprimée: {old_file.name}")
        except Exception as e:
            print(f"❌ Erreur lors de la suppression de {old_file.name}: {e}")

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
