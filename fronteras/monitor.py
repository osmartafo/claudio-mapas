"""Registro de errores para revisión automática.

Cada error que el bot registra con logging.exception se guarda en /data/errores.json (los últimos 200),
sin llaves ni tokens. Un servidor web mínimo los muestra en
  /salud     si el bot está vivo y si está produciendo un video en este momento
  /errores   la lista de errores, en JSON
Para que se vea desde fuera, en Railway hay que generar un dominio público para el servicio
(Settings, Networking, Generate Domain). Una tarea programada lo lee cada 48 horas y corrige el código.
"""
import json, logging, os, re, threading, time, traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CARPETA = "/data" if os.path.isdir("/data") else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datos_locales")
ARCHIVO = os.path.join(CARPETA, "errores.json")
INICIO = time.time()
VERSION = os.environ.get("RAILWAY_GIT_COMMIT_SHA", "")[:7]
estado_bot = {"ahora": None}
_publicos = {}  # nombre aleatorio -> (ruta, vence): videos que Instagram descarga por su cuenta


def compartir_video(ruta, minutos=120):
    """Deja el video disponible unas horas en https://DOMINIO/v/<nombre aleatorio>.mp4 para que Instagram lo descargue."""
    import secrets
    dominio = os.environ.get("RAILWAY_PUBLIC_DOMAIN") or os.environ.get("FRONTERAS_DOMINIO")
    if not dominio:
        return None
    nombre = secrets.token_urlsafe(24)
    ahora = time.time()
    for k in [k for k, (_, v) in _publicos.items() if v < ahora]:
        _publicos.pop(k, None)
    _publicos[nombre] = (ruta, ahora + minutos * 60)
    return f"https://{dominio}/v/{nombre}.mp4"
_candado = threading.Lock()

_PATRONES = [
    (re.compile(r"EAA[A-Za-z0-9]{20,}"), "EAA***"),
    (re.compile(r"GOCSPX-[\w-]+"), "GOCSPX-***"),
    (re.compile(r"sk-ant-[\w-]+"), "sk-ant-***"),
    (re.compile(r"bot\d{6,}:[\w-]+"), "bot***"),
    (re.compile(r"\d{6,}:[A-Za-z0-9_-]{30,}"), "***"),
    (re.compile(r"(access_token|token|key|secret|code|refresh_token)=([^&\s\"']+)", re.I), r"\1=***"),
    (re.compile(r"(Bearer|OAuth)\s+[\w.\-]+", re.I), r"\1 ***"),
]


def limpiar(texto):
    """Quita cualquier llave o token del texto antes de guardarlo o mostrarlo."""
    t = str(texto)
    for v in os.environ.values():
        v = v.strip()
        if len(v) >= 16 and v in t:
            t = t.replace(v, "***")
    for p, r in _PATRONES:
        t = p.sub(r, t)
    return t


def _leer():
    try:
        return json.load(open(ARCHIVO))
    except Exception:
        return []


def registrar(donde, mensaje, detalle=""):
    with _candado:
        lista = _leer()
        lista.append({"cuando": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + " UTC", "donde": donde,
                      "mensaje": limpiar(mensaje)[:800], "detalle": limpiar(detalle)[-3000:], "version": VERSION})
        try:
            os.makedirs(CARPETA, exist_ok=True)
            json.dump(lista[-200:], open(ARCHIVO, "w"), ensure_ascii=False, indent=1)
        except Exception:
            pass


class _Captura(logging.Handler):
    def emit(self, record):
        if record.levelno < logging.ERROR:
            return
        detalle = "".join(traceback.format_exception(*record.exc_info)) if record.exc_info else ""
        mensaje = record.getMessage()
        if record.exc_info and record.exc_info[1] is not None:
            mensaje = f"{mensaje}: {type(record.exc_info[1]).__name__}: {record.exc_info[1]}"
        registrar(record.name if record.name != "root" else "bot", mensaje, detalle)


class _Web(BaseHTTPRequestHandler):
    def _json(self, datos, codigo=200):
        cuerpo = json.dumps(datos, ensure_ascii=False, indent=1).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _video(self, nombre):
        dato = _publicos.get(nombre)
        if not dato or dato[1] < time.time() or not os.path.exists(dato[0]):
            return self._json({"error": "no existe"}, 404)
        tam = os.path.getsize(dato[0])
        ini, fin = 0, tam - 1
        rango = self.headers.get("Range", "")
        if rango.startswith("bytes="):
            a, _, b = rango[6:].partition("-")
            ini = int(a or 0)
            fin = min(int(b) if b else tam - 1, tam - 1)
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {ini}-{fin}/{tam}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(fin - ini + 1))
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(dato[0], "rb") as f:
            f.seek(ini)
            falta = fin - ini + 1
            while falta > 0:
                bloque = f.read(min(1 << 20, falta))
                if not bloque:
                    break
                self.wfile.write(bloque)
                falta -= len(bloque)

    def do_HEAD(self):
        ruta = self.path.split("?")[0]
        if ruta.startswith("/v/") and ruta.endswith(".mp4"):
            return self._video(ruta[3:-4])
        self.send_response(404); self.end_headers()

    def do_GET(self):
        ruta = self.path.split("?")[0].rstrip("/")
        if ruta.startswith("/v/") and ruta.endswith(".mp4"):
            return self._video(ruta[3:-4])
        if ruta in ("", "/salud"):
            self._json({"vivo": True, "version": VERSION, "minutos_encendido": int((time.time() - INICIO) / 60),
                        "produciendo": estado_bot.get("ahora"), "errores_guardados": len(_leer())})
        elif ruta == "/errores":
            self._json(_leer())
        else:
            self._json({"error": "no existe"}, 404)

    def log_message(self, *a):
        pass


def arrancar():
    logging.getLogger().addHandler(_Captura())
    try:
        srv = ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), _Web)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    except Exception as err:
        print("monitor sin servidor web:", err)
