# -*- coding: utf-8 -*-
"""Assure que le package local (cmtch/cmtch) est prioritaire sur le parent."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENT = str(ROOT.parent)
ROOT_S = str(ROOT)

# Retirer le parent qui contient un autre app.py (\\prinects\\Apps\\cmtch\\app.py)
sys.path[:] = [p for p in sys.path if Path(p).resolve() != Path(PARENT).resolve()]
if ROOT_S not in sys.path:
    sys.path.insert(0, ROOT_S)

# Invalider un éventuel import 'app' déjà chargé depuis le mauvais chemin
mod = sys.modules.get("app")
if mod is not None:
    mod_file = getattr(mod, "__file__", "") or ""
    if "cmtch\\cmtch" not in mod_file.replace("/", "\\") and "cmtch/cmtch" not in mod_file:
        del sys.modules["app"]
        for name in list(sys.modules):
            if name.startswith("routers") or name.startswith("core") or name.startswith("services") or name.startswith("db"):
                del sys.modules[name]
