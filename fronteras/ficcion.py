"""Cortometrajes animados de amor y de terror.

Toma lo que escribe el guionista (personajes, líneas de diálogo, sets y escenas) y lo convierte en un corto vertical:
personajes 3D de líneas facetadas con una luz en el pecho, cuartos y patios de noche, letreros de lugar y hora,
pantallas de celular (llamadas, chats, notas de voz), subtítulos al estilo de cada género y una tarjeta final
(encuesta en terror, reflexión en amor).

Spec de un corto
{
  "genero": "terror" | "amor",
  "titulo": "...", "lugar": "ECATEPEC", "hora_inicio": "1:57 a.m.",
  "personajes": [{"id": "ivan", "nombre": "Iván", "voz": "hombre_joven", "color_texto": "#F5A8C8"}],
  "lineas": [{"quien": "narrador" | "ivan", "texto": "..."}],
  "resaltar": ["trompo", "regla"],
  "sets": {"puesto": {"ambiente": "terror", "objetos": [...]}},
  "escenas": [{"desde": "palabras exactas", "set": "puesto", "toma": [{"t": 0, "pos": [...], "mira": [...]}],
               "extra": [...], "ocultar": ["id"], "animar": [...], "hora": "2:00 a.m.",
               "pantalla": {"tipo": "llamada", "nombre": "Tío Beto", "contador": true},
               "alerta": "NO ABRA A NADIE", "golpe": true}],
  "cierre": {"tipo": "encuesta", "pregunta": "¿Tú qué harías?", "opciones": ["Abrir", "Dejarla cerrada"]}
           | {"tipo": "reflexion", "texto": "..."}
}
"""
import copy, os, re

import skia

from . import marca
from .motor import Short, col, clamp, sale, rampa, fuente, escribe, mide, parte_lineas, FPS, FPS_3D

ROJO = "#C8323A"  # carmesí STORY
BLANCO = "#F4F1EA"
COLORES_DIALOGO = ["#F5A8C8", "#B8A9FF", "#9FE0C8", "#FFD08A"]
FORMAS_REALES = ("personaje", "cuarto", "serie_luces", "foco", "bokeh")


def _otro_angulo(camara):
    """La misma escena vista desde el otro lado y más cerca: para partir tomas largas sin que se sientan iguales."""
    try:
        a, b = camara[0], camara[-1]
        mira = b.get("mira", [0, 1, 0])
        def girar(p, k):
            dx, dz = p[0] - mira[0], p[2] - mira[2]
            return [round(mira[0] - dx * 0.75, 2), p[1], round(mira[2] + dz * 0.75 * k, 2)]
        return [{"t": 0, "pos": girar(b["pos"], 1), "mira": mira}, {"t": 1, "pos": girar(a["pos"], 0.9), "mira": a.get("mira", mira)}]
    except Exception:
        return camara


