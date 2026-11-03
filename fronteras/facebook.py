"""Publicar un video como Reel en la página de Facebook de FRONTERAS.

Necesita dos variables
  FACEBOOK_PAGE_ID     el número de la página
  FACEBOOK_PAGE_TOKEN  token de página con permisos pages_manage_posts y pages_read_engagement
"""
import os
import requests

GRAPH = "https://graph.facebook.com/v21.0"


def configurado():
    return bool(os.environ.get("FACEBOOK_PAGE_ID") and os.environ.get("FACEBOOK_PAGE_TOKEN"))


def publicar_reel(ruta_video, descripcion):
    pagina = os.environ["FACEBOOK_PAGE_ID"]
    token = os.environ["FACEBOOK_PAGE_TOKEN"]

    # 1. pedir un espacio para subir
    r = requests.post(f"{GRAPH}/{pagina}/video_reels", data={"upload_phase": "start", "access_token": token}, timeout=60)
    r.raise_for_status()
    video_id = r.json()["video_id"]

    # 2. subir el archivo
    tam = os.path.getsize(ruta_video)
    with open(ruta_video, "rb") as f:
        r = requests.post(f"https://rupload.facebook.com/video-upload/v21.0/{video_id}",
                          headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(tam)},
                          data=f, timeout=600)
    r.raise_for_status()

    # 3. publicar con su texto
    r = requests.post(f"{GRAPH}/{pagina}/video_reels", data={
        "upload_phase": "finish", "video_id": video_id, "video_state": "PUBLISHED",
        "description": descripcion[:2000], "access_token": token}, timeout=120)
    r.raise_for_status()
    return f"https://www.facebook.com/reel/{video_id}"
