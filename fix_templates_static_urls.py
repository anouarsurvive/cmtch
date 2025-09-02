#!/usr/bin/env python3
"""
Script pour corriger les URLs statiques dans les templates.
"""

import os
import re

def fix_templates_static_urls():
    """Corrige les URLs statiques dans tous les templates"""
    print("🔧 CORRECTION DES URLs STATIQUES DANS LES TEMPLATES:")
    
    templates_dir = "templates"
    if not os.path.exists(templates_dir):
        print(f"❌ Dossier templates non trouvé: {templates_dir}")
        return False
    
    # Trouver tous les fichiers HTML dans le dossier templates
    html_files = []
    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            if file.endswith('.html'):
                html_files.append(os.path.join(root, file))
    
    print(f"📁 Fichiers templates trouvés: {len(html_files)}")
    
    fixed_count = 0
    
    for template_file in html_files:
        print(f"\n📄 Traitement de: {template_file}")
        
        try:
            # Lire le fichier
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Remplacer url_for('static', path='...') par /static/...
            # Pattern pour url_for('static', path='css/style.css')
            pattern1 = r"\{\{\s*url_for\('static',\s*path='([^']+)'\)\s*\}\}"
            replacement1 = r"/static/\1"
            content = re.sub(pattern1, replacement1, content)
            
            # Pattern pour url_for("static", path="css/style.css")
            pattern2 = r'\{\{\s*url_for\("static",\s*path="([^"]+)"\)\s*\}\}'
            replacement2 = r"/static/\1"
            content = re.sub(pattern2, replacement2, content)
            
            # Vérifier s'il y a eu des changements
            if content != original_content:
                # Écrire le fichier modifié
                with open(template_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print(f"   ✅ Fichier modifié")
                fixed_count += 1
                
                # Afficher les changements
                changes = []
                for match in re.finditer(pattern1, original_content):
                    changes.append(f"     - {match.group(0)} → /static/{match.group(1)}")
                for match in re.finditer(pattern2, original_content):
                    changes.append(f"     - {match.group(0)} → /static/{match.group(1)}")
                
                if changes:
                    print("   📝 Changements:")
                    for change in changes:
                        print(change)
            else:
                print(f"   ⚠️ Aucun changement nécessaire")
                
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
    
    print(f"\n📊 RÉSUMÉ:")
    print(f"   📁 Fichiers traités: {len(html_files)}")
    print(f"   ✅ Fichiers modifiés: {fixed_count}")
    
    return fixed_count > 0

def main():
    """Fonction principale"""
    print("🚀 CORRECTION DES URLs STATIQUES DANS LES TEMPLATES")
    print("=" * 60)
    
    print("📋 Ce script corrige les références url_for('static', ...)")
    print("   dans les templates pour utiliser des URLs directes /static/...")
    print()
    
    # Correction des templates
    success = fix_templates_static_urls()
    
    if success:
        print(f"\n🎉 CORRECTION TERMINÉE!")
        print(f"   ✅ Templates corrigés avec succès")
        print(f"   ✅ URLs statiques utilisent maintenant /static/...")
        print(f"   ✅ Plus d'erreur NoMatchFound pour 'static'")
        print(f"\n📝 PROCHAINES ÉTAPES:")
        print(f"   1. ✅ Redémarrer l'application")
        print(f"   2. ✅ Tester l'affichage des pages")
        print(f"   3. ✅ Vérifier que les CSS/JS se chargent")
    else:
        print(f"\n⚠️ Aucune correction nécessaire")
        print(f"   ℹ️ Les templates n'utilisent pas url_for('static', ...)")
    
    print(f"\n✅ Opération terminée!")

if __name__ == "__main__":
    main()
