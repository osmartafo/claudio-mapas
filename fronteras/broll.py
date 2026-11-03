"""B-roll animado de FRONTERAS: dibujos de línea que se arman solos.

Cada motivo es una función dibujar(c, cx, cy, s, u, t) donde
  (cx, cy)  centro del dibujo en píxeles
  s         escala (1 = un cuadro de unos 600 px)
  u         avance de 0 a 1 dentro del clip (se arma con u)
  t         tiempo absoluto, para movimientos continuos
Todo es trazo marfil con detalles en oro, sobre el fondo noche del canal.
"""
import math
import skia

MARFIL = (0.929, 0.902, 0.839)
ORO = (0.788, 0.643, 0.361)
ORO_CLARO = (0.910, 0.800, 0.541)
CARMIN = (0.639, 0.212, 0.169)


def _c(rgb, a=1.0):
    return skia.Color4f(rgb[0], rgb[1], rgb[2], a)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def tramo(u, a, b):
    """Avance local de u entre a y b, suavizado."""
    x = clamp((u - a) / max(1e-6, b - a))
    return x * x * (3 - 2 * x)


def trazo(grosor=5, rgb=MARFIL, a=1.0):
    return skia.Paint(AntiAlias=True, Color4f=_c(rgb, a), Style=skia.Paint.kStroke_Style, StrokeWidth=grosor,
                      StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join)


def relleno(rgb=MARFIL, a=1.0):
    return skia.Paint(AntiAlias=True, Color4f=_c(rgb, a))


def dibuja_parcial(c, path, f, paint):
    """Dibuja solo la fracción f del trazo, como si una mano lo fuera trazando."""
    if f <= 0:
        return
    if f >= 1:
        c.drawPath(path, paint)
        return
    med = skia.PathMeasure(path, False)
    while True:
        L = med.getLength()
        seg = skia.Path()
        med.getSegment(0, L * f, seg, True)
        c.drawPath(seg, paint)
        if not med.nextContour():
            break


def linea(pts):
    p = skia.Path()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    return p


def brillo(c, x, y, r, a):
    p = relleno(ORO, 0.35 * a)
    p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, r * 0.6))
    c.drawCircle(x, y, r, p)


# ---------------- motivos ----------------
def muralla(c, cx, cy, s, u, t):
    """Una muralla que se construye ladrillo por ladrillo, con almenas y bandera."""
    filas, cols, bw, bh = 7, 8, 70 * s, 34 * s
    x0, y_suelo = cx - cols * bw / 2, cy + 200 * s
    c.drawLine(cx - 330 * s, y_suelo, cx + 330 * s, y_suelo, trazo(4 * s, MARFIL, 0.6))
    total = filas * cols
    for i in range(total):
        fila, col = divmod(i, cols)
        a = tramo(u, 0.05 + 0.65 * i / total, 0.05 + 0.65 * i / total + 0.08)
        if a <= 0:
            continue
        x = x0 + col * bw - (bw / 2 if fila % 2 else 0)
        y = y_suelo - (fila + 1) * bh - (1 - a) * 30 * s
        w = bw - 6 * s
        if x < x0:
            x, w = x0, bw / 2 - 6 * s
        c.drawRect(skia.Rect.MakeXYWH(x + 3 * s, y + 3 * s, w, bh - 6 * s), trazo(3.5 * s, MARFIL, a))
    # almenas
    a = tramo(u, 0.72, 0.85)
    ytop = y_suelo - filas * bh
    for k in range(cols):
        if k % 2 == 0:
            c.drawRect(skia.Rect.MakeXYWH(x0 + k * bw + 6 * s, ytop - 40 * s * a, bw - 12 * s, 40 * s * a), trazo(3.5 * s, MARFIL, a))
    # bandera ondeando
    a = tramo(u, 0.85, 0.95)
    if a > 0:
        px, py = cx + 200 * s, ytop - 40 * s
        c.drawLine(px, py, px, py - 150 * s * a, trazo(4 * s, MARFIL, a))
        ban = skia.Path()
        ban.moveTo(px, py - 150 * s * a)
        for k in range(21):
            xx = k / 20 * 110 * s
            ban.lineTo(px + xx, py - 150 * s * a + math.sin(t * 5 + k / 3) * 8 * s * (k / 20))
        for k in range(20, -1, -1):
            xx = k / 20 * 110 * s
            ban.lineTo(px + xx, py - 90 * s * a + math.sin(t * 5 + k / 3) * 8 * s * (k / 20))
        ban.close()
        c.drawPath(ban, relleno(ORO, 0.85 * a))


