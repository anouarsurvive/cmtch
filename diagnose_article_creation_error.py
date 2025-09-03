#!/usr/bin/env python3
"""
Script pour diagnostiquer l'erreur 500 lors de la création d'articles.
"""

import sys
import os

# Ajouter le répertoire courant au path pour importer database
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def analyze_article_creation_code():
    """Analyse le code de création d'articles pour identifier les problèmes"""
    print("🔍 ANALYSE DU CODE DE CRÉATION D'ARTICLES:")
    
    try:
        # Lire le fichier app.py
        with open('app.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Trouver la fonction admin_new_article
        lines = content.split('\n')
        start_line = None
        end_line = None
        
        for i, line in enumerate(lines):
            if '@app.post("/admin/articles/nouveau"' in line:
                start_line = i
            elif start_line and line.strip().startswith('@app.') and i > start_line:
                end_line = i
                break
        
        if start_line is None:
            print("❌ Fonction admin_new_article non trouvée")
            return False
        
        if end_line is None:
            end_line = len(lines)
        
        print(f"📄 Fonction trouvée aux lignes {start_line + 1}-{end_line}")
        
        # Analyser le code
        function_lines = lines[start_line:end_line]
        
        print(f"\n🔍 PROBLÈMES IDENTIFIÉS:")
        
        problems = []
        
        # Vérifier la duplication de traitement du formulaire
        body_read_count = 0
        for i, line in enumerate(function_lines):
            if 'await request.body()' in line:
                body_read_count += 1
                if body_read_count > 1:
                    problems.append(f"Ligne {start_line + i + 1}: Body lu plusieurs fois")
        
        # Vérifier la structure logique
        in_multipart = False
        in_else = False
        for i, line in enumerate(function_lines):
            if 'if "multipart/form-data"' in line:
                in_multipart = True
            elif in_multipart and line.strip().startswith('raw_body = await request.body()'):
                problems.append(f"Ligne {start_line + i + 1}: Body relu après traitement multipart")
            elif in_multipart and line.strip().startswith('form = urllib.parse.parse_qs'):
                problems.append(f"Ligne {start_line + i + 1}: Traitement form-urlencoded après multipart")
        
        if problems:
            print("   ❌ Problèmes détectés:")
            for problem in problems:
                print(f"      - {problem}")
        else:
            print("   ✅ Aucun problème évident détecté")
        
        # Afficher la structure du code
        print(f"\n📋 STRUCTURE DU CODE:")
        indent_level = 0
        for i, line in enumerate(function_lines):
            stripped = line.strip()
            if stripped.startswith('if ') or stripped.startswith('elif ') or stripped.startswith('else:'):
                if stripped.startswith('else:'):
                    indent_level -= 1
                print(f"   {'  ' * indent_level}{stripped}")
                if not stripped.startswith('else:'):
                    indent_level += 1
            elif stripped.startswith('await request.body()'):
                print(f"   {'  ' * indent_level}📥 {stripped}")
            elif stripped.startswith('form = '):
                print(f"   {'  ' * indent_level}📝 {stripped}")
        
        return len(problems) > 0
        
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Fonction principale"""
    print("🚀 DIAGNOSTIC DE L'ERREUR 500 - CRÉATION D'ARTICLES")
    print("=" * 60)
    
    print("📋 Ce script analyse le code de création d'articles")
    print("   pour identifier les causes de l'erreur 500.")
    print()
    
    # Analyse du code
    has_problems = analyze_article_creation_code()
    
    if has_problems:
        print(f"\n⚠️ PROBLÈMES DÉTECTÉS!")
        print(f"   ❌ Le code a des problèmes de structure")
        print(f"   💡 Il faut corriger la logique de traitement des formulaires")
        print(f"\n📝 SOLUTIONS RECOMMANDÉES:")
        print(f"   1. Supprimer la duplication de traitement du body")
        print(f"   2. Corriger la structure if/else pour multipart vs form-urlencoded")
        print(f"   3. S'assurer que le body n'est lu qu'une seule fois")
    else:
        print(f"\n✅ CODE APPARENT OK")
        print(f"   ℹ️ Le problème pourrait être ailleurs")
        print(f"   💡 Vérifier les logs d'erreur du serveur")
    
    print(f"\n✅ Diagnostic terminé!")

if __name__ == "__main__":
    main()
