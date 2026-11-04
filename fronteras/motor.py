"""Motor de video de FRONTERAS.

Convierte una especificación (guion + escenas en JSON) y los tiempos de la voz en un video
de documental con mapas en relieve. Todo se dibuja como función del tiempo.

Especificación (lo que escribe el guionista, humano o IA):
{
  "titulo": "...",
  "formato": "vertical" | "horizontal",
  "territorios": {"cesion": [[lon,lat], ...]},          # polígonos propios opcionales
  "escenas": [
    {
      "desde": "frase que dice la voz",                   # la escena empieza cuando la voz la dice
      "camara": [lon, lat, ancho_en_grados],
      "año": "1848",                                      # opcional
      "titulo": "Texto grande",                           # opcional
      "cifra": "15 millones de dólares",                  # opcional
      "zonas": [{"zona": "pais:MEX" | "estado:Texas" | "territorio:cesion",
                 "estilo": "oro" | "rojo" | "crema" | "contorno" | "foco",
                 "desde": "frase", "mantener": false}],
      "etiquetas": [{"texto": "California", "lugar": [lon, lat], "desde": "frase"}],
      "pines": [{"texto": "Ciudad de México", "lugar": [lon, lat], "desde": "frase"}],
      "flechas": [{"puntos": [[lon,lat], [lon,lat], ...], "desde": "frase"}],
      "broll": {"motivo": "muralla", "desde": "frase"}     # dibujo animado a pantalla completa
    }
  ]
}
"""
import json, math, os, subprocess, unicodedata, gzip
import numpy as np
import skia
from . import broll as _broll

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = f"{RAIZ}/assets/datos"
FUENTES = f"{RAIZ}/assets/fuentes"
FPS = 30

# ---------------- identidad FRONTERAS ----------------
NOCHE = "#07090C"
MARFIL = "#EDE6D6"
ORO = "#C9A45C"
ORO_CLARO = "#E8CC8A"
CARMIN = "#A3362B"
PIEDRA = "#8A8170"


def col(h, a=1.0):
    h = h.lstrip("#")
    return skia.Color4f(int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def suave(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def cubica(x):
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def sale(x):  # ease out expo
    x = clamp(x)
    return 1 if x == 1 else 1 - 2 ** (-10 * x)


def rampa(t, t0, d=0.6):
    return suave((t - t0) / d)


def ventana(t, t0, t1, f=0.5):
    return min(rampa(t, t0, f), 1 - rampa(t, t1 - f, f))


# ---------------- voz ----------------
def _n(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if c.isalnum())


class Voz:
    def __init__(self, palabras, duracion):
        self.palabras, self.duracion = palabras, duracion
        self._lista = [_n(w["p"]) for w in palabras]

    @classmethod
    def de_archivo(cls, ruta):
        d = json.load(open(ruta))
        return cls(d["palabras"], d["duracion"])

    def en(self, frase, desde_t=0.0):
        """Segundo en que la voz empieza a decir la frase (la primera vez después de desde_t)."""
        obj = [x for x in (_n(p) for p in frase.split()) if x]
        for i in range(len(self._lista) - len(obj) + 1):
            if self.palabras[i]["t0"] >= desde_t - 0.01 and self._lista[i:i + len(obj)] == obj:
                return self.palabras[i]["t0"]
        # tolerancia: si la frase exacta no está, buscar solo su primera palabra
        for i, w in enumerate(self._lista):
            if self.palabras[i]["t0"] >= desde_t - 0.01 and obj and w == obj[0]:
                return self.palabras[i]["t0"]
        raise ValueError(f"La voz no dice «{frase}»")


# ---------------- geografía ----------------
def _path(geo, K):
    p = skia.Path()
    polys = geo["coordinates"] if geo["type"] == "MultiPolygon" else [geo["coordinates"]]
    for poly in polys:
        for anillo in poly:
            for i, (lon, lat) in enumerate(anillo):
                (p.moveTo if i == 0 else p.lineTo)(lon * K, -lat)
            p.close()
    return p


class Geo:
    """Países y estados del mundo (Natural Earth) como trayectos listos para dibujar."""

    def __init__(self, K):
        self.K = K
        cache = f"{DATOS}/geo.json.gz"
        if os.path.exists(cache):
            self.geo = json.load(gzip.open(cache, "rt", encoding="utf-8"))
        else:
            from shapely.geometry import shape, mapping
            g = {}
            for f in json.load(open(f"{DATOS}/ne_50m_admin_0_countries.geojson"))["features"]:
                pr = f["properties"]
                g[f"pais:{pr['ADM0_A3']}"] = f["geometry"]
                g.setdefault(f"pais:{_n(pr['NAME'])}", f["geometry"])
                g.setdefault(f"pais:{_n(pr.get('NAME_ES') or '')}", f["geometry"])
            for f in json.load(open(f"{DATOS}/ne_10m_admin_1_states_provinces.geojson"))["features"]:
                pr = f["properties"]
                geom = mapping(shape(f["geometry"]).simplify(0.01, preserve_topology=True))
                for nombre in {pr.get("name"), pr.get("name_es"), pr.get("name_en")}:
                    if nombre:
                        g.setdefault(f"estado:{_n(nombre)}", geom)
                        g[f"estado:{pr['adm0_a3']}:{_n(nombre)}"] = geom
            self.geo = g
            json.dump(g, gzip.open(cache, "wt", encoding="utf-8"))
        self.paises = [(k, _path(v, K)) for k, v in self.geo.items() if k.startswith("pais:") and len(k) == 8]
        self._cache = {}

    def zona(self, clave, territorios):
        if clave in self._cache:
            return self._cache[clave]
        tipo, _, nombre = clave.partition(":")
        if tipo == "territorio":
            pts = territorios[nombre]
            if isinstance(pts, dict):
                self._cache[clave] = _path(pts, self.K)
                return self._cache[clave]
            p = skia.Path()
            for i, (lon, lat) in enumerate(pts):
                (p.moveTo if i == 0 else p.lineTo)(lon * self.K, -lat)
            p.close()
        else:
            nombre_n = nombre if (tipo == "pais" and len(nombre) == 3 and nombre.isupper()) else _n(nombre)
            geo = self.geo.get(f"{tipo}:{nombre_n}") or self.geo.get(f"{tipo}:{nombre}")
            if geo is None:
                raise ValueError(f"No encuentro la zona «{clave}»")
            p = _path(geo, self.K)
        self._cache[clave] = p
        return p


# ---------------- fuentes ----------------
_tf = {}


def fuente(nombre, tam):
    if nombre not in _tf:
        _tf[nombre] = skia.Typeface.MakeFromFile(f"{FUENTES}/{nombre}.ttf")
    f = skia.Font(_tf[nombre], tam)
    f.setEdging(skia.Font.Edging.kAntiAlias)
    f.setSubpixel(True)
    return f


SOMBRA_K = 1.0  # los looks claros bajan la sombra del texto


def escribe(c, s, x, y, f, color, alfa=1.0, espacio=0.0, centro=True, sombra=0.6):
    """Texto con espaciado entre letras y sombra suave."""
    if alfa <= 0.003 or not s:
        return
    sombra = sombra * SOMBRA_K
    anchos = f.getWidths(f.textToGlyphs(s))
    total = sum(anchos) + espacio * (len(s) - 1)
    x0 = x - total / 2 if centro else x
    blob_b = skia.TextBlobBuilder()
    pos = []
    cx = x0
    for a in anchos:
        pos.append(skia.Point(cx, y))
        cx += a + espacio
    blob_b.allocRunPos(f, f.textToGlyphs(s), pos)
    blob = blob_b.make()
    if sombra:
        ps = skia.Paint(AntiAlias=True, Color4f=col("#000000", sombra * alfa))
        ps.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, f.getSize() * 0.12))
        c.drawTextBlob(blob, 0, f.getSize() * 0.04, ps)
    c.drawTextBlob(blob, 0, 0, skia.Paint(AntiAlias=True, Color4f=col(color, alfa) if isinstance(color, str) else color))
    return total


