#!/usr/bin/env python3
"""Script pour ajouter la table user_sessions à la base MySQL de production"""

import os
import mysql.connector
from mysql.connector import Error

def add_sessions_table():
    try:
        # Configuration de la base de données MySQL
        connection = mysql.connector.connect(
            host=os.getenv('MYSQL_HOST', 'localhost'),
            database=os.getenv('MYSQL_DATABASE', 'imprimer_cmtch_tennis'),
            user=os.getenv('MYSQL_USER', 'root'),
            password=os.getenv('MYSQL_PASSWORD', ''),
            port=int(os.getenv('MYSQL_PORT', '3306'))
        )
        
        if connection.is_connected():
            print("✅ Connexion à MySQL réussie")
            
            cursor = connection.cursor()
            
            # Vérifier si la table existe déjà
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = %s AND table_name = 'user_sessions'
            """, (os.getenv('MYSQL_DATABASE', 'imprimer_cmtch_tennis'),))
            
            table_exists = cursor.fetchone()[0] > 0
            
            if table_exists:
                print("✅ Table 'user_sessions' existe déjà")
            else:
                print("📦 Création de la table 'user_sessions'...")
                
                # Créer la table user_sessions
                cursor.execute("""
                    CREATE TABLE user_sessions (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id INT NOT NULL,
                        session_token VARCHAR(255) UNIQUE NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL,
                        ip_address VARCHAR(45),
                        user_agent TEXT,
                        is_active TINYINT(1) DEFAULT 1,
                        FOREIGN KEY(user_id) REFERENCES users(id)
                    )
                """)
                
                # Créer les index
                cursor.execute("CREATE INDEX idx_sessions_token ON user_sessions(session_token)")
                cursor.execute("CREATE INDEX idx_sessions_user ON user_sessions(user_id)")
                cursor.execute("CREATE INDEX idx_sessions_expires ON user_sessions(expires_at)")
                
                connection.commit()
                print("✅ Table 'user_sessions' créée avec succès")
                print("✅ Index créés avec succès")
            
            # Vérifier les tables existantes
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            print(f"📋 Tables existantes: {[table[0] for table in tables]}")
            
    except Error as e:
        print(f"❌ Erreur MySQL: {e}")
    except Exception as e:
        print(f"❌ Erreur: {e}")
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()
            print("✅ Connexion fermée")

if __name__ == "__main__":
    add_sessions_table()
