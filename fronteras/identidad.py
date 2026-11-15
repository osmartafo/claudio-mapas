"""Identidad STORY dentro de los videos: barras de cine, marca de agua, sello, acento por tipo y tarjeta final.

Todas las medidas son para un cuadro vertical de 1080x1920 (en horizontal se escalan).
"""
import os

import skia

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARCA = os.path.join(RAIZ, "assets", "marca")

NEGRO, CARBON, HUMO, MARFIL, ORO, ORO_CLARO = "#0A0A0C", "#17161B", "#8D8796", "#EDE6D6", "#C9A24A", "#E6C77A"
ACENTO = {"curiosidades": "#E0953F", "mapas": "#6FB89C", "terror": "#C8323A", "amor": "#D98A97"}
TINTE = {"curiosidades": "#2A1A08", "mapas": "#0B2219", "terror": "#260A10", "amor": "#24121A"}
BARRA = 150
CIERRE_FRASE = {"curiosidades": ("¿Y tú lo ", "sabías", "?"), "mapas": ("Mañana, ", "otro mapa", "."),
                "terror": ("¿TÚ QUÉ ", "HARÍAS", "?"), "amor": ("Mándaselo a ", "quien no olvidas", ".")}
_img = {}


def imagen(nombre):
    if nombre not in _img:
        ruta = os.path.join(MARCA, nombre + ".png")
        _img[nombre] = skia.Image.open(ruta) if os.path.exists(ruta) else None
    return _img[nombre]


def _m():
    from . import motor
    return motor


def barras(c, W, H, a=1.0):
    """Barras negras de cine arriba y abajo con una línea dorada fina en el borde interior."""
    if a <= 0:
        return
    m = _m()
    b = BARRA * (H / 1920)
    c.drawRect(skia.Rect(0, 0, W, b), skia.Paint(Color4f=m.col(NEGRO, a)))
    c.drawRect(skia.Rect(0, H - b, W, H), skia.Paint(Color4f=m.col(NEGRO, a)))
    linea = skia.Paint(Color4f=m.col(ORO, 0.35 * a))
    c.drawRect(skia.Rect(0, b - 1.5, W, b), linea)
    c.drawRect(skia.Rect(0, H - b, W, H - b + 1.5), linea)


def marca_de_agua(c, W, H, a=0.8):
    img = imagen("story_marca_de_agua")
    if img is None or a <= 0:
        return
    k = H / 1920
    lado = 100 * k
    p = skia.Paint(Alphaf=a)
    c.drawImageRect(img, skia.Rect.MakeXYWH(W - 68 * k - lado, 180 * k, lado, lado), skia.SamplingOptions(skia.FilterMode.kLinear), p)


def sello(c, texto, genero, a=1.0, W=1080, H=1920):
    """Línea del color del tipo y texto en mono dorado, arriba a la izquierda (debajo de la barra)."""
    if not texto or a <= 0:
        return
    m = _m()
    k = H / 1920
    c.drawRect(skia.Rect.MakeXYWH(72 * k, 224 * k, 44 * k, 3 * k), skia.Paint(Color4f=m.col(ACENTO.get(genero, ORO), a)))
    m.escribe(c, str(texto).upper(), 132 * k, 236 * k, m.fuente("IBMPlexMono-Medium", 28 * k), ORO_CLARO, alfa=a, espacio=5 * k,
              centro=False, sombra=0.8)


def regla(c, cx, y, ancho, a=1.0):
    """Regla dorada con un rombo al centro, sobre los subtítulos y bajo el nombre."""
    m = _m()
    p = skia.Paint(AntiAlias=True, Color4f=m.col(ORO, 0.9 * a), StrokeWidth=1.6)
    c.drawLine(cx - ancho / 2, y, cx - 9, y, p)
    c.drawLine(cx + 9, y, cx + ancho / 2, y, p)
    rombo = skia.Path()
    rombo.moveTo(cx, y - 6); rombo.lineTo(cx + 6, y); rombo.lineTo(cx, y + 6); rombo.lineTo(cx - 6, y); rombo.close()
    c.drawPath(rombo, skia.Paint(AntiAlias=True, Color4f=m.col(ORO, a)))


def frase_con_acento(c, partes, cx, y, f_normal, f_acento, color_acento, a=1.0, color=MARFIL):
    """Escribe 'antes' + 'acento' + 'después' centrado, con el acento en otra fuente y color."""
    m = _m()
    antes, acento, despues = partes
    w = m.mide(f_normal, antes) + m.mide(f_acento, acento) + m.mide(f_normal, despues)
    x = cx - w / 2
    x += m.escribe(c, antes, x, y, f_normal, color, alfa=a, centro=False, sombra=0.7) or 0
    x += m.escribe(c, acento, x, y, f_acento, color_acento, alfa=a, centro=False, sombra=0.7) or 0
    m.escribe(c, despues, x, y, f_normal, color, alfa=a, centro=False, sombra=0.7)


