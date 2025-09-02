#!/usr/bin/env python3
"""
Script pour utiliser l'image par défaut pour tous les articles (seule image accessible).
"""

import sys
import os

# Ajouter le répertoire courant au path pour importer database
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

def fix_all_images_to_default():
    """Utilise l'image par défaut pour tous les articles"""
    print("🔧 CORRECTION VERS IMAGE PAR DÉFAUT (SEULE IMAGE ACCESSIBLE):")
    
    try:
        conn = get_db_connection()
        
        if hasattr(conn, '_is_mysql'):
            print("🔌 Connexion MySQL établie")
        else:
            print("❌ Connexion SQLite établie (pas MySQL)")
            return
        
        cur = conn.cursor()
        
        # Vérifier l'état actuel des articles
        print("\n📊 ÉTAT ACTUEL:")
        cur.execute("SELECT COUNT(*) FROM articles")
        total_articles = cur.fetchone()[0]
        print(f"   Total articles: {total_articles}")
        
        # Lister tous les articles avec leurs chemins d'images
        print(f"\n📝 ARTICLES AVANT CORRECTION:")
        cur.execute("SELECT id, title, image_path FROM articles ORDER BY id")
        articles = cur.fetchall()
        
        for article in articles:
            article_id, title, image_path = article
            print(f"   Article {article_id}: {title}")
            print(f"     Image actuelle: {image_path}")
        
        # Remplacer toutes les images par l'image par défaut
        print(f"\n🔄 CORRECTION VERS IMAGE PAR DÉFAUT:")
        default_image_path = "/static/article_images/default_article.jpg"
        
        # Remplacer toutes les images par l'image par défaut
        cur.execute("UPDATE articles SET image_path = %s", (default_image_path,))
        articles_updated = cur.rowcount
        
        print(f"   ✅ {articles_updated} articles mis à jour avec l'image par défaut")
        
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
    print("🚀 CORRECTION VERS IMAGE PAR DÉFAUT")
    print("=" * 60)
    
    print("📋 Ce script va utiliser l'image par défaut pour tous les articles")
    print("   car c'est la seule image accessible sur le serveur web.")
    print("   Image par défaut: /static/article_images/default_article.jpg")
    print()
    
    # Demander confirmation
    confirm = input("❓ Continuer avec la correction? (o/n): ").strip().lower()
    if not confirm.startswith('o'):
        print("❌ Correction annulée")
        return
    
    # Effectuer la correction
    updated_count = fix_all_images_to_default()
    
    if updated_count > 0:
        print(f"\n🎉 Correction terminée!")
        print(f"   - {updated_count} articles mis à jour avec l'image par défaut")
        print(f"   - Tous les articles utilisent maintenant l'image accessible")
        print(f"   - Plus d'erreurs 404 sur les images d'articles")
        print(f"\n📝 Prochaine étape: Vérifier que le site fonctionne")
    else:
        print("\n⚠️ Aucune correction effectuée")
    
    print("\n✅ Opération terminée!")

if __name__ == "__main__":
    main()
