#!/usr/bin/env python3
"""
Script de configuration automatique pour HostGator MySQL
"""

import os
import sys

def setup_hostgator_database():
    """Configure automatiquement la base de données HostGator."""
    
    print("🏠 Configuration automatique HostGator MySQL")
    print("=" * 50)
    
    # Informations de connexion HostGator
    HOSTGATOR_CONFIG = {
        "user": "imprimer_cmtch_user",
        "password": "Anouar881984?",
        "database": "imprimer_cmtch_tennis",
        "host": "gator3060.hostgator.com",
        "port": 3306
    }
    
    # URL de connexion MySQL
    database_url = f"mysql://{HOSTGATOR_CONFIG['user']}:{HOSTGATOR_CONFIG['password']}@{HOSTGATOR_CONFIG['host']}:{HOSTGATOR_CONFIG['port']}/{HOSTGATOR_CONFIG['database']}"
    
    print(f"✅ URL de connexion générée : {database_url}")
    
    # Tester la connexion
    try:
        import mysql.connector
        from mysql.connector import Error
        
        print("🔄 Test de connexion MySQL...")
        
        conn = mysql.connector.connect(
            host=HOSTGATOR_CONFIG['host'],
            port=HOSTGATOR_CONFIG['port'],
            user=HOSTGATOR_CONFIG['user'],
            password=HOSTGATOR_CONFIG['password'],
            database=HOSTGATOR_CONFIG['database']
        )
        
        if conn.is_connected():
            print("✅ Connexion MySQL réussie !")
            
            # Vérifier les tables
            cur = conn.cursor()
            cur.execute("SHOW TABLES")
            tables = cur.fetchall()
            
            print(f"📋 Tables existantes : {len(tables)}")
            for table in tables:
                print(f"  - {table[0]}")
            
            conn.close()
            return True
        else:
            print("❌ Échec de la connexion MySQL")
            return False
            
    except ImportError:
        print("❌ mysql-connector-python non installé")
        print("💡 Installez : pip install mysql-connector-python")
        return False
        
    except Exception as e:
        print(f"❌ Erreur de connexion : {e}")
        return False

def create_env_file():
    """Crée un fichier .env avec la configuration HostGator."""
    
    env_content = """# Configuration HostGator MySQL
DATABASE_URL=mysql://imprimer_cmtch_user:Anouar881984?@gator3060.hostgator.com:3306/imprimer_cmtch_tennis
DATABASE_TYPE=mysql
"""
    
    try:
        with open('.env', 'w') as f:
            f.write(env_content)
        print("✅ Fichier .env créé avec la configuration HostGator")
        return True
    except Exception as e:
        print(f"❌ Erreur lors de la création du fichier .env : {e}")
        return False

def main():
    """Fonction principale."""
    
    print("🚀 Configuration HostGator pour CMTCH")
    print("=" * 50)
    
    # Test de connexion
    if setup_hostgator_database():
        print("\n✅ Configuration HostGator réussie !")
        
        # Créer le fichier .env
        if create_env_file():
            print("✅ Fichier .env créé")
        
        print("\n📋 Prochaines étapes :")
        print("1. Ajoutez DATABASE_URL dans les variables d'environnement Render")
        print("2. Redéployez l'application")
        print("3. Testez : curl https://www.cmtch.online/health")
        
        return True
    else:
        print("\n❌ Configuration échouée")
        print("💡 Vérifiez vos informations de connexion HostGator")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
