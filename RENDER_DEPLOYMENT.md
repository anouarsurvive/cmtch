# 🚀 Déploiement Render - Club Tennis Chihia

Guide complet pour déployer votre site sur Render avec GitHub Actions.

## 📋 Prérequis

1. ✅ Compte GitHub avec votre repository
2. ✅ Compte Render (gratuit)
3. ✅ Git installé sur votre machine

## 🔧 Configuration Render

### Étape 1: Créer un compte Render

1. Allez sur [render.com](https://render.com)
2. Cliquez sur "Get Started for Free"
3. Créez un compte avec votre GitHub
4. Autorisez l'accès à vos repositories

### Étape 2: Créer un Web Service

1. Dans le dashboard Render, cliquez sur **"New"** → **"Web Service"**
2. Connectez votre repository GitHub
3. Sélectionnez le repository `cmtch`
4. Render détectera automatiquement le fichier `render.yaml`

### Étape 3: Configuration automatique

Le fichier `render.yaml` configure automatiquement :
- ✅ **Nom du service** : `cmtch`
- ✅ **Environnement** : Python
- ✅ **Plan** : Gratuit
- ✅ **Build Command** : `pip install -r requirements.txt`
- ✅ **Start Command** : `uvicorn app:app --host 0.0.0.0 --port $PORT`
- ✅ **Variables d'environnement** : `SECRET_KEY` (générée automatiquement)
- ✅ **Health Check** : `/`
- ✅ **Auto-déploiement** : Activé

### Étape 4: Premier déploiement

1. Cliquez sur **"Create Web Service"**
2. Render va automatiquement :
   - Cloner votre repository
   - Installer les dépendances
   - Démarrer l'application
   - Générer une URL publique

## 🔑 Configuration GitHub Actions

### Secrets GitHub requis

Dans votre repository GitHub → `Settings` → `Secrets and variables` → `Actions` :

#### Récupérer les informations Render :

1. **Service ID** :
   - Allez dans votre service Render
   - L'URL sera : `https://dashboard.render.com/web/srv-XXXXXXXXXXXX`
   - Le Service ID est : `srv-XXXXXXXXXXXX`

2. **API Key** :
   - Allez dans `Account Settings` → `API Keys`
   - Cliquez sur **"New API Key"**
   - Copiez la clé générée

#### Ajouter les secrets :

- `RENDER_SERVICE_ID` : `srv-XXXXXXXXXXXX` (votre Service ID)
- `RENDER_API_KEY` : `rnd_XXXXXXXXXXXXXXXXXXXX` (votre API Key)

## 🔄 Workflow Automatique

Le workflow `.github/workflows/deploy.yml` :

### Tests automatiques
- ✅ Vérification de la syntaxe Python
- ✅ Import de l'application
- ✅ Tests de base

### Déploiement automatique
- 🚀 Déploiement sur Render à chaque push sur `CMTCH`
- 📧 Notifications de déploiement
- 🔄 Rollback automatique en cas d'échec

## 🛠️ Commandes utiles

### Vérifier le statut local
```bash
# Tester l'application localement
python app.py

# Vérifier les dépendances
pip install -r requirements.txt

# Vérifier la syntaxe
python -m py_compile app.py
```

### Déploiement manuel
```bash
# Ajouter les changements
git add .

# Commit
git commit -m "Mise à jour du site"

# Pousser vers GitHub (déclenche le déploiement)
git push origin CMTCH
```

## 🔍 Monitoring

### Vérifier le déploiement

1. **GitHub Actions** :
   - Allez dans l'onglet `Actions` de votre repository
   - Vérifiez le workflow "Déploiement Automatique"

2. **Render Dashboard** :
   - Allez sur [dashboard.render.com](https://dashboard.render.com)
   - Vérifiez le statut de votre service
   - Consultez les logs en temps réel

### Logs Render
- **Build Logs** : Logs de construction
- **Runtime Logs** : Logs d'exécution
- **Health Check** : Vérification de santé

## 🚨 Dépannage

### Problèmes courants

#### 1. Échec de build
```bash
# Vérifier requirements.txt
pip install -r requirements.txt

# Vérifier la version Python
python --version  # Doit être 3.11+
```

#### 2. Erreur de port
- Render définit automatiquement `$PORT`
- Vérifiez que l'application écoute sur `0.0.0.0:$PORT`

#### 3. Erreur de base de données
- SQLite sera créée automatiquement
- Vérifiez les permissions d'écriture

#### 4. Timeout de build
- Le plan gratuit a des limites
- Optimisez les dépendances si nécessaire

### Solutions

#### Redéployer manuellement
1. Dans Render Dashboard → votre service
2. Cliquez sur **"Manual Deploy"**
3. Sélectionnez **"Deploy latest commit"**

#### Vérifier les logs
1. Dans Render Dashboard → votre service
2. Onglet **"Logs"**
3. Vérifiez les erreurs spécifiques

## 🔒 Sécurité

### Variables d'environnement
- ✅ `SECRET_KEY` : Générée automatiquement par Render
- ✅ `PORT` : Définie automatiquement par Render

### Recommandations
1. ✅ Changez les identifiants admin (admin/admin)
2. ✅ Surveillez les logs d'accès
3. ✅ Configurez un domaine personnalisé
4. ✅ Activez HTTPS (automatique sur Render)

## 📊 Performance

### Optimisations incluses
- ⚡ CSS critique inline
- 🖼️ Lazy loading des images
- 🔄 Service Worker pour le cache
- 📊 Monitoring des Web Vitals

### Monitoring Render
- **Uptime** : Disponibilité du service
- **Response Time** : Temps de réponse
- **Error Rate** : Taux d'erreurs
- **Bandwidth** : Utilisation de la bande passante

## 🌐 Domaine personnalisé

### Configuration
1. Dans Render Dashboard → votre service
2. Onglet **"Settings"** → **"Custom Domains"**
3. Ajoutez votre domaine
4. Configurez les DNS selon les instructions

### HTTPS automatique
- Render fournit automatiquement un certificat SSL
- Redirection automatique HTTP → HTTPS

## 💰 Coûts

### Plan gratuit Render
- ✅ **1 Web Service** gratuit
- ✅ **750 heures** par mois
- ✅ **512 MB RAM**
- ✅ **0.1 CPU**
- ✅ **Auto-sleep** après 15 minutes d'inactivité

### Limites
- ⚠️ **Auto-sleep** : Le service se met en veille
- ⚠️ **Cold start** : Premier accès peut être lent
- ⚠️ **Bandwidth** : Limite mensuelle

## 🎉 Félicitations !

Votre site est maintenant déployé sur Render !

### URL de votre site
```
https://cmtch.onrender.com
```

### Prochaines étapes
1. 🔗 Configurer un domaine personnalisé
2. 📧 Tester toutes les fonctionnalités
3. 🔒 Changer les identifiants admin
4. 📊 Surveiller les performances

---

**Besoin d'aide ?** 
- 📧 Support Render : [support.render.com](https://support.render.com)
- 🐛 Issues GitHub : Créez une issue dans votre repository
- 📚 Documentation : Consultez `README.md` et `DEPLOYMENT.md`
