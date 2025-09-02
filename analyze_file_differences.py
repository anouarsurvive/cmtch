#!/usr/bin/env python3
"""
Script pour analyser les différences entre fichiers accessibles et non accessibles.
"""

import ftplib
import requests
import time

def analyze_file_differences():
    """Analyse les différences entre fichiers accessibles et non accessibles"""
    print("🔍 ANALYSE DES DIFFÉRENCES ENTRE FICHIERS:")
    
    # Configuration FTP
    ftp_host = "ftp.novaprint.tn"
    ftp_user = "cmtch@cmtch.online"
    ftp_password = "Anouar881984?"
    
    try:
        # Connexion FTP
        ftp = ftplib.FTP(ftp_host)
        ftp.login(ftp_user, ftp_password)
        ftp.cwd('/public_html/static/article_images')
        
        # Lister tous les fichiers avec détails
        print("\n📋 CONTENU DU DOSSIER AVEC DÉTAILS:")
        ftp.retrlines('LIST', print)
        
        # Analyser les fichiers accessibles vs non accessibles
        print(f"\n🔍 ANALYSE DÉTAILLÉE:")
        
        # Fichiers accessibles (d'après les tests précédents)
        accessible_files = [
            "default_article.jpg",
            "default_article.html", 
            "default_article.svg"
        ]
        
        # Fichiers non accessibles
        inaccessible_files = [
            "article_1.jpg",
            "article_2.jpg",
            "article_3.jpg",
            "test_simple.txt",
            "test_image.jpg",
            "simple.jpg"
        ]
        
        print(f"\n📊 FICHIERS ACCESSIBLES:")
        for file_name in accessible_files:
            print(f"   ✅ {file_name}")
            # Analyser les détails du fichier
            try:
                # Obtenir les détails du fichier
                ftp.retrlines(f'LIST {file_name}', print)
            except:
                print(f"     ⚠️ Impossible d'obtenir les détails")
        
        print(f"\n📊 FICHIERS NON ACCESSIBLES:")
        for file_name in inaccessible_files:
            print(f"   ❌ {file_name}")
            # Analyser les détails du fichier
            try:
                # Obtenir les détails du fichier
                ftp.retrlines(f'LIST {file_name}', print)
            except:
                print(f"     ⚠️ Impossible d'obtenir les détails")
        
        # Test spécial : Créer une copie exacte de default_article.jpg
        print(f"\n🧪 TEST SPÉCIAL: Copie exacte de default_article.jpg")
        
        try:
            # Lire default_article.jpg
            file_data = []
            ftp.retrbinary("RETR default_article.jpg", file_data.append)
            default_content = b''.join(file_data)
            
            # Créer une copie avec un nom différent
            test_filename = "copy_default.jpg"
            ftp.storbinary(f'STOR {test_filename}', file_data)
            print(f"   ✅ Copie créée: {test_filename}")
            
            # Attendre la synchronisation
            print("   ⏳ Attente de 5 secondes...")
            time.sleep(5)
            
            # Tester l'accessibilité
            test_url = f"https://www.cmtch.online/static/article_images/{test_filename}"
            response = requests.head(test_url, timeout=10)
            print(f"   🌐 Test d'accessibilité: {response.status_code}")
            
            if response.status_code == 200:
                print(f"   ✅ La copie est accessible - le problème n'est pas le contenu")
            else:
                print(f"   ❌ La copie n'est pas accessible - le problème est le nom ou la date")
                
        except Exception as e:
            print(f"   ❌ Erreur lors du test: {e}")
        
        # Test de date : Vérifier si c'est un problème de date de création
        print(f"\n📅 ANALYSE DES DATES:")
        print("   Les fichiers accessibles ont-ils une date de création différente?")
        print("   Les fichiers non accessibles sont-ils plus récents?")
        
        ftp.quit()
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse: {e}")
        return False

def main():
    """Fonction principale"""
    print("🚀 ANALYSE DES DIFFÉRENCES ENTRE FICHIERS")
    print("=" * 60)
    
    print("📋 Ce script analyse pourquoi certains fichiers sont accessibles")
    print("   et d'autres non, malgré des permissions identiques.")
    print()
    
    success = analyze_file_differences()
    
    if success:
        print(f"\n💡 HYPOTHÈSES AVANCÉES:")
        print(f"   1. Restriction par date de création (fichiers récents bloqués)")
        print(f"   2. Restriction par taille de fichier")
        print(f"   3. Restriction par contenu (signature de fichier)")
        print(f"   4. Configuration .htaccess cachée")
        print(f"   5. Cache du serveur web")
        print(f"   6. Restriction par utilisateur propriétaire")
    
    print(f"\n✅ Analyse terminée!")

if __name__ == "__main__":
    main()
