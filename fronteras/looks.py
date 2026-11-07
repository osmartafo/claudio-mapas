"""Looks gráficos completos de FRONTERAS, sacados de referencias de diseño editorial.

Un look cambia todo el lenguaje visual del video, no solo el color:
  el fondo (papel, tapete de corte, risografía, muro de texto, collage),
  cómo se asoma el mapa (franja rasgada, foto de polaroid, mosaico de recortes, pantalla completa),
  las tipografías de título, cifra y subtítulos,
  y las texturas y adornos.
El look "noche" es el original. Los demás usan el mismo motor, así que no cuestan más.
"""
from . import marca
import math
import numpy as np
import skia

# Colores por look: NOCHE es el fondo, MARFIL la tinta del texto, ORO el acento.
LOOKS = {
    "noche": {"nombre": "Noche clásica"},
    "satelite": {
        "nombre": "Satélite a color",
        "NOCHE": "#0B2A4A", "MARFIL": "#FFFFFF", "ORO": "#FFD23F", "ORO_CLARO": "#FFD23F", "CARMIN": "#FF4B3E", "PIEDRA": "#FFFFFF",
        "mapa": None, "base": "base_satelite.jpg", "relieve": "satelite", "ventana": "completa",
        "f_titulo": "HelveticaNowDisplay-ExtraBold", "f_cifra": "HelveticaNowDisplay-ExtraBold", "f_sub": "HelveticaNowDisplay-ExtraBold", "f_ano": "HelveticaNowDisplay-Bold",
        "sub": "color", "mayus_titulo": False, "sombra": 1.6, "grano": 0.0,
        "zonas_vivas": True, "etiqueta_pastilla": True,
    },
    "atlas": {
        "nombre": "Atlas físico",
        "NOCHE": "#5B9BC8", "MARFIL": "#FFFFFF", "ORO": "#FFD23F", "ORO_CLARO": "#FFD23F", "CARMIN": "#E8453C", "PIEDRA": "#3B4A5A",
        "mapa": None, "base": "base_atlas.jpg", "relieve": "atlas", "ventana": "completa",
        "f_titulo": "HelveticaNowDisplay-ExtraBold", "f_cifra": "HelveticaNowDisplay-ExtraBold", "f_sub": "HelveticaNowDisplay-ExtraBold", "f_ano": "HelveticaNowDisplay-Bold",
        "sub": "color", "mayus_titulo": False, "sombra": 2.0, "grano": 0.0,
        "zonas_vivas": True, "etiqueta_pastilla": True, "borde_color": "#2F3B47", "borde_alfa": 0.6, "sub_banda": "#0E1A26",
    },
    "papel": {
        "y_titulo": 235, "y_cifra": 1300, "lineas_cifra": 1,
        "nombre": "Papel rasgado",
        "NOCHE": "#EFECE6", "MARFIL": "#161616", "ORO": "#D9452B", "ORO_CLARO": "#D9452B", "CARMIN": "#D9452B", "PIEDRA": "#7A7570",
        "mapa": ("#2A2A2A", "#E8E3D8"), "mapa_alfa": 1.0, "ventana": "rasgado",
        "f_titulo": "Anton-Regular", "f_cifra": "DMSerifDisplay-Italic", "f_sub": "HelveticaNowDisplay-Bold", "f_ano": "Silkscreen-Regular",
        "sub": "caja", "mayus_titulo": True, "sombra": 0.0, "grano": 0.10, "textura": "papel",
    },
    "acido": {
        "y_titulo": 235, "y_cifra": 1390, "lineas_cifra": 1,
        "nombre": "Ácido",
        "NOCHE": "#B8E02C", "MARFIL": "#0D0D0D", "ORO": "#0D0D0D", "ORO_CLARO": "#0D0D0D", "CARMIN": "#0D0D0D", "PIEDRA": "#3D4A12",
        "mapa": ("#151515", "#D9D9D9"), "mapa_alfa": 1.0, "ventana": "rasgado_alto",
        "f_titulo": "DMSerifDisplay-Italic", "f_cifra": "DMSerifDisplay-Regular", "f_sub": "HelveticaNowDisplay-Bold", "f_ano": "HelveticaNowDisplay-Bold",
        "sub": "caja", "mayus_titulo": False, "sombra": 0.0, "grano": 0.08, "cifra_gigante": True, "textura": "suave",
    },
    "mesa": {
        "y_titulo": 230, "y_cifra": 1415, "lineas_cifra": 1,
        "nombre": "Mesa de recortes",
        "NOCHE": "#2E6A3B", "MARFIL": "#FFFFFF", "ORO": "#F2D21B", "ORO_CLARO": "#F2D21B", "CARMIN": "#E5483A", "PIEDRA": "#A9C9A0",
        "mapa": ("#1C1C1C", "#F3EFE6"), "mapa_alfa": 1.0, "ventana": "polaroid",
        "f_titulo": "HelveticaNowDisplay-ExtraBold", "f_cifra": "HelveticaNowDisplay-ExtraBold", "f_sub": "HelveticaNowDisplay-Bold", "f_ano": "HelveticaNowDisplay-Bold",
        "sub": "caja", "mayus_titulo": False, "sombra": 0.35, "grano": 0.06, "titulo_stickers": True, "textura": "tapete",
    },
    "riso": {
        "y_titulo": 330, "y_cifra": 1250, "lineas_cifra": 2,
        "nombre": "Risografía",
        "NOCHE": "#F2431B", "MARFIL": "#FFE6A6", "ORO": "#FFD23F", "ORO_CLARO": "#FFF2C4", "CARMIN": "#7A1405", "PIEDRA": "#FFB37A",
        "mapa": ("#9E1E06", "#FFC07A"), "mapa_alfa": 0.62, "ventana": "completa",
        "f_titulo": "Anton-Regular", "f_cifra": "Anton-Regular", "f_sub": "HelveticaNowDisplay-Bold", "f_ano": "HelveticaNowDisplay-Bold",
        "sub": "color", "mayus_titulo": True, "sombra": 0.0, "grano": 0.20, "brillo_titulo": True, "esquinas": True, "textura": "riso",
    },
    "muro": {
        "y_titulo": 300, "y_cifra": 1250, "lineas_cifra": 2,
        "nombre": "Muro de texto",
        "NOCHE": "#B3140E", "MARFIL": "#FFFFFF", "ORO": "#FFFFFF", "ORO_CLARO": "#FFFFFF", "CARMIN": "#1A0202", "PIEDRA": "#E88A85",
        "mapa": ("#3A0503", "#E8564E"), "mapa_alfa": 0.45, "ventana": "completa",
        "f_titulo": "HelveticaNowDisplay-ExtraBold", "f_cifra": "HelveticaNowDisplay-ExtraBold", "f_sub": "HelveticaNowDisplay-ExtraBold", "f_ano": "HelveticaNowDisplay-Bold",
        "sub": "color", "mayus_titulo": True, "sombra": 0.3, "grano": 0.08, "muro": True, "textura": "suave",
    },
    "collage": {
        "y_titulo": 235, "y_cifra": 1425, "lineas_cifra": 1,
        "nombre": "Collage rojo",
        "NOCHE": "#D3271F", "MARFIL": "#FFFFFF", "ORO": "#FFFFFF", "ORO_CLARO": "#FFFFFF", "CARMIN": "#141414", "PIEDRA": "#F09A92",
        "mapa": ("#111111", "#EDEDED"), "mapa_alfa": 1.0, "ventana": "mosaico",
        "f_titulo": "PermanentMarker-Regular", "f_cifra": "GochiHand-Regular", "f_sub": "HelveticaNowDisplay-Bold", "f_ano": "GochiHand-Regular",
        "sub": "linea", "mayus_titulo": True, "sombra": 0.25, "grano": 0.12, "textura": "rayones",
    },
}


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def duotono(oscuro, claro):
    """Filtro que convierte el relieve en dos tintas: lo oscuro a un color y lo claro a otro."""
    o, l = hex_rgb(oscuro), hex_rgb(claro)
    fila = lambda k: [(l[k] - o[k]) * 0.30, (l[k] - o[k]) * 0.59, (l[k] - o[k]) * 0.11, 0, o[k]]
    return skia.ColorFilters.Matrix(fila(0) + fila(1) + fila(2) + [0, 0, 0, 1, 0])


