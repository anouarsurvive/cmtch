#!/usr/bin/env python3
"""
Script final de vérification pour confirmer que le problème des images d'articles est résolu.
"""

import os
import sqlite3
from pathlib import Path

def get_db_connection():
    """Retourne une connexion à la base de données SQLite"""
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(BASE_DIR, "database.db")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def final_verification():
    """Vérification finale de la résolution du problème"""
    print("🔍 VÉRIFICATION FINALE - PROBLÈME DES IMAGES D'ARTICLES")
    print("=" * 70)
    
    # 1. Vérifier la base de données
    print("\n📊 VÉRIFICATION DE LA BASE DE DONNÉES:")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Compter les articles
        cur.execute("SELECT COUNT(*) FROM articles")
        total_articles = cur.fetchone()[0]
        print(f"   Total des articles: {total_articles}")
        
        # Vérifier les articles avec images valides
        cur.execute("SELECT COUNT(*) FROM articles WHERE image_path LIKE '/static/article_images/%'")
        articles_with_valid_images = cur.fetchone()[0]
        print(f"   Articles avec images valides: {articles_with_valid_images}")
        
        # Vérifier qu'il n'y a plus de chemins invalides
        cur.execute("SELECT COUNT(*) FROM articles WHERE image_path LIKE 'http%'")
        invalid_urls = cur.fetchone()[0]
        print(f"   URLs externes invalides: {invalid_urls}")
        
        # Vérifier les articles sans images
        cur.execute("SELECT COUNT(*) FROM articles WHERE image_path IS NULL OR image_path = ''")
        articles_without_images = cur.fetchone()[0]
        print(f"   Articles sans images: {articles_without_images}")
        
        conn.close()
        
        # Évaluation de la base de données
        if invalid_urls == 0 and articles_without_images == 0:
            print("   ✅ BASE DE DONNÉES: CORRIGÉE")
        else:
            print("   ❌ BASE DE DONNÉES: PROBLÈMES RESTANTS")
            
    except Exception as e:
        print(f"   ❌ Erreur lors de la vérification de la base de données: {e}")
    
    # 2. Vérifier les fichiers physiques
    print("\n📁 VÉRIFICATION DES FICHIERS PHYSIQUES:")
    images_dir = Path("static/article_images")
    
    if images_dir.exists():
        image_files = list(images_dir.glob("*.svg")) + list(images_dir.glob("*.html")) + list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.png"))
        print(f"   Images disponibles: {len(image_files)}")
        
        for img in image_files:
            print(f"     - {img.name}")
        
        if len(image_files) > 0:
            print("   ✅ DOSSIER D'IMAGES: OK")
        else:
            print("   ❌ DOSSIER D'IMAGES: VIDE")
    else:
        print("   ❌ DOSSIER D'IMAGES: N'EXISTE PAS")
    
    # 3. Vérifier la cohérence
    print("\n🔗 VÉRIFICATION DE LA COHÉRENCE:")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Vérifier que tous les chemins référencés existent
        cur.execute("SELECT DISTINCT image_path FROM articles WHERE image_path IS NOT NULL AND image_path != ''")
        referenced_paths = cur.fetchall()
        
        missing_files = 0
        for row in referenced_paths:
            image_path = row['image_path']
            if image_path.startswith('/static/article_images/'):
                filename = image_path.split('/')[-1]
                file_path = images_dir / filename
                if not file_path.exists():
                    missing_files += 1
                    print(f"     ❌ Fichier manquant: {filename}")
        
        if missing_files == 0:
            print("   ✅ COHÉRENCE: PARFAITE")
        else:
            print(f"   ⚠️ COHÉRENCE: {missing_files} fichiers manquants")
        
        conn.close()
        
    except Exception as e:
        print(f"   ❌ Erreur lors de la vérification de cohérence: {e}")
    
    # 4. Résumé final
    print("\n📋 RÉSUMÉ FINAL:")
    
    if invalid_urls == 0 and articles_without_images == 0 and missing_files == 0:
        print("🎉 PROBLÈME RÉSOLU AVEC SUCCÈS!")
        print("   ✅ Toutes les références d'images invalides ont été supprimées")
        print("   ✅ Tous les articles ont maintenant des images valides")
        print("   ✅ Tous les fichiers référencés existent physiquement")
        print("   ✅ Votre page des articles devrait fonctionner sans erreurs 404")
    else:
        print("⚠️ PROBLÈME PARTIELLEMENT RÉSOLU")
        if invalid_urls > 0:
            print(f"   ❌ {invalid_urls} URLs externes invalides restent")
        if articles_without_images > 0:
            print(f"   ❌ {articles_without_images} articles n'ont pas d'images")
        if missing_files > 0:
            print(f"   ❌ {missing_files} fichiers référencés sont manquants")
    
    print("\n✅ Vérification terminée!")

def main():
    """Fonction principale"""
    final_verification()

if __name__ == "__main__":
    main()
