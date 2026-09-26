# -*- coding: utf-8 -*-
"""Hash / verify mots de passe (délègue à security_utils)."""
from __future__ import annotations

from security_utils import (
    hash_password as secure_hash_password,
    verify_password as secure_verify_password,
    needs_rehash as secure_needs_rehash,
)


def verify_password(password: str, password_hash: str) -> bool:
    """VÃ©rifie qu'un mot de passe correspond Ã  une empreinte (bcrypt ou SHA-256 legacy)."""
    return secure_verify_password(password, password_hash)



def hash_password(password: str) -> str:
    """Retourne l'empreinte bcrypt d'un mot de passe en clair."""
    return secure_hash_password(password)


# SYSTÃˆME DE SAUVEGARDE AUTOMATIQUE POUR RENDER
# Ce systÃ¨me sauvegarde et restaure automatiquement les donnÃ©es
# pour Ã©viter la perte lors des redÃ©marrages de Render

