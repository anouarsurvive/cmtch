from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

# Import de l'application principale
from app import app

@app.get("/test_pwa.html", response_class=HTMLResponse)
async def test_pwa_page(request: Request) -> HTMLResponse:
    """Page de test PWA pour vérifier l'installation"""
    try:
        with open("test_pwa.html", "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Fichier de test PWA non trouvé</h1>", status_code=404)
