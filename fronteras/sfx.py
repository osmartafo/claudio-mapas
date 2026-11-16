"""Efectos de sonido de FRONTERAS, hechos aquí mismo (nada de bancos de sonido).

whoosh  cada cambio de toma
golpe   cuando entra un dibujo o cambia la época
tic     el reloj del año que corre
riser   sube la tensión y termina justo en la revelación (segundo gancho sonoro)
pop     una etiqueta o pantalla que aparece
"""
import wave
import numpy as np

SR = 44100


def _ruido(n, rng):
    return rng.standard_normal(n)


def _filtro(x, corte):
    a = np.exp(-2 * np.pi * corte / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = a * acc + (1 - a) * v
        y[i] = acc
    return y


def whoosh(rng, dur=0.42):
    n = int(SR * dur)
    t = np.arange(n) / SR
    x = _ruido(n, rng)
    # barrido: el ruido se abre y se cierra
    lento = _filtro(x, 900)
    rapido = x - _filtro(x, 2500)
    mezcla = np.sin(np.pi * t / dur) ** 2
    y = lento * (1 - mezcla) + rapido * mezcla * 0.6
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.5
    return y * env * 0.5


def golpe(rng, dur=1.2):
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = 55 * np.exp(-t * 3) + 38
    tono = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 4.5)
    cuerpo = _filtro(_ruido(n, rng), 300) * np.exp(-t * 9) * 3
    return (tono * 0.9 + cuerpo * 0.4)


def tic(rng, dur=0.05):
    n = int(SR * dur)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 120) * 0.25


def riser(rng, dur=1.4):
    """Ruido que se abre y un tono que sube; termina exactamente en el segundo del evento."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    k = t / dur
    x = _ruido(n, rng)
    brillo = x - _filtro(x, 600 + 5000 * k[-1] * 0.2)
    f = 180 * (1 + 3 * k ** 2)
    tono = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.25
    env = k ** 2.2
    return (brillo * 0.35 + tono) * env


def pop(rng, dur=0.08):
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = 900 * np.exp(-t * 30) + 300
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 55) * 0.5


def componer(duracion, eventos, ruta, semilla=3):
    """eventos: lista de (segundo, tipo) con tipo en whoosh, golpe, tic."""
    rng = np.random.default_rng(semilla)
    total = int(SR * (duracion + 2))
    pista = np.zeros((total, 2))
    banco = {"whoosh": [whoosh(rng) for _ in range(4)], "golpe": [golpe(rng)], "tic": [tic(rng)], "riser": [riser(rng)], "pop": [pop(rng)]}
    for k, (seg, tipo) in enumerate(eventos):
        sonidos = banco.get(tipo)
        if not sonidos:
            continue
        s = sonidos[k % len(sonidos)]
        # el whoosh llega a su punto justo en el corte
        antes = {"whoosh": 0.25, "riser": len(s) / SR, "pop": 0.015}.get(tipo, 0.0)
        ini = int((seg - antes) * SR)
        ini = max(0, ini)
        fin = min(total, ini + len(s))
        pan = rng.uniform(-0.3, 0.3)
        pista[ini:fin, 0] += s[: fin - ini] * (1 - pan)
        pista[ini:fin, 1] += s[: fin - ini] * (1 + pan)
    pico = np.abs(pista).max()
    if pico > 0:
        pista *= 0.9 / pico
    with wave.open(ruta, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((pista * 32767).astype("<i2").tobytes())
    return ruta
