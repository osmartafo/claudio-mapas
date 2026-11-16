"""Fotos rápidas de un corto: una foto por escena (a la mitad de la toma) y una hoja de contacto, para revisar el look
antes de renderizar el video completo. Muestra los errores de JavaScript de la escena.

    python -m pruebas.fotos_corto pruebas/corto_amor.json [salida.png]
"""
import base64, copy, io, json, os, sys

from PIL import Image

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)


def modelos(corto):
    from fronteras import catalogo
    sets = corto.get("sets") or {}
    genero = corto.get("genero") or ("terror" if "TERROR" in json.dumps(corto)[:3000].upper() else "amor")
    out = []
    escenas = corto.get("escenas") or []
    if os.environ.get("PLANOS"):
        llena = next((e for e in escenas if e.get("set") and not e.get("ocultar")), escenas[0])
        escenas = [llena] * len(os.environ["PLANOS"].split(","))
    for e in escenas:
        base = sets.get(e.get("set")) or {}
        m = copy.deepcopy(base)
        m["objetos"] = [o for o in list(m.get("objetos") or []) + list(e.get("extra") or [])
                        if o.get("id") not in set(e.get("ocultar") or [])]
        for o in m["objetos"]:
            if o.get("catalogo"):
                try:
                    r = catalogo.buscar(o["catalogo"]) if hasattr(catalogo, "buscar") else None
                    if r:
                        o["archivo"] = r
                except Exception:
                    pass
        m.setdefault("ambiente", "terror" if genero == "terror" else "noche")
        m["genero"] = genero
        m.setdefault("personajes", "caricatura")
        planos = [x for x in os.environ.get("PLANOS", "").split(",") if x]
        if planos:
            m["plano"] = planos[len(out) % len(planos)]
        elif e.get("plano"):
            m["plano"] = e["plano"]
        for k in ("animar", "etiquetas", "lente", "desenfoque", "exposicion"):
            if k in e:
                m[k] = e[k]
        ids = [o["id"] for o in m["objetos"] if o.get("forma") == "personaje"]
        m["habla"] = {ids[0]: [[0.3, 0.7]]} if ids else {}
        m["_dur"] = 4
        out.append((m.get("plano") or "toma", m))
    return out


def main():
    from playwright.sync_api import sync_playwright
    from fronteras import tres
    ruta = sys.argv[1]
    salida = sys.argv[2] if len(sys.argv) > 2 else "/tmp/fotos_corto.png"
    corto = json.load(open(ruta))
    escenas = modelos(corto)
    fotos = []
    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        for plano, m in escenas:
            pag = nav.new_page(viewport={"width": 608, "height": 1080})
            pag.on("console", lambda msg: print("  js:", msg.text) if msg.type in ("error", "warning") else None)
            pag.on("pageerror", lambda err: print("  ERROR js:", err))
            pag.goto(tres._url())
            pag.wait_for_function("window.listo === true", timeout=30000)
            pag.evaluate("([d, w, h]) => window.preparar(d, w, h)", [m, 608, 1080])
            datos = pag.evaluate("u => window.cuadro(u)", 0.5)
            fotos.append((plano, Image.open(io.BytesIO(base64.b64decode(datos.split(",", 1)[1]))).convert("RGB")))
            pag.close()
        nav.close()
    cols = min(4, len(fotos))
    filas = (len(fotos) + cols - 1) // cols
    w, h = 304, 540
    hoja = Image.new("RGB", (cols * w, filas * h), "black")
    for i, (plano, f) in enumerate(fotos):
        hoja.paste(f.resize((w, h)), ((i % cols) * w, (i // cols) * h))
    hoja.save(salida)
    if len(sys.argv) > 3:
        for i, (plano, f) in enumerate(fotos):
            f.save(f"{sys.argv[3]}_{i}.png")
    print("listo", salida, [p for p, _ in fotos])


if __name__ == "__main__":
    main()
