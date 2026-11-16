"""FRONTERAS de principio a fin: tema  ->  guion verificado  ->  voz  ->  música  ->  video.

Uso:
    python -m fronteras.fabrica "por qué Bolivia no tiene mar"
    python -m fronteras.fabrica "..." --horizontal
"""
from . import marca
import json, os, re, sys, time, unicodedata

from . import guionista, voz, musica, sfx, estilos
from .motor import Short, Voz

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.environ.get("FRONTERAS_SALIDA") or ("/data/videos" if os.path.isdir("/data") else f"{RAIZ}/videos")


def _slug(tema):
    s = unicodedata.normalize("NFD", tema.lower())
    s = "".join(c for c in s if c.isalnum() or c == " ")
    return "-".join(s.split()[:6])


def nombre_carpeta(tema):
    return time.strftime("%Y%m%d-%H%M") + "-" + _slug(tema)


def _previa(tema):
    """Carpeta de un intento anterior del mismo tema (últimas 48 h) que ya tiene guion pagado."""
    if not os.path.isdir(SALIDA):
        return None
    cand = [d for d in os.listdir(SALIDA) if d.endswith("-" + _slug(tema)) and os.path.exists(os.path.join(SALIDA, d, "spec.json"))]
    cand = [d for d in cand if time.time() - os.path.getmtime(os.path.join(SALIDA, d, "spec.json")) < 48 * 3600]
    return os.path.join(SALIDA, sorted(cand)[-1]) if cand else None


PALABRAS_MAPA = ("país", "pais", "frontera", "mapa", "imperio", "territorio", "isla", "continente", "capital", "tratado",
                 "guerra", "región", "region", "estado de", "colonia", "independencia", "conquista", "reino", "océano",
                 "oceano", "mar ", "río ", "rio ", "ciudad", "dinastía", "civilización", "ruta", "península", "desierto de")


def modo_de(tema):
    """Curiosidades, mapas, terror o amor. Los cortos se reconocen por su prefijo o por palabras del género."""
    bajo = tema.lower().strip()
    if bajo.startswith(("corto de terror", "terror:", "historia de terror", "leyenda")) or \
            any(p in bajo for p in ("corto de terror", "historia de miedo", "de terror", "leyenda urbana", "fantasma", "espanto", "aparecido")):
        return "terror"
    if bajo.startswith(("corto de amor", "amor:", "historia de amor")) or \
            any(p in bajo for p in ("corto de amor", "historia de amor", "desamor", "romance", "romántic", "romantic", "corto romántico")):
        return "amor"
    t = " " + re.sub(r"[¿?¡!.,;:]", " ", tema.lower()) + " "
    if any(p in t for p in PALABRAS_MAPA):
        return "mapas"
    try:
        from .motor import _n
        import gzip
        if not hasattr(modo_de, "_nombres"):
            g = json.load(gzip.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "datos", "geo.json.gz"), "rt", encoding="utf-8"))
            modo_de._nombres = {k.split(":", 1)[1] for k in g if k.startswith("pais:") and len(k) > 9}
        import re as _re
        palabras = [_n(w) for w in _re.findall(r"\w+", t)]
        juntas = set(palabras) | {a + b for a, b in zip(palabras, palabras[1:])} | {a + b + c for a, b, c in zip(palabras, palabras[1:], palabras[2:])}
        # un país solo no basta (los billetes de Canadá son una curiosidad): hace falta que el tema sea de geografía o historia
        if juntas & modo_de._nombres and any(p in t for p in ("por qué ", "porque ", "cómo se ", "como se ", "dónde ", "donde ")) \
                and any(p in t for p in (" mapa", " tierra", " forma", " tamaño", " límite", " limite", " separ", " divid", " dueño", " pertenece", " es de ", " no tiene ", " tiene tantos ", " habla")):
            return "mapas"
    except Exception:
        pass
    return "curiosidades"


