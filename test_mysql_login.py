#!/usr/bin/env python3
"""
Test de connexion MySQL pour diagnostiquer le problème de login
"""

import os
import hashlib

def test_mysql_login():
    """Test de connexion et authentification MySQL"""
    
    print("🧪 Test de connexion et authentification MySQL")
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
        
        # Test 1: Vérifier l'utilisateur admin
        print("\n📋 Test 1: Vérification de l'utilisateur admin")
        cur.execute("SELECT * FROM users WHERE username = 'admin'")
        admin_user = cur.fetchone()
        
        if admin_user:
            print("✅ Utilisateur admin trouvé")
            print(f"   ID: {admin_user[0]}")
            print(f"   Username: {admin_user[1]}")
            print(f"   Password Hash: {admin_user[2][:20]}...")
            print(f"   Full Name: {admin_user[3]}")
            print(f"   Is Admin: {admin_user[9]}")
            print(f"   Validated: {admin_user[10]}")
        else:
            print("❌ Utilisateur admin non trouvé")
        
        # Test 2: Vérifier le hash du mot de passe
        print("\n📋 Test 2: Vérification du hash du mot de passe")
        admin_password = "admin"
        admin_password_hash = hashlib.sha256(admin_password.encode("utf-8")).hexdigest()
        print(f"   Mot de passe: {admin_password}")
        print(f"   Hash attendu: {admin_password_hash}")
        
        if admin_user:
            stored_hash = admin_user[2]
            print(f"   Hash stocké: {stored_hash}")
            print(f"   Hashs identiques: {stored_hash == admin_password_hash}")
        
        # Test 3: Test d'authentification
        print("\n📋 Test 3: Test d'authentification")
        if admin_user:
            stored_hash = admin_user[2]
            if stored_hash == admin_password_hash:
                print("✅ Authentification réussie")
                if admin_user[10] == 1:  # validated
                    print("✅ Utilisateur validé")
                else:
                    print("❌ Utilisateur non validé")
                if admin_user[9] == 1:  # is_admin
                    print("✅ Droits administrateur")
                else:
                    print("❌ Pas de droits administrateur")
            else:
                print("❌ Échec de l'authentification - Hashs différents")
        
        # Test 4: Vérifier la structure de la table
        print("\n📋 Test 4: Structure de la table users")
        cur.execute("DESCRIBE users")
        columns = cur.fetchall()
        print("   Colonnes de la table users:")
        for col in columns:
            print(f"   - {col[0]}: {col[1]}")
        
        # Test 5: Lister tous les utilisateurs
        print("\n📋 Test 5: Liste de tous les utilisateurs")
        cur.execute("SELECT id, username, is_admin, validated FROM users")
        users = cur.fetchall()
        print(f"   Nombre d'utilisateurs: {len(users)}")
        for user in users:
            print(f"   - ID: {user[0]}, Username: {user[1]}, Admin: {user[2]}, Validated: {user[3]}")
        
        conn.close()
        print("\n🎉 Tests terminés !")
        
    except Error as e:
        print(f"❌ Erreur MySQL: {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False
    
    return True

if __name__ == "__main__":
    test_mysql_login()
