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

- `DATABASE_URL` : URL de connexion PostgreSQL (pour la production)
- `SECRET_KEY` : Clé secrète pour les sessions (générée automatiquement sur Render)

### Utilisateur administrateur par défaut

- **Nom d'utilisateur** : `admin`
- **Mot de passe** : `admin`

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
- `/fix-admin` - Correction/création de l'utilisateur admin
- `/debug-auth` - Diagnostic de l'authentification
- `/backup-database` - Sauvegarde de la base de données (admin)
- `/list-backups` - Liste des sauvegardes (admin)

## 🔒 Sécurité

- Mots de passe hachés avec SHA-256
- Sessions sécurisées avec cookies signés
- Validation des données côté serveur
- Protection CSRF

## 📝 Licence

Ce projet est développé pour le Club Municipal de Tennis Chihia.

## 👥 Contact

- **Email** : club.tennis.chihia@gmail.com
- **Téléphone** : +216 29 60 03 40
- **Adresse** : Route Teboulbi km 6, 3041 Sfax sud
