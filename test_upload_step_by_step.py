#!/usr/bin/env python3
"""
Script pour tester l'upload étape par étape avec permissions AVANT upload.
"""

import ftplib
import io
import time
import requests

def test_upload_step_by_step():
    """Teste l'upload étape par étape"""
    print("🔧 TEST UPLOAD ÉTAPE PAR ÉTAPE:")
    
    # Configuration FTP
    ftp_host = "ftp.novaprint.tn"
    ftp_user = "cmtch@cmtch.online"
    ftp_password = "Anouar881984?"
    remote_dir = "/public_html/static/article_images"
    
    try:
        # ÉTAPE 1: Connexion FTP
        print("\n📡 ÉTAPE 1: Connexion FTP")
        ftp = ftplib.FTP(ftp_host)
        ftp.login(ftp_user, ftp_password)
        print("   ✅ Connexion FTP établie")
        
        # ÉTAPE 2: Navigation vers le dossier
        print("\n📁 ÉTAPE 2: Navigation vers le dossier")
        ftp.cwd(remote_dir)
        print(f"   ✅ Dossier actuel: {ftp.pwd()}")
        
        # ÉTAPE 3: Génération du nom simple
        print("\n🏷️ ÉTAPE 3: Génération du nom simple")
        timestamp = int(time.time())
        simple_name = f"test_{timestamp}.jpg"
        print(f"   ✅ Nom généré: {simple_name}")
        
        # ÉTAPE 4: Création du contenu de test
        print("\n📄 ÉTAPE 4: Création du contenu de test")
        test_content = b"Test content for step by step upload - " + str(timestamp).encode()
        print(f"   ✅ Contenu créé: {len(test_content)} bytes")
        
        # ÉTAPE 5: Upload du fichier
        print("\n⬆️ ÉTAPE 5: Upload du fichier")
        ftp.storbinary(f'STOR {simple_name}', io.BytesIO(test_content))
        print(f"   ✅ Fichier uploadé: {simple_name}")
        
        # ÉTAPE 6: Application des permissions AVANT de fermer la connexion
        print("\n🔐 ÉTAPE 6: Application des permissions")
        try:
            ftp.sendcmd(f"SITE CHMOD 644 {simple_name}")
            print(f"   ✅ Permissions 644 appliquées à {simple_name}")
        except Exception as e:
            print(f"   ❌ Erreur permissions: {e}")
        
        # ÉTAPE 7: Vérification que le fichier existe sur le serveur
        print("\n🔍 ÉTAPE 7: Vérification existence sur serveur")
        try:
            file_size = ftp.size(simple_name)
            print(f"   ✅ Fichier existe sur serveur: {file_size} bytes")
        except Exception as e:
            print(f"   ❌ Fichier non trouvé sur serveur: {e}")
        
        # ÉTAPE 8: Fermeture de la connexion
        print("\n🔌 ÉTAPE 8: Fermeture de la connexion")
        ftp.quit()
        print("   ✅ Connexion fermée")
        
        # ÉTAPE 9: Attente de synchronisation
        print("\n⏳ ÉTAPE 9: Attente de synchronisation")
        print("   ⏳ Attente de 15 secondes...")
        time.sleep(15)
        print("   ✅ Synchronisation terminée")
        
        # ÉTAPE 10: Test d'accessibilité web
        print("\n🌐 ÉTAPE 10: Test d'accessibilité web")
        test_url = f"https://www.cmtch.online/static/article_images/{simple_name}"
        print(f"   🔗 URL testée: {test_url}")
        
        try:
            response = requests.head(test_url, timeout=10)
            if response.status_code == 200:
                print(f"   ✅ {response.status_code} - Image accessible sur le web!")
                print(f"   🎉 SUCCÈS COMPLET!")
                return True
            else:
                print(f"   ❌ {response.status_code} - Image non accessible")
                print(f"   ❌ Problème de permissions ou restriction serveur")
                return False
        except Exception as e:
            print(f"   ❌ Erreur test web: {e}")
            return False
        
    except Exception as e:
        print(f"❌ Erreur générale: {e}")
        return False

def test_different_naming_strategies():
    """Teste différentes stratégies de nommage"""
    print("\n🧪 TEST DE DIFFÉRENTES STRATÉGIES DE NOMMAGE:")
    
    strategies = [
        ("simple", "test_simple.jpg"),
        ("timestamp", f"test_{int(time.time())}.jpg"),
        ("counter", "test_001.jpg"),
        ("descriptive", "test_upload.jpg")
    ]
    
    for strategy_name, filename in strategies:
        print(f"\n   📋 Stratégie: {strategy_name}")
        print(f"   📝 Nom: {filename}")
        
        # Test d'accessibilité
        test_url = f"https://www.cmtch.online/static/article_images/{filename}"
        try:
            response = requests.head(test_url, timeout=5)
            if response.status_code == 200:
                print(f"   ✅ Accessible (HTTP {response.status_code})")
            else:
                print(f"   ❌ Non accessible (HTTP {response.status_code})")
        except:
            print(f"   ❌ Erreur de test")

def main():
    """Fonction principale"""
    print("🚀 TEST UPLOAD ÉTAPE PAR ÉTAPE")
    print("=" * 60)
    
    print("📋 Ce script teste l'upload avec:")
    print("   1. Nom simple généré")
    print("   2. Permissions appliquées AVANT fermeture connexion")
    print("   3. Vérification étape par étape")
    print("   4. Test d'accessibilité web")
    print()
    
    # Test principal
    success = test_upload_step_by_step()
    
    # Test des stratégies de nommage
    test_different_naming_strategies()
    
    # Résumé
    print(f"\n📊 RÉSUMÉ:")
    if success:
        print(f"   🎉 SUCCÈS! L'upload avec permissions fonctionne")
        print(f"   ✅ Les nouvelles images seront accessibles")
        print(f"   ✅ Le problème des permissions est résolu")
    else:
        print(f"   ❌ ÉCHEC! Le problème persiste")
        print(f"   💡 Vérifier la configuration du serveur HostGator")
    
    print(f"\n✅ Test terminé!")

if __name__ == "__main__":
    main()
