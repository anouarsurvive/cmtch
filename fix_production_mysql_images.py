#!/usr/bin/env python3
"""
Script pour corriger les images d'articles dans la base de données MySQL de production sur HostGator.
Ce script corrige les mêmes problèmes que nous avons résolus en local.
"""

import os
import mysql.connector
from pathlib import Path

def get_mysql_connection():
    """Retourne une connexion à la base de données MySQL de production"""
    try:
        # Récupérer les variables d'environnement de production
        database_url = os.getenv('DATABASE_URL')
        
        if not database_url or 'mysql://' not in database_url:
            print("❌ Variable DATABASE_URL MySQL non trouvée")
            return None
        
        # Parser l'URL MySQL
        # Format: mysql://user:password@host:port/database
        url_parts = database_url.replace('mysql://', '').split('@')
        user_pass = url_parts[0].split(':')
        host_db = url_parts[1].split('/')
        host_port = host_db[0].split(':')
        
        user = user_pass[0]
        password = user_pass[1]
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 3306
        database = host_db[1]
        
        print(f"🔌 Connexion à MySQL: {host}:{port}/{database}")
        
        conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        
        print("✅ Connexion MySQL établie")
        return conn
        
    except Exception as e:
        print(f"❌ Erreur de connexion MySQL: {e}")
        return None

def check_production_articles():
    """Vérifie l'état des articles en production"""
    print("\n🔍 VÉRIFICATION DES ARTICLES EN PRODUCTION:")
    
    conn = get_mysql_connection()
    if not conn:
        return
    
    try:
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
        if conn:
            conn.close()
        return 0, 0

def fix_production_images():
    """Corrige les images d'articles en production"""
    print("\n🔧 CORRECTION DES IMAGES EN PRODUCTION:")
    
    conn = get_mysql_connection()
    if not conn:
        return
    
    try:
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
            # Utiliser une image par défaut (vous devrez l'uploader sur HostGator)
            default_image_path = "/static/article_images/default_article.jpg"
            
            cur.execute("UPDATE articles SET image_path = %s WHERE image_path IS NULL OR image_path = ''", (default_image_path,))
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
        if conn:
            conn.rollback()
            conn.close()
        return 0, 0

def verify_production_fix():
    """Vérifie que la correction a bien fonctionné"""
    print("\n🔍 VÉRIFICATION DE LA CORRECTION:")
    
    conn = get_mysql_connection()
    if not conn:
        return
    
    try:
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
        if conn:
            conn.close()

def main():
    """Fonction principale"""
    print("🔄 CORRECTION DES IMAGES D'ARTICLES EN PRODUCTION (MySQL)")
    print("=" * 70)
    
    # Vérifier l'état actuel
    invalid_urls, articles_without_images = check_production_articles()
    
    if invalid_urls == 0 and articles_without_images == 0:
        print("\n✅ Aucune correction nécessaire en production")
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