def tarjeta_final(c, W, H, t, t_fin, duracion, genero, cierre=None, titulo=None):
    """Tarjeta de título de película al final de cada video."""
    m = _m()
    a = m.rampa(t, t_fin, 0.8)
    if a <= 0:
        return
    k = H / 1920
    fondo = skia.Paint(Shader=skia.GradientShader.MakeRadial((W / 2, H * 0.45), max(W, H) * 0.75,
                       [m.col(TINTE.get(genero, CARBON), 1).toColor(), m.col(NEGRO, 1).toColor()], [0.0, 1.0]))
    fondo.setAlphaf(a)
    c.drawRect(skia.Rect(0, 0, W, H), fondo)
    acento = ACENTO.get(genero, ORO)
    ficcion = genero in ("terror", "amor")
    m.escribe(c, "UN CORTO DE" if ficcion else "UNA HISTORIA DE", W / 2, 520 * k, m.fuente("IBMPlexMono-Medium", 24 * k), ORO,
              alfa=a, espacio=10 * k, sombra=0)
    mono = imagen("story_monograma")
    am = m.rampa(t, t_fin + 0.2, 0.7)
    if mono is not None:
        lado = 230 * k
        c.drawImageRect(mono, skia.Rect.MakeXYWH(W / 2 - lado / 2, 550 * k, lado, lado), skia.SamplingOptions(skia.FilterMode.kLinear),
                        skia.Paint(Alphaf=am))
    pal = imagen("story_wordmark")
    if pal is not None:
        ancho = 560 * k
        alto = ancho * pal.height() / pal.width()
        c.drawImageRect(pal, skia.Rect.MakeXYWH(W / 2 - ancho / 2, 905 * k - alto * 0.72, ancho, alto),
                        skia.SamplingOptions(skia.FilterMode.kLinear), skia.Paint(Alphaf=am))
    else:
        m.escribe(c, "STORY", W / 2, 905 * k, m.fuente("DMSerifDisplay-Regular", 140 * k), MARFIL, alfa=am, espacio=18 * k)
    regla(c, W / 2, 960 * k, 420 * k * m.sale((t - t_fin - 0.3) / 0.8), am)
    from . import marca
    m.escribe(c, marca.LEMA, W / 2, 1040 * k, m.fuente("DMSerifDisplay-Italic", 46 * k), MARFIL, alfa=m.rampa(t, t_fin + 0.6, 0.7), sombra=0)
    af = m.rampa(t, t_fin + 1.0, 0.7)
    partes = CIERRE_FRASE.get(genero, ("", "", ""))
    cz = cierre or {}
    if genero == "terror" and cz.get("pregunta"):
        p = str(cz["pregunta"]).upper().rstrip("?")
        palabras = p.split()
        partes = (" ".join(palabras[:-1]) + " ", palabras[-1] if palabras else "", "?")
    if genero == "terror":
        f = m.fuente("Anton-Regular", 92 * k)
        frase_con_acento(c, partes, W / 2, 1300 * k, f, f, acento, af)
    else:
        size = 70 * k
        f, fi = m.fuente("DMSerifDisplay-Regular", size), m.fuente("DMSerifDisplay-Italic", size)
        while m.mide(f, partes[0] + partes[2]) + m.mide(fi, partes[1]) > 900 * k and size > 40 * k:
            size -= 3 * k
            f, fi = m.fuente("DMSerifDisplay-Regular", size), m.fuente("DMSerifDisplay-Italic", size)
        frase_con_acento(c, partes, W / 2, 1300 * k, f, fi, acento, af)
    opciones = (cz.get("opciones") or [])[:2] if cz.get("tipo") == "encuesta" else []
    for i, op in enumerate(opciones):
        ab = m.rampa(t, t_fin + 1.4 + i * 0.2, 0.5)
        r = skia.Rect.MakeXYWH((200 + i * 360) * k, 1390 * k, 320 * k, 96 * k)
        c.drawRect(r, skia.Paint(AntiAlias=True, Color4f=m.col(ORO, ab), Style=skia.Paint.kStroke_Style, StrokeWidth=2))
        f = m.fuente("IBMPlexMono-Medium", 30 * k)
        texto = str(op).upper()
        while m.mide(f, texto, 2) > 290 * k and f.getSize() > 16:
            f = m.fuente("IBMPlexMono-Medium", f.getSize() - 2)
        m.escribe(c, texto, r.centerX(), r.centerY() + f.getSize() * 0.35, f, ORO_CLARO, alfa=ab, espacio=2, sombra=0)
    m.escribe(c, "UNA PRODUCCIÓN STORY · MMXXVI", W / 2, 1640 * k, m.fuente("IBMPlexMono-Medium", 20 * k), HUMO,
              alfa=m.rampa(t, t_fin + 1.6, 0.6), espacio=6 * k, sombra=0)
    barras(c, W, H, a)
