"""Mapa a color natural, estilo satélite, para el look Satélite.

Color: Blue Marble de la NASA (dominio público), 4096x2048, que viene en el paquete three-globe.
Nitidez: el relieve de base_fronteras.jpg (30 px por grado) y la costa exacta de Natural Earth.
Se corre una sola vez y deja:
  assets/datos/satelite_tierra.jpg  color de tierra extendido hacia el mar (para costas nítidas)
  assets/datos/satelite_mar.jpg     color de mar extendido hacia la tierra
  assets/datos/base_satelite.jpg    mapa del mundo listo, 10800x5400
"""
import json, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

Image.MAX_IMAGE_PIXELS = None
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = f"{RAIZ}/assets/datos"


def _blur(a, r):
    from scipy.ndimage import gaussian_filter
    a = a.astype(np.float32)
    if a.ndim == 2:
        return gaussian_filter(a, r, mode=("nearest", "wrap"))
    return np.dstack([gaussian_filter(a[..., k], r, mode=("nearest", "wrap")) for k in range(a.shape[2])])


def _rellenar(color, mascara):
    """Extiende el color de donde la máscara vale 1 hacia donde vale 0."""
    out = color * mascara[..., None]
    peso = mascara.copy()
    for r in (1.5, 4, 12, 40, 120):
        num, den = _blur(color * mascara[..., None], r), _blur(mascara, r)
        lleno = num / np.maximum(den, 1e-4)[..., None]
        falta = (peso < 0.999)[..., None]
        nuevo = np.clip(den / 0.3, 0, 1)[..., None] * (1 - peso[..., None])
        out = np.where(falta, out + lleno * nuevo, out)
        peso = np.clip(peso + nuevo[..., 0], 0, 1)
    return out / np.maximum(peso, 1e-4)[..., None]


def mascara_tierra(W, H):
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    for f in json.load(open(f"{D}/ne_50m_admin_0_countries.geojson"))["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for p in polys:
            d.polygon([((x + 180) / 360 * W, (90 - y) / 180 * H) for x, y in p[0]], fill=255)
            for hueco in p[1:]:
                d.polygon([((x + 180) / 360 * W, (90 - y) / 180 * H) for x, y in hueco], fill=0)
    return im


def _viveza(rgb, sat=1.35, brillo=1.12):
    lum = (rgb * [0.3, 0.59, 0.11]).sum(-1, keepdims=True)
    return np.clip((lum + (rgb - lum) * sat) * brillo, 0, 1)


def preparar(forzar=False):
    destino = f"{D}/base_satelite.jpg"
    if os.path.exists(destino) and not forzar:
        return destino
    bm = np.asarray(Image.open(f"{D}/blue_marble_4k.jpg").convert("RGB")).astype(np.float32) / 255
    h, w = bm.shape[:2]
    agua_bm = ((bm[..., 2] > bm[..., 0] + 0.06) & (bm[..., 2] >= bm[..., 1] * 0.95)).astype(np.float32)
    tierra_ok = np.asarray(mascara_tierra(w, h)).astype(np.float32) / 255
    # tierra confiable: tierra en el mapa y no azul en la foto; mar confiable al revés
    m_t = ((tierra_ok > 0.99) & (agua_bm < 0.5)).astype(np.float32)
    m_m = ((tierra_ok < 0.01) & (agua_bm > 0.5)).astype(np.float32)
    tierra = _viveza(_rellenar(bm, m_t), 1.30, 1.10)
    mar = _rellenar(bm, m_m)
    lm = (mar * [0.3, 0.59, 0.11]).sum(-1, keepdims=True)
    mar = np.clip(lm + (mar - lm) * 1.25, 0, 1) * np.array([0.92, 1.05, 1.12])  # mar un poco más turquesa, como en la referencia
    Image.fromarray((np.clip(tierra, 0, 1) * 255).astype(np.uint8)).save(f"{D}/satelite_tierra.jpg", quality=92)
    Image.fromarray((np.clip(mar, 0, 1) * 255).astype(np.uint8)).save(f"{D}/satelite_mar.jpg", quality=92)

    # mundo en 10800x5400: color de la foto, relieve y costa nítidos
    relieve = Image.open(f"{D}/base_fronteras.jpg").convert("L")
    W, H = relieve.size
    m_alta = mascara_tierra(W, H).filter(ImageFilter.GaussianBlur(0.7))
    T = Image.open(f"{D}/satelite_tierra.jpg").resize((W, H), Image.BICUBIC)
    M = Image.open(f"{D}/satelite_mar.jpg").resize((W, H), Image.BICUBIC)
    salida = Image.new("RGB", (W, H))
    PASO, PAD = 600, 80
    for y0 in range(0, H, PASO):
        a, z = max(0, y0 - PAD), min(H, y0 + PASO + PAD)
        caja = (0, a, W, z)
        rel = np.asarray(relieve.crop(caja)).astype(np.float32) / 255
        detalle = rel - _blur(rel, 14)
        t = np.asarray(T.crop(caja)).astype(np.float32) / 255 * (1 + detalle[..., None] * 2.2)
        mm = np.asarray(M.crop(caja)).astype(np.float32) / 255
        k = np.asarray(m_alta.crop(caja)).astype(np.float32)[..., None] / 255
        franja = np.clip(t * k + mm * (1 - k), 0, 1)
        salida.paste(Image.fromarray((franja[y0 - a:y0 - a + min(PASO, H - y0)] * 255).astype(np.uint8)), (0, y0))
    salida.save(destino, quality=90)
    return destino


if __name__ == "__main__":
    print(preparar(True))
