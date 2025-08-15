# 🚀 Guide de Déploiement GitHub

## 📋 Prérequis

1. **Compte GitHub** avec votre repository
2. **Compte sur une plateforme de déploiement** (Railway, Render, Heroku)
3. **Git installé** sur votre machine

## 🔧 Configuration Initiale

### 1. Préparation du Repository

```bash
# Vérifier que vous êtes dans le bon répertoire
cd cmtch

# Vérifier le statut Git
git status

# Ajouter tous les fichiers
git add .

# Premier commit
git commit -m "Initial commit - Site Club Tennis Chihia"

# Pousser vers GitHub
git push origin main
```

### 2. Configuration des Secrets GitHub

Allez dans votre repository GitHub → `Settings` → `Secrets and variables` → `Actions`

#### Pour Railway :
- `RAILWAY_TOKEN` : Token d'API Railway
- `RAILWAY_SERVICE` : Nom du service Railway

#### Pour Render :
- `RENDER_SERVICE_ID` : ID du service Render  
- `RENDER_API_KEY` : Clé API Render

## 🚀 Déploiement sur Railway (Recommandé)

### Étape 1: Créer un compte Railway
1. Allez sur [railway.app](https://railway.app)
2. Créez un compte avec votre GitHub
3. Autorisez l'accès à votre repository

### Étape 2: Créer un projet
1. Cliquez sur "New Project"
2. Sélectionnez "Deploy from GitHub repo"
3. Choisissez votre repository `cmtch`
4. Railway détectera automatiquement le `Procfile`

### Étape 3: Configuration
1. Dans les paramètres du projet, ajoutez les variables d'environnement :
   ```
   SECRET_KEY=votre-clé-secrète-très-sécurisée
   PORT=8000
   ```

2. Récupérez le token Railway :
   - Allez dans `Account Settings` → `Tokens`
   - Créez un nouveau token
   - Copiez-le dans les secrets GitHub : `RAILWAY_TOKEN`

### Étape 4: Déploiement automatique
- Chaque push sur `main` déclenchera un déploiement automatique
- Le workflow GitHub Actions gère les tests et le déploiement

## 🌐 Déploiement sur Render

### Étape 1: Créer un compte Render
1. Allez sur [render.com](https://render.com)
2. Créez un compte avec votre GitHub

### Étape 2: Créer un Web Service
1. Cliquez sur "New" → "Web Service"
2. Connectez votre repository GitHub
3. Sélectionnez le repository `cmtch`

### Étape 3: Configuration
- **Name** : `cmtch-app`
- **Environment** : `Python 3`
- **Build Command** : `pip install -r requirements.txt`
- **Start Command** : `uvicorn app:app --host 0.0.0.0 --port $PORT`

### Étape 4: Variables d'environnement
Ajoutez dans les paramètres :
```
SECRET_KEY=votre-clé-secrète-très-sécurisée
```

## 🎯 Déploiement sur Heroku

### Étape 1: Installation Heroku CLI
```bash
# Windows
winget install --id=Heroku.HerokuCLI

# macOS
brew tap heroku/brew && brew install heroku

# Linux
curl https://cli-assets.heroku.com/install.sh | sh
```

### Étape 2: Configuration
```bash
# Connexion
heroku login

# Créer l'application
heroku create cmtch-app

# Ajouter le remote
heroku git:remote -a cmtch-app

# Configurer les variables
heroku config:set SECRET_KEY=votre-clé-secrète-très-sécurisée
```

### Étape 3: Déploiement
```bash
# Pousser vers Heroku
git push heroku main

# Ouvrir l'application
heroku open
```

## 🔄 Workflow GitHub Actions

Le fichier `.github/workflows/deploy.yml` configure :

### Tests automatiques
- ✅ Vérification de la syntaxe Python
- ✅ Import de l'application
- ✅ Tests de base

### Déploiement automatique
- 🚀 Déploiement sur Railway (principal)
- 🚀 Déploiement sur Render (optionnel)
- 📧 Notifications de déploiement

### Déclencheurs
- Push sur `main` ou `master`
- Pull requests sur `main` ou `master`

## 🔍 Monitoring du Déploiement

### Vérifier le statut
1. Allez dans l'onglet `Actions` de votre repository GitHub
2. Cliquez sur le workflow "Déploiement Automatique"
3. Vérifiez les logs de chaque étape

### Logs de déploiement
```bash
# Pour Railway
railway logs

# Pour Render
# Disponibles dans l'interface web

# Pour Heroku
heroku logs --tail
```

## 🛠️ Dépannage

### Problèmes courants

#### 1. Échec des tests
```bash
# Vérifier localement
python -c "import app; print('OK')"
python -m py_compile app.py
```

#### 2. Erreur de dépendances
```bash
# Vérifier requirements.txt
pip install -r requirements.txt
```

#### 3. Erreur de port
- Vérifiez que la variable `PORT` est définie
- Railway/Render définissent automatiquement `$PORT`

#### 4. Erreur de base de données
- La base de données SQLite sera créée automatiquement
- Vérifiez les permissions d'écriture

### Commandes utiles

```bash
# Vérifier le statut Git
git status

# Voir les logs de déploiement
git log --oneline

# Tester localement
python app.py

# Vérifier les secrets GitHub
# (via l'interface web GitHub)
```

## 🔒 Sécurité en Production

### Variables d'environnement critiques
```bash
# À changer absolument en production
SECRET_KEY=votre-clé-secrète-très-sécurisée

# Identifiants admin par défaut
# admin / admin
# À changer dans la base de données
```

### Recommandations
1. ✅ Changez la clé secrète
2. ✅ Changez les identifiants admin
3. ✅ Activez HTTPS
4. ✅ Configurez un domaine personnalisé
5. ✅ Surveillez les logs

## 📊 Performance en Production

### Optimisations incluses
- ⚡ CSS critique inline
- 🖼️ Lazy loading des images
- 🔄 Service Worker pour le cache
- 📊 Monitoring des Web Vitals

### Monitoring
- Utilisez les outils de monitoring de votre plateforme
- Surveillez les métriques de performance
- Configurez des alertes

## 🎉 Félicitations !

Votre site est maintenant déployé et accessible en ligne ! 

### Prochaines étapes
1. 🔗 Configurer un domaine personnalisé
2. 📧 Configurer les notifications
3. 🔒 Renforcer la sécurité
4. 📊 Ajouter du monitoring avancé

---

**Besoin d'aide ?** Consultez la documentation de votre plateforme ou créez une issue GitHub.
