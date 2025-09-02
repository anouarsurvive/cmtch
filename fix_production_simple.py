#!/usr/bin/env python3
"""
Script simple pour corriger les images d'articles en production.
Utilise directement la fonction get_db_connection de l'application.
"""

import sys
import os

# Ajouter le répertoire courant au path pour importer database
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

def check_production_articles():
    """Vérifie l'état des articles en production"""
    print("\n🔍 VÉRIFICATION DES ARTICLES EN PRODUCTION:")
    
    try:
        conn = get_db_connection()
        
        # Vérifier le type de connexion
        if hasattr(conn, '_is_mysql'):
            print("🔌 Connexion MySQL établie")
        else:
            print("🔌 Connexion SQLite établie (local)")
        
        cur = conn.cursor()
        
        # Compter le total des articles
        cur.execute("SELECT COUNT(*) FROM articles")
        total_articles = cur.fetchone()[0]
        print(f"📊 Total des articles: {total_articles}")
        
        # Vérifier les articles avec images invalides (URLs externes)
        cur.execute("SELECT COUNT(*) FROM articles WHERE image_path LIKE 'http%'")
        invalid_urls = cur.fetchone()[0]
        print(f"🚫 URLs externes invalides: {invalid_urls}")
        
        # Vérifier les articles sans images
        cur.execute("SELECT COUNT(*) FROM articles WHERE image_path IS NULL OR image_path = ''")
        articles_without_images = cur.fetchone()[0]
        print(f"❌ Articles sans images: {articles_without_images}")
        
        # Afficher quelques exemples d'articles avec images invalides
        if invalid_urls > 0:
            print(f"\n📝 Exemples d'articles avec URLs invalides:")
            cur.execute("SELECT id, title, image_path FROM articles WHERE image_path LIKE 'http%' LIMIT 5")
            invalid_articles = cur.fetchall()
            
            for article in invalid_articles:
                article_id, title, image_path = article
                print(f"   Article {article_id}: {title}")
                print(f"     URL invalide: {image_path}")
                print()
        
        conn.close()
        
        return invalid_urls, articles_without_images
        
    except Exception as e:
        print(f"❌ Erreur lors de la vérification: {e}")
        return 0, 0

def fix_production_images():
    """Corrige les images d'articles en production"""
    print("\n🔧 CORRECTION DES IMAGES EN PRODUCTION:")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Supprimer les références aux URLs externes invalides
        print("🗑️ Suppression des URLs externes invalides...")
        cur.execute("UPDATE articles SET image_path = NULL WHERE image_path LIKE 'http%'")
        invalid_urls_fixed = cur.rowcount
        print(f"   ✅ {invalid_urls_fixed} URLs externes supprimées")
        
        # 2. Ajouter des images par défaut aux articles sans images
        print("🖼️ Ajout d'images par défaut...")
        
        # Vérifier combien d'articles n'ont pas d'images
        cur.execute("SELECT COUNT(*) FROM articles WHERE image_path IS NULL OR image_path = ''")
        articles_without_images = cur.fetchone()[0]
        
        if articles_without_images > 0:
            # Utiliser l'image par défaut uploadée sur HostGator
            default_image_path = "/static/article_images/default_article.jpg"
            
            cur.execute("UPDATE articles SET image_path = ? WHERE image_path IS NULL OR image_path = ''", (default_image_path,))
            default_images_added = cur.rowcount
            print(f"   ✅ {default_images_added} articles ont reçu l'image par défaut")
        else:
            print("   ℹ️ Aucun article sans image à traiter")
        
        # Valider les changements
        conn.commit()
        print("💾 Changements validés en base de données")
        
        conn.close()
        
        return invalid_urls_fixed, articles_without_images
        
    except Exception as e:
        print(f"❌ Erreur lors de la correction: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return 0, 0

def verify_production_fix():
    """Vérifie que la correction a bien fonctionné"""
    print("\n🔍 VÉRIFICATION DE LA CORRECTION:")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Vérifier qu'il n'y a plus d'URLs invalides
        cur.execute("SELECT COUNT(*) FROM articles WHERE image_path LIKE 'http%'")
        remaining_invalid = cur.fetchone()[0]
        
        # Vérifier les articles avec images
        cur.execute("SELECT COUNT(*) FROM articles WHERE image_path IS NOT NULL AND image_path != ''")
        articles_with_images = cur.fetchone()[0]
        
        # Vérifier les articles sans images
        cur.execute("SELECT COUNT(*) FROM articles WHERE image_path IS NULL OR image_path = ''")
        articles_without_images = cur.fetchone()[0]
        
        print(f"📊 Résultats après correction:")
        print(f"   URLs invalides restantes: {remaining_invalid}")
        print(f"   Articles avec images: {articles_with_images}")
        print(f"   Articles sans images: {articles_without_images}")
        
        if remaining_invalid == 0:
            print("   ✅ Toutes les URLs invalides ont été supprimées")
        else:
            print(f"   ⚠️ {remaining_invalid} URLs invalides restent")
        
        if articles_without_images == 0:
            print("   ✅ Tous les articles ont maintenant des images")
        else:
            print(f"   ℹ️ {articles_without_images} articles n'ont pas d'images")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur lors de la vérification: {e}")
        if 'conn' in locals():
            conn.close()

def main():
    """Fonction principale"""
    print("🔄 CORRECTION DES IMAGES D'ARTICLES EN PRODUCTION")
    print("=" * 60)
    
    # Vérifier l'état actuel
    invalid_urls, articles_without_images = check_production_articles()
    
    if invalid_urls == 0 and articles_without_images == 0:
        print("\n✅ Aucune correction nécessaire")
        return
    
    # Demander confirmation
    print(f"\n🔧 Actions à effectuer:")
    print(f"   - Supprimer {invalid_urls} URLs externes invalides")
    print(f"   - Ajouter des images par défaut à {articles_without_images} articles")
    
    confirm = input("\n❓ Continuer avec la correction? (o/n): ").strip().lower()
    if not confirm.startswith('o'):
        print("❌ Correction annulée")
        return
    
    # Effectuer la correction
    fixed_urls, fixed_articles = fix_production_images()
    
    if fixed_urls > 0 or fixed_articles > 0:
        print(f"\n🎉 Correction terminée!")
        print(f"   - {fixed_urls} URLs invalides supprimées")
        print(f"   - {fixed_articles} articles avec images par défaut")
        
        # Vérifier le résultat
        verify_production_fix()
    else:
        print("\n⚠️ Aucune correction effectuée")
    
    print("\n✅ Opération terminée!")

if __name__ == "__main__":
    main()
