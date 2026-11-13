"""Catálogo de modelos 3D reales para las escenas (Objaverse, de Allen AI, con licencias Creative Commons).

En lugar de armar un tiburón con cilindros, el guion pide {"catalogo": "shark"} y aquí se busca el mejor
modelo real de esa categoría: el de más "me gusta", con licencia que permite usarlo en un canal monetizado
(CC0, CC BY o CC BY-SA, nunca "no comercial") y de un tamaño razonable. Se descarga una vez y se guarda.

La primera vez que arranca el bot arma un índice (unos minutos, en segundo plano) con las 1,156 categorías
de objetos cotidianos de Objaverse-LVIS: animales, comida, herramientas, vehículos, muebles, instrumentos...
"""
import gzip, io, json, os, threading, time

import requests

HF = "https://huggingface.co/datasets/allenai/objaverse/resolve/main"
CARPETA = os.path.join("/data" if os.path.isdir("/data") else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datos_locales"), "objaverse")
INDICE = os.path.join(CARPETA, "indice.json")
MODELOS = os.path.join(CARPETA, "modelos")
LICENCIAS_OK = {"cc0", "by", "by-sa"}
NOMBRE_LICENCIA = {"cc0": "CC0", "by": "CC BY 4.0", "by-sa": "CC BY-SA 4.0"}
POR_CATEGORIA = 10

_indice = None
_candado = threading.Lock()
estado = {"listo": False, "avance": 0.0, "error": None}


def _gz(url):
    r = requests.get(url, timeout=180)
    r.raise_for_status()
    return json.loads(gzip.decompress(r.content))


def _puntaje(m):
    return (m.get("likeCount") or 0) * 3 + (m.get("viewCount") or 0) / 200 + (300 if m.get("staffpickedAt") else 0)


def construir():
    """Descarga las anotaciones y la ficha de cada modelo, y se queda con los mejores por categoría."""
    os.makedirs(CARPETA, exist_ok=True)
    lvis = _gz(f"{HF}/lvis-annotations.json.gz")
    rutas = _gz(f"{HF}/object-paths.json.gz")
    categoria_de = {u: c for c, us in lvis.items() for u in us}
    trozos = sorted({rutas[u].split("/")[1] for u in categoria_de if u in rutas})
    mejores = {}
    for i, trozo in enumerate(trozos):
        estado["avance"] = i / len(trozos)
        for intento in range(3):
            try:
                meta = _gz(f"{HF}/metadata/{trozo}.json.gz")
                break
            except Exception:
                time.sleep(3 * (intento + 1))
        else:
            continue
        for uid, m in meta.items():
            c = categoria_de.get(uid)
            if not c or m.get("license") not in LICENCIAS_OK or m.get("isAgeRestricted"):
                continue
            tam = ((m.get("archives") or {}).get("glb") or {}).get("size") or 0
            caras = m.get("faceCount") or 0
            if not tam or tam > 30_000_000 or caras > 400_000:
                continue
            mejores.setdefault(c, []).append({
                "uid": uid, "ruta": rutas[uid], "nombre": m.get("name", "")[:80], "licencia": m["license"],
                "autor": ((m.get("user") or {}).get("username") or "")[:60], "url": m.get("viewerUrl", ""),
                "p": round(_puntaje(m), 1), "tam": tam})
        del meta
    for c in mejores:
        mejores[c] = sorted(mejores[c], key=lambda x: -x["p"])[:POR_CATEGORIA]
    tmp = INDICE + ".tmp"
    json.dump(mejores, open(tmp, "w"))
    os.replace(tmp, INDICE)
    return mejores


def indice():
    global _indice
    if _indice is None and os.path.exists(INDICE):
        _indice = json.load(open(INDICE))
        estado["listo"] = True
    return _indice


def preparar_en_segundo_plano():
    """Arma el índice si falta, sin detener al bot."""
    if indice():
        return

    def tarea():
        global _indice
        try:
            _indice = construir()
            estado["listo"] = True
        except Exception as err:
            estado["error"] = str(err)
            print("No pude armar el catálogo 3D:", err)
    threading.Thread(target=tarea, daemon=True).start()


def categorias():
    return sorted(indice() or {})


def obtener(categoria, evitar=()):
    """Devuelve (ruta_local_glb, credito) del mejor modelo de la categoría, o None."""
    ind = indice() or {}
    opciones = ind.get(categoria) or ind.get(categoria.lower().replace(" ", "_")) or []
    for m in opciones:
        if m["uid"] in evitar:
            continue
        destino = os.path.join(MODELOS, m["uid"] + ".glb")
        if not os.path.exists(destino):
            try:
                os.makedirs(MODELOS, exist_ok=True)
                r = requests.get(f"{HF}/{m['ruta']}", timeout=180)
                r.raise_for_status()
                if not r.content[:4] == b"glTF":
                    continue
                with open(destino + ".tmp", "wb") as f:
                    f.write(r.content)
                os.replace(destino + ".tmp", destino)
            except Exception as err:
                print("Modelo no bajó:", m["uid"], err)
                continue
        credito = f"Modelo 3D \"{m['nombre']}\" de {m['autor'] or 'autor anónimo'} ({NOMBRE_LICENCIA.get(m['licencia'], m['licencia'])}) {m['url']}".strip()
        return destino, credito, m["uid"]
    return None
