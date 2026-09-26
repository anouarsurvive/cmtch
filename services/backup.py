# -*- coding: utf-8 -*-
"""Sauvegarde / restauration de la base de données."""
from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.config import BASE_DIR, DB_PATH
from core.session import get_db_connection


def backup_database():
    """CrÃ©e une sauvegarde de la base de donnÃ©es."""
    try:
        import shutil
        from datetime import datetime
        
        # CrÃ©er le dossier de sauvegarde s'il n'existe pas
        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)
        
        # Nom du fichier de sauvegarde avec timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}.db"
        backup_path = backup_dir / backup_filename
        
        # VÃ©rifier le type de base de donnÃ©es
        database_url = os.getenv('DATABASE_URL')
        
        if database_url and 'mysql://' in database_url:
            # Pour MySQL, on ne peut pas faire une copie directe du fichier
            # On va exporter les donnÃ©es en SQL
            return backup_mysql_database(backup_path)
        elif database_url:
            # Pour PostgreSQL, on ne peut pas faire une copie directe du fichier
            # On va exporter les donnÃ©es en SQL
            return backup_postgresql_database(backup_path)
        else:
            # Pour SQLite, on peut copier le fichier directement
            source_db = Path("database.db")
            if source_db.exists():
                shutil.copy2(source_db, backup_path)
                print(f"âœ… Sauvegarde SQLite crÃ©Ã©e: {backup_path}")
                return str(backup_path)
            else:
                print("âŒ Fichier de base de donnÃ©es SQLite non trouvÃ©")
                return None
                
    except Exception as e:
        print(f"âŒ Erreur lors de la sauvegarde: {e}")
        return None

def backup_mysql_database(backup_path):
    """CrÃ©e une sauvegarde de la base de donnÃ©es MySQL."""
    try:
        import mysql.connector
        
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return None
            
        # Parser l'URL MySQL
        url_parts = database_url.replace('mysql://', '').split('@')
        user_pass = url_parts[0].split(':')
        host_db = url_parts[1].split('/')
        host_port = host_db[0].split(':')
        
        user = user_pass[0]
        password = user_pass[1]
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 3306
        database = host_db[1]
        
        # Connexion Ã  MySQL
        conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        
        # CrÃ©er le fichier de sauvegarde SQL
        sql_backup_path = str(backup_path).replace('.db', '.sql')
        
        with open(sql_backup_path, 'w', encoding='utf-8') as f:
            # Obtenir la liste des tables
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            
            for table in tables:
                table_name = table[0]
                f.write(f"\n-- Table: {table_name}\n")
                f.write(f"DROP TABLE IF EXISTS `{table_name}`;\n")
                
                # Obtenir la structure de la table
                cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
                create_table = cursor.fetchone()
                f.write(f"{create_table[1]};\n\n")
                
                # Obtenir les donnÃ©es de la table
                cursor.execute(f"SELECT * FROM `{table_name}`")
                rows = cursor.fetchall()
                
                if rows:
                    # Obtenir les noms des colonnes
                    cursor.execute(f"DESCRIBE `{table_name}`")
                    columns = [col[0] for col in cursor.fetchall()]
                    
                    for row in rows:
                        values = []
                        for value in row:
                            if value is None:
                                values.append('NULL')
                            elif isinstance(value, str):
                                values.append(f"'{value.replace(chr(39), chr(39)+chr(39))}'")
                            else:
                                values.append(str(value))
                        
                        f.write(f"INSERT INTO `{table_name}` (`{'`, `'.join(columns)}`) VALUES ({', '.join(values)});\n")
        
        conn.close()
        print(f"âœ… Sauvegarde MySQL crÃ©Ã©e: {sql_backup_path}")
        return sql_backup_path
        
    except Exception as e:
        print(f"âŒ Erreur lors de la sauvegarde MySQL: {e}")
        return None