def barco(c, cx, cy, s, u, t):
    """Un barco de vela que navega sobre olas."""
    for k in range(4):
        y = cy + 130 * s + k * 34 * s
        ola = skia.Path()
        ola.moveTo(cx - 340 * s, y)
        for i in range(1, 61):
            x = cx - 340 * s + i * 680 * s / 60
            ola.lineTo(x, y + math.sin(i / 4 + t * 2.5 + k) * 9 * s)
        dibuja_parcial(c, ola, tramo(u, 0.0 + k * 0.05, 0.3 + k * 0.05), trazo(3 * s, MARFIL, 0.55 - k * 0.1))
    dx = (u - 0.5) * 120 * s
    by = math.sin(t * 2.5) * 6 * s
    c.save()
    c.translate(cx + dx, cy + 110 * s + by)
    c.rotate(math.sin(t * 2.5) * 2)
    casco = linea([(-190 * s, -40 * s), (190 * s, -40 * s), (140 * s, 30 * s), (-150 * s, 30 * s), (-190 * s, -40 * s)])
    dibuja_parcial(c, casco, tramo(u, 0.1, 0.35), trazo(5 * s))
    mastil = linea([(0, -40 * s), (0, -330 * s)])
    dibuja_parcial(c, mastil, tramo(u, 0.3, 0.45), trazo(5 * s))
    vela = linea([(10 * s, -310 * s), (150 * s, -70 * s), (10 * s, -70 * s), (10 * s, -310 * s)])
    a = tramo(u, 0.45, 0.65)
    if a > 0:
        c.drawPath(vela, relleno(MARFIL, 0.12 * a))
    dibuja_parcial(c, vela, a, trazo(4 * s))
    vela2 = linea([(-10 * s, -280 * s), (-130 * s, -80 * s), (-10 * s, -80 * s), (-10 * s, -280 * s)])
    dibuja_parcial(c, vela2, tramo(u, 0.55, 0.75), trazo(4 * s))
    a = tramo(u, 0.75, 0.85)
    if a > 0:
        c.drawPath(linea([(0, -330 * s), (60 * s, -315 * s + math.sin(t * 6) * 4 * s), (0, -300 * s)]), relleno(ORO, a))
    c.restore()


def tratado(c, cx, cy, s, u, t):
    """Un documento que se escribe, se firma y se sella."""
    w, h = 380 * s, 480 * s
    hoja = skia.Rect.MakeXYWH(cx - w / 2, cy - h / 2, w, h)
    a = tramo(u, 0.0, 0.15)
    c.drawRect(hoja, relleno(MARFIL, 0.08 * a))
    dibuja_parcial(c, linea([(hoja.left(), hoja.top()), (hoja.right(), hoja.top()), (hoja.right(), hoja.bottom()),
                             (hoja.left(), hoja.bottom()), (hoja.left(), hoja.top())]), tramo(u, 0, 0.18), trazo(4 * s))
    for k in range(9):
        y = hoja.top() + 70 * s + k * 34 * s
        largo = (w - 80 * s) * (0.6 + 0.4 * ((k * 37) % 10) / 10)
        dibuja_parcial(c, linea([(hoja.left() + 40 * s, y), (hoja.left() + 40 * s + largo, y)]),
                       tramo(u, 0.15 + k * 0.04, 0.2 + k * 0.04), trazo(3 * s, MARFIL, 0.6))
    firma = skia.Path()
    fx, fy = hoja.left() + 70 * s, hoja.bottom() - 70 * s
    firma.moveTo(fx, fy)
    for i in range(1, 80):
        x = fx + i * 2.6 * s
        firma.lineTo(x, fy + math.sin(i / 3.2) * 18 * s * (1 - i / 120) - i * 0.4 * s)
    dibuja_parcial(c, firma, tramo(u, 0.55, 0.78), trazo(4 * s, ORO_CLARO))
    a = tramo(u, 0.8, 0.9)
    if a > 0:
        r = 46 * s * (1.4 - 0.4 * a)
        sx, sy = hoja.right() - 80 * s, hoja.bottom() - 80 * s
        brillo(c, sx, sy, r * 1.5, a)
        c.drawCircle(sx, sy, r, relleno(CARMIN, a))
        c.drawCircle(sx, sy, r * 0.7, trazo(3 * s, ORO_CLARO, a))


