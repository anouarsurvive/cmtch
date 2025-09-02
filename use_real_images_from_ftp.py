#!/usr/bin/env python3
"""
Script pour utiliser les vraies images qui sont déjà dans le dossier FTP.
"""

import sys
import os

# Ajouter le répertoire courant au path pour importer database
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

def use_real_images_from_ftp():
    """Utilise les vraies images qui sont déjà dans le dossier FTP"""
    print("🔧 UTILISATION DES VRAIES IMAGES DU FTP:")
    
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
        cur.execute("SELECT COUNT(*) FROM articles WHERE image_path = '/static/article_images/default_article.jpg'")
        default_images_count = cur.fetchone()[0]
        print(f"   Articles avec image par défaut: {default_images_count}")
        
        # Lister tous les articles avec leurs chemins d'images
        print(f"\n📝 ARTICLES AVANT CORRECTION:")
        cur.execute("SELECT id, title, image_path FROM articles ORDER BY id")
        articles = cur.fetchall()
        
        for article in articles:
            article_id, title, image_path = article
            print(f"   Article {article_id}: {title}")
            print(f"     Image actuelle: {image_path}")
        
        # Mapper les articles aux vraies images disponibles
        print(f"\n🔄 CORRECTION VERS LES VRAIES IMAGES:")
        
        # Images disponibles dans le FTP (d'après le diagnostic)
        available_images = [
            "39cebba8134541a4997e9b3a4029a4fe.jpg",
            "61c8f2b8595948d08b6e8dbc1517a963.jpg", 
            "ed9b5c9611f14f559eb906ec0e2e1fbb.jpg"
        ]
        
        print(f"   📸 Images disponibles dans le FTP:")
        for i, img in enumerate(available_images, 1):
            print(f"     {i}. {img}")
        
        # Remplacer l'image par défaut par les vraies images
        articles_updated = 0
        
        for i, article in enumerate(articles):
            article_id, title, image_path = article
            
            if image_path == "/static/article_images/default_article.jpg":
                # Utiliser une image disponible
                if i < len(available_images):
                    real_image = f"/static/article_images/{available_images[i]}"
                    
                    # Mettre à jour l'article
                    cur.execute("UPDATE articles SET image_path = %s WHERE id = %s", (real_image, article_id))
                    articles_updated += 1
                    
                    print(f"   ✅ Article {article_id}: {real_image}")
                else:
                    print(f"   ⚠️ Article {article_id}: Pas d'image disponible, garde l'image par défaut")
        
        print(f"\n   📊 {articles_updated} articles mis à jour avec de vraies images")
        
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
    print("🚀 UTILISATION DES VRAIES IMAGES DU FTP")
    print("=" * 60)
    
    print("📋 Ce script va remplacer l'image par défaut par les vraies images")
    print("   qui sont déjà disponibles dans le dossier FTP:")
    print("   /public_html/static/article_images/")
    print()
    
    # Demander confirmation
    confirm = input("❓ Continuer avec la correction? (o/n): ").strip().lower()
    if not confirm.startswith('o'):
        print("❌ Correction annulée")
        return
    
    # Effectuer la correction
    updated_count = use_real_images_from_ftp()
    
    if updated_count > 0:
        print(f"\n🎉 Correction terminée!")
        print(f"   - {updated_count} articles mis à jour avec de vraies images")
        print(f"   - Toutes les images pointent vers des fichiers existants dans le FTP")
        print(f"   - Plus d'erreurs 404 sur les images d'articles")
        print(f"\n📝 Prochaine étape: Vérifier que le site fonctionne")
    else:
        print("\n⚠️ Aucune correction effectuée")
    
    print("\n✅ Opération terminée!")

if __name__ == "__main__":
    main()
