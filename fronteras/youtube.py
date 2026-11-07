"""Subir el video a YouTube con la YouTube Data API v3.

Variables
  YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET   del cliente OAuth "App de escritorio" del proyecto naked publicador
  YOUTUBE_REFRESH_TOKEN                      opcional; si falta, se guarda al conectar con /youtube
  YOUTUBE_PRIVACIDAD                         private (por defecto), unlisted o public

Conexión (una sola vez): el bot manda un enlace, el dueño entra con la cuenta del canal,
el navegador termina en una página de localhost que no carga, y esa dirección completa se le pega al bot.
Mientras Google no audite la app, YouTube deja los videos subidos por API en privado.
"""
import json, os, re, urllib.parse
import requests

REDIRECCION = "http://localhost:8765"
ALCANCE = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"
CARPETA = os.environ.get("FRONTERAS_DATOS") or ("/data" if os.path.isdir("/data") else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARCHIVO = os.path.join(CARPETA, "youtube.json")


def _cliente():
    secreto = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    if not secreto:  # por si se guardó en Railway con otro nombre (los secretos de Google empiezan con GOCSPX)
        secreto = next((v.strip() for v in os.environ.values() if v.strip().startswith("GOCSPX-")), "")
    return os.environ.get("YOUTUBE_CLIENT_ID", "").strip(), secreto


def tiene_cliente():
    i, s = _cliente()
    return bool(i and s)


def _refresh():
    if os.environ.get("YOUTUBE_REFRESH_TOKEN"):
        return os.environ["YOUTUBE_REFRESH_TOKEN"].strip()
    try:
        return json.load(open(ARCHIVO)).get("refresh_token")
    except Exception:
        return None


def configurado():
    return tiene_cliente() and bool(_refresh())


def enlace_conexion():
    i, _ = _cliente()
    q = {"client_id": i, "redirect_uri": REDIRECCION, "response_type": "code", "scope": ALCANCE,
         "access_type": "offline", "prompt": "consent", "include_granted_scopes": "true"}
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(q)


def parece_respuesta(texto):
    return "localhost:8765" in texto and "code=" in texto


def conectar(texto):
    """Recibe la dirección de localhost que pegó el dueño y guarda el permiso permanente."""
    m = re.search(r"[?&]code=([^&\s]+)", texto)
    if not m:
        raise RuntimeError("No encontré el código en esa dirección")
    i, s = _cliente()
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "code": urllib.parse.unquote(m.group(1)), "client_id": i, "client_secret": s,
        "redirect_uri": REDIRECCION, "grant_type": "authorization_code"}, timeout=30)
    d = r.json()
    if not r.ok or not d.get("refresh_token"):
        raise RuntimeError(f"Google dijo {d.get('error_description') or d.get('error') or r.text[:200]}")
    os.makedirs(CARPETA, exist_ok=True)
    json.dump({"refresh_token": d["refresh_token"]}, open(ARCHIVO, "w"))
    return canal(_acceso())


def _acceso():
    i, s = _cliente()
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": i, "client_secret": s, "refresh_token": _refresh(), "grant_type": "refresh_token"}, timeout=30)
    d = r.json()
    if not r.ok:
        raise RuntimeError(f"Google dijo {d.get('error_description') or d.get('error')}. Vuelve a conectar con /youtube")
    return d["access_token"]


def canal(token=None):
    token = token or _acceso()
    r = requests.get("https://www.googleapis.com/youtube/v3/channels", params={"part": "snippet", "mine": "true"},
                     headers={"Authorization": f"Bearer {token}"}, timeout=30)
    items = r.json().get("items") or []
    return items[0]["snippet"]["title"] if items else "tu canal"


def subir(ruta_video, texto, privacidad=None):
    titulo, _, resto = texto.partition("\n")
    titulo = titulo.strip()[:90]
    if "#shorts" not in titulo.lower():
        titulo = (titulo + " #Shorts")[:100]
    cuerpo = {
        "snippet": {"title": titulo, "description": resto.strip()[:4900], "categoryId": "27",
                    "defaultLanguage": "es", "defaultAudioLanguage": "es"},
        "status": {"privacyStatus": privacidad or os.environ.get("YOUTUBE_PRIVACIDAD", "private"), "selfDeclaredMadeForKids": False},
    }
    token = _acceso()
    tam = os.path.getsize(ruta_video)
    r = requests.post("https://www.googleapis.com/upload/youtube/v3/videos",
                      params={"uploadType": "resumable", "part": "snippet,status"},
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
                               "X-Upload-Content-Length": str(tam), "X-Upload-Content-Type": "video/mp4"},
                      data=json.dumps(cuerpo), timeout=60)
    if not r.ok:
        raise RuntimeError(f"YouTube dijo {r.status_code}: {r.text[:300]}")
    with open(ruta_video, "rb") as f:
        s = requests.put(r.headers["Location"], data=f, headers={"Content-Type": "video/mp4", "Content-Length": str(tam)}, timeout=900)
    if not s.ok:
        raise RuntimeError(f"YouTube dijo {s.status_code}: {s.text[:300]}")
    return f"https://youtube.com/shorts/{s.json()['id']}"
