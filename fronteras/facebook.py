"""Publicar el video como Reel en Facebook e Instagram, con una sola app de Meta.

Variables
  FACEBOOK_PAGE_ID     número de la página de Facebook
  FACEBOOK_PAGE_TOKEN  token de página (pages_manage_posts, pages_read_engagement,
                       instagram_basic, instagram_content_publish)
  INSTAGRAM_ID         opcional; si falta se busca el Instagram ligado a la página
"""
import json, os, time
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
    _subidos[os.path.abspath(ruta_video)] = video_id
    return f"https://www.facebook.com/reel/{video_id}"


_subidos = {}  # video local -> id del video ya subido a Facebook, para que Instagram lo tome de ahí


def _url_en_facebook(ruta_video):
    """Una dirección pública del video alojado en Facebook. Si aún no se subió, se sube oculto (sin publicar)."""
    token, pagina = _token(), os.environ["FACEBOOK_PAGE_ID"]
    vid = _subidos.get(os.path.abspath(ruta_video))
    if not vid:
        with open(ruta_video, "rb") as f:
            d = _revisa(requests.post(f"https://graph-video.facebook.com/{V}/{pagina}/videos",
                                      data={"published": "false", "no_story": "true", "access_token": token},
                                      files={"source": ("video.mp4", f, "video/mp4")}, timeout=900))
        vid = d["id"]
    for _ in range(60):
        r = requests.get(f"{GRAPH}/{vid}", params={"fields": "source", "access_token": token}, timeout=30)
        if r.ok and r.json().get("source"):
            return r.json()["source"]
        time.sleep(5)
    raise RuntimeError("Facebook no entregó la dirección del video para Instagram")


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


def _diagnostico_instagram(ig, contenedor, token):
    """Deja en el registro de errores todo lo que Meta dice del rechazo, para encontrar la causa de raíz."""
    import logging
    datos = {}
    for nombre, url, campos in [
        ("contenedor", f"{GRAPH}/{contenedor}", "status_code,status,id"),
        ("cuenta", f"{GRAPH}/{ig}", "username,followers_count,media_count"),
        ("cupo", f"{GRAPH}/{ig}/content_publishing_limit", "quota_usage,config"),
    ]:
        try:
            datos[nombre] = requests.get(url, params={"fields": campos, "access_token": token}, timeout=30).json()
        except Exception as err:
            datos[nombre] = str(err)
    try:
        datos["permisos"] = requests.get(f"{GRAPH}/me/permissions", params={"access_token": _token_crudo()}, timeout=30).json()
    except Exception as err:
        datos["permisos"] = str(err)
    logging.error(f"Diagnóstico de Instagram: {json.dumps(datos, ensure_ascii=False)[:2500]}")


def _esperar_y_publicar(ig, contenedor, token):
    for _ in range(90):
        st = _revisa(requests.get(f"{GRAPH}/{contenedor}", params={"fields": "status_code,status", "access_token": token}, timeout=30))
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            _diagnostico_instagram(ig, contenedor, token)
            raise RuntimeError(f"Instagram no pudo procesar el video: {st.get('status')}")
        time.sleep(5)
    else:
        raise RuntimeError("Instagram tardó demasiado en procesar el video")
    p = _revisa(requests.post(f"{GRAPH}/{ig}/media_publish", data={"creation_id": contenedor, "access_token": token}, timeout=60))
    link = _revisa(requests.get(f"{GRAPH}/{p['id']}", params={"fields": "permalink", "access_token": token}, timeout=30))
    return link.get("permalink") or "https://www.instagram.com/"


RECETAS_IG = [
    # 1080x1920 H.264 main, 30 fps, GOP cerrado, sin B frames, AAC 48 kHz
    ["-vf", "scale=1080:1920,setsar=1", "-c:v", "libx264", "-profile:v", "main", "-level:v", "4.1", "-pix_fmt", "yuv420p",
     "-r", "30", "-vsync", "cfr", "-g", "60", "-keyint_min", "60", "-sc_threshold", "0", "-bf", "0",
     "-preset", "veryfast", "-crf", "21", "-maxrate", "8M", "-bufsize", "16M",
     "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2"],
    # más ligera: 720x1280, perfil high 4.0, bitrate fijo bajo, audio 44.1 kHz
    ["-vf", "scale=720:1280,setsar=1", "-c:v", "libx264", "-profile:v", "high", "-level:v", "4.0", "-pix_fmt", "yuv420p",
     "-r", "30", "-vsync", "cfr", "-g", "30", "-preset", "medium", "-b:v", "3500k", "-maxrate", "4M", "-bufsize", "8M",
     "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"],
]


