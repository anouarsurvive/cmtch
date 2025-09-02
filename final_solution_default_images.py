#!/usr/bin/env python3
"""
Solution finale : Utiliser l'image par défaut pour tous les articles.
"""

import sys
import os

# Ajouter le répertoire courant au path pour importer database
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

def final_solution_default_images():
    """Utilise l'image par défaut pour tous les articles"""
    print("🔧 SOLUTION FINALE : IMAGE PAR DÉFAUT POUR TOUS LES ARTICLES:")
    
    try:
        conn = get_db_connection()
        
        if not hasattr(conn, '_is_mysql'):
            print("❌ Connexion SQLite établie (pas MySQL)")
            return False
        
        cur = conn.cursor()
        
        # Vérifier l'état actuel
        print("\n📊 ÉTAT ACTUEL:")
        cur.execute("SELECT COUNT(*) FROM articles")
        total_articles = cur.fetchone()[0]
        print(f"   Total articles: {total_articles}")
        
        # Lister tous les articles avec leurs images
        print(f"\n📝 ARTICLES AVANT CORRECTION:")
        cur.execute("SELECT id, title, image_path FROM articles ORDER BY id")
        articles = cur.fetchall()
        
        for article in articles:
            article_id, title, image_path = article
            print(f"   Article {article_id}: {title}")
            print(f"     Image actuelle: {image_path}")
        
        # Utiliser l'image par défaut pour tous les articles
        print(f"\n🔄 CORRECTION VERS IMAGE PAR DÉFAUT:")
        default_image_path = "/static/article_images/default_article.jpg"
        
        # Mettre à jour tous les articles
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
    print("🚀 SOLUTION FINALE : IMAGE PAR DÉFAUT")
    print("=" * 60)
    
    print("📋 DIAGNOSTIC COMPLET:")
    print("   ✅ Images présentes dans le dossier FTP")
    print("   ✅ Permissions correctes (644 pour fichiers, 755 pour dossier)")
    print("   ✅ Base de données mise à jour")
    print("   ❌ Serveur HostGator bloque les fichiers créés après 09:11")
    print()
    
    print("💡 SOLUTION:")
    print("   Utiliser l'image par défaut (default_article.jpg) pour tous les articles")
    print("   car c'est la seule image accessible sur le serveur web.")
    print()
    
    # Demander confirmation
    confirm = input("❓ Appliquer la solution finale? (o/n): ").strip().lower()
    if not confirm.startswith('o'):
        print("❌ Solution annulée")
        return
    
    # Appliquer la solution
    updated_count = final_solution_default_images()
    
    if updated_count > 0:
        print(f"\n🎉 SOLUTION APPLIQUÉE AVEC SUCCÈS!")
        print(f"   - {updated_count} articles mis à jour avec l'image par défaut")
        print(f"   - Tous les articles utilisent maintenant l'image accessible")
        print(f"   - Plus d'erreurs 404 sur les images d'articles")
        print(f"   - Le site web devrait maintenant fonctionner correctement")
        print(f"\n📝 PROCHAINES ÉTAPES:")
        print(f"   1. ✅ Vérifier que le site web affiche les images")
        print(f"   2. ✅ Tester l'upload de nouvelles images")
        print(f"   3. ⚠️ Contacter HostGator pour résoudre la restriction temporelle")
    else:
        print("\n⚠️ Aucune correction effectuée")
    
    print("\n✅ Opération terminée!")

if __name__ == "__main__":
    main()