def hacer_video(tema, horizontal=False, aviso=lambda *a: print(*a), nuevo=False, forzar=None, modo=None):
    """nuevo=False reusa el guion y la voz de un intento anterior del mismo tema, para no pagar dos veces.
    forzar fija partes del estilo, ej. {"look": "satelite", "cerebro": "detective", "voz": "..."}."""
    forzar = {k: v for k, v in (forzar or {}).items() if v}
    previa = None if nuevo else _previa(tema)
    carpeta = previa or os.path.join(SALIDA, nombre_carpeta(tema))
    os.makedirs(carpeta, exist_ok=True)

    aviso(1, "Investigando el tema y escribiendo el guion")
    if previa:
        spec = json.load(open(f"{carpeta}/spec.json"))
        est = spec.get("estilo") or estilos.elegir(forzar)
        if forzar.get("look"):  # el look es solo visual: se puede cambiar sin volver a escribir ni grabar
            est = dict(est, look=forzar["look"])
    else:
        est = estilos.elegir(forzar)
        aviso(1, f"Escribiendo con estilo {estilos.describir(est)}")
        detectado = modo_de(tema)  # un corto pedido por su nombre gana sobre el tipo fijo del menú de estilo
        modo = modo or (detectado if detectado in ("terror", "amor") else None) or forzar.get("modo") or detectado
        aviso(1, f"Escribiendo ({'curiosidad en 3D' if modo == 'curiosidades' else 'historia con mapas'}) con estilo {estilos.describir(est)}")
        if modo in ("terror", "amor"):
            from . import guion_ficcion
            idea = re.sub(r"^\s*corto de (terror|amor)\s*:\s*", "", tema, flags=re.I)
            spec = guion_ficcion.escribir_ficcion(idea, modo, aviso=lambda m: aviso(1, m))
        elif modo == "curiosidades":
            spec = guionista.escribir_curiosidad(tema, estilo_texto=estilos.instrucciones_guion(est), aviso=lambda m: aviso(1, m))
        else:
            try:
                spec = guionista.escribir(tema, estilo_texto=estilos.instrucciones_guion(est), modo=modo)
            except Exception as err:  # si el guion de mapas no sale, se hace como curiosidad en 3D: nunca se queda sin video
                print("Guion de mapas falló, paso a curiosidad 3D:", err)
                aviso(1, "Reescribiendo como curiosidad en 3D")
                spec = guionista.escribir_curiosidad(tema, estilo_texto=estilos.instrucciones_guion(est), aviso=lambda m: aviso(1, m))
    spec["estilo"] = est
    spec["formato"] = "horizontal" if horizontal and spec.get("modo") not in ("terror", "amor") else "vertical"
    json.dump(spec, open(f"{carpeta}/spec.json", "w"), ensure_ascii=False, indent=1)

    precarga = None
    if spec.get("modo") in ("curiosidades", "terror", "amor"):  # los modelos 3D se bajan en paralelo mientras se graba la voz
        import threading
        from . import catalogo
        precarga = threading.Thread(target=catalogo.precargar, args=(spec,), daemon=True)
        precarga.start()

    ficcion = spec.get("modo") in ("terror", "amor")
    aviso(2, "Grabando las voces de los personajes" if ficcion else "Grabando la voz")
    if not (os.path.exists(f"{carpeta}/voz.mp3") and os.path.exists(f"{carpeta}/palabras.json")):
        if ficcion:
            voz.generar_dialogo(spec["lineas"], spec.get("voces") or {}, f"{carpeta}/voz.mp3", f"{carpeta}/palabras.json")
        else:
            voz.generar(spec["guion"], f"{carpeta}/voz.mp3", f"{carpeta}/palabras.json", voz_id=est.get("voz"))
    v = Voz.de_archivo(f"{carpeta}/palabras.json")

    aviso(3, "Componiendo la música")
    musica.componer(v.duracion + (11.0 if ficcion else 4.8), f"{carpeta}/musica.wav",
                    semilla=int(est.get("musica", abs(hash(tema)) % 1000)), animo=spec.get("modo") if ficcion else None)

    aviso(4, "Animando las escenas" if ficcion else "Animando los mapas")
    if ficcion:
        from .ficcion import Corto
        short = Corto(spec, v)
        horizontal = False
    else:
        try:
            short = Short(spec, v)
        except ValueError:  # una escena pide una palabra que la voz no dijo: se quita esa escena y se sigue
            aviso(4, "Animando los mapas (ajusté una escena)")
            spec["escenas"] = _limpia(spec, v)
            short = Short(spec, v)
    if precarga:
        precarga.join(timeout=300)
    if any(e.get("tipo") == "3d" for e in short.escenas):
        aviso(4, "Animando en 3D", 0.0)
        short.preparar_3d(carpeta, aviso=lambda f: aviso(4, "Animando en 3D", 0.5 * f))
    try:
        sfx.componer(short.duracion, short.eventos(), f"{carpeta}/sfx.wav")
        fx = f"{carpeta}/sfx.wav"
    except Exception as err:
        print("Aviso sfx:", err)
        fx = None
    # cada versión es un archivo propio: rehacer con otro look nunca borra las anteriores
    salida_video = f"{carpeta}/video_{est.get('look', 'noche')}_{time.strftime('%H%M%S')}.mp4"
    video = short.render(salida_video, voz_mp3=f"{carpeta}/voz.mp3", musica_wav=f"{carpeta}/musica.wav", sfx_wav=fx,
                         progreso=lambda f: aviso(4, "Armando el video", f))

    revisar_final(video, short.duracion, getattr(short, "T_FIN", None))
    texto = f"{spec.get('titulo', tema)}\n\n{spec.get('descripcion', '')}\n\nFuentes\n" + "\n".join(spec.get("fuentes", []))
    if getattr(short, "creditos", None):
        texto += "\n\nModelos 3D (Objaverse, Sketchfab)\n" + "\n".join(short.creditos)
    if ficcion:
        texto = f"{spec.get('titulo', tema)}\n\n{spec.get('descripcion', '')}\n\nCorto animado original de {marca.NOMBRE.title()}. Historia de ficción." + \
            (("\n\nModelos 3D (Objaverse, Sketchfab)\n" + "\n".join(short.creditos)) if getattr(short, "creditos", None) else "") + \
            "\n\nMúsica original de " + marca.NOMBRE.title() + "."
    else:
        texto += "\n\nMapas de Natural Earth y NASA Blue Marble, relieve de AWS Terrain Tiles. Música original de " + marca.NOMBRE.title() + "."
    open(f"{carpeta}/descripcion.txt", "w").write(texto)
    return video, texto


