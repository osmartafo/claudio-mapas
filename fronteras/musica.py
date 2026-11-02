"""Música original de FRONTERAS, generada por código (sin licencias de terceros).

Fondo orquestal suave: dron grave, colchón de cuerdas y notas de piano espaciadas, con reverberación.
Cada video tiene su propia variación (semilla) para que no suenen todos iguales.
"""
import numpy as np
import wave

SR = 44100
NOTAS = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}

# progresiones en tono menor, sobrias y de documental
PROGRESIONES = [
    [("D", "m"), ("A#", "M"), ("F", "M"), ("C", "M")],
    [("A", "m"), ("F", "M"), ("C", "M"), ("G", "M")],
    [("E", "m"), ("C", "M"), ("G", "M"), ("D", "M")],
    [("D", "m"), ("G", "m"), ("A#", "M"), ("A", "M")],
]


def hz(nota, octava):
    return 440.0 * 2 ** ((NOTAS[nota] + 12 * (octava + 1) - 69) / 12)


def acorde(raiz, tipo, octava):
    base = NOTAS[raiz] + 12 * (octava + 1)
    tercera = 3 if tipo == "m" else 4
    return [440.0 * 2 ** ((n - 69) / 12) for n in (base, base + tercera, base + 7, base + 12)]


def _paso_bajo(x, corte):
    a = np.exp(-2 * np.pi * corte / SR)
    y = np.empty_like(x)
    acc = 0.0
    # filtro de un polo (vectorizado por bloques para que sea rápido)
    from scipy.signal import lfilter
    return lfilter([1 - a], [1, -a], x)


def _reverb(x, segundos=3.2, mezcla=0.38, rng=None):
    n = int(SR * segundos)
    ir = rng.normal(0, 1, n) * np.exp(-np.linspace(0, 7, n))
    ir /= np.sqrt((ir ** 2).sum())
    from scipy.signal import fftconvolve
    mojado = fftconvolve(x, ir)[: len(x)]
    return x * (1 - mezcla) + mojado * mezcla * 2.2


def componer(duracion, ruta, semilla=1):
    rng = np.random.default_rng(semilla)
    prog = PROGRESIONES[semilla % len(PROGRESIONES)]
    total = int(SR * (duracion + 3))
    t = np.arange(total) / SR
    izq = np.zeros(total)
    der = np.zeros(total)
    compas = 8.0
    for k in range(int(duracion / compas) + 2):
        raiz, tipo = prog[k % len(prog)]
        ini = int(k * compas * SR)
        largo = int((compas + 2.5) * SR)
        fin = min(total, ini + largo)
        tt = np.arange(fin - ini) / SR
        env = np.minimum(1, tt / 2.2) * np.clip((compas + 2.5 - tt) / 2.5, 0, 1)
        # colchón de cuerdas: sierras desafinadas y filtradas
        for f in acorde(raiz, tipo, 3):
            for desaf, lado in ((-0.18, 0), (0.21, 1)):
                fase = rng.uniform(0, 1)
                saw = 2 * ((tt * f * (1 + desaf / 100) + fase) % 1) - 1
                (izq if lado == 0 else der)[ini:fin] += saw * env * 0.05
        # dron grave
        f0 = hz(raiz, 1)
        izq[ini:fin] += np.sin(2 * np.pi * f0 * tt) * env * 0.18
        der[ini:fin] += np.sin(2 * np.pi * f0 * tt + 0.3) * env * 0.18
        # notas de piano espaciadas
        notas = acorde(raiz, tipo, 4) + [acorde(raiz, tipo, 5)[1]]
        for j in range(3):
            if rng.random() < 0.8:
                f = notas[rng.integers(len(notas))]
                o = ini + int((0.6 + j * 2.6 + rng.uniform(0, 0.4)) * SR)
                d = int(3.5 * SR)
                if o + d < total:
                    tp = np.arange(d) / SR
                    nota = (np.sin(2 * np.pi * f * tp) + 0.35 * np.sin(4 * np.pi * f * tp) + 0.1 * np.sin(6 * np.pi * f * tp))
                    nota *= np.exp(-tp * 1.6) * np.minimum(1, tp / 0.004) * 0.09
                    pan = rng.uniform(0.3, 0.7)
                    izq[o:o + d] += nota * (1 - pan) * 2
                    der[o:o + d] += nota * pan * 2
    izq = _paso_bajo(izq, 2400)
    der = _paso_bajo(der, 2400)
    izq = _reverb(izq, rng=rng)
    der = _reverb(der, rng=rng)
    # entrada y salida suaves
    fade = np.minimum(1, t / 2.0) * np.clip((duracion + 3 - t) / 3.0, 0, 1)
    est = np.stack([izq * fade, der * fade], axis=1)
    est /= np.abs(est).max() + 1e-9
    est *= 0.8
    with wave.open(ruta, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((est * 32767).astype("<i2").tobytes())
    return ruta


if __name__ == "__main__":
    import sys
    componer(float(sys.argv[1]), sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1)
