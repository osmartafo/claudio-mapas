"""Relieve en alta resolución para cada video.

El mapa base del mundo (base_fronteras.jpg) mide 30 pixeles por grado y se pixelea al acercar la cámara.
Aquí se baja la elevación real del terreno solo de la zona que el video necesita (AWS Terrain Tiles,
formato terrarium, datos abiertos, sin llave) y se dibuja un relieve sombreado nítido con los colores
del canal. Se arma por capas: cada nivel de zoom cubre las escenas que lo necesitan, y se funde con el
mapa base en los bordes. Si no hay internet o algo falla, el video sale con el mapa base de siempre.
"""
import io, math, os, time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image

URL = os.environ.get("FRONTERAS_TESELAS", "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png")
CACHE = os.environ.get("FRONTERAS_CACHE_TESELAS", "/tmp/teselas")
MAX_TESELAS = int(os.environ.get("FRONTERAS_MAX_TESELAS", "260"))  # por capa
Z_MAX = 10
BASE_DENS = 30.0  # pixeles por grado del mapa base


# ---------------- teselas ----------------
def _tx(lon, z):
    return (lon + 180) / 360 * 2 ** z


def _ty(lat, z):
    lat = max(-85.0, min(85.0, lat))
    r = math.radians(lat)
    return (1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * 2 ** z


def teselas(caja, z):
    lon0, lat0, lon1, lat1 = caja
    x0, x1 = int(math.floor(_tx(lon0, z))), int(math.floor(_tx(lon1, z)))
    y0, y1 = int(math.floor(_ty(lat1, z))), int(math.floor(_ty(lat0, z)))
    n = 2 ** z
    return [(z, x, y) for y in range(max(0, y0), min(n - 1, y1) + 1) for x in range(x0, x1 + 1)]


def _bajar(t, sesion):
    z, x, y = t
    n = 2 ** z
    ruta = os.path.join(CACHE, str(z), str(x % n), f"{y}.png")
    if os.path.exists(ruta):
        return t, ruta
    for intento in range(3):
        try:
            r = sesion.get(URL.format(z=z, x=x % n, y=y), timeout=20)
            if r.ok and r.content[:4] == b"\x89PNG":
                os.makedirs(os.path.dirname(ruta), exist_ok=True)
                tmp = ruta + ".tmp"
                open(tmp, "wb").write(r.content)
                os.replace(tmp, ruta)
                return t, ruta
        except Exception:
            time.sleep(1 + intento)
    return t, None


def _mosaico(lista, aviso=print):
    import requests
    s = requests.Session()
    s.headers["User-Agent"] = "fronteras-mapas/1.0"
    with ThreadPoolExecutor(16) as ex:
        res = dict(ex.map(lambda t: _bajar(t, s), lista))
    malas = [t for t, r in res.items() if not r]
    if len(malas) > 0.1 * len(lista):
        raise RuntimeError(f"no bajaron {len(malas)} de {len(lista)} teselas")
    xs = sorted({t[1] for t in lista}); ys = sorted({t[2] for t in lista})
    elev = np.zeros((len(ys) * 256, len(xs) * 256), np.float32)
    for (z, x, y), ruta in res.items():
        if not ruta:
            continue
        a = np.asarray(Image.open(ruta).convert("RGB")).astype(np.float32)
        e = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
        i, j = ys.index(y), xs.index(x)
        elev[i * 256:(i + 1) * 256, j * 256:(j + 1) * 256] = e
    return elev, xs[0], ys[0]


# ---------------- dibujo ----------------
def _sombreado(elev, z, y0):
    """Relieve sombreado sobre la malla mercator (cada fila tiene su propio tamaño de pixel en metros)."""
    filas = np.arange(elev.shape[0]) + 0.5 + y0 * 256
    lat = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * filas / (256 * 2 ** z)))))
    m = (40075016.7 / (256 * 2 ** z)) * np.cos(np.radians(lat))[:, None]
    exag = 2.2 + 0.25 * max(0, 9 - z)  # más exageración cuando la vista es amplia, como en el mapa base
    e = np.where(elev < 0, 0, elev) * exag
    gy, gx = np.gradient(e)
    gx, gy = gx / m, gy / m
    az, alt = math.radians(315), math.radians(42)
    pend = np.arctan(np.hypot(gx, gy))
    asp = np.arctan2(-gx, gy)
    hs = np.sin(alt) * np.cos(pend) + np.cos(alt) * np.sin(pend) * np.cos(az - asp)
    return np.clip(hs, 0, 1), lat


