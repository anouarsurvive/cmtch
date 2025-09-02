#!/usr/bin/env python3
"""
Script pour examiner toutes les tables de la base de données et identifier les références aux photos.
"""

import sys
import os

# Ajouter le répertoire courant au path pour importer database
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

def check_all_tables_for_photos():
    """Vérifie toutes les tables pour les références aux photos"""
    print("🔍 VÉRIFICATION COMPLÈTE DE LA BASE DE DONNÉES:")
    
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
        
        photo_references = []
        
        for table in tables:
            table_name = table[0]
            print(f"\n🔍 Table: {table_name}")
            
            try:
                # Obtenir la structure de la table
                cur.execute(f"DESCRIBE {table_name}")
                columns = cur.fetchall()
                
                # Chercher les colonnes qui pourraient contenir des chemins de photos
                photo_columns = []
                for col in columns:
                    col_name = col[0]
                    col_type = col[1]
                    
                    # Vérifier si la colonne pourrait contenir des chemins de photos
                    if any(keyword in col_name.lower() for keyword in ['photo', 'image', 'avatar', 'profile']):
                        photo_columns.append(col_name)
                
                if photo_columns:
                    print(f"   📸 Colonnes photos trouvées: {', '.join(photo_columns)}")
                    
                    # Vérifier le contenu de ces colonnes
                    for col in photo_columns:
                        try:
                            cur.execute(f"SELECT DISTINCT {col} FROM {table_name} WHERE {col} IS NOT NULL AND {col} != '' LIMIT 10")
                            values = cur.fetchall()
                            
                            for value in values:
                                photo_path = value[0]
                                if photo_path and isinstance(photo_path, str):
                                    if '/photos/' in photo_path or '/static/' in photo_path:
                                        photo_references.append({
                                            'table': table_name,
                                            'column': col,
                                            'path': photo_path
                                        })
                                        print(f"     → {photo_path}")
                        except Exception as e:
                            print(f"     ❌ Erreur lecture colonne {col}: {e}")
                
                # Compter les lignes dans la table
                cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cur.fetchall()[0][0]
                print(f"   📊 Total: {count} lignes")
                
            except Exception as e:
                print(f"   ❌ Erreur table {table_name}: {e}")
        
        # Résumé des références aux photos
        print(f"\n📸 RÉSUMÉ DES RÉFÉRENCES AUX PHOTOS:")
        if photo_references:
            print(f"   ✅ {len(photo_references)} références aux photos trouvées:")
            for ref in photo_references:
                print(f"     - Table: {ref['table']}, Colonne: {ref['column']}")
                print(f"       Chemin: {ref['path']}")
        else:
            print("   ❌ Aucune référence aux photos trouvée")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur lors de la vérification: {e}")

def main():
    """Fonction principale"""
    print("🚀 VÉRIFICATION COMPLÈTE - RÉFÉRENCES AUX PHOTOS")
    print("=" * 60)
    
    check_all_tables_for_photos()
    
    print("\n✅ Vérification terminée!")

if __name__ == "__main__":
    main()
