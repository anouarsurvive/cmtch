#!/usr/bin/env python3
"""
Test rapide de connexion HostGator MySQL
"""

import os
import sys

def test_hostgator_connection():
    """Test de connexion HostGator MySQL"""
    
    print("🧪 Test de connexion HostGator MySQL")
    print("=" * 50)
    
    # URL de connexion
    database_url = "mysql://imprimer_cmtch_user:Anouar881984?@gator3060.hostgator.com:3306/imprimer_cmtch_tennis"
    print(f"🔗 URL : {database_url}")
    
    try:
        import mysql.connector
        from mysql.connector import Error
        
        print("🔄 Tentative de connexion...")
        
        # Parser l'URL
        url_parts = database_url.replace('mysql://', '').split('@')
        user_pass = url_parts[0].split(':')
        host_db = url_parts[1].split('/')
        host_port = host_db[0].split(':')
        
        user = user_pass[0]
        password = user_pass[1]
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 3306
        database = host_db[1]
        
        print(f"👤 Utilisateur : {user}")
        print(f"🌐 Hôte : {host}")
        print(f"🔌 Port : {port}")
        print(f"🗄️ Base : {database}")
        
        # Connexion
        conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
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
            
            # Vérifier les utilisateurs
            cur.execute("SELECT COUNT(*) FROM users")
            users_count = cur.fetchone()[0]
            print(f"👥 Utilisateurs : {users_count}")
            
            conn.close()
            return True
        else:
            print("❌ Échec de la connexion MySQL")
            return False
            
    except ImportError:
        print("❌ mysql-connector-python non installé")
        return False
        
    except Exception as e:
        print(f"❌ Erreur de connexion : {e}")
        return False

if __name__ == "__main__":
    success = test_hostgator_connection()
    if success:
        print("\n🎉 Test réussi ! La connexion HostGator fonctionne.")
    else:
        print("\n💥 Test échoué. Vérifiez la configuration.")
    sys.exit(0 if success else 1)
