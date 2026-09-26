# -*- coding: utf-8 -*-
"""Detection langue / direction texte."""
from __future__ import annotations

import re

def detect_language(text: str) -> str:
    """
    DÃ©tecte la langue d'un texte (arabe ou franÃ§ais)
    Retourne 'ar' pour l'arabe, 'fr' pour le franÃ§ais
    """
    if not text or not text.strip():
        return 'fr'  # Par dÃ©faut franÃ§ais
    
    # Compter les caractÃ¨res arabes
    arabic_chars = re.findall(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]', text)
    arabic_count = len(arabic_chars)
    
    # Compter les caractÃ¨res franÃ§ais/latins
    latin_chars = re.findall(r'[a-zA-ZÃ Ã¢Ã¤Ã©Ã¨ÃªÃ«Ã¯Ã®Ã´Ã¶Ã¹Ã»Ã¼Ã¿Ã§Ã±]', text)
    latin_count = len(latin_chars)
    
    # Si plus de caractÃ¨res arabes que latins, c'est de l'arabe
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