def ejercito(c, cx, cy, s, u, t):
    """Filas de soldados que avanzan marchando, con lanzas."""
    for fila in range(3):
        for k in range(6):
            i = fila * 6 + k
            a = tramo(u, 0.03 * i, 0.03 * i + 0.15)
            if a <= 0:
                continue
            x = cx - 290 * s + k * 105 * s + fila * 35 * s + (1 - a) * -120 * s + u * 50 * s
            y = cy - 150 * s + fila * 150 * s
            paso = math.sin(t * 8 + i) * 8 * s
            p = trazo(4 * s, MARFIL, a)
            c.drawCircle(x, y - 40 * s, 13 * s, p)
            c.drawLine(x, y - 26 * s, x, y + 20 * s, p)
            c.drawLine(x, y + 20 * s, x - 14 * s + paso, y + 55 * s, p)
            c.drawLine(x, y + 20 * s, x + 14 * s - paso, y + 55 * s, p)
            c.drawLine(x + 22 * s, y - 70 * s, x + 22 * s, y + 40 * s, trazo(3 * s, ORO, a))
            c.drawPath(linea([(x + 22 * s, y - 70 * s), (x + 15 * s, y - 55 * s), (x + 29 * s, y - 55 * s), (x + 22 * s, y - 70 * s)]),
                       relleno(ORO, a))


def ciudad(c, cx, cy, s, u, t):
    """Una ciudad que crece edificio por edificio y se ilumina."""
    base = cy + 220 * s
    c.drawLine(cx - 340 * s, base, cx + 340 * s, base, trazo(4 * s, MARFIL, 0.6))
    alturas = [180, 300, 220, 420, 260, 360, 200, 480, 240, 320]
    ancho = 62 * s
    for i, hgt in enumerate(alturas):
        a = tramo(u, 0.05 * i, 0.05 * i + 0.3)
        if a <= 0:
            continue
        x = cx - 320 * s + i * 66 * s
        hh = hgt * s * a
        c.drawRect(skia.Rect.MakeXYWH(x, base - hh, ancho, hh), trazo(3.5 * s))
        luz = tramo(u, 0.6 + 0.02 * i, 0.75 + 0.02 * i)
        for f in range(int(hh / (34 * s))):
            for k in range(2):
                if (i * 7 + f * 3 + k) % 3:
                    c.drawRect(skia.Rect.MakeXYWH(x + 12 * s + k * 24 * s, base - hh + 14 * s + f * 34 * s, 12 * s, 16 * s),
                               relleno(ORO_CLARO, 0.85 * luz))


def tren(c, cx, cy, s, u, t):
    """Un tren que cruza sobre la vía con humo."""
    y = cy + 120 * s
    dibuja_parcial(c, linea([(cx - 360 * s, y + 50 * s), (cx + 360 * s, y + 50 * s)]), tramo(u, 0, 0.2), trazo(4 * s))
    for k in range(18):
        x = cx - 340 * s + k * 40 * s
        c.drawLine(x, y + 44 * s, x + 20 * s, y + 60 * s, trazo(3 * s, MARFIL, 0.4 * tramo(u, 0, 0.25)))
    x0 = cx - 500 * s + u * 700 * s
    for k in range(3):
        xx = x0 - k * 170 * s
        c.drawRect(skia.Rect.MakeXYWH(xx, y - 70 * s, 150 * s, 100 * s), trazo(4 * s))
        c.drawCircle(xx + 35 * s, y + 38 * s, 16 * s, trazo(4 * s))
        c.drawCircle(xx + 115 * s, y + 38 * s, 16 * s, trazo(4 * s))
    c.drawRect(skia.Rect.MakeXYWH(x0 + 110 * s, y - 120 * s, 30 * s, 50 * s), trazo(4 * s))
    for k in range(6):
        fase = (t * 0.8 + k / 6) % 1
        c.drawCircle(x0 + 125 * s - fase * 160 * s, y - 140 * s - fase * 150 * s, (14 + fase * 40) * s,
                     trazo(3 * s, MARFIL, 0.6 * (1 - fase)))