def mide(f, s, espacio=0.0):
    return sum(f.getWidths(f.textToGlyphs(s))) + espacio * (len(s) - 1)


def parte_lineas(f, s, maximo, espacio=0.0):
    pals, lineas, act = s.split(), [], ""
    for p in pals:
        prueba = (act + " " + p).strip()
        if mide(f, prueba, espacio) <= maximo or not act:
            act = prueba
        else:
            lineas.append(act)
            act = p
    if act:
        lineas.append(act)
    return lineas


def bloque(s, nombre, tam, tam_min, ancho, max_lineas=2, espacio_rel=0.0):
    """Ajusta un texto a una caja: parte en líneas y baja el tamaño hasta que cabe completo.
    Regla de oro de FRONTERAS, ningún texto se sale de la pantalla."""
    s = " ".join(str(s).split())
    while True:
        f = fuente(nombre, tam)
        esp = tam * espacio_rel
        lineas = parte_lineas(f, s, ancho, esp)
        cabe = len(lineas) <= max_lineas and all(mide(f, l, esp) <= ancho for l in lineas)
        if cabe or tam <= tam_min:
            break
        tam = max(tam_min, tam - 4)
    if len(lineas) > max_lineas:  # último recurso, se recorta con puntos suspensivos
        lineas = lineas[:max_lineas]
        while lineas[-1] and mide(f, lineas[-1] + "…", esp) > ancho:
            lineas[-1] = lineas[-1][:-1]
        lineas[-1] = lineas[-1].rstrip() + "…"
    return f, tam, lineas


