# -*- coding: utf-8 -*-
"""Detection langue / direction texte."""
from __future__ import annotations

import re

def detect_language(text: str) -> str:
    """
    Détecte la langue d'un texte (arabe ou français)
    Retourne 'ar' pour l'arabe, 'fr' pour le français
    """
    if not text or not text.strip():
        return 'fr'  # Par défaut français
    
    # Compter les caractères arabes
    arabic_chars = re.findall(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]', text)
    arabic_count = len(arabic_chars)
    
    # Compter les caractères français/latins
    latin_chars = re.findall(r'[a-zA-Zàâäéèêëïîôöùûüÿçñ]', text)
    latin_count = len(latin_chars)
    
    # Si plus de caractères arabes que latins, c'est de l'arabe
    if arabic_count > latin_count:
        return 'ar'
    else:
        return 'fr'

def get_text_direction(language: str) -> str:
    """
    Retourne la direction du texte selon la langue
    """
    return 'rtl' if language == 'ar' else 'ltr'

def get_text_align(language: str) -> str:
    """
    Retourne l'alignement du texte selon la langue
    """
    return 'right' if language == 'ar' else 'left'
