#!/usr/bin/env python3
"""
Script pour corriger les chemins d'images d'articles qui pointent vers /photos/.
"""

import sys
import os

# Ajouter le répertoire courant au path pour importer database
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

def fix_article_photo_paths():
    """Corrige les chemins d'images d'articles qui pointent vers /photos/"""
    print("🔧 CORRECTION DES CHEMINS D'IMAGES D'ARTICLES VERS /PHOTOS/:")
    
    try:
        conn = get_db_connection()
        
        if hasattr(conn, '_is_mysql'):
            print("🔌 Connexion MySQL établie")
        else:
            print("❌ Connexion SQLite établie (pas MySQL)")
            return
        
        cur = conn.cursor()
        
        # Vérifier l'état actuel des articles avec des URLs vers /photos/
        print("\n📊 ÉTAT ACTUEL:")
        cur.execute("SELECT COUNT(*) FROM articles WHERE image_path LIKE '%/photos/%'")
        photos_articles = cur.fetchone()[0]
        print(f"   Articles avec chemins /photos/: {photos_articles}")
        
        # Lister tous les articles avec leurs chemins d'images
        print(f"\n📝 ARTICLES AVANT CORRECTION:")
        cur.execute("SELECT id, title, image_path FROM articles ORDER BY id")
        articles = cur.fetchall()
        
        for article in articles:
            article_id, title, image_path = article
            print(f"   Article {article_id}: {title}")
            print(f"     Image actuelle: {image_path}")
            
            # Identifier le type de chemin
            if image_path and isinstance(image_path, str):
                if '/photos/' in image_path:
                    print(f"     ⚠️  Chemin /photos/ (problématique)")
                elif image_path.startswith('/static/'):
                    print(f"     ✅ Chemin /static/ (valide)")
                elif image_path.startswith('http'):
                    print(f"     🚫 URL externe (problématique)")
                else:
                    print(f"     ❓ Format inconnu")
        
        # Corriger les chemins vers /photos/ en les remplaçant par l'image par défaut
        print(f"\n🔄 CORRECTION DES CHEMINS /PHOTOS/:")
        default_image_path = "/static/article_images/default_article.jpg"
        
        # Remplacer les chemins /photos/ par l'image par défaut
        cur.execute("UPDATE articles SET image_path = %s WHERE image_path LIKE '%/photos/%'", (default_image_path,))
        photos_fixed = cur.rowcount
        
        # Remplacer aussi les URLs externes par l'image par défaut
        cur.execute("UPDATE articles SET image_path = %s WHERE image_path LIKE 'http%'", (default_image_path,))
        urls_fixed = cur.rowcount
        
        print(f"   ✅ {photos_fixed} chemins /photos/ corrigés")
        print(f"   ✅ {urls_fixed} URLs externes corrigées")
        
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
        
        return photos_fixed + urls_fixed
        
    except Exception as e:
        print(f"❌ Erreur lors de la correction: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return 0

def main():
    """Fonction principale"""
    print("🚀 CORRECTION DES CHEMINS /PHOTOS/ - ARTICLES")
    print("=" * 60)
    
    print("⚠️  ATTENTION: Ce script va corriger les chemins d'images d'articles")
    print("   qui pointent vers /photos/ en les remplaçant par l'image par défaut.")
    print()
    
    # Demander confirmation
    confirm = input("❓ Continuer avec la correction? (o/n): ").strip().lower()
    if not confirm.startswith('o'):
        print("❌ Correction annulée")
        return
    
    # Effectuer la correction
    fixed_count = fix_article_photo_paths()
    
    if fixed_count > 0:
        print(f"\n🎉 Correction terminée!")
        print(f"   - {fixed_count} chemins d'images corrigés")
        print(f"   - Tous les articles pointent maintenant vers l'image par défaut")
        print(f"\n📝 Prochaine étape: Vérifier que le site fonctionne")
    else:
        print("\n⚠️ Aucune correction effectuée")
    
    print("\n✅ Opération terminée!")

if __name__ == "__main__":
    main()
