#!/usr/bin/env python3
"""
Script pour vérifier la structure de la base de données MySQL de production.
"""

import sys
import os

# Ajouter le répertoire courant au path pour importer database
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

def check_mysql_structure():
    """Vérifie la structure de la base MySQL"""
    print("🔍 VÉRIFICATION DE LA STRUCTURE MYSQL:")
    
    try:
        conn = get_db_connection()
        
        if hasattr(conn, '_is_mysql'):
            print("🔌 Connexion MySQL établie")
        else:
            print("❌ Connexion SQLite établie (pas MySQL)")
            return
        
        cur = conn.cursor()
        
        # Lister toutes les tables
        print("\n📋 Tables disponibles dans la base:")
        cur.execute("SHOW TABLES")
        tables = cur.fetchall()
        
        if tables:
            for table in tables:
                table_name = table[0]
                print(f"   - {table_name}")
                
                # Compter les lignes dans chaque table
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cur.fetchone()[0]
                    print(f"     → {count} lignes")
                except Exception as e:
                    print(f"     → Erreur: {e}")
        else:
            print("   Aucune table trouvée")
        
        # Vérifier si la table articles existe
        print(f"\n🔍 Recherche de la table 'articles':")
        if any('articles' in table[0].lower() for table in tables):
            print("   ✅ Table 'articles' trouvée")
        else:
            print("   ❌ Table 'articles' non trouvée")
            print("   📝 Tables similaires possibles:")
            for table in tables:
                if 'article' in table[0].lower() or 'post' in table[0].lower() or 'content' in table[0].lower():
                    print(f"     - {table[0]}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur lors de la vérification: {e}")

def main():
    """Fonction principale"""
    print("🚀 VÉRIFICATION DE LA STRUCTURE MYSQL")
    print("=" * 50)
    
    check_mysql_structure()
    
    print("\n✅ Vérification terminée!")

if __name__ == "__main__":
    main()
