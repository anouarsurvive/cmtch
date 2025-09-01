# 🖼️ Configuration du Stockage des Photos sur HostGator

## 🎯 **Objectif**
Configurer le stockage des photos sur HostGator pour éviter la perte des images lors des redéploiements Render.

## 📋 **Étape 1 : Obtenir les Paramètres FTP HostGator**

### 1.1 Accéder au cPanel HostGator
1. **Connectez-vous** à votre compte HostGator
2. **Allez dans** cPanel
3. **Trouvez** "Comptes FTP" ou "FTP Accounts"

### 1.2 Créer un Compte FTP (si nécessaire)
- **Nom d'utilisateur** : `cmtch_photos` (ou similaire)
- **Mot de passe** : Choisissez un mot de passe fort
- **Répertoire** : `/public_html/photos` (ou `/public_html/cmtch/photos`)
- **Privilèges** : Lecture/Écriture

### 1.3 Informations de Connexion
Vous obtiendrez :
- **Serveur FTP** : `gator3060.hostgator.com` (ou votre serveur)
- **Port** : `21` (FTP standard) ou `22` (SFTP)
- **Nom d'utilisateur** : `cmtch_photos@votre-domaine.com`
- **Mot de passe** : Votre mot de passe FTP
- **Répertoire** : `/public_html/photos`

## 📋 **Étape 2 : Créer le Dossier Photos**

### 2.1 Via cPanel File Manager
1. **Allez dans** "Gestionnaire de fichiers"
2. **Naviguez vers** `public_html`
3. **Créez un dossier** `photos`
4. **Définissez les permissions** : `755` (lecture/écriture pour le propriétaire)

### 2.2 Via FTP
```bash
# Connexion FTP
ftp gator3060.hostgator.com
# Login avec vos identifiants
# Créer le dossier
mkdir public_html/photos
```

## 📋 **Étape 3 : Configurer l'Application**

### 3.1 Variables d'Environnement Render
Ajoutez ces variables dans Render :
- **FTP_HOST** : `gator3060.hostgator.com`
- **FTP_USER** : `cmtch_photos@votre-domaine.com`
- **FTP_PASSWORD** : `votre_mot_de_passe_ftp`
- **FTP_PHOTOS_DIR** : `/public_html/photos`
- **PHOTOS_BASE_URL** : `https://www.cmtch.online/photos`

### 3.2 Modifier le Code
Le code sera modifié pour utiliser ces variables d'environnement.

## 📋 **Étape 4 : Tester la Configuration**

### 4.1 Test de Connexion
```bash
# Tester la connexion FTP
curl https://www.cmtch.online/test-ftp-connection
```

### 4.2 Test d'Upload
```bash
# Tester l'upload d'une photo
curl -X POST https://www.cmtch.online/test-photo-upload
```

## 🔧 **Alternative : Stockage Local Temporaire**

Si vous préférez une solution temporaire, vous pouvez :

### Option A : Sauvegarde des Photos
- **Créer un système de sauvegarde** des photos
- **Sauvegarder sur un service cloud** (Google Drive, Dropbox)
- **Restaurer après chaque déploiement**

### Option B : Stockage Externe
- **Utiliser un CDN** (Cloudinary, AWS S3)
- **Service de stockage gratuit** (Imgur API)
- **Stockage sur un autre serveur**

## 🚨 **Important**

### ⚠️ **Sécurité**
- **Ne jamais** commiter les mots de passe FTP dans le code
- **Utiliser** les variables d'environnement
- **Limiter** les permissions FTP au minimum nécessaire

### ⚠️ **Performance**
- **Optimiser** les images avant upload (compression)
- **Utiliser** des formats modernes (WebP)
- **Implémenter** un système de cache

## 📞 **Support**

Si vous avez des difficultés :
1. **Vérifiez** vos paramètres FTP dans cPanel
2. **Testez** la connexion avec un client FTP (FileZilla)
3. **Contactez** le support HostGator si nécessaire

## 🎯 **Résultat Attendu**

Après configuration :
- ✅ **Les photos sont stockées** sur HostGator
- ✅ **Les photos persistent** après les redéploiements
- ✅ **Accès rapide** via URL directe
- ✅ **Pas de perte** de données d'images
