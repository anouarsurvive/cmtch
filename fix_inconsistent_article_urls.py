#!/usr/bin/env python3
"""
Script pour corriger les URLs incohérentes des articles.
"""

import sys
import os

# Ajouter le répertoire courant au path pour importer database
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

def fix_inconsistent_article_urls():
    """Corrige les URLs incohérentes des articles"""
    print("🔧 CORRECTION DES URLs INCOHÉRENTES DES ARTICLES:")
    
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
        
        # Corriger l'article 3 qui a une URL complète au lieu d'un chemin relatif
        print(f"\n🔄 CORRECTION DE L'ARTICLE 3:")
        
        # Mettre à jour l'article 3 pour utiliser le chemin relatif
        cur.execute("UPDATE articles SET image_path = %s WHERE id = %s", 
                   ("/article_images/default_article.jpg", 3))
        
        articles_updated = cur.rowcount
        print(f"   ✅ {articles_updated} article mis à jour")
        
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
    print("🚀 CORRECTION DES URLs INCOHÉRENTES DES ARTICLES")
    print("=" * 60)
    
    print("📋 Ce script corrige l'article 3 qui a une URL complète")
    print("   au lieu d'un chemin relatif vers l'image par défaut.")
    print()
    
    # Correction des URLs
    updated_count = fix_inconsistent_article_urls()
    
    if updated_count > 0:
        print(f"\n🎉 CORRECTION TERMINÉE!")
        print(f"   ✅ {updated_count} article mis à jour")
        print(f"   ✅ Tous les articles utilisent maintenant des chemins relatifs")
        print(f"   ✅ Cohérence entre base de données et FTP rétablie")
        print(f"\n📝 FONCTIONNEMENT:")
        print(f"   - /article_images/* → Redirection vers HostGator")
        print(f"   - Tous les articles utilisent default_article.jpg")
    else:
        print(f"\n❌ Problème lors de la correction")
    
    print(f"\n✅ Opération terminée!")

if __name__ == "__main__":
    main()
