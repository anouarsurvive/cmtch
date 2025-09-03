#!/usr/bin/env python3
"""
Script pour corriger les images en production sur HostGator
"""

import os
import sys

# Ajouter le répertoire courant au path pour importer les modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def fix_production_database():
    """Corrige la base de données de production"""
    print("🔧 Correction de la base de données de production...")
    
    try:
        # Import des modules de base de données
        from database import get_mysql_connection
        
        # Connexion à la base de données MySQL de production
        conn = get_mysql_connection()
        if not conn:
            print("❌ Impossible de se connecter à la base de données MySQL")
            return False
        
        cur = conn.cursor()
        
        # Récupérer tous les articles
        cur.execute("SELECT id, title, image_path FROM articles")
        articles = cur.fetchall()
        
        print(f"📊 {len(articles)} articles trouvés en production")
        
        fixed_count = 0
        
        for article_id, title, image_path in articles:
            print(f"\n📝 Article {article_id}: {title[:50]}...")
            print(f"   Image actuelle: {image_path}")
            
            # Vérifier si l'image est manquante ou invalide
            needs_fix = False
            
            if not image_path or image_path == '':
                print("   ❌ Aucune image")
                needs_fix = True
            elif not image_path.startswith('https://www.cmtch.online'):
                print("   ❌ URL non-HostGator")
                needs_fix = True
            elif 'article_images' in image_path and not image_path.endswith('default_article.jpg'):
                print("   ❌ Image spécifique potentiellement manquante")
                needs_fix = True
            
            if needs_fix:
                # Utiliser l'image par défaut HostGator
                default_url = "https://www.cmtch.online/static/article_images/default_article.jpg"
                
                try:
                    cur.execute("UPDATE articles SET image_path = %s WHERE id = %s", (default_url, article_id))
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
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la correction: {e}")
        return False

def verify_production_fix():
    """Vérifie que toutes les images sont maintenant valides en production"""
    print("\n🔍 Vérification des corrections en production...")
    
    try:
        from database import get_mysql_connection
        
        conn = get_mysql_connection()
        if not conn:
            print("❌ Impossible de se connecter à la base de données MySQL")
            return False
        
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
        
        print(f"📊 Résultats en production:")
        print(f"   - Articles sans images: {no_images}")
        print(f"   - Articles avec image par défaut: {default_images}")
        print(f"   - Articles avec URLs HostGator: {hostgator_images}")
        
        if no_images == 0:
            print("✅ Tous les articles ont maintenant des images en production!")
        else:
            print("⚠️ Certains articles n'ont toujours pas d'images")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la vérification: {e}")
        return False

def main():
    """Fonction principale"""
    print("🖼️ Correction des images en production")
    print("=" * 50)
    
    # Correction
    if fix_production_database():
        # Vérification
        verify_production_fix()
        
        print("\n💡 Prochaines étapes:")
        print("   1. Tester l'affichage des articles sur le site")
        print("   2. Vérifier qu'il n'y a plus d'erreurs 404")
        print("   3. Les images par défaut devraient maintenant s'afficher")
    else:
        print("\n❌ Échec de la correction")

if __name__ == "__main__":
    main()
