"""Variedad de FRONTERAS sin gastar más créditos.

Cada video combina, al azar pero sin repetir lo reciente:
  un cerebro (cómo escribe el guionista),
  una voz,
  una paleta de color,
  un estilo gráfico,
  una música (semilla y carácter).
Todo se decide aquí, en código, así que no cuesta llamadas extra.
Las referencias nuevas se agregan como una entrada más en estas listas.
"""
import json, os, random, time

CARPETA = "/data" if os.path.isdir("/data") else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORIAL = os.path.join(CARPETA, "estilos_usados.json")

# ---------------- cerebros: forma de escribir ----------------
CEREBROS = {
    "documentalista": {
        "nombre": "Documentalista",
        "voz_texto": "Tono de documental serio y preciso. Frases limpias, datos exactos, cero chistes. Como un narrador de un gran documental de historia.",
        "gancho": "Abre con un dato que parece imposible y es verdad.",
    },
    "cronista": {
        "nombre": "Cronista callejero",
        "voz_texto": "Tono de cronista mexicano con colmillo. Coloquial pero inteligente, con ironía fina y alguna frase que suene a plática de sobremesa. Nada vulgar.",
        "gancho": "Abre retando una creencia común, como si le hablaras a un amigo que está muy seguro de algo.",
    },
    "detective": {
        "nombre": "Detective",
        "voz_texto": "Tono de misterio e investigación. Presentas pistas una por una, haces preguntas y dejas que el espectador sospeche antes de revelar.",
        "gancho": "Abre con una pregunta o un enigma concreto que el mapa va a resolver.",
    },
    "profesor": {
        "nombre": "Profesor apasionado",
        "voz_texto": "Tono de maestro que ama su tema. Explicas con analogías cotidianas y comparaciones fáciles de imaginar (cuántas veces cabe, a qué ciudad equivale).",
        "gancho": "Abre con una comparación sorprendente que cualquiera entiende.",
    },
    "epico": {
        "nombre": "Narrador épico",
        "voz_texto": "Tono cinematográfico y épico, en presente histórico (el ejército cruza, el rey firma). Ritmo de tráiler de película.",
        "gancho": "Abre en medio de la acción, en el momento más tenso de la historia.",
    },
    "datos": {
        "nombre": "Contador de datos",
        "voz_texto": "Tono de periodista de datos. Cada frase trae una cifra, un año o una comparación. Directo, rápido, sin adornos.",
        "gancho": "Abre con la cifra más impactante del tema.",
    },
}

# ---------------- voces ----------------
# id de ElevenLabs y ajustes. Se agregan más con la variable FRONTERAS_VOCES (ids separados por coma)
VOCES = [
    {"id": "tBkfgTXKnmHoYewBvh7e", "nombre": "Eduardo"},
    {"id": "JBFqnCBsd6RMkjVDRZzb", "nombre": "George"},
]

# ---------------- paletas ----------------
# fondo, texto, acento, acento claro, alerta, neutro, y el tinte del relieve (multiplica R, G, B)
PALETAS = {
    "noche_oro":   {"nombre": "Noche y oro",   "NOCHE": "#07090C", "MARFIL": "#EDE6D6", "ORO": "#C9A45C", "ORO_CLARO": "#E8CC8A", "CARMIN": "#A3362B", "PIEDRA": "#8A8170", "tinte": (1.00, 1.00, 1.00)},
    "tinta_azul":  {"nombre": "Tinta azul",    "NOCHE": "#060A12", "MARFIL": "#E6EEF5", "ORO": "#5FA8D3", "ORO_CLARO": "#A9D6F0", "CARMIN": "#D2473A", "PIEDRA": "#7D8A99", "tinte": (0.62, 0.80, 1.10)},
    "carmesi":     {"nombre": "Carmesí",       "NOCHE": "#0A0707", "MARFIL": "#F2E9E4", "ORO": "#C8372D", "ORO_CLARO": "#F07A63", "CARMIN": "#E8C27A", "PIEDRA": "#8C7B76", "tinte": (1.05, 0.70, 0.65)},
    "atlas_verde": {"nombre": "Atlas verde",   "NOCHE": "#050B09", "MARFIL": "#EAF1E6", "ORO": "#4FB38A", "ORO_CLARO": "#9EDDBF", "CARMIN": "#D9643A", "PIEDRA": "#7E8F86", "tinte": (0.70, 1.00, 0.85)},
    "archivo":     {"nombre": "Archivo sepia", "NOCHE": "#0D0904", "MARFIL": "#F3E3C3", "ORO": "#D08A3A", "ORO_CLARO": "#F0BC79", "CARMIN": "#9E2E22", "PIEDRA": "#9B8466", "tinte": (1.10, 0.88, 0.62)},
    "neon":        {"nombre": "Neón frío",     "NOCHE": "#05050A", "MARFIL": "#F4F4FA", "ORO": "#33D1FF", "ORO_CLARO": "#9BE8FF", "CARMIN": "#FF3D8B", "PIEDRA": "#7C7C96", "tinte": (0.55, 0.65, 0.95)},
}