def revisar_final(video, duracion, hasta=None):
    """Revisión medida del video terminado (lo que el ojo no ve): largo, audio, volumen y tramos negros.
    Lo que falle queda anotado en el registro de errores para la revisión automática cada 48 horas."""
    import subprocess
    problemas = []
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", video],
                           capture_output=True, text=True, timeout=60)
        d = json.loads(r.stdout)
        dur = float(d["format"]["duration"])
        if abs(dur - duracion) > 1.0:
            problemas.append(f"dura {dur:.1f} s y debía durar {duracion:.1f} s")
        if "audio" not in {x["codec_type"] for x in d.get("streams", [])}:
            problemas.append("no tiene audio")
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-t", f"{hasta or duracion:.2f}", "-i", video, "-vf", "blackdetect=d=1.5:pix_th=0.06",
                            "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True, timeout=600)
        negros = [l for l in r.stderr.splitlines() if "black_start" in l]
        # imagen congelada (cámara trabada o toma perdida): más de 1.5 s sin cambio antes del final
        rf = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-t", f"{hasta or duracion:.2f}", "-i", video, "-vf",
                             "freezedetect=n=0.002:d=1.5", "-an", "-f", "null", "-"], capture_output=True, text=True, timeout=600)
        congelados = [l for l in rf.stderr.splitlines() if "freeze_start" in l]
        if congelados:
            problemas.append(f"{len(congelados)} tramos con la imagen congelada de más de 1.5 s")
        if negros:
            problemas.append(f"{len(negros)} tramos negros de más de 1.5 s")
        lufs = [l for l in r.stderr.splitlines() if l.strip().startswith("I:")]
        if lufs:
            valor = float(lufs[-1].split()[1])
            if abs(valor + 14) > 2.5:
                problemas.append(f"volumen {valor} LUFS (meta -14)")
    except Exception as err:
        problemas.append(f"no se pudo revisar: {err}")
    if problemas:
        try:
            from . import monitor
            monitor.registrar("revision_video", "; ".join(problemas), video)
        except Exception:
            pass
        print("Revisión del video:", "; ".join(problemas))
    return problemas


def _limpia(spec, v):
    buenas = [spec["escenas"][0]]
    for e in spec["escenas"][1:]:
        try:
            v.en(e["desde"])
            for g in ("zonas", "etiquetas", "pines", "flechas"):
                e[g] = [x for x in e.get(g, []) if not x.get("desde") or _dice(v, x["desde"])]
            if isinstance(e.get("broll"), dict) and e["broll"].get("desde") and not _dice(v, e["broll"]["desde"]):
                e["broll"].pop("desde")
            buenas.append(e)
        except ValueError:
            pass
    return buenas


def _dice(v, frase):
    try:
        v.en(frase)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    video, texto = hacer_video(" ".join(args), horizontal="--horizontal" in sys.argv)
    print(video)
    print(texto)