def avion(c, cx, cy, s, u, t):
    """Un avión que traza una ruta punteada entre dos puntos."""
    a0, a1 = (cx - 280 * s, cy + 160 * s), (cx + 280 * s, cy - 120 * s)
    ruta = skia.Path()
    ruta.moveTo(*a0)
    ruta.quadTo(cx, cy - 320 * s, *a1)
    p = trazo(4 * s, ORO_CLARO)
    p.setPathEffect(skia.DashPathEffect.Make([18 * s, 14 * s], 0))
    f = tramo(u, 0.05, 0.85)
    dibuja_parcial(c, ruta, f, p)
    for (x, y) in (a0, a1):
        c.drawCircle(x, y, 12 * s, relleno(ORO))
        c.drawCircle(x, y, 24 * s, trazo(3 * s, ORO, 0.7))
    med = skia.PathMeasure(ruta, False)
    pos, tan = med.getPosTan(med.getLength() * f)
    ang = math.degrees(math.atan2(tan.y(), tan.x()))
    c.save()
    c.translate(pos.x(), pos.y())
    c.rotate(ang)
    cuerpo = linea([(-40 * s, 0), (40 * s, 0)])
    c.drawPath(cuerpo, trazo(7 * s))
    c.drawPath(linea([(5 * s, 0), (-15 * s, -38 * s)]), trazo(6 * s))
    c.drawPath(linea([(5 * s, 0), (-15 * s, 38 * s)]), trazo(6 * s))
    c.drawPath(linea([(-35 * s, 0), (-45 * s, -16 * s)]), trazo(5 * s))
    c.restore()


def montanas(c, cx, cy, s, u, t):
    """Una cordillera que se dibuja y un sol que sale detrás."""
    a = tramo(u, 0.4, 0.8)
    sy = cy + 40 * s - 160 * s * a
    if a > 0:
        brillo(c, cx + 120 * s, sy, 120 * s, a)
        c.drawCircle(cx + 120 * s, sy, 70 * s, trazo(4 * s, ORO, a))
    pts = [(-340, 200), (-220, 20), (-150, 90), (-40, -150), (60, 40), (150, -40), (240, 100), (340, 200)]
    cordillera = linea([(cx + x * s, cy + y * s) for x, y in pts])
    dibuja_parcial(c, cordillera, tramo(u, 0.0, 0.45), trazo(5 * s))
    nieve = linea([(cx - 80 * s, cy - 80 * s), (cx - 40 * s, cy - 150 * s), (cx + 0 * s, cy - 82 * s)])
    dibuja_parcial(c, nieve, tramo(u, 0.45, 0.6), trazo(4 * s, MARFIL, 0.8))
    c.drawLine(cx - 340 * s, cy + 200 * s, cx + 340 * s, cy + 200 * s, trazo(4 * s, MARFIL, tramo(u, 0.0, 0.2)))


def rio(c, cx, cy, s, u, t):
    """Un río que corre serpenteando entre dos orillas."""
    for k, off in enumerate((-50, 50)):
        orilla = skia.Path()
        orilla.moveTo(cx - 320 * s, cy + off * s)
        for i in range(1, 81):
            x = cx - 320 * s + i * 640 * s / 80
            orilla.lineTo(x, cy + off * s + math.sin(i / 9) * 90 * s)
        dibuja_parcial(c, orilla, tramo(u, 0, 0.4), trazo(5 * s))
    for k in range(10):
        fase = (t * 0.35 + k / 10) % 1
        i = fase * 80
        x = cx - 320 * s + i * 640 * s / 80
        y = cy + math.sin(i / 9) * 90 * s
        c.drawLine(x - 20 * s, y, x + 20 * s, y, trazo(4 * s, ORO_CLARO, 0.8 * tramo(u, 0.35, 0.5)))


