#!/usr/bin/env python3
"""
Script pour remplacer les chemins d'images inexistants par les images par défaut en production.
"""

import sys
import os

# Ajouter le répertoire courant au path pour importer database
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

def fix_production_image_paths():
    """Remplace les chemins d'images inexistants par les images par défaut"""
    print("🔧 CORRECTION DES CHEMINS D'IMAGES EN PRODUCTION:")
    
    try:
        conn = get_db_connection()
        
        if hasattr(conn, '_is_mysql'):
            print("🔌 Connexion MySQL établie")
        else:
            print("❌ Connexion SQLite établie (pas MySQL)")
            return
        
        cur = conn.cursor()
        
        # Vérifier l'état actuel
        print("\n📊 ÉTAT ACTUEL:")
        cur.execute("SELECT COUNT(*) FROM articles")
        total_articles = cur.fetchone()[0]
        print(f"   Total des articles: {total_articles}")
        
        # Lister tous les articles avec leurs chemins d'images
        print(f"\n📝 ARTICLES AVANT CORRECTION:")
        cur.execute("SELECT id, title, image_path FROM articles ORDER BY id")
        articles = cur.fetchall()
        
        for article in articles:
            article_id, title, image_path = article
            print(f"   Article {article_id}: {title}")
            print(f"     Image actuelle: {image_path}")
        
        # Remplacer tous les chemins d'images par l'image par défaut
        print(f"\n🔄 REMPLACEMENT DES CHEMINS D'IMAGES:")
        default_image_path = "/static/article_images/default_article.jpg"
        
        cur.execute("UPDATE articles SET image_path = %s", (default_image_path,))
        updated_count = cur.rowcount
        
        print(f"   ✅ {updated_count} articles mis à jour avec l'image par défaut")
        
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
        
        return updated_count
        
    except Exception as e:
        print(f"❌ Erreur lors de la correction: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return 0

def main():
    """Fonction principale"""
    print("🚀 CORRECTION DES CHEMINS D'IMAGES - PRODUCTION")
    print("=" * 60)
    
    print("⚠️  ATTENTION: Ce script va remplacer TOUS les chemins d'images")
    print("   par l'image par défaut dans la base de production.")
    print()
    
    # Demander confirmation
    confirm = input("❓ Continuer avec la correction? (o/n): ").strip().lower()
    if not confirm.startswith('o'):
        print("❌ Correction annulée")
        return
    
    # Effectuer la correction
    updated_count = fix_production_image_paths()
    
    if updated_count > 0:
        print(f"\n🎉 Correction terminée!")
        print(f"   - {updated_count} articles mis à jour")
        print(f"   - Tous pointent maintenant vers l'image par défaut")
        print(f"\n📝 Prochaine étape: Vérifier que le site fonctionne")
    else:
        print("\n⚠️ Aucune correction effectuée")
    
    print("\n✅ Opération terminée!")

if __name__ == "__main__":
    main()