def _borde_rasgado(x0, x1, y, rng, amp=18, paso=14):
    pts = []
    x = x0
    while x <= x1 + paso:
        pts.append((x, y + rng.uniform(-amp, amp) + math.sin(x / 37.0) * amp * 0.6))
        x += paso * rng.uniform(0.6, 1.4)
    return pts


def preparar(short, clave):
    """Precalcula lo que el look necesita: ventana del mapa, texturas, muro de texto."""
    L = LOOKS.get(clave) or LOOKS["noche"]
    W, H = short.W, short.H
    rng = np.random.default_rng(11)
    p = {"clave": clave, "cfg": L, "clip": None, "marco": None, "texturas": []}
    if clave == "noche":
        return p
    v = L["ventana"]
    if v in ("rasgado", "rasgado_alto"):
        y1, y2 = (0.25, 0.62) if v == "rasgado" else (0.27, 0.58)
        y1, y2 = H * y1, H * y2
        arriba = _borde_rasgado(-20, W + 20, y1, rng)
        abajo = _borde_rasgado(-20, W + 20, y2, rng)
        path = skia.Path()
        path.moveTo(*arriba[0])
        for q in arriba[1:]:
            path.lineTo(*q)
        for q in reversed(abajo):
            path.lineTo(*q)
        path.close()
        p["clip"] = path
        # labio blanco del papel rasgado
        labios = []
        for borde, signo in ((arriba, -1), (abajo, 1)):
            lab = skia.Path()
            lab.moveTo(*borde[0])
            for q in borde[1:]:
                lab.lineTo(*q)
            for q in reversed(borde):
                lab.lineTo(q[0], q[1] + signo * rng.uniform(6, 16))
            lab.close()
            labios.append(lab)
        p["marco"] = ("labios", labios)
    elif v == "polaroid":
        r = skia.Rect.MakeXYWH(W * 0.11, H * 0.24, W * 0.78, H * 0.40)
        path = skia.Path()
        path.addRect(r)
        m = skia.Matrix.RotateDeg(-3, (r.centerX(), r.centerY()))
        path.transform(m)
        p["clip"] = path
        marco = skia.Path()
        marco.addRect(skia.Rect.MakeLTRB(r.left() - 22, r.top() - 22, r.right() + 22, r.bottom() + 90))
        marco.transform(m)
        p["marco"] = ("polaroid", marco)
    elif v == "mosaico":
        lado, hueco = W * 0.24, W * 0.035
        x0 = (W - 3 * lado - 2 * hueco) / 2
        y0 = H * 0.25
        path = skia.Path()
        for i in range(3):
            for j in range(3):
                q = skia.Path()
                q.addRect(skia.Rect.MakeXYWH(x0 + j * (lado + hueco), y0 + i * (lado + hueco), lado, lado))
                q.transform(skia.Matrix.RotateDeg(rng.uniform(-2.5, 2.5), (x0 + j * (lado + hueco) + lado / 2, y0 + i * (lado + hueco) + lado / 2)))
                path.addPath(q)
        p["clip"] = path
        p["marco"] = ("mosaico", path)
    # texturas de fondo en imagen, se hacen una sola vez
    t = L.get("textura")
    if t:
        p["texturas"].append(_textura(t, W, H, L))
    if L.get("muro"):
        p["muro"] = _muro(short, W, H, L)
    return p


