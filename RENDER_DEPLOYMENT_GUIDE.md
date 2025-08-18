# Guide de déploiement sur Render

## 🚀 Déploiement automatique

Votre application CMTCH est maintenant prête pour le déploiement sur Render !

### Étape 1 : Créer un compte Render

1. Allez sur [render.com](https://render.com)
2. Cliquez sur "Get Started"
3. Créez un compte avec votre GitHub
4. Autorisez l'accès à votre repository `cmtch`

### Étape 2 : Créer un service web

1. Dans le dashboard Render, cliquez sur **"New"** → **"Web Service"**
2. Connectez votre repository GitHub si ce n'est pas déjà fait
3. Sélectionnez le repository `anouarsurvive/cmtch`
4. Render détectera automatiquement le fichier `render.yaml`

### Étape 3 : Configuration automatique

Le fichier `render.yaml` configure automatiquement :

```yaml
services:
  - type: web
    name: cmtch
    env: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app:app --host 0.0.0.0 --port $PORT --workers 1
    envVars:
      - key: SECRET_KEY
        generateValue: true
      - key: PORT
        value: 8000
      - key: PYTHON_VERSION
        value: "3.11"
      - key: DATABASE_URL
        fromDatabase:
          name: cmtch-db
          property: connectionString
    healthCheckPath: /health
    autoDeploy: true

  - type: pserv
    name: cmtch-db
    plan: free
    env: postgresql
    ipAllowList: []
```

### Étape 4 : Déploiement

1. Cliquez sur **"Create Web Service"**
2. Render va :
   - Créer automatiquement la base de données PostgreSQL
   - Installer les dépendances Python
   - Démarrer l'application
   - Configurer les variables d'environnement

### Étape 5 : Vérification

Une fois le déploiement terminé :

1. **Vérifiez l'état de santé** : `https://votre-app.onrender.com/health`
2. **Créez l'utilisateur admin** : `https://votre-app.onrender.com/fix-admin`
3. **Accédez à l'application** : `https://votre-app.onrender.com`

## 🔧 Configuration manuelle (si nécessaire)

### Variables d'environnement

Si vous devez configurer manuellement :

| Variable | Valeur | Description |
|----------|--------|-------------|
| `SECRET_KEY` | Auto-généré | Clé secrète pour les sessions |
| `PORT` | 8000 | Port de l'application |
| `PYTHON_VERSION` | 3.11 | Version Python |
| `DATABASE_URL` | Auto-configuré | URL de la base PostgreSQL |

### Commandes de build et démarrage

- **Build Command** : `pip install -r requirements.txt`
- **Start Command** : `uvicorn app:app --host 0.0.0.0 --port $PORT --workers 1`

## 📊 Monitoring

### Endpoints de santé

- `/health` - État général de l'application
- `/debug-auth` - Diagnostic de l'authentification
- `/test-admin-reservations` - Test des réservations admin

### Logs

Dans le dashboard Render :
1. Allez dans votre service web
2. Cliquez sur **"Logs"**
3. Surveillez les messages d'initialisation :
   ```
   🔄 Initialisation de la base de données...
   ✅ Base de données initialisée avec succès
   🎉 Application prête !
   ```

## 🔄 Déploiement automatique

Avec `autoDeploy: true`, chaque push sur la branche `main` déclenche automatiquement :

1. **GitHub Actions** : Tests et validation
2. **Render** : Déploiement automatique
3. **Base de données** : Initialisation automatique

## 🛠️ Dépannage

### Problème : Base de données vide

**Solution** : Utilisez l'endpoint `/fix-admin` pour créer l'utilisateur admin.

### Problème : Erreur de connexion

**Solution** : Vérifiez les logs Render et l'endpoint `/health`.

### Problème : Application ne démarre pas

**Solution** : 
1. Vérifiez les logs de build
2. Assurez-vous que `requirements.txt` est à jour
3. Vérifiez la version Python (3.11)

## 📱 Accès à l'application

### URLs importantes

- **Site principal** : `https://votre-app.onrender.com`
- **Administration** : `https://votre-app.onrender.com/admin/membres`
- **Réservations** : `https://votre-app.onrender.com/reservations`
- **Articles** : `https://votre-app.onrender.com/articles`

### Identifiants par défaut

- **Admin** : `admin` / `admin`
- ⚠️ **Changez ces identifiants après le premier déploiement !**

## 🔒 Sécurité

### Recommandations

1. **Changez le mot de passe admin** immédiatement
2. **Activez HTTPS** (automatique sur Render)
3. **Surveillez les logs** régulièrement
4. **Faites des sauvegardes** avec `/backup-database`

### Sauvegarde

Utilisez l'endpoint `/backup-database` (admin uniquement) pour créer des sauvegardes.

## 📞 Support

En cas de problème :

1. **Vérifiez les logs** dans le dashboard Render
2. **Testez les endpoints** de santé
3. **Consultez la documentation** GitHub
4. **Créez une issue** sur GitHub si nécessaire

---

**🎉 Votre application CMTCH est maintenant déployée et opérationnelle !**