def corona(c, cx, cy, s, u, t):
    """Una corona que se dibuja y brilla."""
    pts = [(-200, 120), (-220, -100), (-110, 10), (0, -160), (110, 10), (220, -100), (200, 120), (-200, 120)]
    cor = linea([(cx + x * s, cy + y * s) for x, y in pts])
    dibuja_parcial(c, cor, tramo(u, 0, 0.5), trazo(6 * s, ORO_CLARO))
    c.drawLine(cx - 200 * s, cy + 160 * s, cx + 200 * s, cy + 160 * s, trazo(6 * s, ORO_CLARO, tramo(u, 0.4, 0.55)))
    for i, (x, y) in enumerate([(-220, -100), (0, -160), (220, -100)]):
        a = tramo(u, 0.55 + i * 0.08, 0.65 + i * 0.08)
        if a > 0:
            brillo(c, cx + x * s, cy + y * s - 22 * s, 30 * s, a)
            c.drawCircle(cx + x * s, cy + y * s - 22 * s, 15 * s * a, relleno(CARMIN if i == 1 else ORO, a))


def bandera(c, cx, cy, s, u, t):
    """Una bandera que se iza en un mástil y ondea."""
    base = cy + 240 * s
    c.drawLine(cx - 120 * s, base, cx + 120 * s, base, trazo(5 * s, MARFIL, tramo(u, 0, 0.15)))
    dibuja_parcial(c, linea([(cx - 100 * s, base), (cx - 100 * s, cy - 260 * s)]), tramo(u, 0.05, 0.3), trazo(6 * s))
    sube = tramo(u, 0.3, 0.7)
    if sube <= 0:
        return
    top = base - 170 * s - (490 - 170) * s * sube
    ban = skia.Path()
    ban.moveTo(cx - 100 * s, top)
    for k in range(31):
        ban.lineTo(cx - 100 * s + k / 30 * 280 * s, top + math.sin(t * 4 + k / 4) * 14 * s * (k / 30))
    for k in range(30, -1, -1):
        ban.lineTo(cx - 100 * s + k / 30 * 280 * s, top + 170 * s + math.sin(t * 4 + k / 4) * 14 * s * (k / 30))
    ban.close()
    c.drawPath(ban, relleno(MARFIL, 0.12))
    c.drawPath(ban, trazo(4 * s))


def batalla(c, cx, cy, s, u, t):
    """Un cañón que dispara, humo y una explosión a lo lejos."""
    bx, by = cx - 250 * s, cy + 140 * s
    c.save()
    c.translate(bx, by)
    c.rotate(-20)
    dibuja_parcial(c, linea([(-60 * s, -22 * s), (150 * s, -22 * s), (150 * s, 22 * s), (-60 * s, 22 * s), (-60 * s, -22 * s)]),
                   tramo(u, 0, 0.25), trazo(5 * s))
    c.restore()
    c.drawCircle(bx - 30 * s, by + 50 * s, 40 * s, trazo(5 * s, MARFIL, tramo(u, 0.1, 0.3)))
    disparo = tramo(u, 0.35, 0.6)
    if 0 < disparo < 1:
        x = bx + 150 * s + disparo * 320 * s
        y = by - 60 * s - math.sin(disparo * math.pi) * 200 * s
        c.drawCircle(x, y, 10 * s, relleno(MARFIL))
    for k in range(5):
        h = tramo(u, 0.35 + k * 0.03, 0.75)
        if 0 < h < 1:
            c.drawCircle(bx + 160 * s + k * 10 * s, by - 80 * s - h * 120 * s, (20 + 50 * h) * s, trazo(3 * s, MARFIL, 0.6 * (1 - h)))
    ex = tramo(u, 0.6, 0.85)
    if ex > 0:
        x, y = bx + 470 * s, by - 80 * s
        brillo(c, x, y, 140 * s * ex, 1 - 0.5 * ex)
        for k in range(12):
            ang = k / 12 * math.tau
            r0, r1 = 30 * s * ex, 150 * s * ex
            c.drawLine(x + math.cos(ang) * r0, y + math.sin(ang) * r0, x + math.cos(ang) * r1, y + math.sin(ang) * r1,
                       trazo(5 * s, ORO_CLARO if k % 2 else CARMIN, 1 - ex * 0.6))