class Corto(Short):
    def __init__(self, spec, voz):
        self.spec, self.voz = spec, voz
        self.genero = spec.get("genero", "terror")
        self.W, self.H, self.vertical = 1080, 1920, True
        self.ANCHO_SEGURO = 860
        self.K, self.terr = 1.0, {}
        self.geo = None
        self.clave_look, self.L = "noche", {}
        self.graf = {"subtitulo": "", "mayusculas": False, "grano": 0.0}
        self.creditos = []
        self.cierre = spec.get("cierre") or {}
        # tarjeta final de STORY (y antes la reflexión escrita en amor)
        self.duracion = voz.duracion + (10.5 if self.cierre.get("tipo") == "reflexion" else 6.0)
        self._expandir_sets()
        self._resolver()
        self.T_FIN = voz.duracion + 0.4
        self._grano = self._hacer_grano()
        # colores de texto por personaje: el narrador en blanco, cada voz con el suyo
        self.color_de = {"narrador": BLANCO}
        for i, p in enumerate(spec.get("personajes") or []):
            self.color_de[p["id"]] = p.get("color_texto") or COLORES_DIALOGO[i % len(COLORES_DIALOGO)]
        self.resaltar = {self._norm(w) for w in spec.get("resaltar") or []}
        self._grupos = self._agrupar()
        self._marcar_habla()

    @staticmethod
    def _norm(w):
        import unicodedata
        s = unicodedata.normalize("NFD", str(w).lower())
        return "".join(ch for ch in s if ch.isalnum())

    # ---- los sets se escriben una vez y cada escena solo dice dónde está la cámara
    def _expandir_sets(self):
        sets = self.spec.get("sets") or {}
        escenas = []
        for e in self.spec.get("escenas") or []:
            e = dict(e)
            base = sets.get(e.get("set")) if e.get("set") else None
            if base or e.get("objetos"):
                m = copy.deepcopy(base) if base else {}
                objs = list(m.get("objetos") or []) + list(e.get("objetos") or []) + list(e.get("extra") or [])
                ocultar = set(e.get("ocultar") or [])
                m["objetos"] = [o for o in objs if o.get("id") not in ocultar]
                m.setdefault("ambiente", "terror" if self.genero == "terror" else "noche")
                m["camara"] = e.pop("toma", None) or e.get("camara_3d") or m.get("camara") or \
                    [{"t": 0, "pos": [0, 1.5, 4], "mira": [0, 1, 0]}, {"t": 1, "pos": [0.3, 1.4, 3.3], "mira": [0, 1, 0]}]
                for k in ("animar", "etiquetas", "flechas", "lente", "desenfoque", "exposicion"):
                    if k in e:
                        m[k] = e[k]
                e["modelo"], e["tipo"] = m, "3d"
            elif e.get("pantalla"):
                e["tipo"] = "pantalla"
            e.pop("camara", None)
            escenas.append(e)
        if escenas and escenas[0].get("desde"):
            escenas[0] = dict(escenas[0])
            escenas[0].pop("desde")
        self.spec = dict(self.spec, escenas=escenas)

    def _inicios_de_linea(self):
        """Segundo en que empieza y termina cada línea del guion, contando sus palabras sobre la voz grabada."""
        pal = self.voz.palabras
        lineas = self.spec.get("lineas") or []
        inicios, k = [], 0
        for ln in lineas:
            n = len([w for w in str(ln.get("texto", "")).split() if "[" not in w and "]" not in w])
            if k >= len(pal):
                break
            fin = min(len(pal), k + max(1, n))
            inicios.append((pal[k]["t0"], pal[fin - 1]["t1"]))
            k = fin
        return inicios

    def _resolver(self):
        """Tiempos de cada escena: por número de línea, si no por sus palabras exactas, y si nada coincide
        se reparten parejo entre sus vecinas. Ninguna escena se pierde (antes una frase mal copiada dejaba
        toda la historia en una sola toma congelada)."""
        escenas = [dict(e, camara=[0, 0, 100]) for e in self.spec["escenas"]]
        inicios = self._inicios_de_linea()
        tiempos, t_prev = [], 0.0
        for i, e in enumerate(escenas):
            t = None
            if i == 0:
                t = 0.0
            elif isinstance(e.get("linea"), (int, float)) and inicios and 1 <= int(e["linea"]) <= len(inicios):
                t = max(0.0, inicios[int(e["linea"]) - 1][0] - 0.2)
            if t is None and e.get("desde"):
                try:
                    t = self.voz.corte(e["desde"], t_prev)
                except (ValueError, KeyError):
                    t = None
            if t is not None and tiempos and any(x is not None and t <= x for x in tiempos):
                t = None  # fuera de orden: se acomoda abajo
            tiempos.append(t)
            if t is not None:
                t_prev = t
        # escenas que comparten tiempo o no lo tienen: se reparten parejo entre las conocidas
        fin_total = self.voz.duracion
        i = 0
        while i < len(tiempos):
            if tiempos[i] is None:
                j = i
                while j < len(tiempos) and tiempos[j] is None:
                    j += 1
                a = tiempos[i - 1] if i > 0 else 0.0
                b = tiempos[j] if j < len(tiempos) else fin_total
                paso = (b - a) / (j - i + 1)
                for k in range(i, j):
                    tiempos[k] = round(a + paso * (k - i + 1), 3)
                i = j
            i += 1
        for e, t in zip(escenas, tiempos):
            e["_t0"] = t
        from .motor import _sin_relampagos
        self.escenas = _sin_relampagos(escenas, minimo=1.4) or [{"tipo": "pantalla", "_t0": 0.0, "camara": [0, 0, 100]}]
        for i, e in enumerate(self.escenas):
            e["_t1"] = self.escenas[i + 1]["_t0"] if i + 1 < len(self.escenas) else self.voz.duracion + 0.6
        # una toma nunca dura demasiado: si pasa de 6 s se parte en dos con otro ángulo
        partidas = []
        for e in self.escenas:
            dur = e["_t1"] - e["_t0"]
            if dur > 6.5 and isinstance(e.get("modelo"), dict):
                mitad = e["_t0"] + dur / 2
                a = dict(e, _t1=mitad)
                b = copy.deepcopy(e)
                b["_t0"] = mitad
                b["modelo"]["camara"] = _otro_angulo(b["modelo"].get("camara"))
                partidas += [a, b]
            else:
                partidas.append(e)
        self.escenas = partidas

    def _resolver_broll(self):
        pass

    # ---- el pecho de cada personaje late mientras habla
    def _marcar_habla(self):
        for e in self.escenas:
            m = e.get("modelo")
            if not isinstance(m, dict):
                continue
            ids = {o.get("id") for o in m.get("objetos") or [] if o.get("forma") == "personaje"}
            dur = e["_t1"] - e["_t0"] + 0.15
            habla = {}
            for w in self.voz.palabras:
                q = w.get("quien")
                if q in ids and e["_t0"] <= w["t0"] < e["_t1"]:
                    habla.setdefault(q, []).append([round((w["t0"] - e["_t0"]) / dur, 4), round((w["t1"] - e["_t0"]) / dur, 4)])
            m["habla"] = habla
            m["_dur"] = round(dur, 3)

    def _sin_figuras(self, hay_catalogo):
        """En los cortos los personajes, cuartos y luces son parte del dibujo: solo se quitan objetos del catálogo
        que no se encontraron."""
        for e in self.escenas:
            m = e.get("modelo")
            if isinstance(m, dict):
                m["objetos"] = [o for o in m.get("objetos") or [] if not o.get("_sin_modelo")]

    # ---- subtítulos: frases cortas por quien habla
    def _agrupar(self):
        maximo = 3 if self.genero == "terror" else 6
        largo = 18 if self.genero == "terror" else 30
        grupos, act = [], []
        for w in self.voz.palabras:
            if act and (act[-1].get("quien") != w.get("quien") or len(act) >= maximo or
                        len(" ".join(x["p"] for x in act + [w])) > largo):
                grupos.append(act)
                act = []
            act.append(w)
            if w["p"][-1] in ",.:?!;…":
                grupos.append(act)
                act = []
        if act:
            grupos.append(act)
        return grupos

    def _es_clave(self, w, ultimo):
        n = self._norm(w["p"])
        if n in self.resaltar:
            return True
        return ultimo and w["p"][-1] in ".!?…" and len(n) > 4

    def _subtitulos(self, c, t):
        for i, g in enumerate(self._grupos):
            fin = self._grupos[i + 1][0]["t0"] if i + 1 < len(self._grupos) else g[-1]["t1"] + 0.6
            if not (g[0]["t0"] - 0.05 <= t < fin):
                continue
            quien = g[0].get("quien", "narrador")
            color = self.color_de.get(quien, BLANCO) if self.genero == "terror" else "#FFFFFF"
            a = rampa(t, g[0]["t0"] - 0.05, 0.08)
            if self.genero == "terror":
                ps = [w["p"].upper() for w in g]
                tam, nombre, y = 82, "Anton-Regular", self.H * 0.735
            else:
                ps = [w["p"] for w in g]
                tam, nombre, y = 62, "DMSerifDisplay-Regular", self.H * 0.70
            while True:
                f = fuente(nombre, tam)
                esp = tam * 0.26
                anchos = [mide(f, p) for p in ps]
                total = sum(anchos) + esp * (len(ps) - 1)
                if total <= self.ANCHO_SEGURO or tam <= 40:
                    break
                tam -= 3
            x = self.W / 2 - total / 2
            if True:  # caja oscura difuminada detrás para que se lea sobre cualquier toma
                caja = skia.Rect.MakeXYWH(x - tam * 0.45, y - tam * 0.95, total + tam * 0.9, tam * 1.3)
                p = skia.Paint(AntiAlias=True, Color4f=col("#0A0A10", (0.55 if self.genero == "terror" else 0.35) * a))
                p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 14))
                c.drawRoundRect(caja, 18, 18, p)
            if self.genero != "terror":
                from . import identidad
                identidad.regla(c, self.W / 2, y - tam * 1.55, 140, a)
                fi = fuente("DMSerifDisplay-Italic", tam)
            for j, (w, pal, an) in enumerate(zip(g, ps, anchos)):
                dicha = t >= w["t0"] - 0.03
                if self.genero != "terror":
                    ahora = w["t0"] - 0.03 <= t < w["t1"] + 0.1
                    escribe(c, pal, x, y, fi if ahora else f, "#D98A97" if ahora else "#EDE6D6", alfa=a * (1.0 if dicha else 0.0),
                            centro=False, sombra=0.9)
                    x += an + esp
                    continue
                clave = self._es_clave(w, j == len(g) - 1) and quien == "narrador" and self.genero == "terror"
                cw = ROJO if (clave and dicha) else color
                alfa = a * (1.0 if dicha else (0.28 if self.genero == "terror" else 0.0))
                escribe(c, pal, x, y, f, cw, alfa=alfa, centro=False, sombra=0.9)
                x += an + esp
            return

    # ---- letrero de lugar y hora (arriba a la izquierda), la hora avanza con las escenas
    def _sello(self, c, t):
        """Sello STORY arriba a la izquierda: lugar y hora en terror, capítulo y hora en amor."""
        from . import identidad
        hora = self.spec.get("hora_inicio", "")
        for e in self.escenas:
            if e["_t0"] <= t and e.get("hora"):
                hora = e["hora"]
        if self.genero == "terror":
            texto = " · ".join(x for x in (str(self.spec.get("lugar") or "").upper(), str(hora).upper()) if x)
        else:
            romanos = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
            import zlib
            cap = self.spec.get("capitulo") or romanos[zlib.crc32(str(self.spec.get("titulo", "")).encode()) % len(romanos)]
            texto = " · ".join(x for x in ("CAPÍTULO " + str(cap), str(hora).upper()) if x.strip())
        a = rampa(t, 0.3, 0.6) * (1 - rampa(t, self.T_FIN, 0.4))
        identidad.sello(c, texto, self.genero, a)

    def _alerta(self, c, t, e):
        texto = e.get("alerta")
        if not texto:
            return
        k = sale((t - e["_t0"]) / 0.3)
        y = 300 - 120 * (1 - k)
        r = skia.Rect.MakeXYWH(140, y, self.W - 280, 120)
        c.drawRoundRect(r, 18, 18, skia.Paint(AntiAlias=True, Color4f=col("#C8262E", 0.95)))
        escribe(c, "⚠  ALERTA EXTREMA", 175, y + 46, fuente("HelveticaNowDisplay-Bold", 30), "#FFFFFF", centro=False, sombra=0)
        escribe(c, str(texto).upper(), 175, y + 92, fuente("HelveticaNowDisplay-ExtraBold", 40), "#FFFFFF", centro=False, sombra=0)

    # ---- pantallas de celular: llamada, chat o pantalla bloqueada con notificación
    def _pantalla(self, c, t, e):
        p = e.get("pantalla")
        if not isinstance(p, dict):
            return
        k = sale((t - e["_t0"]) / 0.35)
        c.drawRect(skia.Rect(0, 0, self.W, self.H), skia.Paint(Color4f=col("#000000", 0.55 * k)))
        w, h = 640, 1180
        x0, y0 = (self.W - w) / 2, (self.H - h) / 2 - 60 + 200 * (1 - k)
        tel = skia.Rect.MakeXYWH(x0, y0, w, h)
        som = skia.Paint(AntiAlias=True, Color4f=col("#000000", 0.6 * k))
        som.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 30))
        c.drawRoundRect(tel, 70, 70, som)
        c.drawRoundRect(tel, 70, 70, skia.Paint(AntiAlias=True, Color4f=col("#16161C", k)))
        c.drawRoundRect(tel, 70, 70, skia.Paint(AntiAlias=True, Color4f=col("#2C2C36", k), Style=skia.Paint.kStroke_Style, StrokeWidth=6))
        hora = (e.get("hora") or self.spec.get("hora_inicio") or "3:23").split(" ")[0]
        fb = lambda n: fuente("HelveticaNowDisplay-Bold", n)
        fr = lambda n: fuente("HelveticaNowDisplay-Regular", n)
        escribe(c, hora, x0 + 70, y0 + 70, fb(28), "#FFFFFF", alfa=k, centro=False, sombra=0)
        cx = self.W / 2
        tipo = p.get("tipo", "llamada")
        nombre = str(p.get("nombre", "Mamá"))
        if tipo == "llamada":
            c.drawCircle(cx, y0 + 330, 95, skia.Paint(AntiAlias=True, Color4f=col("#8E8E9A", k)))
            escribe(c, nombre[:1].upper(), cx, y0 + 365, fb(100), "#FFFFFF", alfa=k, sombra=0)
            escribe(c, nombre, cx, y0 + 520, fr(62), "#FFFFFF", alfa=k, sombra=0)
            if p.get("contador"):
                s = max(0, int(t - e["_t0"]))
                estado = f"{s // 60}:{s % 60:02d}"
            else:
                estado = p.get("estado", "llamando…")
            escribe(c, estado, cx, y0 + 580, fr(36), "#B0B0BC", alfa=k, sombra=0)
            for i, (etq, colr) in enumerate((("silenciar", "#3A3A44"), ("teclado", "#3A3A44"), ("altavoz", "#3A3A44"))):
                bx = cx + (i - 1) * 170
                c.drawCircle(bx, y0 + 820, 62, skia.Paint(AntiAlias=True, Color4f=col(colr, k)))
                escribe(c, etq, bx, y0 + 925, fr(24), "#B0B0BC", alfa=k, sombra=0)
            c.drawCircle(cx, y0 + 1040, 66, skia.Paint(AntiAlias=True, Color4f=col("#E5484D", k)))
        elif tipo == "chat":
            c.drawRect(skia.Rect.MakeXYWH(x0 + 6, y0 + 110, w - 12, 110), skia.Paint(Color4f=col("#202C33", k)))
            c.drawCircle(x0 + 90, y0 + 165, 34, skia.Paint(AntiAlias=True, Color4f=col("#7E57C2", k)))
            escribe(c, nombre[:1].upper(), x0 + 90, y0 + 180, fb(36), "#FFFFFF", alfa=k, sombra=0)
            escribe(c, nombre, x0 + 145, y0 + 160, fb(36), "#FFFFFF", alfa=k, centro=False, sombra=0)
            escribe(c, "en línea", x0 + 145, y0 + 200, fr(24), "#9FB0B8", alfa=k, centro=False, sombra=0)
            y = y0 + 300
            for i, msg in enumerate(p.get("mensajes") or []):
                ti = e["_t0"] + 0.4 + i * 0.9
                am = rampa(t, ti, 0.25) * k
                if am <= 0:
                    continue
                mio = msg.get("de") == "yo"
                fm = fr(32)
                if msg.get("nota_voz"):
                    bw, bh = 400, 96
                else:
                    lineas = parte_lineas(fm, str(msg.get("texto", "")), 400)
                    bw = max(mide(fm, l) for l in lineas) + 60 if lineas else 200
                    bh = 40 * len(lineas) + 46
                bx = x0 + w - 40 - bw if mio else x0 + 40
                c.drawRoundRect(skia.Rect.MakeXYWH(bx, y, bw, bh), 24, 24, skia.Paint(AntiAlias=True, Color4f=col("#005C4B" if mio else "#202C33", am)))
                if msg.get("nota_voz"):
                    c.drawCircle(bx + 50, y + bh / 2, 22, skia.Paint(AntiAlias=True, Color4f=col("#9FE0C8", am)))
                    for j in range(26):
                        hh = 10 + 30 * abs(((j * 37) % 11) / 11 - 0.5) * 2
                        c.drawRoundRect(skia.Rect.MakeXYWH(bx + 90 + j * 10, y + bh / 2 - hh / 2, 5, hh), 2, 2, skia.Paint(AntiAlias=True, Color4f=col("#9FE0C8", am)))
                else:
                    for j, l in enumerate(lineas):
                        escribe(c, l, bx + 30, y + 52 + j * 40, fm, "#E9EDEF", alfa=am, centro=False, sombra=0)
                y += bh + 22
        else:  # pantalla bloqueada con una notificación
            escribe(c, hora, cx, y0 + 330, fuente("HelveticaNowDisplay-Light", 170), "#FFFFFF", alfa=k, sombra=0)
            escribe(c, p.get("fecha", "jueves 14 de noviembre"), cx, y0 + 400, fr(32), "#D0D0DA", alfa=k, sombra=0)
            an = rampa(t, e["_t0"] + 0.6, 0.3) * k
            r = skia.Rect.MakeXYWH(x0 + 40, y0 + 480 + 30 * (1 - an), w - 80, 150)
            c.drawRoundRect(r, 30, 30, skia.Paint(AntiAlias=True, Color4f=col("#3A3A46", 0.92 * an)))
            escribe(c, nombre, x0 + 80, y0 + 540, fb(32), "#FFFFFF", alfa=an, centro=False, sombra=0)
            escribe(c, str(p.get("texto", "Nota de voz (0:03)"))[:34], x0 + 80, y0 + 590, fr(30), "#D0D0DA", alfa=an, centro=False, sombra=0)

    # ---- tarjeta final: en amor primero la reflexión escrita, luego el título STORY
    def _cierre(self, c, t):
        from . import identidad
        cz = self.cierre
        t_titulo = self.T_FIN
        if cz.get("tipo") == "reflexion" and cz.get("texto"):
            t_titulo = self.T_FIN + 4.6
            a = rampa(t, self.T_FIN, 0.8) * (1 - rampa(t, t_titulo - 0.3, 0.5))
            if a > 0:
                W, H = self.W, self.H
                c.drawRect(skia.Rect(0, 0, W, H), skia.Paint(Color4f=col("#0A0A0C", 0.82 * a)))
                f = fuente("DMSerifDisplay-Italic", 50)
                parrafos = [p for p in re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡])", str(cz["texto"])) if p.strip()]
                mitad = max(1, len(parrafos) // 2)
                bloques = [" ".join(parrafos[:mitad]), " ".join(parrafos[mitad:])] if len(parrafos) > 1 else parrafos
                y = H * 0.38
                identidad.regla(c, W / 2, y - 90, 140, a)
                for i, b in enumerate(bloques):
                    ab = a * rampa(t, self.T_FIN + 0.5 + i * 1.8, 0.8)
                    for l in parte_lineas(f, b, 860):
                        escribe(c, l, W / 2, y, f, "#EDE6D6", alfa=ab, sombra=0.6)
                        y += 68
                    y += 46
                identidad.barras(c, W, H, a)
        identidad.tarjeta_final(c, self.W, self.H, t, t_titulo, self.duracion, self.genero, cz, self.spec.get("titulo"))

    def _marca(self, c, t):
        from . import identidad
        identidad.barras(c, self.W, self.H, 1.0)
        identidad.marca_de_agua(c, self.W, self.H, 0.8 * (1 - rampa(t, self.T_FIN, 0.4)))

    def eventos(self):
        ev = []
        for i, e in enumerate(self.escenas):
            if self.genero == "terror" and (e.get("golpe") or e.get("pantalla") or e.get("alerta")) and i > 0:
                ev.append((e["_t0"], "golpe"))
        return ev

    def dibujar(self, c, t):
        e = self.escena_en(t)
        c.clear(col("#05050A"))
        if not self._cuadro_3d(c, e, t):
            # una pantalla sola usa de fondo la última toma 3D, oscurecida
            i = self.escenas.index(e)
            for prev in reversed(self.escenas[:i]):
                if prev.get("_n"):
                    self._cuadro_3d(c, prev, prev["_t1"])
                    break
        self._alerta(c, t, e)
        self._pantalla(c, t, e)
        self._sello(c, t)
        if t < self.T_FIN:
            self._subtitulos(c, t)
        self._marca(c, t)
        self._cierre(c, t)
