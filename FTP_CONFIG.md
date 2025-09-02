# 🔧 Configuration FTP pour HostGator

## 📋 Variables d'Environnement Requises

Pour utiliser les scripts d'upload vers HostGator, vous devez configurer les variables d'environnement suivantes :

### 🔑 Variables Obligatoires

```bash
# Serveur FTP HostGator
FTP_HOST=votre-serveur.hostgator.com

# Nom d'utilisateur FTP
FTP_USER=votre_username

# Mot de passe FTP
FTP_PASSWORD=votre_password
```

### 🔧 Variables Optionnelles

```bash
# Chemin sur le serveur (par défaut: /public_html/static/article_images/)
FTP_PATH=/public_html/static/article_images/
```

## 🚀 Configuration sur Windows

### 1. **Variables d'Environnement Système**
1. Appuyez sur `Win + R`, tapez `sysdm.cpl` et appuyez sur Entrée
2. Onglet "Avancé" → "Variables d'environnement"
3. Dans "Variables système", cliquez "Nouveau"
4. Ajoutez chaque variable une par une

### 2. **Configuration PowerShell (Session actuelle)**
```powershell
$env:FTP_HOST = "votre-serveur.hostgator.com"
$env:FTP_USER = "votre_username"
$env:FTP_PASSWORD = "votre_password"
$env:FTP_PATH = "/public_html/static/article_images/"
```

### 3. **Fichier .env (Recommandé pour le développement)**
Créez un fichier `.env` à la racine de votre projet :
```env
FTP_HOST=votre-serveur.hostgator.com
FTP_USER=votre_username
FTP_PASSWORD=votre_password
FTP_PATH=/public_html/static/article_images/
```

## 🔍 Où Trouver Vos Informations FTP

### **Dans votre panneau HostGator :**
1. Connectez-vous à votre panneau de contrôle HostGator
2. Section "Fichiers" → "Gestionnaire de fichiers" ou "FTP"
3. Notez :
   - **Serveur FTP** : généralement `votre-domaine.com` ou `votre-serveur.hostgator.com`
   - **Nom d'utilisateur** : votre nom d'utilisateur FTP
   - **Mot de passe** : votre mot de passe FTP

### **Dans votre email de bienvenue HostGator :**
- Les informations FTP sont généralement incluses dans l'email de configuration

## 🧪 Test de la Connexion

### **Test simple avec PowerShell :**
```powershell
# Définir les variables
$env:FTP_HOST = "votre-serveur.hostgator.com"
$env:FTP_USER = "votre_username"
$env:FTP_PASSWORD = "votre_password"

# Tester le script
python upload_default_image_to_hostgator.py
```

## ⚠️ Sécurité

### **Ne jamais commiter vos informations FTP :**
- Ajoutez `.env` à votre `.gitignore`
- N'incluez jamais les mots de passe dans le code source
- Utilisez des variables d'environnement ou des fichiers de configuration sécurisés

### **Permissions FTP recommandées :**
- **Lecture** : ✅ Nécessaire pour télécharger des fichiers
- **Écriture** : ✅ Nécessaire pour uploader des fichiers
- **Suppression** : ⚠️ Optionnel, pour nettoyer les anciens fichiers

## 🔄 Workflow Complet

### **1. Configuration des Variables**
```bash
# Définir les variables d'environnement
export FTP_HOST="votre-serveur.hostgator.com"
export FTP_USER="votre_username"
export FTP_PASSWORD="votre_password"
```

### **2. Upload de l'Image par Défaut**
```bash
python upload_default_image_to_hostgator.py
```

### **3. Correction de la Base de Données**
```bash
python fix_production_mysql_images.py
```

### **4. Vérification**
- Visitez votre site et vérifiez qu'il n'y a plus d'erreurs 404
- Vérifiez que les images s'affichent correctement

## 🆘 Dépannage

### **Erreur de Connexion FTP :**
- Vérifiez que le serveur FTP est correct
- Vérifiez vos identifiants
- Vérifiez que votre IP n'est pas bloquée

### **Erreur de Permission :**
- Vérifiez que le dossier de destination existe
- Vérifiez les permissions sur le dossier
- Contactez le support HostGator si nécessaire

### **Erreur de Chemin :**
- Vérifiez que `FTP_PATH` pointe vers le bon dossier
- Le chemin doit généralement commencer par `/public_html/`

---

*Configuration créée le : 2025-01-02*  
*Pour : Upload des images par défaut vers HostGator*
