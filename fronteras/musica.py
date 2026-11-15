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


def _guardar(izq, der, duracion, ruta):
    t = np.arange(len(izq)) / SR
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


def _terror(duracion, ruta, rng):
    """Atmósfera de terror: dron grave disonante que respira, golpes sordos y un cristal agudo que inquieta."""
    total = int(SR * (duracion + 3))
    t = np.arange(total) / SR
    raiz = hz(["D", "C#", "E", "F"][rng.integers(4)], 1)
    izq = np.zeros(total)
    der = np.zeros(total)
    for mult, amp in ((1, 0.30), (2 ** (1 / 12), 0.10), (2 ** (6 / 12), 0.07), (2, 0.08)):
        lfo = 0.6 + 0.4 * np.sin(2 * np.pi * (0.05 + rng.uniform(0, 0.05)) * t + rng.uniform(0, 6))
        izq += np.sin(2 * np.pi * raiz * mult * t) * amp * lfo
        der += np.sin(2 * np.pi * raiz * mult * 1.003 * t + 0.4) * amp * lfo
    ruido = _paso_bajo(rng.normal(0, 1, total), 380) * 0.5
    izq += ruido
    der += np.roll(ruido, 900)
    # golpes sordos espaciados (como un corazón lejano)
    k = 6.0 + rng.uniform(0, 3)
    while k < duracion:
        d = int(0.9 * SR)
        tp = np.arange(d) / SR
        g = np.sin(2 * np.pi * 48 * tp * np.exp(-tp * 3)) * np.exp(-tp * 5) * 0.9
        o = int(k * SR)
        if o + d < total:
            izq[o:o + d] += g
            der[o:o + d] += g
        k += 7.5 + rng.uniform(0, 5)
    # cristal agudo que aparece y se va
    for _ in range(int(duracion / 14) + 1):
        f = hz(["A#", "B", "D#"][rng.integers(3)], 5) * rng.choice([1, 1.06])
        o = int(rng.uniform(3, max(4, duracion - 4)) * SR)
        d = int(5 * SR)
        if o + d < total:
            tp = np.arange(d) / SR
            v = np.sin(2 * np.pi * f * tp) * np.sin(np.pi * tp / 5) ** 2 * 0.05
            izq[o:o + d] += v
            der[o:o + d] += v * 0.7
    izq = _reverb(_paso_bajo(izq, 1800), segundos=4.5, mezcla=0.5, rng=rng)
    der = _reverb(_paso_bajo(der, 1800), segundos=4.5, mezcla=0.5, rng=rng)
    return _guardar(izq, der, duracion, ruta)


def _amor(duracion, ruta, rng):
    """Noche tranquila: piano eléctrico cálido en tono mayor, colchón suave y arpegio lento, tipo lo-fi."""
    progs = [[("C", "M"), ("G", "M"), ("A", "m"), ("F", "M")], [("F", "M"), ("A", "m"), ("G", "M"), ("C", "M")],
             [("D", "M"), ("A", "M"), ("B", "m"), ("G", "M")]]
    prog = progs[rng.integers(len(progs))]
    total = int(SR * (duracion + 3))
    izq = np.zeros(total)
    der = np.zeros(total)
    compas = 4.0
    for k in range(int(duracion / compas) + 2):
        raiz, tipo = prog[k % len(prog)]
        ini = int(k * compas * SR)
        fin = min(total, ini + int((compas + 2) * SR))
        tt = np.arange(fin - ini) / SR
        env = np.minimum(1, tt / 1.2) * np.clip((compas + 2 - tt) / 2, 0, 1)
        for f in acorde(raiz, tipo, 3)[:3]:
            v = (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)) * env * 0.05
            izq[ini:fin] += v
            der[ini:fin] += v
        f0 = hz(raiz, 2)
        izq[ini:fin] += np.sin(2 * np.pi * f0 * tt) * env * 0.12
        der[ini:fin] += np.sin(2 * np.pi * f0 * tt) * env * 0.12
        notas = acorde(raiz, tipo, 4)
        for j in range(4):  # arpegio lento de piano eléctrico
            f = notas[(j + k) % len(notas)]
            o = ini + int(j * compas / 4 * SR)
            d = int(2.2 * SR)
            if o + d < total and rng.random() < 0.85:
                tp = np.arange(d) / SR
                n = (np.sin(2 * np.pi * f * tp + 0.8 * np.sin(2 * np.pi * f * 2 * tp) * np.exp(-tp * 4)))
                n *= np.exp(-tp * 2.2) * np.minimum(1, tp / 0.006) * 0.08
                pan = 0.35 + 0.3 * (j % 2)
                izq[o:o + d] += n * (1 - pan) * 2
                der[o:o + d] += n * pan * 2
    izq = _reverb(_paso_bajo(izq, 3200), segundos=2.6, mezcla=0.35, rng=rng)
    der = _reverb(_paso_bajo(der, 3200), segundos=2.6, mezcla=0.35, rng=rng)
    return _guardar(izq, der, duracion, ruta)


def componer(duracion, ruta, semilla=1, animo=None):
    rng = np.random.default_rng(semilla)
    if animo == "terror":
        return _terror(duracion, ruta, rng)
    if animo == "amor":
        return _amor(duracion, ruta, rng)
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