def multitud(c, cx, cy, s, u, t):
    """Una multitud de personas que aparece poco a poco."""
    n = 0
    for fila in range(6):
        for k in range(9):
            n += 1
            a = tramo(u, 0.012 * n, 0.012 * n + 0.1)
            if a <= 0:
                continue
            x = cx - 320 * s + k * 80 * s + (fila % 2) * 40 * s
            y = cy - 230 * s + fila * 90 * s
            r = 13 * s
            col = ORO if (k * 7 + fila * 3) % 11 == 0 else MARFIL
            c.drawCircle(x, y, r, relleno(col, a))
            c.drawArc(skia.Rect.MakeXYWH(x - 26 * s, y + 18 * s, 52 * s, 52 * s), 180, 180, False, trazo(4 * s, col, a))


def reloj(c, cx, cy, s, u, t):
    """Un reloj de arena que deja caer el tiempo."""
    w, h = 220 * s, 300 * s
    marco = linea([(cx - w, cy - h), (cx + w, cy - h), (cx + 30 * s, cy), (cx + w, cy + h), (cx - w, cy + h), (cx - 30 * s, cy), (cx - w, cy - h)])
    dibuja_parcial(c, marco, tramo(u, 0, 0.3), trazo(5 * s))
    arena = tramo(u, 0.25, 1.0)
    ht = (1 - arena) * (h - 40 * s)
    if ht > 2:
        p = linea([(cx - ht / h * w, cy - ht - 10 * s), (cx + ht / h * w, cy - ht - 10 * s), (cx, cy - 10 * s)])
        p.close()
        c.drawPath(p, relleno(ORO, 0.85))
    hb = arena * (h - 40 * s)
    if hb > 2:
        p = linea([(cx - w + 20 * s, cy + h - 10 * s), (cx + w - 20 * s, cy + h - 10 * s), (cx, cy + h - 10 * s - hb)])
        p.close()
        c.drawPath(p, relleno(ORO, 0.85))
    if 0.25 < u < 0.98:
        c.drawLine(cx, cy - 5 * s, cx, cy + h - 10 * s - hb, trazo(3 * s, ORO_CLARO))


def puente(c, cx, cy, s, u, t):
    """Un puente de arcos que une dos orillas."""
    y = cy + 40 * s
    dibuja_parcial(c, linea([(cx - 340 * s, y), (cx + 340 * s, y)]), tramo(u, 0, 0.25), trazo(6 * s))
    for k in range(4):
        x0 = cx - 320 * s + k * 160 * s
        arco = skia.Path()
        arco.addArc(skia.Rect.MakeXYWH(x0, y, 160 * s, 180 * s), 180, -180)
        dibuja_parcial(c, arco, tramo(u, 0.25 + k * 0.1, 0.45 + k * 0.1), trazo(5 * s))
    for k in range(3):
        yy = y + 200 * s + k * 26 * s
        ola = skia.Path()
        ola.moveTo(cx - 340 * s, yy)
        for i in range(1, 41):
            ola.lineTo(cx - 340 * s + i * 17 * s, yy + math.sin(i / 2 + t * 3 + k) * 6 * s)
        c.drawPath(ola, trazo(3 * s, MARFIL, 0.4 * tramo(u, 0.5, 0.7)))