# ---------------- estilos gráficos ----------------
GRAFICOS = {
    "clasico":   {"nombre": "Clásico",    "subtitulo": "color",  "mayusculas": False, "linea": 1.0, "grano": 0.07, "titulo": "centro",    "tarjeta": "cuadricula"},
    "caja":      {"nombre": "Caja",       "subtitulo": "caja",   "mayusculas": True,  "linea": 1.3, "grano": 0.05, "titulo": "centro",    "tarjeta": "puntos"},
    "editorial": {"nombre": "Editorial",  "subtitulo": "color",  "mayusculas": False, "linea": 0.8, "grano": 0.09, "titulo": "izquierda", "tarjeta": "lisa"},
    "impacto":   {"nombre": "Impacto",    "subtitulo": "caja",   "mayusculas": True,  "linea": 1.6, "grano": 0.04, "titulo": "izquierda", "tarjeta": "cuadricula"},
    "subrayado": {"nombre": "Subrayado",  "subtitulo": "linea",  "mayusculas": False, "linea": 1.1, "grano": 0.06, "titulo": "centro",    "tarjeta": "puntos"},
}


def _voces():
    extra = [v.strip() for v in os.environ.get("FRONTERAS_VOCES", "").split(",") if v.strip()]
    lista = list(VOCES) + [{"id": v, "nombre": f"Voz {v[:5]}"} for v in extra if v not in {x["id"] for x in VOCES}]
    return lista


def _historial():
    try:
        return json.load(open(HISTORIAL))
    except Exception:
        return []


def elegir(forzar=None):
    """Elige una combinación que no se parezca a las últimas. forzar permite fijar partes, ej. {"paleta": "neon"}."""
    hist = _historial()[-6:]
    rng = random.Random(time.time_ns())

    def toma(clave, opciones, memoria):
        if forzar and forzar.get(clave) in opciones:
            return forzar[clave]
        usados = [h.get(clave) for h in hist[-memoria:]]
        libres = [o for o in opciones if o not in usados] or list(opciones)
        return rng.choice(libres)

    voces = _voces()
    e = {
        "cerebro": toma("cerebro", list(CEREBROS), 3),
        "paleta": toma("paleta", list(PALETAS), 3),
        "grafico": toma("grafico", list(GRAFICOS), 2),
        "voz": toma("voz", [v["id"] for v in voces], max(1, len(voces) - 1)),
        "musica": rng.randint(1, 10_000),
    }
    try:
        json.dump((_historial() + [e])[-40:], open(HISTORIAL, "w"))
    except Exception:
        pass
    return e


def describir(e):
    voz = next((v["nombre"] for v in _voces() if v["id"] == e.get("voz")), "voz")
    return " · ".join([CEREBROS.get(e.get("cerebro"), {}).get("nombre", "?"), voz,
                       PALETAS.get(e.get("paleta"), {}).get("nombre", "?"), GRAFICOS.get(e.get("grafico"), {}).get("nombre", "?")])


def instrucciones_guion(e):
    c = CEREBROS.get(e.get("cerebro")) or CEREBROS["documentalista"]
    return f"ESTILO DE ESCRITURA DE ESTE VIDEO ({c['nombre']}). {c['voz_texto']} {c['gancho']} Mantén la estructura de retención y las reglas del formato."
