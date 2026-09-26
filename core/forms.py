# -*- coding: utf-8 -*-
"""Parsing multipart/form-data."""
from __future__ import annotations

import re
from typing import Any, Dict

def parse_multipart_form(body: bytes, content_type: str) -> Dict[str, Any]:
    """Parse un corps multipart/form-data et retourne un dict des champs.

    Cette fonction analyse les donnÃ©es envoyÃ©es dans le corps d'une requÃªte
    multipart/form-data. Les champs simples (texte) sont retournÃ©s comme des
    chaÃ®nes de caractÃ¨res. Les champs de fichier sont retournÃ©s sous la forme
    d'un dictionnaire avec les clÃ©s 'filename' et 'content' (contenu binaire).

    Args:
        body: corps brut de la requÃªte en bytes.
        content_type: valeur de l'en-tÃªte Content-Type (avec le boundary).

    Returns:
        Un dictionnaire oÃ¹ les clÃ©s sont les noms de champs.
    """
    result: Dict[str, Any] = {}
    # Extraire le boundary depuis le header
    m = re.search(r"boundary=([^;]+)", content_type)
    if not m:
        return result
    boundary = m.group(1)
    # Les guillemets autour du boundary sont supprimÃ©s le cas Ã©chÃ©ant
    if boundary.startswith('"') and boundary.endswith('"'):
        boundary = boundary[1:-1]
    boundary_bytes = ('--' + boundary).encode()
    parts = body.split(boundary_bytes)
    # On ignore la premiÃ¨re et la derniÃ¨re partie (avant le premier boundary et aprÃ¨s le boundary de fermeture)
    for part in parts[1:-1]:
        part = part.strip(b"\r\n")
        if not part:
            continue
        # SÃ©parer les entÃªtes du contenu
        header_block, _, data = part.partition(b"\r\n\r\n")
        headers: Dict[str, str] = {}
        for header_line in header_block.split(b"\r\n"):
            try:
                key, _, value = header_line.decode(errors="replace").partition(":")
                headers[key.strip().lower()] = value.strip()
            except Exception:
                continue
        content_disp = headers.get('content-disposition', '')
        # Extraire les paramÃ¨tres du Content-Disposition
        disp_params = dict(re.findall(r'([^;=\s]+)="?([^";]*)"?', content_disp))
        field_name = disp_params.get('name')
        filename = disp_params.get('filename')
        # Nettoyer le contenu (supprimer le CRLF final)
        cleaned = data.rstrip(b"\r\n")
        if filename:
            result[field_name] = {"filename": filename, "content": cleaned}
        else:
            try:
                result[field_name] = cleaned.decode(errors="replace")
            except Exception:
                result[field_name] = ''
    return result
