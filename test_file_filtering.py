#!/usr/bin/env python3
"""
Script pour tester le filtrage des fichiers sur HostGator.
"""

import requests
import ftplib
import io

def test_file_filtering():
    """Teste le filtrage des fichiers sur HostGator"""
    print("🔍 TEST DU FILTRAGE DES FICHIERS:")
    
    # Configuration FTP
    ftp_host = "ftp.novaprint.tn"
    ftp_user = "cmtch@cmtch.online"
    ftp_password = "Anouar881984?"
    
    try:
        # Connexion FTP
        ftp = ftplib.FTP(ftp_host)
        ftp.login(ftp_user, ftp_password)
        ftp.cwd('/public_html/static/article_images')
        
        # Test 1: Créer un fichier de test simple
        print("\n📁 TEST 1: Fichier de test simple")
        test_content = b"Test content for HostGator"
        ftp.storbinary('STOR test_simple.txt', io.BytesIO(test_content))
        
        # Test 2: Créer un fichier JPG de test (copie de default_article.jpg)
        print("\n📁 TEST 2: Fichier JPG de test")
        try:
            # Lire default_article.jpg
            file_data = []
            ftp.retrbinary("RETR default_article.jpg", file_data.append)
            default_content = b''.join(file_data)
            
            # Créer une copie avec un nom simple
            ftp.storbinary('STOR test_image.jpg', io.BytesIO(default_content))
            print("   ✅ Fichier test_image.jpg créé")
            
        except Exception as e:
            print(f"   ❌ Erreur création test_image.jpg: {e}")
        
        # Test 3: Créer un fichier avec un nom très simple
        print("\n📁 TEST 3: Fichier avec nom simple")
        ftp.storbinary('STOR simple.jpg', io.BytesIO(default_content))
        print("   ✅ Fichier simple.jpg créé")
        
        ftp.quit()
        
        # Attendre un peu pour que les fichiers soient disponibles
        import time
        print("\n⏳ Attente de 5 secondes pour la synchronisation...")
        time.sleep(5)
        
        # Tester l'accessibilité des nouveaux fichiers
        print("\n🌐 TEST D'ACCESSIBILITÉ DES NOUVEAUX FICHIERS:")
        test_files = [
            "test_simple.txt",
            "test_image.jpg", 
            "simple.jpg"
        ]
        
        for file_name in test_files:
            try:
                url = f"https://www.cmtch.online/static/article_images/{file_name}"
                response = requests.head(url, timeout=10)
                print(f"   {file_name}: {response.status_code}")
                if response.status_code == 200:
                    print(f"     ✅ Accessible")
                else:
                    print(f"     ❌ Non accessible")
            except Exception as e:
                print(f"   {file_name}: Erreur - {e}")
        
        # Test 4: Analyser les noms des fichiers existants
        print("\n📊 ANALYSE DES NOMS DE FICHIERS:")
        existing_files = [
            "39cebba8134541a4997e9b3a4029a4fe.jpg",  # 404
            "61c8f2b8595948d08b6e8dbc1517a963.jpg",  # 404
            "ed9b5c9611f14f559eb906ec0e2e1fbb.jpg",  # 404
            "d902e16affb04fd3a6c10192bdf4a5c5.jpg",  # 404
            "default_article.jpg"  # 200
        ]
        
        for file_name in existing_files:
            # Analyser le nom
            name_length = len(file_name)
            has_numbers = any(c.isdigit() for c in file_name)
            has_letters = any(c.isalpha() for c in file_name)
            has_underscores = '_' in file_name
            has_dashes = '-' in file_name
            
            print(f"   {file_name}:")
            print(f"     Longueur: {name_length}")
            print(f"     Contient chiffres: {has_numbers}")
            print(f"     Contient lettres: {has_letters}")
            print(f"     Contient underscores: {has_underscores}")
            print(f"     Contient tirets: {has_dashes}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")
        return False

def main():
    """Fonction principale"""
    print("🚀 TEST DU FILTRAGE DES FICHIERS")
    print("=" * 60)
    
    print("📋 Ce script va tester pourquoi certains fichiers sont accessibles")
    print("   et d'autres non sur HostGator.")
    print()
    
    success = test_file_filtering()
    
    if success:
        print(f"\n💡 HYPOTHÈSES À TESTER:")
        print(f"   1. Filtrage par longueur du nom de fichier")
        print(f"   2. Filtrage par caractères spéciaux dans le nom")
        print(f"   3. Filtrage par taille de fichier")
        print(f"   4. Filtrage par date de création")
        print(f"   5. Configuration spécifique du serveur web")
    
    print(f"\n✅ Test terminé!")

if __name__ == "__main__":
    main()
