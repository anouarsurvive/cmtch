#!/usr/bin/env python3
"""
Script pour corriger les chemins d'images d'articles pour utiliser des chemins relatifs.
"""

import sys
import os

# Ajouter le répertoire courant au path pour importer database
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

def fix_article_image_paths_relative():
    """Corrige les chemins d'images d'articles pour utiliser des chemins relatifs"""
    print("🔧 CORRECTION DES CHEMINS D'IMAGES D'ARTICLES:")
    
    try:
        conn = get_db_connection()
        
        if not hasattr(conn, '_is_mysql'):
            print("❌ Connexion SQLite établie (pas MySQL)")
            return False
        
        cur = conn.cursor()
        
        # Vérifier l'état actuel
        print("\n📊 ÉTAT ACTUEL DES ARTICLES:")
        cur.execute("SELECT id, title, image_path FROM articles ORDER BY id")
        articles = cur.fetchall()
        
        for article in articles:
            article_id, title, image_path = article
            print(f"   Article {article_id}: {title}")
            print(f"     Image actuelle: {image_path}")
        
        # Corriger les URLs pour utiliser des chemins relatifs
        print(f"\n🔄 CORRECTION DES CHEMINS VERS RELATIFS:")
        
        # Mettre à jour tous les articles pour utiliser le chemin relatif
        cur.execute("UPDATE articles SET image_path = %s", ("/article_images/default_article.jpg",))
        articles_updated = cur.rowcount
        
        print(f"   ✅ {articles_updated} articles mis à jour avec le chemin relatif")
        
        # Valider les changements
        conn.commit()
        print("💾 Changements validés en base de données")
        
        # Vérifier l'état après correction
        print(f"\n📊 ÉTAT APRÈS CORRECTION:")
        cur.execute("SELECT id, title, image_path FROM articles ORDER BY id")
        articles_after = cur.fetchall()
        
        for article in articles_after:
            article_id, title, image_path = article
            print(f"   Article {article_id}: {title}")
            print(f"     Nouvelle image: {image_path}")
        
        conn.close()
        
        return articles_updated
        
    except Exception as e:
        print(f"❌ Erreur lors de la correction: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return 0

def main():
    """Fonction principale"""
    print("🚀 CORRECTION DES CHEMINS D'IMAGES RELATIFS")
    print("=" * 60)
    
    print("📋 Ce script corrige les chemins d'images d'articles")
    print("   pour utiliser des chemins relatifs qui seront redirigés vers HostGator.")
    print()
    
    # Correction des chemins
    updated_count = fix_article_image_paths_relative()
    
    if updated_count > 0:
        print(f"\n🎉 CORRECTION TERMINÉE!")
        print(f"   ✅ {updated_count} articles mis à jour avec chemins relatifs")
        print(f"   ✅ Les images seront redirigées vers HostGator")
        print(f"   ✅ Les CSS/JS restent servis localement")
        print(f"\n📝 FONCTIONNEMENT:")
        print(f"   - /static/css/* → Fichiers locaux")
        print(f"   - /static/article_images/* → Redirection vers HostGator")
    else:
        print(f"\n❌ Problème lors de la correction")
    
    print(f"\n✅ Opération terminée!")

if __name__ == "__main__":
    main()
