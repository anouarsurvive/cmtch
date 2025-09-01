#!/usr/bin/env python3
"""
Script d'initialisation des tables HostGator MySQL
"""

import os
import sys

def init_hostgator_tables():
    """Initialise les tables dans la base de données HostGator."""
    
    print("🏗️ Initialisation des tables HostGator MySQL")
    print("=" * 50)
    
    try:
        import mysql.connector
        from mysql.connector import Error
        
        # Informations de connexion
        config = {
            "user": "imprimer_cmtch_user",
            "password": "Anouar881984?",
            "host": "gator3060.hostgator.com",
            "port": 3306,
            "database": "imprimer_cmtch_tennis"
        }
        
        print("🔄 Connexion à la base de données...")
        conn = mysql.connector.connect(**config)
        cur = conn.cursor()
        
        print("✅ Connexion réussie !")
        
        # Table des utilisateurs
        print("📋 Création de la table users...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(255),
                email VARCHAR(255),
                phone VARCHAR(50),
                ijin_number VARCHAR(100),
                birth_date VARCHAR(20),
                photo_path VARCHAR(500),
                is_admin TINYINT DEFAULT 0,
                validated TINYINT DEFAULT 0,
                is_trainer TINYINT DEFAULT 0,
                email_verification_token VARCHAR(255) NULL,
                email_verified TINYINT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table des articles
        print("📋 Création de la table articles...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                content TEXT,
                image_path VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table des réservations
        print("📋 Création de la table reservations...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                court_number INT NOT NULL,
                date DATE NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        conn.commit()
        print("✅ Tables créées avec succès !")
        
        # Créer l'utilisateur admin
        print("👤 Création de l'utilisateur admin...")
        
        # Vérifier si l'admin existe déjà
        cur.execute("SELECT id FROM users WHERE username = 'admin'")
        admin_exists = cur.fetchone()
        
        if not admin_exists:
            import hashlib
            admin_password = "admin"
            admin_password_hash = hashlib.sha256(admin_password.encode("utf-8")).hexdigest()
            
            cur.execute("""
                INSERT INTO users (username, password_hash, full_name, email, phone, ijin_number, birth_date, is_admin, validated, is_trainer)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, ("admin", admin_password_hash, "Administrateur", "admin@cmtch.tn", "+21612345678", "ADMIN001", "1990-01-01", 1, 1, 0))
            
            conn.commit()
            print("✅ Utilisateur admin créé !")
            print("   👤 Username: admin")
            print("   🔑 Password: admin")
        else:
            print("ℹ️ Utilisateur admin existe déjà")
        
        # Vérifier les tables créées
        print("\n📊 État des tables :")
        cur.execute("SHOW TABLES")
        tables = cur.fetchall()
        for table in tables:
            table_name = table[0]
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cur.fetchone()[0]
            print(f"   - {table_name}: {count} enregistrement(s)")
        
        conn.close()
        print("\n🎉 Initialisation terminée avec succès !")
        
    except Error as e:
        print(f"❌ Erreur MySQL: {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False
    
    return True

if __name__ == "__main__":
    init_hostgator_tables()
