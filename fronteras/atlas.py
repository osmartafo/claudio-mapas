"""Mapa físico de Natural Earth I (relieve sombreado, cobertura del suelo, agua y ríos), dominio público.

El original mide 21600x10800 (60 px por grado). Se guarda cortado en cuadros de 30 grados para que cada video
cargue solo la zona que usa, más una versión de 10800x5400 para las tomas lejanas.
  python -m fronteras.atlas ruta/Mapa_mundial_fisico_21600.tif
"""
import os, sys
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA = f"{RAIZ}/assets/datos/atlas"
DENS = 60  # pixeles por grado
CUADRO = 30  # grados por cuadro


def preparar(tif):
    os.makedirs(CARPETA, exist_ok=True)
    im = Image.open(tif).convert("RGB")
    lado = CUADRO * DENS
    for j in range(180 // CUADRO):
        for i in range(360 // CUADRO):
            im.crop((i * lado, j * lado, (i + 1) * lado, (j + 1) * lado)).save(f"{CARPETA}/c_{i}_{j}.jpg", quality=88)
    im.resize((10800, 5400), Image.LANCZOS).save(f"{RAIZ}/assets/datos/base_atlas.jpg", quality=90)


def recorte(caja, ancho, alto):
    """Devuelve la zona caja=(lon0, lat0, lon1, lat1) como arreglo float 0..1 de alto x ancho."""
    lon0, lat0, lon1, lat1 = caja
    i0, i1 = int((lon0 + 180) // CUADRO), int((min(lon1, 179.999) + 180) // CUADRO)
    j0, j1 = int((90 - lat1) // CUADRO), int((90 - max(lat0, -89.999)) // CUADRO)
    lado = CUADRO * DENS
    mosaico = Image.new("RGB", ((i1 - i0 + 1) * lado, (j1 - j0 + 1) * lado))
    for j in range(max(0, j0), min(5, j1) + 1):
        for i in range(max(0, i0), min(11, i1) + 1):
            mosaico.paste(Image.open(f"{CARPETA}/c_{i}_{j}.jpg"), ((i - i0) * lado, (j - j0) * lado))
    x0 = (lon0 + 180 - i0 * CUADRO) * DENS
    x1 = (lon1 + 180 - i0 * CUADRO) * DENS
    y0 = (90 - lat1 - j0 * CUADRO) * DENS
    y1 = (90 - lat0 - j0 * CUADRO) * DENS
    out = mosaico.transform((ancho, alto), Image.EXTENT, (x0, y0, x1, y1), Image.BICUBIC)
    return np.asarray(out).astype(np.float32) / 255


def disponible():
    return os.path.exists(f"{CARPETA}/c_0_0.jpg")


if __name__ == "__main__":
    preparar(sys.argv[1])
