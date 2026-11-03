"""FRONTERAS de principio a fin: tema  ->  guion verificado  ->  voz  ->  música  ->  video.

Uso:
    python -m fronteras.fabrica "por qué Bolivia no tiene mar"
    python -m fronteras.fabrica "..." --horizontal
"""
import json, os, re, sys, time, unicodedata

from . import guionista, voz, musica, sfx
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


def hacer_video(tema, horizontal=False, aviso=lambda *a: print(*a), nuevo=False):
    """nuevo=False reusa el guion y la voz de un intento anterior del mismo tema, para no pagar dos veces."""
    previa = None if nuevo else _previa(tema)
    carpeta = previa or os.path.join(SALIDA, nombre_carpeta(tema))
    os.makedirs(carpeta, exist_ok=True)

    aviso(1, "Investigando el tema y escribiendo el guion")
    if previa:
        spec = json.load(open(f"{carpeta}/spec.json"))
    else:
        spec = guionista.escribir(tema)
    spec["formato"] = "horizontal" if horizontal else "vertical"
    json.dump(spec, open(f"{carpeta}/spec.json", "w"), ensure_ascii=False, indent=1)

    aviso(2, "Grabando la voz")
    if not (os.path.exists(f"{carpeta}/voz.mp3") and os.path.exists(f"{carpeta}/palabras.json")):
        voz.generar(spec["guion"], f"{carpeta}/voz.mp3", f"{carpeta}/palabras.json")
    v = Voz.de_archivo(f"{carpeta}/palabras.json")

    aviso(3, "Componiendo la música")
    musica.componer(v.duracion + 3.2, f"{carpeta}/musica.wav", semilla=abs(hash(tema)) % 1000)

    aviso(4, "Animando los mapas")
    try:
        short = Short(spec, v)
    except ValueError as e:  # una escena pide una palabra que la voz no dijo: se quita esa escena y se sigue
        aviso(4, "Animando los mapas (ajusté una escena)")
        spec["escenas"] = _limpia(spec, v)
        short = Short(spec, v)
    try:
        sfx.componer(short.duracion, short.eventos(), f"{carpeta}/sfx.wav")
        fx = f"{carpeta}/sfx.wav"
    except Exception as err:
        print("Aviso sfx:", err)
        fx = None
    video = short.render(f"{carpeta}/video.mp4", voz_mp3=f"{carpeta}/voz.mp3", musica_wav=f"{carpeta}/musica.wav", sfx_wav=fx,
                         progreso=lambda f: aviso(4, "Animando los mapas", f))

    texto = f"{spec.get('titulo', tema)}\n\n{spec.get('descripcion', '')}\n\nFuentes\n" + "\n".join(spec.get("fuentes", []))
    texto += "\n\nMapas y relieve de Natural Earth. Música original de FRONTERAS."
    open(f"{carpeta}/descripcion.txt", "w").write(texto)
    return video, texto


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