def _duracion(ruta):
    import subprocess
    try:
        return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", ruta],
                                    capture_output=True, text=True).stdout.strip())
    except Exception:
        return 0.0


def _copia_para_instagram(ruta_video, receta=0, acelerar=1.0):
    """Instagram es muy exigente con el formato. Cada receta es una copia distinta que cumple sus especificaciones;
    si Instagram rechaza una, se intenta la siguiente. acelerar > 1 acorta el video para que quepa en 90 s."""
    import subprocess
    salida = os.path.splitext(ruta_video)[0] + f"_ig{receta}{'r' if acelerar > 1 else ''}.mp4"
    if os.path.exists(salida) and os.path.getmtime(salida) >= os.path.getmtime(ruta_video):
        return salida
    args = list(RECETAS_IG[receta])
    if acelerar > 1:
        vf = args.index("-vf") + 1
        args[vf] = f"setpts=PTS/{acelerar:.4f}," + args[vf]
        args = args + ["-af", f"atempo={acelerar:.4f}"]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", ruta_video, "-map_metadata", "-1"] + args +
                   ["-movflags", "+faststart", salida], check=True)
    return salida


def publicar_instagram(ruta_video, descripcion):
    """Prueba varias copias del video, porque Instagram a veces rechaza una sin decir por qué (error 2207076)."""
    ig, token = instagram_id(), _token()
    dur = _duracion(ruta_video)
    intentos = [(0, 1.0), (1, 1.0)]
    if dur > 89.5:  # algunas cuentas solo aceptan Reels de hasta 90 s por la API
        intentos.append((1, dur / 89.0))
    ultimo = None
    for n, (receta, acel) in enumerate(intentos):
        try:
            copia = _copia_para_instagram(ruta_video, receta, acel)
        except Exception as err:
            print("No pude preparar la copia para Instagram:", err)
            copia = ruta_video
        for intento in range(2):
            try:
                return _publicar_instagram(ig, token, copia, descripcion, usar_facebook=(n == len(intentos) - 1))
            except Exception as err:
                ultimo = err
                print(f"Instagram receta {receta} intento {intento + 1} falló:", err)
                if "procesar" not in str(err):  # error de red o de Meta, vale la pena repetir igual
                    time.sleep(20 * (intento + 1))
                    continue
                break  # Instagram no aceptó esta copia, se pasa a la siguiente receta
    raise ultimo


def _publicar_instagram(ig, token, ruta_video, descripcion, usar_facebook=True):
    base = {"media_type": "REELS", "caption": descripcion[:2200], "share_to_feed": "true", "access_token": token}
    # camino 1: subida directa del archivo
    try:
        d = _revisa(requests.post(f"{GRAPH}/{ig}/media", data=dict(base, upload_type="resumable"), timeout=60))
        contenedor = d["id"]
        destino = d.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{V}/{contenedor}"
        datos = open(ruta_video, "rb").read()
        _revisa(requests.post(destino, headers={"Authorization": f"OAuth {token}", "offset": "0",
                                                "file_size": str(len(datos))}, data=datos, timeout=600))
        return _esperar_y_publicar(ig, contenedor, token)
    except Exception as err:
        print("Instagram directo falló:", err)
        if not usar_facebook:
            raise
    # camino 2: Instagram toma el video desde la copia alojada en Facebook
    url = _url_en_facebook(ruta_video)
    print("Instagram toma el video desde Facebook")
    d = _revisa(requests.post(f"{GRAPH}/{ig}/media", data=dict(base, video_url=url), timeout=60))
    return _esperar_y_publicar(ig, d["id"], token)


