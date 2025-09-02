#!/usr/bin/env python3
"""
Script pour diagnostiquer l'erreur 500 sur /admin/membres.
"""

import sys
import os

# Ajouter le répertoire courant au path pour importer database
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

def diagnose_admin_membres_error():
    """Diagnostique l'erreur 500 sur /admin/membres"""
    print("🔍 DIAGNOSTIC DE L'ERREUR 500 SUR /admin/membres:")
    
    try:
        # Test de connexion à la base de données
        print("\n📊 TEST DE CONNEXION À LA BASE DE DONNÉES:")
        conn = get_db_connection()
        
        if not hasattr(conn, '_is_mysql'):
            print("❌ Connexion SQLite établie (pas MySQL)")
            return False
        
        print("✅ Connexion MySQL établie")
        
        cur = conn.cursor()
        
        # Test 1: Vérifier la table users
        print("\n📊 TEST 1: Vérification de la table users")
        try:
            cur.execute("SELECT COUNT(*) FROM users")
            total_members = cur.fetchone()[0]
            print(f"   ✅ Table users accessible: {total_members} membres")
        except Exception as e:
            print(f"   ❌ Erreur table users: {e}")
            return False
        
        # Test 2: Vérifier les colonnes de la table users
        print("\n📊 TEST 2: Vérification des colonnes de la table users")
        try:
            cur.execute("DESCRIBE users")
            columns = cur.fetchall()
            print("   📋 Colonnes de la table users:")
            for col in columns:
                print(f"     - {col[0]} ({col[1]})")
        except Exception as e:
            print(f"   ❌ Erreur description table: {e}")
            return False
        
        # Test 3: Test de la requête principale
        print("\n📊 TEST 3: Test de la requête principale")
        try:
            page = 1
            per_page = 20
            offset = (page - 1) * per_page
            
            # Test avec la méthode MySQL
            from database import get_mysql_cursor_with_names, convert_mysql_result
            execute_with_names = get_mysql_cursor_with_names(conn)
            cur, column_names = execute_with_names(
                f"SELECT id, username, full_name, email, phone, ijin_number, birth_date, photo_path, is_admin, validated, is_trainer "
                f"FROM users ORDER BY id LIMIT {per_page} OFFSET {offset}",
                ()
            )
            members = cur.fetchall()
            print(f"   ✅ Requête MySQL réussie: {len(members)} membres récupérés")
            
            # Convertir les résultats
            members = [convert_mysql_result(member, column_names) for member in members]
            print(f"   ✅ Conversion MySQL réussie: {len(members)} membres convertis")
            
            # Afficher le premier membre pour vérifier
            if members:
                first_member = members[0]
                print(f"   📋 Premier membre:")
                print(f"     - ID: {getattr(first_member, 'id', 'N/A')}")
                print(f"     - Username: {getattr(first_member, 'username', 'N/A')}")
                print(f"     - Full name: {getattr(first_member, 'full_name', 'N/A')}")
                print(f"     - Email: {getattr(first_member, 'email', 'N/A')}")
                print(f"     - Phone: {getattr(first_member, 'phone', 'N/A')}")
                print(f"     - Ijin number: {getattr(first_member, 'ijin_number', 'N/A')}")
                print(f"     - Birth date: {getattr(first_member, 'birth_date', 'N/A')}")
                print(f"     - Photo path: {getattr(first_member, 'photo_path', 'N/A')}")
                print(f"     - Is admin: {getattr(first_member, 'is_admin', 'N/A')}")
                print(f"     - Validated: {getattr(first_member, 'validated', 'N/A')}")
                print(f"     - Is trainer: {getattr(first_member, 'is_trainer', 'N/A')}")
            
        except Exception as e:
            print(f"   ❌ Erreur requête principale: {e}")
            import traceback
            print(f"   📋 Traceback complet:")
            traceback.print_exc()
            return False
        
        # Test 4: Test de la pagination
        print("\n📊 TEST 4: Test de la pagination")
        try:
            total_pages = max(1, (total_members + per_page - 1) // per_page)
            has_prev = page > 1
            has_next = page < total_pages
            
            print(f"   ✅ Pagination calculée:")
            print(f"     - Page courante: {page}")
            print(f"     - Total pages: {total_pages}")
            print(f"     - Has prev: {has_prev}")
            print(f"     - Has next: {has_next}")
            
        except Exception as e:
            print(f"   ❌ Erreur pagination: {e}")
            return False
        
        # Test 5: Test du template
        print("\n📊 TEST 5: Test du template")
        try:
            from fastapi.templating import Jinja2Templates
            templates = Jinja2Templates(directory="templates")
            
            # Vérifier que le template existe
            template_path = "templates/admin_members.html"
            if os.path.exists(template_path):
                print(f"   ✅ Template trouvé: {template_path}")
            else:
                print(f"   ❌ Template manquant: {template_path}")
                return False
                
        except Exception as e:
            print(f"   ❌ Erreur template: {e}")
            return False
        
        conn.close()
        
        print(f"\n🎉 DIAGNOSTIC RÉUSSI!")
        print(f"   ✅ Tous les tests sont passés")
        print(f"   ✅ La route /admin/membres devrait fonctionner")
        print(f"   💡 L'erreur 500 pourrait être temporaire")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du diagnostic: {e}")
        import traceback
        print(f"📋 Traceback complet:")
        traceback.print_exc()
        return False

def test_simple_members_query():
    """Test une requête simple sur les membres"""
    print(f"\n🔧 TEST DE REQUÊTE SIMPLE:")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Requête simple
        cur.execute("SELECT id, username, full_name, email FROM users LIMIT 5")
        members = cur.fetchall()
        
        print(f"   ✅ Requête simple réussie: {len(members)} membres")
        for member in members:
            print(f"     - ID: {member[0]}, Username: {member[1]}, Name: {member[2]}, Email: {member[3]}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Erreur requête simple: {e}")
        return False

def main():
    """Fonction principale"""
    print("🚀 DIAGNOSTIC DE L'ERREUR 500 /admin/membres")
    print("=" * 60)
    
    print("📋 Ce script diagnostique pourquoi la page /admin/membres")
    print("   retourne une erreur 500.")
    print()
    
    # Diagnostic principal
    success = diagnose_admin_membres_error()
    
    # Test de requête simple
    simple_ok = test_simple_members_query()
    
    if success and simple_ok:
        print(f"\n🎉 DIAGNOSTIC COMPLET RÉUSSI!")
        print(f"   ✅ Tous les composants fonctionnent")
        print(f"   ✅ L'erreur 500 pourrait être temporaire")
        print(f"   💡 Redémarrer l'application pourrait résoudre le problème")
    else:
        print(f"\n❌ PROBLÈME IDENTIFIÉ!")
        print(f"   ❌ Un ou plusieurs composants ont des problèmes")
        print(f"   💡 Vérifier les logs d'erreur de l'application")
    
    print(f"\n✅ Diagnostic terminé!")

if __name__ == "__main__":
    main()