def backup_postgresql_database(backup_path):
    """CrÃ©e une sauvegarde de la base de donnÃ©es PostgreSQL."""
    try:
        import psycopg2
        
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return None
            
        # Connexion Ã  PostgreSQL
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # CrÃ©er le fichier de sauvegarde SQL
        sql_backup_path = str(backup_path).replace('.db', '.sql')
        
        with open(sql_backup_path, 'w', encoding='utf-8') as f:
            # Obtenir la liste des tables
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """)
            tables = cursor.fetchall()
            
            for table in tables:
                table_name = table[0]
                f.write(f"\n-- Table: {table_name}\n")
                f.write(f"DROP TABLE IF EXISTS \"{table_name}\" CASCADE;\n")
                
                # Obtenir la structure de la table
                cursor.execute(f"""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = '{table_name}' AND table_schema = 'public'
                    ORDER BY ordinal_position
                """)
                columns = cursor.fetchall()
                
                if columns:
                    f.write(f"CREATE TABLE \"{table_name}\" (\n")
                    column_defs = []
                    for col in columns:
                        col_name, data_type, is_nullable, default_val = col
                        col_def = f'    "{col_name}" {data_type}'
                        if is_nullable == 'NO':
                            col_def += ' NOT NULL'
                        if default_val:
                            col_def += f' DEFAULT {default_val}'
                        column_defs.append(col_def)
                    f.write(',\n'.join(column_defs))
                    f.write("\n);\n\n")
                
                # Obtenir les donnÃ©es de la table
                cursor.execute(f'SELECT * FROM "{table_name}"')
                rows = cursor.fetchall()
                
                if rows:
                    # Obtenir les noms des colonnes
                    column_names = [desc[0] for desc in cursor.description]
                    
                    for row in rows:
                        values = []
                        for value in row:
                            if value is None:
                                values.append('NULL')
                            elif isinstance(value, str):
                                values.append(f"'{value.replace(chr(39), chr(39)+chr(39))}'")
                            else:
                                values.append(str(value))
                        
                        columns_str = '", "'.join(column_names)
                        f.write(f'INSERT INTO "{table_name}" ("{columns_str}") VALUES ({", ".join(values)});\n')
        
        conn.close()
        print(f"âœ… Sauvegarde PostgreSQL crÃ©Ã©e: {sql_backup_path}")
        return sql_backup_path
        
    except Exception as e:
        print(f"âŒ Erreur lors de la sauvegarde PostgreSQL: {e}")
        return None

def find_latest_backup():
    """Trouve la sauvegarde la plus rÃ©cente."""
    try:
        backup_dir = Path("backups")
        if not backup_dir.exists():
            return None
            
        # Chercher les fichiers de sauvegarde
        backup_files = []
        for file_path in backup_dir.glob("backup_*.db"):
            backup_files.append(file_path)
        for file_path in backup_dir.glob("backup_*.sql"):
            backup_files.append(file_path)
            
        if not backup_files:
            return None
            
        # Retourner le fichier le plus rÃ©cent
        latest_backup = max(backup_files, key=lambda x: x.stat().st_mtime)
        return str(latest_backup)
        
    except Exception as e:
        print(f"âŒ Erreur lors de la recherche de sauvegarde: {e}")
        return None

def restore_database(backup_path):
    """Restaure la base de donnÃ©es depuis une sauvegarde."""
    try:
        backup_path = Path(backup_path)
        if not backup_path.exists():
            print(f"âŒ Fichier de sauvegarde non trouvÃ©: {backup_path}")
            return False
            
        # VÃ©rifier le type de base de donnÃ©es
        database_url = os.getenv('DATABASE_URL')
        
        if database_url and 'mysql://' in database_url:
            return restore_mysql_database(backup_path)
        elif database_url:
            return restore_postgresql_database(backup_path)
        else:
            return restore_sqlite_database(backup_path)
            
    except Exception as e:
        print(f"âŒ Erreur lors de la restauration: {e}")
        return False

def restore_sqlite_database(backup_path):
    """Restaure la base de donnÃ©es SQLite depuis une sauvegarde."""
    try:
        import shutil
        
        # Sauvegarder la base actuelle
        current_db = Path("database.db")
        if current_db.exists():
            backup_current = Path("database_backup_before_restore.db")
            shutil.copy2(current_db, backup_current)
            print(f"âœ… Sauvegarde de la base actuelle: {backup_current}")
        
        # Restaurer depuis la sauvegarde
        shutil.copy2(backup_path, current_db)
        print(f"âœ… Base de donnÃ©es SQLite restaurÃ©e depuis: {backup_path}")
        return True
        
    except Exception as e:
        print(f"âŒ Erreur lors de la restauration SQLite: {e}")
        return False

def restore_mysql_database(backup_path):
    """Restaure la base de donnÃ©es MySQL depuis une sauvegarde."""
    try:
        import mysql.connector
        
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return False
            
        # Parser l'URL MySQL
        url_parts = database_url.replace('mysql://', '').split('@')
        user_pass = url_parts[0].split(':')
        host_db = url_parts[1].split('/')
        host_port = host_db[0].split(':')
        
        user = user_pass[0]
        password = user_pass[1]
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 3306
        database = host_db[1]
        
        # Connexion Ã  MySQL
        conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        
        # Lire et exÃ©cuter le fichier SQL
        with open(backup_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
            
        cursor = conn.cursor()
        
        # ExÃ©cuter les commandes SQL une par une
        for statement in sql_content.split(';'):
            statement = statement.strip()
            if statement:
                try:
                    cursor.execute(statement)
                except Exception as e:
                    print(f"âš ï¸ Erreur lors de l'exÃ©cution de: {statement[:50]}... - {e}")
        
        conn.commit()
        conn.close()
        print(f"âœ… Base de donnÃ©es MySQL restaurÃ©e depuis: {backup_path}")
        return True
        
    except Exception as e:
        print(f"âŒ Erreur lors de la restauration MySQL: {e}")
        return False

def restore_postgresql_database(backup_path):
    """Restaure la base de donnÃ©es PostgreSQL depuis une sauvegarde."""
    try:
        import psycopg2
        
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return False
            
        # Connexion Ã  PostgreSQL
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Lire et exÃ©cuter le fichier SQL
        with open(backup_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
            
        # ExÃ©cuter les commandes SQL une par une
        for statement in sql_content.split(';'):
            statement = statement.strip()
            if statement:
                try:
                    cursor.execute(statement)
                except Exception as e:
                    print(f"âš ï¸ Erreur lors de l'exÃ©cution de: {statement[:50]}... - {e}")
        
        conn.commit()
        conn.close()
        print(f"âœ… Base de donnÃ©es PostgreSQL restaurÃ©e depuis: {backup_path}")
        return True
        
    except Exception as e:
        print(f"âŒ Erreur lors de la restauration PostgreSQL: {e}")
        return False

def auto_backup_system():
    """SystÃ¨me de sauvegarde automatique pour prÃ©server les donnÃ©es sur Render."""
    try:
        print("ðŸ”„ DÃ©marrage du systÃ¨me de sauvegarde automatique...")
        
        # VÃ©rifier si le systÃ¨me est dÃ©sactivÃ©
        flag_file = Path("DISABLE_AUTO_BACKUP")
        if flag_file.exists():
            print("ðŸš« SystÃ¨me de sauvegarde automatique dÃ©sactivÃ© par l'utilisateur")
            return
        
        # VÃ©rifier si on est sur Render (prÃ©sence de DATABASE_URL)
        if not os.getenv('DATABASE_URL'):
            print("â„¹ï¸ Pas sur Render - systÃ¨me de sauvegarde ignorÃ©")
            return
        
        # VÃ©rifier d'abord si la base de donnÃ©es contient des donnÃ©es
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # VÃ©rifier si la table users existe et contient des donnÃ©es
            cur.execute("SELECT COUNT(*) FROM users")
            users_count = cur.fetchone()[0]
            
            if users_count > 0:
                print(f"âœ… Base de donnÃ©es contient {users_count} utilisateur(s) - Sauvegarde uniquement")
                # Si des donnÃ©es existent, faire seulement une sauvegarde
                backup_file = backup_database()
                if backup_file:
                    print(f"âœ… Sauvegarde crÃ©Ã©e: {backup_file}")
                else:
                    print("âš ï¸ Ã‰chec de la sauvegarde")
            else:
                print("ðŸ“­ Base de donnÃ©es vide - Tentative de restauration")
                # Si la base est vide, essayer de restaurer
                latest_backup = find_latest_backup()
                if latest_backup:
                    print(f"ðŸ”„ Restauration depuis {latest_backup}")
                    if restore_database(latest_backup):
                        print("âœ… Restauration rÃ©ussie")
                    else:
                        print("âŒ Ã‰chec de la restauration")
                else:
                    print("ðŸ“­ Aucune sauvegarde trouvÃ©e")
                    
        except Exception as e:
            print(f"âŒ Erreur lors de la vÃ©rification de la base: {e}")
        finally:
            conn.close()
            
    except Exception as e:
        print(f"âŒ Erreur dans le systÃ¨me de sauvegarde automatique: {e}")

#
# Si vous voulez l'activer, utilisez l'endpoint /enable-auto-backup
# Si vous voulez le dÃ©sactiver, utilisez l'endpoint /disable-auto-backup
#

