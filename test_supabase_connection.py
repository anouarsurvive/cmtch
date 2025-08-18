#!/usr/bin/env python3
"""
Script de test pour vérifier la connexion Supabase
"""

import os
import sys

def test_supabase_connection():
    """Teste la connexion à Supabase."""
    
    print("🔍 Test de connexion Supabase")
    print("=" * 50)
    
    # Vérifier si DATABASE_URL est définie
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("❌ DATABASE_URL non définie")
        print("💡 Ajoutez DATABASE_URL dans les variables d'environnement")
        return False
    
    print(f"✅ DATABASE_URL trouvée")
    
    # Vérifier si c'est une URL Supabase
    if 'supabase.co' in database_url:
        print("✅ URL Supabase détectée")
    else:
        print("⚠️ URL ne semble pas être Supabase")
    
    # Tester la connexion
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        print("🔄 Test de connexion...")
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        # Test simple
        cur.execute("SELECT version()")
        version = cur.fetchone()
        print(f"✅ Connexion réussie - PostgreSQL {version[0]}")
        
        # Vérifier les tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = cur.fetchall()
        
        print(f"📋 Tables trouvées : {len(tables)}")
        for table in tables:
            print(f"  - {table[0]}")
        
        conn.close()
        return True
        
    except ImportError:
        print("❌ psycopg2 non installé")
        print("💡 Installez : pip install psycopg2-binary")
        return False
        
    except Exception as e:
        print(f"❌ Erreur de connexion : {e}")
        print("💡 Vérifiez l'URL de connexion")
        return False

def main():
    """Fonction principale."""
    success = test_supabase_connection()
    
    if success:
        print("\n🎉 Connexion Supabase réussie !")
        print("✅ Votre base de données est prête")
    else:
        print("\n❌ Échec de la connexion")
        print("💡 Vérifiez la configuration")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