def brujula(c, cx, cy, s, u, t):
    """Una rosa de los vientos que gira y se detiene apuntando."""
    R = 250 * s
    circ = skia.Path()
    circ.addCircle(cx, cy, R)
    dibuja_parcial(c, circ, tramo(u, 0, 0.3), trazo(5 * s))
    c.drawCircle(cx, cy, R * 0.82, trazo(2.5 * s, MARFIL, 0.5 * tramo(u, 0.1, 0.3)))
    for k in range(16):
        a = tramo(u, 0.2 + k * 0.01, 0.35 + k * 0.01)
        ang = k / 16 * math.tau
        r0 = R * (0.82 if k % 2 else 0.75)
        c.drawLine(cx + math.cos(ang) * r0, cy + math.sin(ang) * r0, cx + math.cos(ang) * R, cy + math.sin(ang) * R, trazo(3 * s, MARFIL, a))
    giro = (1 - tramo(u, 0.3, 0.9)) * 540 + math.sin(t * 2) * 3
    c.save()
    c.translate(cx, cy)
    c.rotate(giro)
    a = tramo(u, 0.3, 0.45)
    norte = linea([(0, -R * 0.7), (28 * s, 0), (0, 0)])
    norte.close()
    sur = linea([(0, R * 0.7), (-28 * s, 0), (0, 0)])
    sur.close()
    c.drawPath(norte, relleno(ORO, a))
    c.drawPath(sur, relleno(MARFIL, a * 0.8))
    c.restore()
    c.drawCircle(cx, cy, 12 * s, relleno(ORO_CLARO, tramo(u, 0.3, 0.45)))


def frontera(c, cx, cy, s, u, t):
    """Una frontera que se traza y separa a dos grupos."""
    p = trazo(6 * s, CARMIN)
    p.setPathEffect(skia.DashPathEffect.Make([26 * s, 16 * s], 0))
    f = linea([(cx, cy - 300 * s), (cx + 40 * s, cy - 120 * s), (cx - 30 * s, cy + 40 * s), (cx + 20 * s, cy + 300 * s)])
    dibuja_parcial(c, f, tramo(u, 0.0, 0.45), p)
    for lado in (-1, 1):
        for k in range(3):
            a = tramo(u, 0.45 + k * 0.08, 0.6 + k * 0.08)
            if a <= 0:
                continue
            x = cx + lado * (130 + k * 80) * s
            y = cy + (k - 1) * 60 * s
            col = ORO if lado < 0 else MARFIL
            c.drawCircle(x, y - 40 * s, 16 * s, trazo(4 * s, col, a))
            c.drawLine(x, y - 22 * s, x, y + 40 * s, trazo(4 * s, col, a))
            c.drawLine(x, y + 40 * s, x - 18 * s, y + 85 * s, trazo(4 * s, col, a))
            c.drawLine(x, y + 40 * s, x + 18 * s, y + 85 * s, trazo(4 * s, col, a))


def libro(c, cx, cy, s, u, t):
    """Un libro abierto cuyas páginas pasan."""
    w, h = 300 * s, 360 * s
    izq = linea([(cx, cy - h / 2), (cx - w, cy - h / 2 + 30 * s), (cx - w, cy + h / 2 + 30 * s), (cx, cy + h / 2)])
    der = linea([(cx, cy - h / 2), (cx + w, cy - h / 2 + 30 * s), (cx + w, cy + h / 2 + 30 * s), (cx, cy + h / 2)])
    dibuja_parcial(c, izq, tramo(u, 0, 0.3), trazo(5 * s))
    dibuja_parcial(c, der, tramo(u, 0, 0.3), trazo(5 * s))
    c.drawLine(cx, cy - h / 2, cx, cy + h / 2, trazo(5 * s, MARFIL, tramo(u, 0, 0.2)))
    for k in range(7):
        for lado in (-1, 1):
            y = cy - h / 2 + 70 * s + k * 40 * s
            c.drawLine(cx + lado * 40 * s, y, cx + lado * (w - 40 * s), y + 6 * s, trazo(3 * s, MARFIL, 0.5 * tramo(u, 0.25 + k * 0.03, 0.35 + k * 0.03)))
    for k in range(3):
        f = tramo(u, 0.5 + k * 0.12, 0.65 + k * 0.12)
        if 0 < f < 1:
            x = cx + math.cos(f * math.pi) * w
            pag = linea([(cx, cy - h / 2), (x, cy - h / 2 + 30 * s - math.sin(f * math.pi) * 60 * s), (x, cy + h / 2 + 30 * s - math.sin(f * math.pi) * 60 * s), (cx, cy + h / 2)])
            c.drawPath(pag, trazo(4 * s, ORO_CLARO))


