#!/usr/bin/env python3
"""
Script pour corriger les images manquantes en utilisant l'image par défaut
"""

import sqlite3
import os

def get_db_connection():
    """Connexion à la base de données SQLite"""
    return sqlite3.connect("cmtch.db")

def fix_missing_images():
    """Corrige les images manquantes en utilisant l'image par défaut"""
    print("🔧 Correction des images manquantes...")
    
    # Connexion à la base de données
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Récupérer tous les articles
    cur.execute("SELECT id, title, image_path FROM articles")
    articles = cur.fetchall()
    
    print(f"📊 {len(articles)} articles trouvés")
    
    fixed_count = 0
    
    for article_id, title, image_path in articles:
        print(f"\n📝 Article {article_id}: {title[:50]}...")
        print(f"   Image actuelle: {image_path}")
        
        # Vérifier si l'image est manquante ou invalide
        needs_fix = False
        
        if not image_path or image_path == '':
            print("   ❌ Aucune image")
            needs_fix = True
        elif image_path.startswith('/article_images/') and not os.path.exists(f"static{image_path}"):
            print("   ❌ Image locale manquante")
            needs_fix = True
        elif not image_path.startswith('http'):
            print("   ❌ Chemin relatif invalide")
            needs_fix = True
        
        if needs_fix:
            # Utiliser l'image par défaut HostGator
            default_url = "https://www.cmtch.online/static/article_images/default_article.jpg"
            
            try:
                cur.execute("UPDATE articles SET image_path = ? WHERE id = ?", (default_url, article_id))
                conn.commit()
                print(f"   ✅ Image par défaut assignée: {default_url}")
                fixed_count += 1
            except Exception as e:
                print(f"   ❌ Erreur mise à jour: {e}")
        else:
            print("   ✅ Image valide")
    
    conn.close()
    
    print(f"\n🎉 Correction terminée!")
    print(f"   ✅ {fixed_count} articles corrigés")
    print(f"   📊 {len(articles)} articles traités au total")

def verify_fix():
    """Vérifie que toutes les images sont maintenant valides"""
    print("\n🔍 Vérification des corrections...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Vérifier les articles sans images
    cur.execute("SELECT COUNT(*) FROM articles WHERE image_path IS NULL OR image_path = ''")
    no_images = cur.fetchone()[0]
    
    # Vérifier les articles avec images par défaut
    cur.execute("SELECT COUNT(*) FROM articles WHERE image_path LIKE '%default_article.jpg%'")
    default_images = cur.fetchone()[0]
    
    # Vérifier les articles avec URLs HostGator
    cur.execute("SELECT COUNT(*) FROM articles WHERE image_path LIKE '%cmtch.online%'")
    hostgator_images = cur.fetchone()[0]
    
    print(f"📊 Résultats:")
    print(f"   - Articles sans images: {no_images}")
    print(f"   - Articles avec image par défaut: {default_images}")
    print(f"   - Articles avec URLs HostGator: {hostgator_images}")
    
    if no_images == 0:
        print("✅ Tous les articles ont maintenant des images!")
    else:
        print("⚠️ Certains articles n'ont toujours pas d'images")
    
    conn.close()

def main():
    """Fonction principale"""
    print("🖼️ Correction des images manquantes")
    print("=" * 50)
    
    # Correction
    fix_missing_images()
    
    # Vérification
    verify_fix()
    
    print("\n💡 Prochaines étapes:")
    print("   1. Tester l'affichage des articles sur le site")
    print("   2. Vérifier qu'il n'y a plus d'erreurs 404")
    print("   3. Créer de nouveaux articles avec des images personnalisées")

if __name__ == "__main__":
    main()
