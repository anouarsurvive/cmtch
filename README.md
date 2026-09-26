# Club Municipal de Tennis Chihia (CMTCH)

Application web pour la gestion du Club Municipal de Tennis Chihia.

## 🎾 Description

Cette application web permet de gérer :
- Les inscriptions des membres
- Les réservations de courts de tennis
- La publication d'articles et actualités
- L'administration des membres et réservations

## 🚀 Technologies utilisées

- **Backend** : FastAPI (Python)
- **Base de données** : PostgreSQL (production) / SQLite (développement)
- **Frontend** : HTML, CSS, JavaScript avec Jinja2 templates
- **Déploiement** : Render

## 📋 Fonctionnalités

### Espace public
- Présentation du club
- Formulaire d'inscription
- Liste des articles et actualités
- Connexion des membres

### Espace membres
- Réservation de courts de tennis
- Consultation des réservations personnelles
- Statistiques de fréquentation

### Espace administration
- Validation des inscriptions
- Gestion des membres
- Gestion des réservations
- Publication d'articles
- Sauvegarde de la base de données

## 🛠️ Installation locale

### Prérequis
- Python 3.11+
- pip

### Installation

1. Cloner le repository :
```bash
git clone https://github.com/anouarsurvive/cmtch.git
cd cmtch
```

2. Installer les dépendances :
```bash
pip install -r requirements.txt
```

3. Lancer l'application :
```bash
python app.py
```

4. Accéder à l'application : http://localhost:8000

## 🔧 Configuration

### Variables d'environnement

- `DATABASE_URL` : URL de connexion PostgreSQL/MySQL (production)
- `SECRET_KEY` : Clé secrète pour les sessions (**obligatoire** en production ; générée sur Render)
- `COOKIE_SECURE` : `true` en HTTPS (défaut auto si Render/DATABASE_URL)
- `IMGBB_API_KEY` : Clé API ImgBB pour les images d'articles
- `ENABLE_OPS_ENDPOINTS` : `true` uniquement pour maintenance temporaire (défaut `false`)
- `SETUP_TOKEN` : Jeton requis pour les endpoints ops si activés (`?token=...` ou header `X-Setup-Token`)
- `SMTP_*` / `EMAIL_FROM` : configuration email

Voir `.env.example` pour un modèle local.

### Utilisateur administrateur par défaut

- **Nom d'utilisateur** : `admin`
- **Mot de passe** : `admin` (uniquement à la première initialisation DB)

⚠️ **Important** : Changez ces identifiants après le premier déploiement !

## 🌐 Déploiement

### Sur Render

1. Connectez votre repository GitHub à Render
2. Créez un nouveau service web
3. Configurez les variables d'environnement
4. Déployez !

L'application se configure automatiquement avec :
- Initialisation automatique de la base de données
- Création des tables si nécessaire
- Migration des données SQLite vers PostgreSQL

## 📊 Endpoints utiles

- `/health` - État de santé de l'application
- `/backup-database` - Sauvegarde (admin authentifié)
- `/list-backups` - Liste des sauvegardes (admin authentifié)

Les anciens endpoints de debug (`/fix-admin`, `/debug-auth`, `/restore-backup`, etc.)
sont **désactivés par défaut**. Pour une maintenance ponctuelle uniquement :
`ENABLE_OPS_ENDPOINTS=true` + `SETUP_TOKEN` défini, puis appeler avec `?token=...`.

## 🔒 Sécurité

- Mots de passe hachés avec **bcrypt** (migration auto depuis SHA-256 au login)
- Sessions via cookies HttpOnly + `Secure` en production
- Protection **CSRF** (cookie + champ formulaire / header `X-CSRF-Token`)
- Secrets via variables d'environnement (plus de clés en dur)
- Endpoints ops / diagnostic désactivés hors maintenance

## 📝 Licence

Ce projet est développé pour le Club Municipal de Tennis Chihia.

## 👥 Contact

- **Email** : club.tennis.chihia@gmail.com
- **Téléphone** : +216 29 60 03 40
- **Adresse** : Route Teboulbi km 6, 3041 Sfax sud