def _color(hs, elev):
    """Mismos tonos que basemap._gradua: piedra cálida y oscura en tierra, océano casi negro."""
    from PIL import ImageFilter
    tierra_m = (elev > 0).astype(np.float32)
    lum = np.asarray(Image.fromarray((hs * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(18))).astype(np.float32) / 255
    detalle = np.clip((hs - lum) * 2.6 + 0.5, 0, 1)
    alto = np.clip(elev / 3000, 0, 1)
    t = np.clip(detalle * 0.85 + (hs - 0.55) * 0.5 + 0.08 * alto, 0, 1)[..., None]
    sombra = np.array([0.075, 0.068, 0.058], np.float32)
    luz = np.array([0.52, 0.46, 0.37], np.float32)
    tierra = sombra + (luz - sombra) * (t ** 1.25)
    prof = np.clip(1 + elev / 1500, 0, 1)[..., None]  # 1 en la costa, 0 en mar profundo
    mar = np.array([0.020, 0.028, 0.038], np.float32) + np.array([0.030, 0.040, 0.050], np.float32) * prof ** 3
    # costa suave, sin escalones
    borde = np.asarray(Image.fromarray((tierra_m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))).astype(np.float32)[..., None] / 255
    return tierra * borde + mar * (1 - borde)


def _a_equirect(rgb, lat_filas, z, x0, caja, dens_lon, K):
    """Pasa de mercator a lon/lat lineal, que es como el motor dibuja el mundo."""
    lon0, lat0, lon1, lat1 = caja
    ancho = int(round((lon1 - lon0) * dens_lon))
    alto = int(round((lat1 - lat0) * dens_lon / K))
    escala = min(1.0, 7000 / max(ancho, alto))
    ancho, alto = max(8, int(ancho * escala)), max(8, int(alto * escala))
    lats = lat1 - (np.arange(alto) + 0.5) / alto * (lat1 - lat0)
    lons = lon0 + (np.arange(ancho) + 0.5) / ancho * (lon1 - lon0)
    # filas: buscar en la lista de latitudes de la malla mercator (decrece con la fila)
    fy = np.interp(-lats, -lat_filas, np.arange(len(lat_filas)))
    fx = (lons + 180) / 360 * 2 ** z * 256 - x0 * 256 - 0.5
    fx = np.clip(fx, 0, rgb.shape[1] - 1)
    y0i = np.floor(fy).astype(int); y1i = np.minimum(y0i + 1, rgb.shape[0] - 1); wy = (fy - y0i)[:, None, None]
    x0i = np.floor(fx).astype(int); x1i = np.minimum(x0i + 1, rgb.shape[1] - 1); wx = (fx - x0i)[None, :, None]
    filas = rgb[y0i] * (1 - wy) + rgb[y1i] * wy
    return filas[:, x0i] * (1 - wx) + filas[:, x1i] * wx


def _ajustar_a_base(rgb, base_rgb):
    """Iguala brillo y contraste con el mapa base de la misma zona, para que la unión no se note."""
    for k in range(3):
        a, b = rgb[..., k], base_rgb[..., k]
        sa, sb = a.std() + 1e-4, b.std() + 1e-4
        rgb[..., k] = (a - a.mean()) * min(1.6, max(0.6, sb / sa)) + b.mean()
    return np.clip(rgb, 0, 1)


def _difuminar_bordes(alto, ancho, margen=0.07):
    my, mx = max(2, int(alto * margen)), max(2, int(ancho * margen))
    ry = np.minimum(np.arange(alto), np.arange(alto)[::-1]) / my
    rx = np.minimum(np.arange(ancho), np.arange(ancho)[::-1]) / mx
    a = np.clip(np.minimum(ry[:, None], rx[None, :]), 0, 1)
    return a * a * (3 - 2 * a)


# ---------------- plan por escenas ----------------
def plan(camaras, K, W=1080, H=1920):
    """Agrupa las tomas por el zoom que necesitan. Devuelve [(z, caja)] de menor a mayor zoom.
    Cada nivel cubre las tomas que lo necesitan o necesitan más, así las transiciones también salen nítidas."""
    tomas = []
    for lon, lat, ancho in camaras:
        if ancho <= 0:
            continue
        necesita = 1.35 * W / (ancho * 0.86)  # pixeles por grado con el golpe de zoom incluido
        if necesita <= BASE_DENS * 1.15:
            continue
        z = min(Z_MAX, max(6, math.ceil(math.log2(necesita * 360 / 256))))
        m_lon, m_lat = ancho * 0.62, ancho * (H / W) * K * 0.62
        tomas.append((z, (lon - m_lon, lat - m_lat, lon + m_lon, lat + m_lat)))
    salida = []
    for z in sorted({t[0] for t in tomas}):
        cajas = [c for zz, c in tomas if zz >= z]
        caja = (max(-180, min(c[0] for c in cajas)), max(-84, min(c[1] for c in cajas)),
                min(180, max(c[2] for c in cajas)), min(84, max(c[3] for c in cajas)))
        zz = z
        while zz > 6 and len(teselas(caja, zz)) > MAX_TESELAS:
            zz -= 1
        if len(teselas(caja, zz)) > MAX_TESELAS * 1.6:
            continue
        if all(zz != o[0] for o in salida):  # si ya hay una capa de ese zoom, esa es más grande
            salida.append((zz, caja))
    return salida


def capas(camaras, K, base_img=None, W=1080, H=1920, aviso=print):
    """Devuelve [(rgba uint8, caja)] listas para dibujar encima del mapa base."""
    resultado = []
    for z, caja in plan(camaras, K, W, H):
        try:
            lista = teselas(caja, z)
            elev, x0, y0 = _mosaico(lista)
            hs, lat_filas = _sombreado(elev, z, y0)
            rgb = _color(hs, elev)
            dens = 256 * 2 ** z / 360
            eq = _a_equirect(rgb, lat_filas, z, x0, caja, dens, K)
            if base_img is not None:
                bw, bh = base_img.size
                recorte = base_img.crop((int((caja[0] + 180) / 360 * bw), int((90 - caja[3]) / 180 * bh),
                                         int((caja[2] + 180) / 360 * bw), int((90 - caja[1]) / 180 * bh)))
                eq = _ajustar_a_base(eq, np.asarray(recorte).astype(np.float32) / 255)
            alfa = _difuminar_bordes(*eq.shape[:2])
            rgba = np.dstack([np.clip(eq, 0, 1) * 255, alfa * 255]).astype(np.uint8)
            resultado.append((rgba, caja))
            aviso(f"relieve z{z} listo ({len(lista)} teselas, {rgba.shape[1]}x{rgba.shape[0]})")
        except Exception as ex:
            aviso(f"relieve z{z} no se pudo ({ex}); queda el mapa base")
    return resultado