def _a_imagen(arr):
    return skia.Image.fromarray(np.ascontiguousarray(arr), colorType=skia.kRGBA_8888_ColorType)


def _textura(tipo, W, H, L):
    rng = np.random.default_rng(5)
    w, h = W // 2, H // 2
    a = np.zeros((h, w, 4), np.uint8)
    if tipo in ("papel", "suave", "riso"):
        fuerza = {"papel": 22, "suave": 10, "riso": 34}[tipo]
        n = rng.normal(128, fuerza, (h, w)).clip(0, 255)
        if tipo == "riso":  # manchas grandes de tinta
            yy, xx = np.mgrid[0:h, 0:w]
            for _ in range(7):
                cx, cy, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(60, 220)
                n += 40 * np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r * r)))
        n = n.clip(0, 255).astype(np.uint8)
        a[..., 0] = a[..., 1] = a[..., 2] = n
        a[..., 3] = 255
        return ("overlay", _a_imagen(a))
    if tipo == "tapete":
        sup = skia.Surface(W, H)
        with sup as c:
            c.clear(skia.Color4f(0, 0, 0, 0))
            fina = skia.Paint(AntiAlias=True, Color4f=skia.Color4f(0.72, 0.85, 0.68, 0.22), StrokeWidth=1.2)
            gruesa = skia.Paint(AntiAlias=True, Color4f=skia.Color4f(0.80, 0.90, 0.75, 0.45), StrokeWidth=2.2)
            paso = 54
            for k, x in enumerate(range(0, W + paso, paso)):
                c.drawLine(x, 0, x, H, gruesa if k % 5 == 0 else fina)
            for k, y in enumerate(range(0, H + paso, paso)):
                c.drawLine(0, y, W, y, gruesa if k % 5 == 0 else fina)
        return ("normal", sup.makeImageSnapshot())
    if tipo == "rayones":
        sup = skia.Surface(W, H)
        with sup as c:
            c.clear(skia.Color4f(0, 0, 0, 0))
            for _ in range(70):
                x, y = rng.uniform(0, W), rng.uniform(0, H)
                ang, largo = rng.uniform(0, math.pi), rng.uniform(20, 240)
                pa = skia.Paint(AntiAlias=True, Color4f=skia.Color4f(1, 1, 1, rng.uniform(0.08, 0.3)), StrokeWidth=rng.uniform(0.6, 1.8))
                c.drawLine(x, y, x + math.cos(ang) * largo, y + math.sin(ang) * largo, pa)
            for _ in range(900):
                c.drawCircle(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0.5, 2.2),
                             skia.Paint(AntiAlias=True, Color4f=skia.Color4f(0, 0, 0, rng.uniform(0.05, 0.2))))
        return ("normal", sup.makeImageSnapshot())
    return None


