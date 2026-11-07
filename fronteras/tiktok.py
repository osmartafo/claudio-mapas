"""Subir el video a TikTok con la Content Posting API (Direct Post).

Variables en Railway
  TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET   de la app en developers.tiktok.com (producto Content Posting API,
                                            con Direct Post activado y esta dirección de regreso registrada:
                                            https://osmartafo.github.io/claudio-mapas/tiktok.html)

Conexión (una sola vez): con /tiktok el bot manda un enlace, el dueño entra con la cuenta del canal,
TikTok lo regresa a la página de FRONTERAS, que muestra la dirección completa para copiarla y pegársela al bot.
Mientras TikTok no audite la app, todo lo que se sube queda visible solo para el dueño (SELF_ONLY).
"""
import json, math, os, re, time, urllib.parse
import requests

API = "https://open.tiktokapis.com/v2"
REDIRECCION = "https://osmartafo.github.io/claudio-mapas/tiktok.html"
ALCANCE = "user.info.basic,video.publish"
CARPETA = "/data" if os.path.isdir("/data") else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVO = os.path.join(CARPETA, "tiktok.json")


def _cliente():
    return os.environ.get("TIKTOK_CLIENT_KEY", "").strip(), os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()


def tiene_cliente():
    k, s = _cliente()
    return bool(k and s)


def _guardado():
    try:
        return json.load(open(ARCHIVO))
    except Exception:
        return {}


def configurado():
    return tiene_cliente() and bool(_guardado().get("refresh_token"))


def enlace_conexion():
    k, _ = _cliente()
    q = {"client_key": k, "scope": ALCANCE, "response_type": "code", "redirect_uri": REDIRECCION, "state": "fronteras-tt"}
    return "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(q)


def parece_respuesta(texto):
    return "fronteras-tt" in texto and "code=" in texto


def _token(datos):
    k, s = _cliente()
    r = requests.post(f"{API}/oauth/token/", data=dict(datos, client_key=k, client_secret=s),
                      headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
    d = r.json()
    if not r.ok or not d.get("access_token"):
        raise RuntimeError(f"TikTok dijo {d.get('error_description') or d.get('error') or r.text[:200]}")
    d["vence"] = time.time() + int(d.get("expires_in", 86400)) - 300
    os.makedirs(CARPETA, exist_ok=True)
    json.dump(d, open(ARCHIVO, "w"))
    return d


def conectar(texto):
    m = re.search(r"[?&]code=([^&\s]+)", texto)
    if not m:
        raise RuntimeError("No encontré el código en esa dirección")
    _token({"code": urllib.parse.unquote(m.group(1)), "grant_type": "authorization_code", "redirect_uri": REDIRECCION})
    return cuenta()


def _acceso():
    d = _guardado()
    if d.get("access_token") and d.get("vence", 0) > time.time():
        return d["access_token"]
    if not d.get("refresh_token"):
        raise RuntimeError("TikTok no está conectado. Usa /tiktok")
    return _token({"grant_type": "refresh_token", "refresh_token": d["refresh_token"]})["access_token"]


def _post(ruta, cuerpo, token=None):
    r = requests.post(f"{API}{ruta}", json=cuerpo, timeout=60,
                      headers={"Authorization": f"Bearer {token or _acceso()}", "Content-Type": "application/json; charset=UTF-8"})
    d = r.json()
    err = d.get("error") or {}
    if not r.ok or (err.get("code") not in (None, "ok")):
        raise RuntimeError(f"TikTok dijo {err.get('code')}: {err.get('message') or r.text[:200]}")
    return d.get("data") or {}


def cuenta():
    r = requests.get(f"{API}/user/info/", params={"fields": "display_name"},
                     headers={"Authorization": f"Bearer {_acceso()}"}, timeout=30)
    return ((r.json().get("data") or {}).get("user") or {}).get("display_name") or "tu cuenta"


def subir(ruta_video, texto):
    token = _acceso()
    info = _post("/post/publish/creator_info/query/", {}, token)
    opciones = info.get("privacy_level_options") or ["SELF_ONLY"]
    privacidad = "PUBLIC_TO_EVERYONE" if "PUBLIC_TO_EVERYONE" in opciones and os.environ.get("TIKTOK_PUBLICO") == "1" else (
        "SELF_ONLY" if "SELF_ONLY" in opciones else opciones[0])
    titulo, _, resto = texto.partition("\n")
    descripcion = (titulo.strip() + "\n\n" + resto.strip().split("\n\nFuentes")[0])[:2000]
    tam = os.path.getsize(ruta_video)
    # trozos: si pesa menos de 64 MB va en uno; si no, trozos de 10 MB y el último absorbe el resto
    trozo = tam if tam <= 64 * 1024 * 1024 else 10 * 1024 * 1024
    n = max(1, tam // trozo)
    datos = _post("/post/publish/video/init/", {
        "post_info": {"title": descripcion, "privacy_level": privacidad, "disable_comment": False,
                      "disable_duet": False, "disable_stitch": False, "is_aigc": True},
        "source_info": {"source": "FILE_UPLOAD", "video_size": tam, "chunk_size": trozo, "total_chunk_count": n}}, token)
    with open(ruta_video, "rb") as f:
        for i in range(n):
            ini = i * trozo
            fin = tam - 1 if i == n - 1 else ini + trozo - 1
            f.seek(ini)
            parte = f.read(fin - ini + 1)
            r = requests.put(datos["upload_url"], data=parte, timeout=600, headers={
                "Content-Type": "video/mp4", "Content-Length": str(len(parte)), "Content-Range": f"bytes {ini}-{fin}/{tam}"})
            if r.status_code not in (200, 201, 206):
                raise RuntimeError(f"TikTok rechazó la subida ({r.status_code}): {r.text[:200]}")
    for _ in range(60):
        st = _post("/post/publish/status/fetch/", {"publish_id": datos["publish_id"]}, token)
        if st.get("status") == "PUBLISH_COMPLETE":
            ids = st.get("publicaly_available_post_id") or []
            return f"https://www.tiktok.com/@/video/{ids[0]}" if ids else "https://www.tiktok.com/"
        if st.get("status") == "FAILED":
            raise RuntimeError(f"TikTok no pudo publicarlo: {st.get('fail_reason')}")
        time.sleep(5)
    return "https://www.tiktok.com/"
