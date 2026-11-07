"""Ajustes que el dueño elige con botones y que sobreviven a las actualizaciones (se guardan en /data).

  estilo     look, narrador (cerebro) y voz fijos, o automático
  piloto     modo piloto automático: cuántos videos al día, a qué horas y dónde se publican
  temas      temas ya producidos, para que el piloto no repita
"""
import json, os, threading

CARPETA = "/data" if os.path.isdir("/data") else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datos_locales")
ARCHIVO = os.path.join(CARPETA, "ajustes.json")
_candado = threading.Lock()

PILOTO_BASE = {
    "activo": False,
    "chat": None,                 # a dónde manda los reportes
    "por_dia": 1,                 # videos al día
    "horas": [11, 19, 15],        # horas de México en que publica, se usan las primeras por_dia
    "destinos": {"fb": True, "ig": True, "yt": True, "tt": True},
    "yt_publico": False,          # YouTube deja en privado lo que sube una app no auditada; esto pide público
    "ultimo": {},                 # "2026-11-07 11" -> tema, para no publicar dos veces en la misma hora
}


def _leer():
    try:
        return json.load(open(ARCHIVO))
    except Exception:
        return {}


def _escribir(d):
    os.makedirs(CARPETA, exist_ok=True)
    tmp = ARCHIVO + ".tmp"
    json.dump(d, open(tmp, "w"), ensure_ascii=False, indent=1)
    os.replace(tmp, ARCHIVO)


def estilo(chat):
    return dict(_leer().get("estilo", {}).get(str(chat), {}))


def fijar_estilo(chat, clave, valor):
    with _candado:
        d = _leer()
        e = d.setdefault("estilo", {}).setdefault(str(chat), {})
        if valor in (None, "", "auto"):
            e.pop(clave, None)
        else:
            e[clave] = valor
        _escribir(d)


def piloto():
    p = dict(PILOTO_BASE)
    p.update(_leer().get("piloto", {}))
    p["destinos"] = dict(PILOTO_BASE["destinos"], **p.get("destinos", {}))
    return p


def fijar_piloto(**cambios):
    with _candado:
        d = _leer()
        p = dict(PILOTO_BASE)
        p.update(d.get("piloto", {}))
        p.update(cambios)
        d["piloto"] = p
        _escribir(d)
        return p


def temas_hechos():
    return list(_leer().get("temas", []))


def anotar_tema(tema):
    with _candado:
        d = _leer()
        t = d.setdefault("temas", [])
        if tema not in t:
            t.append(tema)
        d["temas"] = t[-300:]
        _escribir(d)


OPCIONES_POR_DIA = (1, 2, 3, 5, 8, 10, 12)


def horario(n):
    """Horas del día (en minutos desde medianoche, hora de México) en que el piloto publica n videos.
    De 1 a 3 se usan las horas fuertes; con más se reparten parejo entre las 8:00 y las 22:00."""
    fijos = {1: [11 * 60], 2: [11 * 60, 19 * 60], 3: [11 * 60, 15 * 60, 19 * 60]}
    if n in fijos:
        return fijos[n]
    ini, fin = 8 * 60, 22 * 60
    paso = (fin - ini) / (n - 1)
    return [int(ini + round(i * paso / 5) * 5) for i in range(n)]


def contar_hoy(clave, fecha):
    """Suma uno al contador del día (por ejemplo subidas a YouTube) y regresa el total."""
    with _candado:
        d = _leer()
        c = d.setdefault("contadores", {})
        llave = f"{fecha} {clave}"
        c[llave] = c.get(llave, 0) + 1
        d["contadores"] = dict(list(c.items())[-60:])
        _escribir(d)
        return c[llave]


def visto_hoy(clave, fecha):
    return _leer().get("contadores", {}).get(f"{fecha} {clave}", 0)


def ideas_dadas():
    return list(_leer().get("ideas_dadas", []))


def anotar_ideas(ideas):
    with _candado:
        d = _leer()
        lista = d.get("ideas_dadas", [])
        lista += [i for i in ideas if i not in lista]
        d["ideas_dadas"] = lista[-200:]
        _escribir(d)
