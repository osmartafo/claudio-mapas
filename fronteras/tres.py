"""Escenas 3D estilo caricatura (three.js en Chromium sin ventana).

Cada escena 3D del guion trae un "modelo": objetos hechos con formas simples (caja, cilindro, cono, esfera,
toro, cápsula, cuña, engrane, resorte, tubo, plano), animaciones, etiquetas, flechas y movimientos de cámara.
render_escena() guarda los cuadros como JPEG en una carpeta, y el motor de video los usa de fondo
en lugar del mapa. Si algo falla, la escena cae a una tarjeta ilustrada en 2D y el video sale igual.
"""
import base64, os, threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA_JS = f"{RAIZ}/assets/tres"
_servidor = {}


def _url():
    """Sirve assets/tres por http local (los módulos de JavaScript no cargan desde file://)."""
    if "url" not in _servidor:
        srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(_Callado, directory=CARPETA_JS))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        _servidor["url"] = f"http://127.0.0.1:{srv.server_address[1]}/escena.html"
    return _servidor["url"]


class _Callado(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def render_escenas(trabajos, ancho=1080, alto=1920, fps=30, aviso=None):
    """trabajos: lista de (modelo, segundos, carpeta). Dibuja cada escena en su carpeta como c00000.jpg..."""
    from playwright.sync_api import sync_playwright
    hechos = 0
    total = sum(max(1, round(seg * fps)) for _, seg, _ in trabajos) or 1
    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                                      "--ignore-gpu-blocklist", "--disable-dev-shm-usage"])
        for modelo, seg, carpeta in trabajos:
            os.makedirs(carpeta, exist_ok=True)
            if len([f for f in os.listdir(carpeta) if f.endswith(".jpg")]) == max(1, round(seg * fps)):
                continue  # ya estaba dibujada (por ejemplo al rehacer el video con otro look)
            pag = nav.new_page(viewport={"width": ancho, "height": alto})
            pag.goto(_url())
            pag.wait_for_function("window.listo === true", timeout=30000)
            pag.evaluate("([d, w, h]) => window.preparar(d, w, h)", [modelo, ancho, alto])
            n = max(1, round(seg * fps))
            for i in range(n):
                datos = pag.evaluate("u => window.cuadro(u)", i / max(1, n - 1))
                with open(f"{carpeta}/c{i:05d}.jpg", "wb") as f:
                    f.write(base64.b64decode(datos.split(",", 1)[1]))
                hechos += 1
                if aviso and hechos % 15 == 0:
                    aviso(hechos / total)
            pag.close()
        nav.close()
    return True


def _trabajador(lote, ancho, alto, fps):
    return render_escenas(lote, ancho, alto, fps)


def render_paralelo(trabajos, ancho=720, alto=1280, fps=30, aviso=None):
    """Reparte las escenas entre varios navegadores para tardar menos. Se dibuja a 720x1280 y el motor lo escala."""
    import time
    from concurrent.futures import ProcessPoolExecutor, wait
    import multiprocessing as mp
    n = max(1, min(len(trabajos), int(os.environ.get("FRONTERAS_3D_PROCESOS", min(4, os.cpu_count() or 2)))))
    lotes = [[] for _ in range(n)]
    for k, tr in enumerate(sorted(trabajos, key=lambda x: -x[1])):
        min(lotes, key=lambda l: sum(x[1] for x in l)).append(tr)
    total = sum(max(1, round(seg * fps)) for _, seg, _ in trabajos) or 1
    with ProcessPoolExecutor(n, mp_context=mp.get_context("spawn")) as ex:
        futuros = [ex.submit(_trabajador, l, ancho, alto, fps) for l in lotes if l]
        while True:
            hechos, pend = wait(futuros, timeout=2)
            if aviso:
                listos = sum(len(os.listdir(c)) for _, _, c in trabajos if os.path.isdir(c))
                aviso(min(1.0, listos / total))
            if not pend:
                break
        for f in futuros:
            f.result()
