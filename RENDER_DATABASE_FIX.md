# 🔧 Correction du problème de base de données sur Render

## 🚨 **Problème identifié**

Sur Render, en mode gratuit, la base de données PostgreSQL est **éphémère**. Cela signifie que :
- ✅ Les données sont perdues à chaque redémarrage de l'application
- ✅ Les données sont perdues à chaque redéploiement
- ✅ Les données sont perdues lors des maintenances Render

## 💡 **Solution implémentée**

### 🔄 **Système de sauvegarde automatique**

Un système de sauvegarde automatique a été mis en place qui :

1. **Au démarrage de l'application** :
   - Vérifie si la base de données est vide
   - Si vide : restaure depuis la dernière sauvegarde
   - Si non vide : crée une nouvelle sauvegarde

2. **Sauvegarde intelligente** :
   - Garde seulement les 5 sauvegardes les plus récentes
   - Supprime automatiquement les anciennes sauvegardes
   - Sauvegarde complète avec structure et données

### 📁 **Fichiers créés**

- `backup_auto.py` : Script de sauvegarde automatique
- `backups/` : Dossier contenant les sauvegardes (ignoré par Git)
- Endpoints de gestion : `/restore-backup`, `/fix-admin`

## 🛠️ **Utilisation**

### **Après un redéploiement**

1. **Attendre** que l'application démarre (le système de sauvegarde s'exécute automatiquement)
2. **Vérifier** l'état : `https://www.cmtch.online/health`
3. **Si problème** : Utiliser `/fix-admin` pour recréer l'admin

### **Endpoints utiles**

- **`/health`** : Vérifier l'état de l'application et de la base
- **`/diagnostic-db`** : Diagnostic détaillé de la base de données
- **`/fix-admin`** : Créer/corriger l'utilisateur admin
- **`/restore-backup`** : Forcer la restauration depuis une sauvegarde
- **`/init-articles`** : Créer des articles de test

### **Identifiants par défaut**

- **Username** : `admin`
- **Password** : `admin`

## 🔍 **Diagnostic**

### **Vérifier l'état de la base**

```bash
# Vérifier l'état général
curl https://www.cmtch.online/health

# Diagnostic détaillé
curl https://www.cmtch.online/diagnostic-db

# Créer l'admin si nécessaire
curl https://www.cmtch.online/fix-admin
```

### **Logs de sauvegarde**

Les logs de sauvegarde apparaissent dans les logs de l'application Render :
- `🔄 Démarrage du système de sauvegarde automatique...`
- `✅ Sauvegarde créée` ou `📭 Base de données vide détectée`
- `✅ Restauration réussie` ou `❌ Échec de la restauration`

## 🚀 **Solution permanente**

### **Option 1 : Mise à niveau Render (Recommandé)**

Pour une solution permanente, passer au plan **Starter** de Render :
- Base de données PostgreSQL persistante
- Pas de perte de données
- Meilleure performance

### **Option 2 : Base de données externe**

Utiliser une base de données externe (Supabase, Railway, etc.) :
- Modifier `DATABASE_URL` dans les variables d'environnement Render
- Base de données persistante et fiable

## 📋 **Checklist après déploiement**

- [ ] Vérifier `/health` - doit retourner `healthy`
- [ ] Vérifier `/diagnostic-db` - toutes les tables doivent exister
- [ ] Tester la connexion admin : `admin/admin`
- [ ] Vérifier que les données sont présentes
- [ ] Si problème : utiliser `/fix-admin` puis `/init-articles`

## 🔧 **Dépannage**

### **Base de données vide**

1. Utiliser `/fix-admin` pour créer l'admin
2. Utiliser `/init-articles` pour créer des articles de test
3. Vérifier `/diagnostic-db` pour confirmer

### **Erreur de connexion**

1. Vérifier que l'application est démarrée
2. Vérifier les logs Render pour les erreurs
3. Utiliser `/health` pour diagnostiquer

### **Sauvegarde échoue**

1. Vérifier que `pg_dump` et `psql` sont disponibles
2. Vérifier les permissions sur le dossier `backups/`
3. Vérifier la connexion à la base de données

## 📞 **Support**

En cas de problème persistant :
1. Vérifier les logs Render
2. Utiliser les endpoints de diagnostic
3. Contacter l'administrateur avec les logs d'erreur
