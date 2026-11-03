"""Publicar el video como Reel en Facebook e Instagram, con una sola app de Meta.

Variables
  FACEBOOK_PAGE_ID     número de la página de Facebook
  FACEBOOK_PAGE_TOKEN  token de página (pages_manage_posts, pages_read_engagement,
                       instagram_basic, instagram_content_publish)
  INSTAGRAM_ID         opcional; si falta se busca el Instagram ligado a la página
"""
import os, time
import requests

V = "v21.0"
GRAPH = f"https://graph.facebook.com/{V}"


_cache = {}


def _token():
    """Token de página. Si en Railway pegaron un token de usuario, aquí se cambia solo por el de la página."""
    if "pagina" in _cache:
        return _cache["pagina"]
    tok = _token_crudo()
    try:
        r = requests.get(f"{GRAPH}/{os.environ['FACEBOOK_PAGE_ID']}", params={"fields": "access_token", "access_token": tok}, timeout=30)
        if r.ok and r.json().get("access_token"):
            tok = r.json()["access_token"]
    except Exception:
        pass
    _cache["pagina"] = tok
    return tok


def _token_crudo():
    """El token de Meta, aunque se haya guardado en Railway con otro nombre (todos empiezan con EAA)."""
    if os.environ.get("FACEBOOK_PAGE_TOKEN"):
        return os.environ["FACEBOOK_PAGE_TOKEN"].strip()
    for k, v in os.environ.items():
        if v.strip().startswith("EAA") and len(v.strip()) > 80:
            return v.strip()
    return ""


def configurado():
    return bool(os.environ.get("FACEBOOK_PAGE_ID") and _token_crudo())


def _revisa(r):
    if not r.ok:
        try:
            err = r.json().get("error", {})
            msg = err.get("error_user_msg") or err.get("message") or r.text
        except Exception:
            msg = r.text
        raise RuntimeError(f"Meta dijo {r.status_code}: {str(msg)[:300]}")
    return r.json()


# ---------------- Facebook ----------------
def publicar_reel(ruta_video, descripcion):
    pagina, token = os.environ["FACEBOOK_PAGE_ID"], _token()
    d = _revisa(requests.post(f"{GRAPH}/{pagina}/video_reels", data={"upload_phase": "start", "access_token": token}, timeout=60))
    video_id = d["video_id"]
    tam = os.path.getsize(ruta_video)
    with open(ruta_video, "rb") as f:
        _revisa(requests.post(f"https://rupload.facebook.com/video-upload/{V}/{video_id}",
                              headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(tam)},
                              data=f, timeout=600))
    _revisa(requests.post(f"{GRAPH}/{pagina}/video_reels", data={
        "upload_phase": "finish", "video_id": video_id, "video_state": "PUBLISHED",
        "description": descripcion[:2000], "access_token": token}, timeout=120))
    return f"https://www.facebook.com/reel/{video_id}"


# ---------------- Instagram ----------------
def instagram_id():
    if os.environ.get("INSTAGRAM_ID"):
        return os.environ["INSTAGRAM_ID"]
    d = _revisa(requests.get(f"{GRAPH}/{os.environ['FACEBOOK_PAGE_ID']}",
                             params={"fields": "instagram_business_account", "access_token": _token()}, timeout=30))
    ig = (d.get("instagram_business_account") or {}).get("id")
    if not ig:
        raise RuntimeError("La página de Facebook no tiene un Instagram profesional ligado")
    return ig


def instagram_configurado():
    if not configurado():
        return False
    try:
        instagram_id()
        return True
    except Exception:
        return False


def publicar_instagram(ruta_video, descripcion):
    ig, token = instagram_id(), _token()
    # 1. contenedor de Reel con subida directa del archivo
    d = _revisa(requests.post(f"{GRAPH}/{ig}/media", data={
        "media_type": "REELS", "upload_type": "resumable", "caption": descripcion[:2200],
        "share_to_feed": "true", "access_token": token}, timeout=60))
    contenedor = d["id"]
    tam = os.path.getsize(ruta_video)
    with open(ruta_video, "rb") as f:
        _revisa(requests.post(f"https://rupload.facebook.com/ig-api-upload/{V}/{contenedor}",
                              headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(tam)},
                              data=f, timeout=600))
    # 2. esperar a que Instagram procese el video
    for _ in range(60):
        s = _revisa(requests.get(f"{GRAPH}/{contenedor}", params={"fields": "status_code,status", "access_token": token}, timeout=30))
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram no pudo procesar el video: {s.get('status')}")
        time.sleep(5)
    else:
        raise RuntimeError("Instagram tardó demasiado en procesar el video")
    # 3. publicar
    p = _revisa(requests.post(f"{GRAPH}/{ig}/media_publish", data={"creation_id": contenedor, "access_token": token}, timeout=60))
    link = _revisa(requests.get(f"{GRAPH}/{p['id']}", params={"fields": "permalink", "access_token": token}, timeout=30))
    return link.get("permalink") or "https://www.instagram.com/"
