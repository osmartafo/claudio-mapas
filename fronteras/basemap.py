"""Prepara el mapa base de Fronteras: relieve real (Natural Earth, dominio público) con el color del canal.

Se corre una sola vez. Toma assets/datos/shadedrelief.jpg y deja assets/datos/base_fronteras.jpg
"""
import os
import numpy as np
from PIL import Image, ImageFilter

Image.MAX_IMAGE_PIXELS = None
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGEN = f"{RAIZ}/assets/datos/shadedrelief.jpg"
DESTINO = f"{RAIZ}/assets/datos/base_fronteras.jpg"


def preparar(forzar=False):
    if os.path.exists(DESTINO) and not forzar:
        return DESTINO
    fuente = Image.open(ORIGEN).convert("RGB")
    W, H = fuente.size
    salida = Image.new("RGB", (W, H))
    PAD, PASO = 64, 540
    for y0 in range(0, H, PASO):
        a, z = max(0, y0 - PAD), min(H, y0 + PASO + PAD)
        franja = _gradua(np.asarray(fuente.crop((0, a, W, z))).astype(np.float32) / 255)
        salida.paste(Image.fromarray(franja[y0 - a:y0 - a + min(PASO, H - y0)]), (0, y0))
    salida.save(DESTINO, quality=93)
    return DESTINO


def _gradua(im):
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    lum = 0.30 * r + 0.55 * g + 0.15 * b

    # agua: azul claramente mayor que rojo
    agua = np.clip((b - r - 0.10) / 0.12, 0, 1)
    agua = np.asarray(Image.fromarray((agua * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32) / 255

    # relieve: detalle de luz y sombra separado del color de fondo
    base = np.asarray(Image.fromarray((lum * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(18))).astype(np.float32) / 255
    detalle = np.clip((lum - base) * 3.2 + 0.5, 0, 1)

    # tierra en tonos piedra cálida y oscura (luz de atardecer)
    sombra = np.array([0.075, 0.068, 0.058])
    luz = np.array([0.52, 0.46, 0.37])
    t = np.clip(detalle * 0.85 + (lum - 0.55) * 0.6, 0, 1)[..., None]
    tierra = sombra + (luz - sombra) * (t ** 1.25)
    # un recuerdo mínimo del color original (verdes y ocres)
    gris = lum[..., None]
    tierra = tierra * (1 + 0.22 * (im - gris))

    # océano casi negro azulado; más claro donde el mar es poco profundo
    prof = np.clip((b - 0.55) / 0.35, 0, 1)[..., None]
    mar = np.array([0.020, 0.028, 0.038]) + np.array([0.016, 0.024, 0.032]) * prof

    final = tierra * (1 - agua[..., None]) + mar * agua[..., None]
    return (np.clip(final, 0, 1) * 255).astype(np.uint8)


if __name__ == "__main__":
    print(preparar(forzar=True))
