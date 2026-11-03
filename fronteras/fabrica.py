"""FRONTERAS de principio a fin: tema  ->  guion verificado  ->  voz  ->  música  ->  video.

Uso:
    python -m fronteras.fabrica "por qué Bolivia no tiene mar"
    python -m fronteras.fabrica "..." --horizontal
"""
import json, os, re, sys, time, unicodedata

from . import guionista, voz, musica
from .motor import Short, Voz

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.environ.get("FRONTERAS_SALIDA", f"{RAIZ}/videos")


def nombre_carpeta(tema):
    s = unicodedata.normalize("NFD", tema.lower())
    s = "".join(c for c in s if c.isalnum() or c == " ")
    return time.strftime("%Y%m%d-%H%M") + "-" + "-".join(s.split()[:6])


def hacer_video(tema, horizontal=False, aviso=lambda *a: print(*a)):
    carpeta = os.path.join(SALIDA, nombre_carpeta(tema))
    os.makedirs(carpeta, exist_ok=True)

    aviso(1, "Investigando el tema y escribiendo el guion")
    spec = guionista.escribir(tema)
    if horizontal:
        spec["formato"] = "horizontal"
    json.dump(spec, open(f"{carpeta}/spec.json", "w"), ensure_ascii=False, indent=1)

    aviso(2, "Grabando la voz")
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
    video = short.render(f"{carpeta}/video.mp4", voz_mp3=f"{carpeta}/voz.mp3", musica_wav=f"{carpeta}/musica.wav",
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