# ---------------- el motor ----------------
def aplicar_paleta(clave):
    """Cambia los colores del motor y de los dibujos según la paleta del video."""
    from . import estilos, broll, looks
    pal = estilos.PALETAS.get(clave) or looks.LOOKS.get(clave) or estilos.PALETAS["noche_oro"]
    if "NOCHE" not in pal:
        pal = estilos.PALETAS["noche_oro"]
    g = globals()
    for k in ("NOCHE", "MARFIL", "ORO", "ORO_CLARO", "CARMIN", "PIEDRA"):
        g[k] = pal[k]
    rgb = lambda h: tuple(int(h.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    broll.MARFIL, broll.ORO, broll.ORO_CLARO, broll.CARMIN = rgb(pal["MARFIL"]), rgb(pal["ORO"]), rgb(pal["ORO_CLARO"]), rgb(pal["CARMIN"])
    return pal


class Short:
    def __init__(self, spec, voz):
        self.spec, self.voz = spec, voz
        from . import estilos, looks
        global SOMBRA_K
        est = spec.get("estilo") or {}
        self.clave_look = est.get("look", "noche") if est.get("look") in looks.LOOKS else "noche"
        self.L = looks.LOOKS[self.clave_look]
        if self.clave_look == "noche":
            self.paleta = aplicar_paleta(est.get("paleta", "noche_oro"))
            self.graf = dict(estilos.GRAFICOS.get(est.get("grafico")) or estilos.GRAFICOS["clasico"])
            tr, tg, tb = self.paleta.get("tinte", (1, 1, 1))
            self._tinte = skia.Paint(ColorFilter=skia.ColorFilters.Matrix([tr, 0, 0, 0, 0, 0, tg, 0, 0, 0, 0, 0, tb, 0, 0, 0, 0, 0, 1, 0]))
            SOMBRA_K = 1.0
        else:
            self.paleta = aplicar_paleta(self.clave_look)
            self.graf = {"subtitulo": self.L["sub"], "mayusculas": self.L.get("mayus_titulo", False), "linea": 1.0,
                         "grano": self.L["grano"], "titulo": "centro", "tarjeta": "lisa"}
            self._tinte = skia.Paint(ColorFilter=looks.duotono(*self.L["mapa"]), Alphaf=self.L.get("mapa_alfa", 1.0))
            SOMBRA_K = self.L.get("sombra", 1.0)
        vertical = spec.get("formato", "vertical") == "vertical"
        self.W, self.H = (1080, 1920) if vertical else (1920, 1080)
        self.vertical = vertical
        # zona segura, lejos de los bordes y de los botones de Shorts, Reels y TikTok
        self.ANCHO_SEGURO = 860 if vertical else 1560
        self.K = math.cos(math.radians(spec.get("latitud_media", 30)))
        self.geo = Geo(self.K)
        self.base = skia.Image.open(f"{DATOS}/base_fronteras.jpg")
        self.terr = spec.get("territorios", {})
        self.duracion = voz.duracion + 3.2
        self._resolver()
        self._grano = self._hacer_grano()
        self.capas_relieve = []
        if os.environ.get("FRONTERAS_RELIEVE", "1") != "0":
            try:
                from . import relieve
                from PIL import Image as _PI
                _PI.MAX_IMAGE_PIXELS = None
                base_pil = _PI.open(f"{DATOS}/base_fronteras.jpg").convert("RGB")
                for rgba, caja in relieve.capas([e["camara"] for e in self.escenas], self.K, base_pil, self.W, self.H):
                    img = skia.Image.fromarray(rgba, colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kUnpremul_AlphaType)
                    self.capas_relieve.append((img, caja))
            except Exception as ex:
                print(f"relieve en alta no disponible: {ex}")
        from . import looks as _lk
        self.look = _lk.preparar(self, self.clave_look)

    # tiempos de cada escena y elemento, sacados de la voz
    def _resolver(self):
        t_prev = 0.0
        self.escenas = []
        cam = [-40, 20, 120]
        for i, e in enumerate(self.spec["escenas"]):
            e = dict(e)
            if not (isinstance(e.get("camara"), list) and len(e["camara"]) == 3):
                e["camara"] = list(cam)
            cam = e["camara"]
            t0 = 0.0 if i == 0 else self.voz.en(e["desde"], t_prev)
            t_prev = t0
            self.escenas.append(dict(e, _t0=t0))
        for i, e in enumerate(self.escenas):
            e["_t1"] = self.escenas[i + 1]["_t0"] if i + 1 < len(self.escenas) else self.voz.duracion + 0.6
            for grupo in ("zonas", "etiquetas", "pines", "flechas"):
                for el in e.get(grupo, []):
                    el["_t"] = self.voz.en(el["desde"], e["_t0"]) if el.get("desde") else e["_t0"] + 0.15
            b = e.get("broll")
            if isinstance(b, str):
                b = e["broll"] = {"motivo": b}
            if isinstance(b, dict) and b.get("motivo"):
                ti = self.voz.en(b["desde"], e["_t0"]) if b.get("desde") else e["_t0"]
                ti = min(ti, e["_t1"] - 1.6)
                b["_ti"] = max(e["_t0"], ti)
                b["_tf"] = b["_ti"] + clamp(e["_t1"] - b["_ti"] - 0.2, 1.4, 5.0)
            else:
                e.pop("broll", None)
        # zonas que no existen se descartan con aviso, en vez de tumbar el video
        for e in self.escenas:
            buenas = []
            for z in e.get("zonas", []):
                try:
                    self.geo.zona(z["zona"], self.terr)
                    buenas.append(z)
                except (ValueError, KeyError) as err:
                    print("Aviso:", err)
            e["zonas"] = buenas
        # una zona con "mantener" sigue visible hasta el final
        self.T_FIN = self.voz.duracion + 0.4

    # ---- cámara: corte suave entre escenas y empuje lento dentro de cada una
    def camara(self, t):
        e_act = self.escenas[0]
        for e in self.escenas:
            if t >= e["_t0"]:
                e_act = e
        i = self.escenas.index(e_act)
        lon, lat, ancho = e_act["camara"]
        dur = max(0.1, e_act["_t1"] - e_act["_t0"])
        u = clamp((t - e_act["_t0"]) / dur)
        ancho *= 1 - 0.07 * u  # empuje lento
        if i > 0:
            pl, pa, pw = self.escenas[i - 1]["camara"]
            pw *= 0.93
            # transición corta y con golpe: con tomas de 3 segundos no hay tiempo para viajes lentos
            trans = clamp(0.3 * dur, 0.45, 1.1)
            k = sale((t - e_act["_t0"]) / trans)
            lon = pl + (lon - pl) * k
            lat = pa + (lat - pa) * k
            ancho = math.exp(math.log(pw) + (math.log(ancho) - math.log(pw)) * k)
        else:  # apertura: baja desde muy lejos
            k = sale(t / 2.6)
            ancho = math.exp(math.log(ancho * 4.5) + (math.log(ancho) - math.log(ancho * 4.5)) * k)
        # golpe de zoom al entrar cada toma
        ancho *= 1 - 0.07 * math.exp(-max(0.0, t - e_act["_t0"]) * 5)
        lon += 0.12 * math.sin(t * 0.31)
        lat += 0.08 * math.cos(t * 0.27)
        return lon, lat, ancho

    def matriz(self, t):
        lon, lat, ancho = self.camara(t)
        s = self.W / (ancho * self.K)
        m = skia.Matrix()
        m.setTranslate(self.W / 2, self.H * (0.52 if self.vertical else 0.5))
        m.preScale(s, s)
        m.preTranslate(-lon * self.K, lat)
        return m, s

    def px(self, m, lon, lat):
        p = m.mapXY(lon * self.K, -lat)
        return p.x(), p.y()

    # ---- capas
    def _fondo(self, c, m):
        if self.clave_look == "noche":
            c.clear(col(NOCHE))
        c.save()
        c.concat(m)
        c.translate(-180 * self.K, -90)
        c.scale(self.K * 360 / self.base.width(), 180 / self.base.height())
        c.drawImage(self.base, 0, 0, skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear), self._tinte)
        c.restore()
        # relieve en alta resolución de la zona del video, encima del mapa base
        for img, (lon0, lat0, lon1, lat1) in self.capas_relieve:
            c.save()
            c.concat(m)
            c.drawImageRect(img, skia.Rect(lon0 * self.K, -lat1, lon1 * self.K, -lat0),
                            skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear), self._tinte)
            c.restore()
        # fronteras de países, finas y discretas
        c.save()
        c.concat(m)
        s = m.getScaleX()
        p = skia.Paint(AntiAlias=True, Color4f=col(MARFIL, 0.16), Style=skia.Paint.kStroke_Style, StrokeWidth=1.6 * self.graf["linea"] / s)
        for _, path in self.geo.paises:
            c.drawPath(path, p)
        c.restore()

    def _zona(self, c, m, path, estilo, a):
        if a <= 0.003:
            return
        s = m.getScaleX()
        c.save()
        if estilo == "foco":
            c.restore()
            inv = skia.Path(path)
            inv.transform(m)
            inv.setFillType(skia.PathFillType.kInverseWinding)
            c.drawPath(inv, skia.Paint(AntiAlias=True, Color4f=col("#000000", 0.55 * a)))
            return
        c.concat(m)
        tonos = {"oro": (ORO, 0.30), "rojo": (CARMIN, 0.42), "crema": (MARFIL, 0.20), "contorno": (ORO, 0.0)}
        tono, relleno = tonos.get(estilo, (ORO, 0.3))
        if relleno:
            c.drawPath(path, skia.Paint(AntiAlias=True, Color4f=col(tono, relleno * a)))
        brillo = skia.Paint(AntiAlias=True, Color4f=col(tono, 0.55 * a), Style=skia.Paint.kStroke_Style, StrokeWidth=14 / s,
                            StrokeJoin=skia.Paint.kRound_Join)
        brillo.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 10 / s))
        c.drawPath(path, brillo)
        borde = ORO_CLARO if tono == ORO else (MARFIL if tono == MARFIL else "#D9644F")
        c.drawPath(path, skia.Paint(AntiAlias=True, Color4f=col(borde, 0.95 * a), Style=skia.Paint.kStroke_Style,
                                    StrokeWidth=3.2 / s, StrokeJoin=skia.Paint.kRound_Join))
        c.restore()

    def _etiqueta(self, c, x, y, texto, a, tam=None):
        if a <= 0.003:
            return
        tam = tam or (34 if self.vertical else 30)
        s = texto.upper()
        f, tam, lin = bloque(s, "HelveticaNowDisplay-Bold", tam, 22, self.ANCHO_SEGURO - 80, 1, 0.16)
        s = lin[0]
        esp = tam * 0.16
        w = mide(f, s, esp)
        y = clamp(y, 160, self.H - 420 if self.vertical else self.H - 200)
        dy = (1 - sale(a)) * 14
        margen = (self.W - self.ANCHO_SEGURO) / 2
        x_txt = clamp(x, margen + w / 2, self.W - margen - w / 2)
        # pequeño rombo dorado y texto marfil con espaciado amplio
        c.save()
        c.translate(x, y + dy)
        rombo = skia.Path()
        r = tam * 0.17
        rombo.moveTo(0, -r); rombo.lineTo(r, 0); rombo.lineTo(0, r); rombo.lineTo(-r, 0); rombo.close()
        c.drawPath(rombo, skia.Paint(AntiAlias=True, Color4f=col(ORO, a)))
        escribe(c, s, x_txt - x, -tam * 0.75, f, MARFIL, alfa=a, espacio=esp, sombra=0.9)
        c.restore()

    def _pin(self, c, x, y, texto, a, t, t0):
        if a <= 0.003:
            return
        pulso = ((t - t0) % 2.0) / 2.0
        c.drawCircle(x, y, 10 + 46 * pulso, skia.Paint(AntiAlias=True, Color4f=col(ORO, 0.5 * (1 - pulso) * a),
                                                          Style=skia.Paint.kStroke_Style, StrokeWidth=2.5))
        c.drawCircle(x, y, 9, skia.Paint(AntiAlias=True, Color4f=col(ORO_CLARO, a)))
        c.drawCircle(x, y, 15, skia.Paint(AntiAlias=True, Color4f=col(ORO, 0.9 * a), Style=skia.Paint.kStroke_Style, StrokeWidth=2))
        self._etiqueta(c, x, y - 34, texto, a)

    def _flecha(self, c, pts, avance, a):
        if avance <= 0 or a <= 0:
            return
        p = skia.Path()
        p.moveTo(*pts[0])
        if len(pts) == 2:
            (x0, y0), (x1, y1) = pts
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            nx, ny = -(y1 - y0) * 0.18, (x1 - x0) * 0.18
            p.quadTo(mx + nx, my + ny, x1, y1)
        else:
            for i in range(1, len(pts) - 1):
                mx, my = (pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2
                p.quadTo(*pts[i], mx, my)
            p.lineTo(*pts[-1])
        med = skia.PathMeasure(p, False)
        L = med.getLength()
        seg = skia.Path()
        med.getSegment(0, L * avance, seg, True)
        g = skia.Paint(AntiAlias=True, Color4f=col(ORO, 0.45 * a), Style=skia.Paint.kStroke_Style, StrokeWidth=22,
                       StrokeCap=skia.Paint.kRound_Cap)
        g.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 9))
        c.drawPath(seg, g)
        c.drawPath(seg, skia.Paint(AntiAlias=True, Color4f=col(ORO_CLARO, a), Style=skia.Paint.kStroke_Style, StrokeWidth=7,
                                   StrokeCap=skia.Paint.kRound_Cap))
        pos, tan = med.getPosTan(L * avance)
        ang = math.atan2(tan.y(), tan.x())
        cab = skia.Path()
        R = 30
        cab.moveTo(pos.x() + math.cos(ang) * R * 0.7, pos.y() + math.sin(ang) * R * 0.7)
        cab.lineTo(pos.x() + math.cos(ang + 2.55) * R, pos.y() + math.sin(ang + 2.55) * R)
        cab.lineTo(pos.x() + math.cos(ang - 2.55) * R, pos.y() + math.sin(ang - 2.55) * R)
        cab.close()
        c.drawPath(cab, skia.Paint(AntiAlias=True, Color4f=col(ORO_CLARO, a)))

    def _titulos(self, c, t, e):
        a = ventana(t, e["_t0"] + 0.1, e["_t1"] + 0.05, 0.45)
        if a <= 0.003:
            return
        W = self.W
        L = self.L
        y_base = (L.get("y_titulo", 300) if self.vertical else 150)
        sube = (1 - sale((t - e["_t0"] - 0.1) / 0.9)) * 26
        if e.get("año"):
            f_ano = L.get("f_ano", "HelveticaNowDisplay-Bold")
            f = fuente(f_ano, 34 if self.vertical else 28)
            s = str(e["año"])
            # el año corre como contador desde el año de la escena anterior
            i = self.escenas.index(e)
            prev = next((str(x.get("año")) for x in reversed(self.escenas[:i]) if x.get("año")), None)
            if prev and s.isdigit() and prev[:4].isdigit() and len(s) == 4:
                k = cubica((t - e["_t0"]) / 0.9)
                if k < 1:
                    s = str(round(int(prev[:4]) + (int(s) - int(prev[:4])) * k))
            esp = 12
            while mide(f, s, esp) > self.ANCHO_SEGURO - 220 and f.getSize() > 20:
                f = fuente(f_ano, f.getSize() - 2)
                esp = max(4, esp - 1)
            w = mide(f, s, esp)
            y = y_base - (128 if L.get("f_titulo") else 92) + sube
            escribe(c, s, W / 2, y, f, ORO, alfa=a, espacio=esp)
            lp = skia.Paint(AntiAlias=True, Color4f=col(ORO, 0.7 * a), StrokeWidth=2)
            largo = 70 * sale((t - e["_t0"]) / 0.8)
            c.drawLine(W / 2 - w / 2 - 24 - largo, y - 11, W / 2 - w / 2 - 24, y - 11, lp)
            c.drawLine(W / 2 + w / 2 + 24, y - 11, W / 2 + w / 2 + 24 + largo, y - 11, lp)
        if e.get("titulo"):
            texto_t = e["titulo"].upper() if L.get("mayus_titulo") else e["titulo"]
            max_l = 2 if (L.get("y_titulo") or not self.vertical) else 3
            f, tam, lineas = bloque(texto_t, L.get("f_titulo", "HelveticaNowDisplay-Bold"), 104 if L.get("f_titulo") else (96 if self.vertical else 84), 44,
                                    self.ANCHO_SEGURO - (60 if L.get("titulo_stickers") else 0), max_l)
            if L.get("titulo_stickers"):  # cada línea es un recorte pegado, como en una mesa de trabajo
                fondos = [L["CARMIN"], L["ORO"], "#FFFFFF", "#6B4226"]
                for k, ln in enumerate(lineas):
                    w_ = mide(f, ln)
                    yk = y_base + sube + k * tam * 1.18
                    c.save()
                    c.rotate((-2.5 if k % 2 == 0 else 2.0), W / 2, yk - tam * 0.35)
                    c.drawRect(skia.Rect.MakeXYWH(W / 2 - w_ / 2 - 26, yk - tam * 0.86, w_ + 52, tam * 1.12),
                               skia.Paint(AntiAlias=True, Color4f=col(fondos[(k + self.escenas.index(e)) % 4], a)))
                    tinta = "#3A2412" if fondos[(k + self.escenas.index(e)) % 4] in (L["ORO"], "#FFFFFF") else "#FFFFFF"
                    escribe(c, ln, W / 2, yk, f, tinta, alfa=a, sombra=0)
                    c.restore()
                lineas = []
            if L.get("brillo_titulo") and lineas:  # halo borroso tipo risografía
                for k, ln in enumerate(lineas):
                    g = skia.Paint(AntiAlias=True, Color4f=col(ORO_CLARO, 0.55 * a))
                    g.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, tam * 0.18))
                    w_ = mide(f, ln)
                    c.drawString(ln, W / 2 - w_ / 2, y_base + sube + k * tam * 1.02, f, g)
            izq = self.graf["titulo"] == "izquierda"
            x_t = (W - self.ANCHO_SEGURO) / 2 if izq else W / 2
            if izq:  # barrita de acento a la izquierda del título
                c.drawRect(skia.Rect.MakeXYWH(x_t, y_base + sube - tam * 0.8, 8, tam * 0.9 * len(lineas)),
                           skia.Paint(Color4f=col(ORO, a)))
                x_t += 30
            for k, ln in enumerate(lineas):
                escribe(c, ln, x_t, y_base + sube + k * tam * 1.02, f, MARFIL, alfa=a, sombra=0.85, centro=not izq)
        if e.get("cifra"):
            ac = ventana(t, e["_t0"] + 0.5, e["_t1"] + 0.05, 0.45)
            grande = 190 if L.get("cifra_gigante") else (96 if L.get("f_cifra") else (82 if self.vertical else 70))
            f, tam, lineas = bloque(e["cifra"], L.get("f_cifra", "HelveticaNowDisplay-Regular"), grande, 40,
                                    self.ANCHO_SEGURO, L.get("lineas_cifra", 2))
            hay_broll = e.get("broll") and e["broll"]["_ti"] - 0.3 <= t < e["broll"]["_tf"] + 0.3
            y = (1345 if hay_broll else L.get("y_cifra", 1250)) if self.vertical else (880 if hay_broll else 840)
            if not hay_broll:  # con dibujo en pantalla la cifra crece hacia abajo para no taparlo
                y -= (len(lineas) - 1) * tam * 0.55
            y += (1 - sale((t - e["_t0"] - 0.5) / 0.9)) * 20
            for k, ln in enumerate(lineas):
                escribe(c, ln, W / 2, y + k * tam * 1.05, f, ORO_CLARO, alfa=ac, sombra=0.9)

    def _subtitulos(self, c, t):
        pal = self.voz.palabras
        grupos, act = [], []
        for w in pal:
            act.append(w)
            if len(act) >= 4 or len(" ".join(x["p"] for x in act)) > 20 or w["p"][-1] in ",.:?!;":
                grupos.append(act)
                act = []
        if act:
            grupos.append(act)
        for i, g in enumerate(grupos):
            fin = grupos[i + 1][0]["t0"] if i + 1 < len(grupos) else g[-1]["t1"] + 0.6
            if g[0]["t0"] - 0.05 <= t < fin:
                tam = 52 if self.vertical else 44
                ps = [w["p"].strip("¿?¡!,.:;…").replace("...", "") for w in g]
                if self.graf["mayusculas"]:
                    ps = [p.upper() for p in ps]
                while True:  # se encoge hasta que la frase cabe completa en la zona segura
                    f = fuente(self.L.get("f_sub", "HelveticaNowDisplay-Bold"), tam)
                    esp = tam * 0.28
                    anchos = [mide(f, p) for p in ps]
                    total = sum(anchos) + esp * (len(ps) - 1)
                    if total <= self.ANCHO_SEGURO or tam <= 30:
                        break
                    tam -= 2
                x = self.W / 2 - total / 2
                y = 1505 if self.vertical else 975
                a = rampa(t, g[0]["t0"] - 0.05, 0.12)
                for w, p, an in zip(g, ps, anchos):
                    dicha = t >= w["t0"] - 0.03
                    ahora = w["t0"] - 0.03 <= t < w["t1"] + 0.1
                    modo = self.graf["subtitulo"]
                    if ahora and modo == "caja":
                        c.drawRoundRect(skia.Rect.MakeXYWH(x - tam * 0.18, y - tam * 0.86, an + tam * 0.36, tam * 1.1), 10, 10,
                                        skia.Paint(AntiAlias=True, Color4f=col(ORO, a)))
                        escribe(c, p, x, y, f, NOCHE, alfa=a, centro=False, sombra=0)
                    else:
                        color = ORO_CLARO if (ahora and modo == "color") else MARFIL
                        escribe(c, p, x, y, f, color, alfa=a * (1 if dicha else 0.5), centro=False, sombra=0.95)
                        if ahora and modo == "linea":
                            c.drawRect(skia.Rect.MakeXYWH(x, y + tam * 0.14, an, tam * 0.09), skia.Paint(Color4f=col(ORO, a)))
                    x += an + esp
                return

    # ---- destello breve en cada corte, para que el cambio de toma se sienta
    def _destello(self, c, t):
        for e in self.escenas[1:]:
            d = t - e["_t0"]
            if 0 <= d < 0.18:
                fuerte = 0.22 if (e.get("año") or e.get("broll")) else 0.12
                c.drawRect(skia.Rect(0, 0, self.W, self.H),
                           skia.Paint(Color4f=col(ORO_CLARO, fuerte * (1 - d / 0.18)), BlendMode=skia.BlendMode.kScreen))
                return

    # ---- momentos que llevan efecto de sonido
    def eventos(self):
        ev = []
        for i, e in enumerate(self.escenas):
            if i > 0:
                ev.append((e["_t0"], "whoosh"))
            if e.get("año") and i > 0:
                ev.append((e["_t0"] + 0.05, "golpe"))
                for k in range(6):
                    ev.append((e["_t0"] + k * 0.13, "tic"))
            if e.get("broll"):
                ev.append((e["broll"]["_ti"] + 0.05, "golpe"))
        ev.append((self.T_FIN, "golpe"))
        return sorted(ev)

    # ---- B-roll: dibujo de línea animado a pantalla completa
    def _broll(self, c, t):
        for e in self.escenas:
            b = e.get("broll")
            if not b or not (b["_ti"] - 0.05 <= t < b["_tf"] + 0.45):
                continue
            W, H = self.W, self.H
            dur = b["_tf"] - b["_ti"]
            entra = sale((t - b["_ti"]) / 0.55)
            sal = 1 - clamp((t - b["_tf"]) / 0.45)
            cx, cy = W / 2, H * (0.47 if self.vertical else 0.53)
            c.save()
            # entra como un círculo que se abre desde el centro
            r = math.hypot(W, H) * 0.6 * entra
            clip = skia.Path()
            clip.addCircle(cx, cy, max(1, r))
            c.clipPath(clip, doAntiAlias=True)
            c.drawRect(skia.Rect(0, 0, W, H), skia.Paint(Color4f=col(NOCHE, 0.94 * sal)))
            c.saveLayerAlpha(None, int(255 * sal))
            # papel cuadriculado tenue y un aro dorado que gira
            gp = skia.Paint(AntiAlias=True, Color4f=col(MARFIL, 0.05), StrokeWidth=1)
            paso = 60
            off = (t * 12) % paso
            if self.graf["tarjeta"] == "cuadricula":
                for x in range(-paso, W + paso, paso):
                    c.drawLine(x + off, 0, x + off, H, gp)
                for y in range(-paso, H + paso, paso):
                    c.drawLine(0, y + off, W, y + off, gp)
            elif self.graf["tarjeta"] == "puntos":
                gp.setColor4f(col(MARFIL, 0.10))
                for x in range(-paso, W + paso, paso // 2 * 2):
                    for y in range(-paso, H + paso, paso):
                        c.drawCircle(x + off, y + off, 1.6, gp)
            ap = skia.Paint(AntiAlias=True, Color4f=col(ORO, 0.25), Style=skia.Paint.kStroke_Style, StrokeWidth=2)
            ap.setPathEffect(skia.DashPathEffect.Make([4, 14], t * 20))
            c.drawCircle(cx, cy, 500 if self.vertical else 400, ap)
            s = (1.4 if self.vertical else 1.0) * (1 + 0.04 * clamp((t - b["_ti"]) / dur))
            u = clamp((t - b["_ti"]) / max(1.2, dur * 0.85))
            try:
                _broll.dibujar(c, b["motivo"], cx, cy, s, u, t)
            except Exception as err:
                print("Aviso broll:", err)
            c.restore()
            c.restore()

    def _hacer_grano(self):
        rng = np.random.default_rng(7)
        imgs = []
        for _ in range(4):
            n = (rng.normal(0.5, 0.18, (self.H // 2, self.W // 2)) * 255).clip(0, 255).astype(np.uint8)
            rgba = np.dstack([n, n, n, np.full_like(n, 255)])
            imgs.append(skia.Image.fromarray(rgba, colorType=skia.kRGBA_8888_ColorType))
        return imgs

    def _acabado(self, c, t):
        W, H = self.W, self.H
        if self.clave_look != "noche":
            from . import looks as _lk
            gp = skia.Paint(Alphaf=self.graf["grano"], BlendMode=skia.BlendMode.kOverlay)
            c.drawImageRect(self._grano[int(t * FPS) % 4], skia.Rect(0, 0, W, H), skia.SamplingOptions(), gp)
            _lk.acabado(self, c, t)
            return
        vin = skia.Paint(Shader=skia.GradientShader.MakeRadial((W / 2, H / 2), max(W, H) * 0.72,
                         [col("#000000", 0).toColor(), col("#000000", 0.7).toColor()], [0.45, 1.0]))
        c.drawRect(skia.Rect(0, 0, W, H), vin)
        # degradado arriba y abajo para que respiren los textos
        for y0, y1, a0, a1 in ((0, H * 0.28, 0.75, 0), (H * 0.70, H, 0, 0.8)):
            g = skia.Paint(Shader=skia.GradientShader.MakeLinear([(0, y0), (0, y1)], [col("#000000", a0).toColor(), col("#000000", a1).toColor()]))
            c.drawRect(skia.Rect(0, y0, W, y1), g)
        gp = skia.Paint(Alphaf=self.graf["grano"], BlendMode=skia.BlendMode.kOverlay)
        c.drawImageRect(self._grano[int(t * FPS) % 4], skia.Rect(0, 0, W, H), skia.SamplingOptions(), gp)

    def _marca(self, c, t):
        f = fuente("HelveticaNowDisplay-Bold", 30 if self.vertical else 26)
        y = self.H - 70 if self.vertical else self.H - 44
        a = 0.6 * (1 - rampa(t, self.T_FIN, 0.4))
        escribe(c, "FRONTERAS", self.W / 2, y, f, MARFIL, alfa=a, espacio=9, sombra=0.5)

    def _cierre(self, c, t):
        a = rampa(t, self.T_FIN, 0.9)
        if a <= 0:
            return
        W, H = self.W, self.H
        c.drawRect(skia.Rect(0, 0, W, H), skia.Paint(Color4f=col(NOCHE, 0.9 * a)))
        cy = H / 2
        f = fuente("HelveticaNowDisplay-Bold", 132 if self.vertical else 120)
        escribe(c, "FRONTERAS", W / 2, cy, f, MARFIL, alfa=a, espacio=22 * (0.6 + 0.4 * sale((t - self.T_FIN) / 1.6)))
        lp = skia.Paint(AntiAlias=True, Color4f=col(ORO, a), StrokeWidth=2)
        L = 180 * sale((t - self.T_FIN - 0.3) / 1.0)
        c.drawLine(W / 2 - L, cy + 52, W / 2 + L, cy + 52, lp)
        f2 = fuente("HelveticaNowDisplay-Regular", 46 if self.vertical else 40)
        escribe(c, "La historia que dibujó el mapa", W / 2, cy + 128, f2, ORO_CLARO, alfa=rampa(t, self.T_FIN + 0.5, 0.8))

    # ---- un fotograma
    def dibujar(self, c, t):
        m, s = self.matriz(t)
        from . import looks as _lk
        if self.clave_look != "noche":
            c.clear(col(NOCHE))
            _lk.fondo_extra(self, c, t)
        c.save()
        if self.look.get("clip") is not None:
            c.clipPath(self.look["clip"], doAntiAlias=True)
        self._fondo(c, m)
        # zonas (las de escenas pasadas con "mantener" siguen)
        for e in self.escenas:
            for z in e.get("zonas", []):
                fin = self.T_FIN + 2 if z.get("mantener") else e["_t1"] + 0.3
                a = ventana(t, z["_t"], fin, 0.6)
                if a > 0:
                    self._zona(c, m, self.geo.zona(z["zona"], self.terr), z.get("estilo", "oro"), a)
        for e in self.escenas:
            for f_ in e.get("flechas", []):
                a = ventana(t, f_["_t"], e["_t1"] + 0.3, 0.4)
                if a > 0:
                    self._flecha(c, [self.px(m, *p) for p in f_["puntos"]], cubica((t - f_["_t"]) / 1.4), a)
        c.restore()
        _lk.marco(self, c, t)
        for e in self.escenas:
            for p_ in e.get("pines", []):
                a = ventana(t, p_["_t"], e["_t1"] + 0.3, 0.4)
                if a > 0:
                    self._pin(c, *self.px(m, *p_["lugar"]), p_["texto"], a, t, p_["_t"])
            for l_ in e.get("etiquetas", []):
                a = ventana(t, l_["_t"], e["_t1"] + 0.3, 0.4)
                if a > 0:
                    self._etiqueta(c, *self.px(m, *l_["lugar"]), l_["texto"], a)
        self._broll(c, t)
        self._destello(c, t)
        self._acabado(c, t)
        for e in self.escenas:
            if e["_t0"] - 0.1 <= t < e["_t1"] + 0.6:
                self._titulos(c, t, e)
        if t < self.T_FIN:
            self._subtitulos(c, t)
        self._marca(c, t)
        self._cierre(c, t)

    # ---- salida
    def foto(self, t, ruta):
        sup = skia.Surface(self.W, self.H)
        with sup as c:
            self.dibujar(c, t)
        sup.makeImageSnapshot().save(ruta, skia.kJPEG)

    def render(self, salida, voz_mp3=None, musica_wav=None, progreso=None, sfx_wav=None):
        tmp = salida[:-4] + ".tmp.mp4"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{self.W}x{self.H}",
               "-r", str(FPS), "-i", "-"]
        mezcla = []
        if voz_mp3:
            cmd += ["-i", voz_mp3]
        if musica_wav:
            cmd += ["-i", musica_wav]
        if voz_mp3 and musica_wav and sfx_wav:
            cmd += ["-i", sfx_wav, "-filter_complex", "[1:a]volume=1.0,asplit=2[vz1][vz2];[2:a]volume=0.22[mu];[mu][vz1]sidechaincompress=threshold=0.05:ratio=4:attack=20:release=400[mud];[3:a]volume=0.32[fx];[vz2][mud][fx]amix=inputs=3:duration=longest:normalize=0,alimiter=limit=0.95[aud]",
                    "-map", "0:v", "-map", "[aud]"]
        elif voz_mp3 and musica_wav:
            cmd += ["-filter_complex", "[1:a]volume=1.0,asplit=2[vz1][vz2];[2:a]volume=0.22[mu];[mu][vz1]sidechaincompress=threshold=0.05:ratio=4:attack=20:release=400[mud];[vz2][mud]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95[aud]",
                    "-map", "0:v", "-map", "[aud]"]
        elif voz_mp3 or musica_wav:
            cmd += ["-map", "0:v", "-map", "1:a"]
        if voz_mp3 or musica_wav:
            cmd += ["-c:a", "aac", "-b:a", "192k"]
        cmd += ["-t", f"{self.duracion:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", tmp]
        pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        sup = skia.Surface(self.W, self.H)
        total = int(self.duracion * FPS)
        for n in range(total):
            if progreso and n % 150 == 0:
                progreso(n / total)
            with sup as c:
                self.dibujar(c, n / FPS)
            pr.stdin.write(sup.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType).tobytes())
        pr.stdin.close()
        if pr.wait() != 0:
            raise RuntimeError("ffmpeg falló al renderizar")
        os.replace(tmp, salida)
        return salida
