# 🎾 Club Municipal de Tennis Chihia

Site web moderne pour le Club Municipal de Tennis Chihia avec système de réservation, gestion des membres et espace d'administration.

## 🚀 Déploiement avec GitHub + Render

### Configuration rapide Render

1. **Créer un compte Render**
   - Allez sur [render.com](https://render.com)
   - Créez un compte avec votre GitHub
   - Autorisez l'accès à votre repository

2. **Déploiement automatique**
   - Cliquez sur "New" → "Web Service"
   - Sélectionnez votre repository `cmtch`
   - Render détectera automatiquement le fichier `render.yaml`
   - Cliquez sur "Create Web Service"

3. **Configuration GitHub Actions**
   - Dans votre repository GitHub → `Settings` → `Secrets and variables` → `Actions`
   - Ajoutez les secrets Render :
     - `RENDER_SERVICE_ID` : `srv-XXXXXXXXXXXX` (depuis le dashboard Render)
     - `RENDER_API_KEY` : `rnd_XXXXXXXXXXXXXXXXXXXX` (depuis Account Settings → API Keys)

4. **Déploiement automatique**
   - Chaque push sur `main` déclenchera un déploiement automatique
   - Le workflow GitHub Actions gère les tests et le déploiement

### URL de votre site
```
https://cmtch-app.onrender.com
```

## 🔧 Configuration GitHub Actions

Le repository inclut un workflow GitHub Actions automatique :

### Workflow automatique
Le workflow `.github/workflows/deploy.yml` :
1. ✅ Exécute les tests à chaque push
2. 🚀 Déploie automatiquement sur Render
3. 📧 Envoie des notifications de déploiement

## 🛠️ Développement local

### Prérequis
- Python 3.11+
- pip

### Installation
```bash
# Cloner le repository
git clone https://github.com/votre-username/cmtch.git
cd cmtch

# Créer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/macOS
# ou
venv\Scripts\activate     # Windows

# Installer les dépendances
pip install -r requirements.txt

# Lancer l'application
python app.py
```

### Accès
- 🌐 Site web : http://localhost:8000
- 👤 Admin : admin / admin

## 📁 Structure du projet

```
cmtch/
├── app.py                 # Application FastAPI principale
├── requirements.txt       # Dépendances Python
├── render.yaml           # Configuration Render
├── .github/
│   └── workflows/
│       └── deploy.yml    # Workflow GitHub Actions
├── static/               # Fichiers statiques
│   ├── css/
│   ├── js/
│   └── images/
├── templates/            # Templates Jinja2
└── database.db          # Base de données SQLite
```

## 🔒 Sécurité

### Variables d'environnement
- ✅ `SECRET_KEY` : Générée automatiquement par Render
- ✅ `PORT` : Définie automatiquement par Render

### Identifiants par défaut
- **Admin** : admin / admin
- ⚠️ **Important** : Changez ces identifiants en production !

## 📊 Fonctionnalités

- 🏠 **Page d'accueil** moderne avec animations
- 👥 **Gestion des membres** avec validation
- 📅 **Système de réservation** des courts
- 📰 **Articles de presse** avec images
- 📊 **Tableau de bord** avec statistiques
- 🔧 **Interface d'administration** complète
- 📱 **Design responsive** mobile-first
- ⚡ **Optimisations de performance** avancées

## 🚀 Performance

Le site inclut des optimisations avancées :
- ⚡ CSS critique inline
- 🖼️ Lazy loading des images
- 🔄 Service Worker pour le cache
- 📊 Monitoring des Web Vitals
- 🎯 Animations optimisées

## 📚 Documentation

- 📖 **Guide complet** : `RENDER_DEPLOYMENT.md`
- 🚀 **Performance** : `PERFORMANCE.md`
- 🔧 **Déploiement général** : `DEPLOYMENT.md`

## 📞 Support

Pour toute question ou problème :
1. Vérifiez les [Issues GitHub](https://github.com/votre-username/cmtch/issues)
2. Créez une nouvelle issue si nécessaire
3. Consultez la documentation de déploiement Render

## 📄 Licence

Ce projet est développé pour le Club Municipal de Tennis Chihia.

---

**Développé avec ❤️ pour le tennis à Chihia**
