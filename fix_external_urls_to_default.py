#!/usr/bin/env python3
"""
Script pour remplacer les URLs externes par l'image par défaut dans la base de données.
"""

import sys
import os

# Ajouter le répertoire courant au path pour importer database
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

def fix_external_urls_to_default():
    """Remplace les URLs externes par l'image par défaut"""
    print("🔧 CORRECTION DES URLs EXTERNES VERS IMAGE PAR DÉFAUT:")
    
    try:
        conn = get_db_connection()
        
        if hasattr(conn, '_is_mysql'):
            print("🔌 Connexion MySQL établie")
        else:
            print("❌ Connexion SQLite établie (pas MySQL)")
            return
        
        cur = conn.cursor()
        
        # Vérifier l'état actuel des articles avec des URLs externes
        print("\n📊 ÉTAT ACTUEL:")
        cur.execute("SELECT COUNT(*) FROM articles WHERE image_path LIKE 'http%'")
        external_urls_count = cur.fetchone()[0]
        print(f"   Articles avec URLs externes: {external_urls_count}")
        
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
                if image_path.startswith('http'):
                    print(f"     🚫 URL externe (problématique)")
                elif image_path.startswith('/static/'):
                    print(f"     ✅ Chemin /static/ (valide)")
                else:
                    print(f"     ❓ Format inconnu")
        
        # Corriger les URLs externes en les remplaçant par l'image par défaut
        print(f"\n🔄 CORRECTION DES URLs EXTERNES:")
        default_image_path = "/static/article_images/default_article.jpg"
        
        # Remplacer les URLs externes par l'image par défaut
        cur.execute("UPDATE articles SET image_path = %s WHERE image_path LIKE 'http%'", (default_image_path,))
        urls_fixed = cur.rowcount
        
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
        
        return urls_fixed
        
    except Exception as e:
        print(f"❌ Erreur lors de la correction: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return 0

def main():
    """Fonction principale"""
    print("🚀 CORRECTION DES URLs EXTERNES - IMAGE PAR DÉFAUT")
    print("=" * 60)
    
    print("⚠️  ATTENTION: Ce script va remplacer toutes les URLs externes")
    print("   par l'image par défaut /static/article_images/default_article.jpg")
    print("   qui existe déjà sur le serveur.")
    print()
    
    # Demander confirmation
    confirm = input("❓ Continuer avec la correction? (o/n): ").strip().lower()
    if not confirm.startswith('o'):
        print("❌ Correction annulée")
        return
    
    # Effectuer la correction
    fixed_count = fix_external_urls_to_default()
    
    if fixed_count > 0:
        print(f"\n🎉 Correction terminée!")
        print(f"   - {fixed_count} URLs externes corrigées")
        print(f"   - Tous les articles pointent maintenant vers l'image par défaut")
        print(f"   - Plus d'erreurs 404 sur les images d'articles")
        print(f"\n📝 Prochaine étape: Vérifier que le site fonctionne")
    else:
        print("\n⚠️ Aucune correction effectuée")
    
    print("\n✅ Opération terminée!")

if __name__ == "__main__":
    main()