def fuego(c, cx, cy, s, u, t):
    """Llamas que crecen y se agitan."""
    crece = tramo(u, 0, 0.4)
    for k in range(5):
        x = cx + (k - 2) * 70 * s
        alto = (220 + 80 * math.sin(k * 1.7)) * s * crece * (1 + 0.12 * math.sin(t * 9 + k))
        llama = skia.Path()
        llama.moveTo(x - 50 * s, cy + 200 * s)
        llama.cubicTo(x - 60 * s, cy + 200 * s - alto * 0.5, x + math.sin(t * 7 + k) * 25 * s, cy + 200 * s - alto * 0.7,
                      x + math.sin(t * 6 + k) * 15 * s, cy + 200 * s - alto)
        llama.cubicTo(x + 30 * s, cy + 200 * s - alto * 0.6, x + 60 * s, cy + 200 * s - alto * 0.4, x + 50 * s, cy + 200 * s)
        col = ORO_CLARO if k % 2 else CARMIN
        c.drawPath(llama, relleno(col, 0.25 * crece))
        c.drawPath(llama, trazo(4 * s, col, crece))
    c.drawLine(cx - 220 * s, cy + 210 * s, cx + 220 * s, cy + 210 * s, trazo(6 * s, MARFIL, crece))


def dinero(c, cx, cy, s, u, t):
    """Monedas que caen y se apilan."""
    for col in range(3):
        n = 8
        for k in range(n):
            i = col * n + k
            a = tramo(u, 0.03 * i, 0.03 * i + 0.12)
            if a <= 0:
                continue
            x = cx + (col - 1) * 170 * s
            y_final = cy + 220 * s - k * 30 * s
            y = y_final - (1 - a) * 300 * s
            c.drawOval(skia.Rect.MakeXYWH(x - 70 * s, y - 16 * s, 140 * s, 32 * s), relleno(ORO, 0.3 * a))
            c.drawOval(skia.Rect.MakeXYWH(x - 70 * s, y - 16 * s, 140 * s, 32 * s), trazo(4 * s, ORO_CLARO, a))


MOTIVOS = {
    "muralla": muralla, "barco": barco, "tratado": tratado, "ejercito": ejercito, "ciudad": ciudad,
    "tren": tren, "avion": avion, "montanas": montanas, "rio": rio, "corona": corona, "bandera": bandera,
    "batalla": batalla, "multitud": multitud, "reloj": reloj, "puente": puente, "brujula": brujula,
    "frontera": frontera, "libro": libro, "fuego": fuego, "dinero": dinero,
}
SINONIMOS = {
    "pared": "muralla", "fortaleza": "muralla", "castillo": "muralla", "muro": "muralla",
    "flota": "barco", "barcos": "barco", "conquista": "barco", "colonos": "barco", "viaje": "barco",
    "documento": "tratado", "firma": "tratado", "acuerdo": "tratado", "ley": "tratado", "constitucion": "tratado",
    "soldados": "ejercito", "tropas": "ejercito", "guerra": "batalla", "canon": "batalla", "explosion": "batalla",
    "edificios": "ciudad", "rascacielos": "ciudad", "poblacion": "multitud", "gente": "multitud", "personas": "multitud",
    "rey": "corona", "reina": "corona", "imperio": "corona", "independencia": "bandera", "pais": "bandera",
    "tiempo": "reloj", "anos": "reloj", "siglos": "reloj", "exploracion": "brujula", "mapa": "brujula",
    "limite": "frontera", "division": "frontera", "historia": "libro", "incendio": "fuego", "revolucion": "fuego",
    "oro": "dinero", "monedas": "dinero", "venta": "dinero", "compra": "dinero", "millones": "dinero",
    "cordillera": "montanas", "montana": "montanas", "volcan": "montanas", "agua": "rio", "canal": "rio",
    "ferrocarril": "tren", "vuelo": "avion", "ruta": "avion",
}


def dibujar(c, motivo, cx, cy, s, u, t):
    import unicodedata
    clave = "".join(ch for ch in unicodedata.normalize("NFD", (motivo or "").lower()) if ch.isalnum())
    f = MOTIVOS.get(clave) or MOTIVOS.get(SINONIMOS.get(clave, ""), libro)
    f(c, cx, cy, s, u, t)