def _muro(short, W, H, L):
    """Pared de texto repetido con el título del video, como fondo."""
    from .motor import fuente, mide
    frase = (short.spec.get("titulo") or marca.NOMBRE).upper() + ". "
    f = fuente("HelveticaNowDisplay-ExtraBold", 34)
    sup = skia.Surface(W, H + 120)
    o = hex_rgb(L["CARMIN"])
    with sup as c:
        c.clear(skia.Color4f(0, 0, 0, 0))
        pa = skia.Paint(AntiAlias=True, Color4f=skia.Color4f(o[0], o[1], o[2], 0.55))
        ancho = mide(f, frase)
        y, k = 30, 0
        while y < H + 120:
            x = -((k * 97) % int(ancho))
            while x < W:
                c.drawString(frase, x, y, f, pa)
                x += ancho
            y += 40
            k += 1
    return sup.makeImageSnapshot()


def fondo_extra(short, c, t):
    """Lo que va detrás del mapa: textura base y muro de texto."""
    p = short.look
    if p.get("muro") is not None:
        desp = (t * 18) % 40
        c.drawImage(p["muro"], 0, -desp)


def marco(short, c, t):
    """Lo que va encima del mapa: labios de papel, marco de polaroid, sombras de recortes."""
    p = short.look
    if not p.get("marco"):
        return
    tipo, forma = p["marco"]
    papel = skia.Color4f(*hex_rgb("#FAF8F3"), 1)
    if tipo == "labios":
        for lab in forma:
            sombra = skia.Paint(AntiAlias=True, Color4f=skia.Color4f(0, 0, 0, 0.25))
            sombra.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 6))
            c.drawPath(lab, sombra)
            c.drawPath(lab, skia.Paint(AntiAlias=True, Color4f=papel))
    elif tipo == "polaroid":
        hueco = p["clip"]
        anillo = skia.Op(forma, hueco, skia.PathOp.kDifference_PathOp)
        sombra = skia.Paint(AntiAlias=True, Color4f=skia.Color4f(0, 0, 0, 0.45))
        sombra.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 18))
        c.save()
        c.translate(10, 16)
        c.drawPath(anillo, sombra)
        c.restore()
        c.drawPath(anillo, skia.Paint(AntiAlias=True, Color4f=papel))
    elif tipo == "mosaico":
        pa = skia.Paint(AntiAlias=True, Color4f=skia.Color4f(1, 1, 1, 0.9), Style=skia.Paint.kStroke_Style, StrokeWidth=3)
        c.drawPath(forma, pa)


def acabado(short, c, t):
    """Texturas finales del look y textos de esquina estilo editorial."""
    p = short.look
    W, H = short.W, short.H
    for tex in p.get("texturas", []):
        if not tex:
            continue
        modo, img = tex
        pa = skia.Paint(Alphaf=1.0)
        if modo == "overlay":
            pa = skia.Paint(Alphaf=0.5, BlendMode=skia.BlendMode.kOverlay)
        c.drawImageRect(img, skia.Rect(0, 0, W, H), skia.SamplingOptions(), pa)
    if p["cfg"].get("esquinas") and t < short.T_FIN:
        from .motor import fuente, escribe
        f = fuente("HelveticaNowDisplay-Bold", 22)
        tinta = p["cfg"]["MARFIL"]
        m = (W - short.ANCHO_SEGURO) / 2
        escribe(c, " ".join(marca.LEMA.upper().split()[:2]), m, 150, f, tinta, alfa=0.85, centro=False, sombra=0)
        escribe(c, " ".join(marca.LEMA.upper().split()[2:]), m, 178, f, tinta, alfa=0.85, centro=False, sombra=0)
        escribe(c, marca.NOMBRE, W / 2, 150, f, tinta, alfa=0.85, sombra=0)
        anio = next((str(e.get("año")) for e in short.escenas if e.get("año") and e["_t0"] <= t), "")
        if anio:
            from .motor import mide
            escribe(c, anio, W - m - mide(f, anio), 150, f, tinta, alfa=0.85, centro=False, sombra=0)
        # código de barras decorativo
        rng = np.random.default_rng(3)
        x = W / 2 - 60
        tp = skia.Color4f(*hex_rgb(tinta), 0.8)
        while x < W / 2 + 60:
            g = rng.uniform(1, 4)
            c.drawRect(skia.Rect.MakeXYWH(x, H - 330, g, 26), skia.Paint(Color4f=tp))
            x += g + rng.uniform(1.5, 4)
