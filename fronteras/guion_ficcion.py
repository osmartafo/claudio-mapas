"""Guionista de cortometrajes de amor y de terror, con el método de Zepfilms y la estructura de los cortos de referencia.

Tres pasos, igual que las curiosidades:
  1. premisa, personajes, escaleta y guion (líneas de narrador y diálogo)
  2. script doctor: audita con el método y reescribe
  3. dirección: sets 3D, tomas, letreros de hora, pantallas de celular y tarjeta final
"""
import json, os

import anthropic

from .guionista import _llamar

LEYES = """LAS TRES LEYES DEL MÉTODO (Zepfilms)
1. Sin personaje no hay conflicto y sin conflicto no hay historia. Alguien quiere algo, actúa y choca.
2. Ser fiel al personaje. Nadie dice ni hace algo que esa persona, en su contexto, no haría.
3. Lo que no se ve o no se oye no existe. Nada de pensamientos explicados: acciones, objetos y frases dichas.
Además: plantar y cosechar (todo detalle raro del inicio se paga al final), subtexto en el diálogo (la gente no dice
lo que siente, lo rodea), y cortar todo lo que no empuje la historia."""

ESTRUCTURA_TERROR = """ESTRUCTURA DE TERROR (cortos de referencia de 80 a 110 segundos, leyendas urbanas mexicanas en primera persona)
- Línea 1, gancho en 3 segundos: una REGLA heredada o una ANOMALÍA concreta. Ejemplos del estilo:
  "Mi tío me dejó el puesto con una sola regla." / "En el espejo, Valeria seguía en la esquina."
- Contexto en dos frases: la regla exacta y cuánto tiempo se cumplió. Remata con "Hasta anoche."
- Lugar real de México y hora de madrugada que avanza (1:57, 2:00, 2:04 a.m.). Lo cotidiano vuelto amenaza:
  un puesto de tacos, un cuarto con papel tapiz de flores, una tiendita, un microbús, la azotea, el zaguán.
- Llega la anomalía con 2 o 3 DETALLES SENSORIALES que no cuadran (el pelo mojado, descalzo, un billete de 1985,
  una voz idéntica a la tuya). Esos detalles se plantan y se cosechan en el giro.
- El protagonista ROMPE la regla por bondad, costumbre o curiosidad. Es su decisión y le cuesta.
- Diálogos cortos y raros del otro personaje (entre 3 y 8 palabras), con doble sentido.
- Escalada física: las luces se apagan una por una hacia mí, tocan tres veces desde adentro, algo respira.
- Revelación por un CELULAR: una llamada o una nota de voz de un familiar que explica a medias el pasado
  (una deuda, una desaparición). Nunca se explica todo.
- Golpe final: una frase de 3 a 7 palabras que voltea todo y corta en seco ("Ma, ábreme. Soy yo." / "Ya te abrí.").
- Narrador en primera persona, pasado simple, frases de 2 a 7 palabras, ritmo de respiración contenida.
- Opcional al final una pregunta al público con dos opciones (¿Tú qué harías? Abrir la puerta / Dejarla cerrada)."""

ESTRUCTURA_AMOR = """ESTRUCTURA DE AMOR (corto de referencia de 70 a 90 segundos, sin narrador, solo diálogo)
- Dos personajes de noche en un lugar tranquilo (una fiesta a lo lejos, una alberca, una azotea, un coche estacionado,
  la banca de un parque). Uno está apagado por algo que no dice (una ruptura, una distancia, una pérdida) y el otro
  lo conoce de años y lo acompaña con humor.
- Abre con una observación concreta ("Oye, llevas un rato viendo la alberca sin decir nada.") y una evasiva.
- El conflicto se dice de lado, con subtexto, nunca con frases de autoayuda.
- Un RECUERDO ESPECÍFICO y físico que funciona como objeto (una playlist con nombre, una sudadera, una canción,
  un plan cancelado). Se planta en la mitad y se cosecha en el giro.
- Giro emocional: lo que extraña no es a la otra persona sino quién era él o ella cuando se emocionaba por todo.
  "Y eso sigue ahí."
- Cierre con una invitación de vuelta a la vida, ligera y concreta ("Nos falta uno en el beer pong." / "Vamos, pues.").
- Español de México natural, coloquial, alguna grosería suave si el personaje la diría. Líneas de 3 a 14 palabras.
- Al final una reflexión escrita para la pantalla, de dos a tres frases, que diga la idea sin repetir el diálogo."""

DOPAMINA_FICCION = """ESTRUCTURA DOPAMÍNICA (manda sobre todo lo demás: nadie debe deslizar al siguiente video)
- Primeros 2 segundos: una frase que abre un bucle que el cerebro necesita cerrar (una regla, una anomalía, una frase
  dicha a medias, un "no digas eso"). Cero contexto antes del gancho.
- Una MICRO RECOMPENSA cada 5 a 8 segundos (unas 2 o 3 líneas): en terror un detalle que no cuadra, un ruido, una luz
  que se apaga, un susto; en amor una revelación, un recuerdo concreto, una frase que pega o una risa.
- Falsa calma: en terror deja un respiro corto justo antes del golpe más fuerte.
- Bucles anidados: antes de cerrar un misterio abre el siguiente. La revelación más fuerte va al final.
- Ritmo que cambia: una línea de dos palabras después de una larga; preguntas; silencios marcados con puntos.
- Últimos 5 segundos: el golpe final cierra el bucle del gancho y deja una pregunta o una emoción que invita a comentar
  o a volver a verlo.
- Prohibido: introducciones, explicar el chiste o el miedo, despedidas, pedir like."""

PASO_FICCION = """Eres guionista de cortometrajes animados verticales para un canal de shorts, con el método de guion de Zepfilms.
Escribes un corto de GENERO a partir de la idea que te dan. Si la idea es vaga, elige la premisa más fuerte.

{leyes}

{estructura}

{dopamina}

REGLAS DE ESCRITURA
- 140 a 200 palabras en total entre todas las líneas (el corto dura de 70 a 100 segundos).
- Cada línea es lo que dice UNA voz. "quien" es "narrador" o el id de un personaje.
- En terror casi todo es narrador; los otros personajes dicen pocas líneas y cortas.
- En amor no hay narrador: solo los dos personajes.
- Números con letra. Sin acotaciones dentro del texto, salvo acotaciones de actuación en inglés entre corchetes
  que la voz sabe interpretar, máximo tres en todo el corto: [whispers], [sighs], [laughs softly], [nervous].
- Nada de violencia gráfica ni sangre explícita: el miedo sale de lo que no cuadra y de lo que no se ve.

VOCES DISPONIBLES (campo "voz" de cada personaje)
narrador_suspenso (hombre, narrador de terror), narradora_drama (mujer, narradora), hombre_joven, hombre_maduro,
mujer_joven, mujer_madura, nino.

Responde SOLO con JSON
{{"titulo": "título corto que intrigue, máx 60 caracteres", "descripcion": "2 frases y 3 hashtags",
 "premisa": "personaje + acción + conflicto en una frase", "logline": "150 a 300 caracteres",
 "lugar": "lugar real de México en mayúsculas o vacío en amor", "hora_inicio": "1:57 a.m. o vacío",
 "personajes": [{{"id": "corto_sin_espacios", "nombre": "", "voz": "una de la lista", "quiere": "", "necesita": "", "aspecto": "edad, ropa, peinado en 6 palabras"}}],
 "narrador_voz": "narrador_suspenso o narradora_drama (solo terror)",
 "escaleta": ["gancho", "contexto", "anomalía", "decisión", "escalada", "revelación", "golpe final"],
 "plantar_cosechar": [["detalle plantado", "cómo se cosecha"]],
 "lineas": [{{"quien": "narrador", "texto": ""}}],
 "resaltar": ["6 a 10 palabras clave que irán en rojo en pantalla, tal cual aparecen en las líneas"],
 "objetos": ["8 a 15 objetos físicos que aparecen en la historia, en inglés y en singular (mirror, door, clock, chair)"],
 "cierre": {{"tipo": "encuesta", "pregunta": "¿Tú qué harías?", "opciones": ["", ""]}} o {{"tipo": "reflexion", "texto": ""}}}}
"""

PASO_AUDITORIA = """Eres script doctor con el método de Zepfilms. Recibes un cortometraje de GENERO (JSON con escaleta y líneas).
Revisa en este orden y corrige:
1. Premisa clara en una frase y gancho en las primeras dos líneas (si no engancha en 3 segundos, reescríbelo).
2. El protagonista quiere algo y TOMA una decisión que le cuesta.
3. Conflicto y escalada: cada línea sube la tensión o la emoción; corta lo que se repite.
4. Plantar y cosechar: cada detalle raro se paga; ninguno queda suelto ni se explica de más.
5. Diálogo con subtexto, fiel a cada personaje, español de México natural.
6. Lo que no se ve no existe: nada de pensamientos explicados.
7. Golpe final corto y que reencuadre todo (terror) o invitación concreta y reflexión que no repita (amor).
8. Largo total entre 140 y 200 palabras.
9. Estructura dopamínica: gancho que abre un bucle en 2 segundos, una micro recompensa cada 2 o 3 líneas, bucles
   anidados, lo más fuerte al final. Marca la línea exacta donde el espectador se iría y arréglala.

{estructura}

{dopamina}

Responde SOLO con JSON
{{"calificacion": 1 a 10, "problemas": ["máx 5, concretos"], "funciona": ["máx 3"],
 "lineas": [{{"quien": "", "texto": ""}}], "resaltar": [], "cierre": {{}}}}
con las líneas ya reescritas (mismo formato y mismos ids de personaje).
"""

PASO_DIRECCION = """Eres director de animación 3D de cortometrajes verticales. Recibes un corto de GENERO ya escrito, con sus líneas
numeradas. Tu trabajo es armar los SETS (una sola vez) y las ESCENAS (un corte cada 2 a 4 segundos, de 18 a 30 escenas).

EL MUNDO 3D (metros, y es hacia arriba, el piso en y=0, la cámara mira hacia -z)
Formas especiales:
- {{"id": "ana", "forma": "personaje", "pose": "de_pie|caminando|sentado|cabizbajo|brazos_cruzados|senalando|manos_cara|acostado",
   "peinado": "corto|largo|chongo|gorra", "luz": "#hex (luz del pecho, en amor: azul #4D8BFF para el triste, naranja #FF9A4D para el cálido)",
   "color": "#hex de piel/cuerpo (tonos medios, nunca blanco puro)", "color_ropa": "#hex", "cara": "ojos|ojos_brillo (terror)",
   "pos": [x,0,z], "rot": [0,grados,0]}}
  Mide 1.7 m. De pie: pecho 1.3, cabeza 1.6. Sentado (pose sentado o cabizbajo): pecho 0.9, cabeza 1.25, y necesita una silla
  o banca de 0.45 m de alto en la misma posición. El personaje mira hacia +z con rot 0.
- {{"id": "cuarto", "forma": "cuarto", "tam": [ancho, alto, fondo], "color": "#hex pared", "papel": "flores|rayas|azulejo",
   "piso": "#hex", "techo": true, "puerta": {{"pared": "fondo|izq|der", "x": 0.9, "luz_detras": "#hex opcional"}},
   "ventana": {{"pared": "izq|der|fondo", "x": -0.6}}}}  Tres paredes y el lado +z abierto para la cámara.
  La hoja de la puerta se anima con el id "<id del cuarto>_puerta" y "girar": [0, 70, 0].
- {{"id": "luces", "forma": "serie_luces", "puntos": [[-3,2.6,-3],[3,2.6,-3.5]], "colores": ["#FFD9A0","#FF8FB8","#9FD8FF"]}}
- {{"id": "foco1", "forma": "foco", "pos": [x,y,z], "color": "#FFB870", "intensidad": 2.5, "sombra": true}}  luz práctica.
- {{"id": "bokeh", "forma": "bokeh"}}  bolitas de luz desenfocadas al fondo, para noches de fiesta.
Objetos reales: {{"id": "silla", "catalogo": "nombre EXACTO de la lista", "tamano": medida mayor en metros, "pos": [x,0,z], "rot": [0,g,0]}}
Formas simples SOLO para arquitectura o utilería neutra (caja, cilindro, plano) con "color" y "material" (madera, metal, tela,
vidrio, brillo, piedra). PROHIBIDO armar con formas simples personas, animales, comida o caras.

SET
"sets": {{"patio": {{"ambiente": "noche|terror|interior", "objetos": [...]}}}}  Usa 1 a 3 sets por corto.
Ambientes: terror (luz fría violeta, niebla), noche (azul profundo con luces de fiesta), interior (cálido de casa).

ESCENA
{{"desde": "2 o 3 palabras EXACTAS de una línea, en orden", "set": "patio",
  "toma": [{{"t": 0, "pos": [x,y,z], "mira": [x,y,z]}}, {{"t": 1, "pos": [...], "mira": [...]}}],
  "ocultar": ["ids que no deben salir en esta toma"], "extra": [objetos solo de esta toma],
  "animar": [{{"id": "", "t0": 0, "t1": 1, "girar": [0,40,0] | "mover": [x,y,z] | "mirar": [0,35,0] | "parpadeo": true | "apagar": true}}],
  "hora": "2:00 a.m. (solo terror, cuando avanza)", "golpe": true (solo en los sustos),
  "pantalla": {{"tipo": "llamada", "nombre": "Tío Beto", "contador": true}} | {{"tipo": "chat", "nombre": "Mamá ❤",
     "mensajes": [{{"de": "yo", "texto": ""}}, {{"de": "ella", "nota_voz": true}}]}} | {{"tipo": "bloqueo", "nombre": "Mamá ❤", "texto": "Nota de voz (0:03)"}},
  "alerta": "texto corto de alerta (opcional, terror)"}}
Una escena con "pantalla" puede ir sin set: se ve el celular sobre la última toma.

LENGUAJE DE CÁMARA (como los cortos de referencia)
- Variedad: plano de establecimiento, plano medio de dos, primer plano del pecho o la cara del que habla, inserto de un objeto
  clave (el reloj, la puerta, el celular, los pies), y en terror muchas tomas en primera persona (cámara a 1.6 m de altura
  mirando lo que ve el narrador).
- En amor: corta al que habla. Primer plano a 1.0 a 1.4 m del pecho, la cámara a la altura del pecho. Planos generales con las luces.
- En terror: tomas lentas que se acercan, contrapicados, lo raro a medio cuadro u oculto. Los pies mojados, la puerta, el espejo.
- La cámara SIEMPRE a más de 0.8 m de cualquier objeto y dentro del cuarto (|x| < ancho/2 - 0.3, z < fondo/2 + 2).
- "mira" apunta a la altura del detalle (pecho, cabeza, objeto). Se mueve poco: 0.2 a 0.8 m entre t=0 y t=1.
- Cada línea de diálogo tiene al menos una toma de quien la dice. Cada "plantar" tiene un inserto.

REGLAS
- La primera escena no lleva "desde". Todo "desde" copia palabras que aparecen tal cual en las líneas y en orden.
- Las escenas van en el orden del guion. 18 a 30 escenas.
- JSON compacto, números con máximo 2 decimales.

Responde SOLO con JSON {{"sets": {{...}}, "escenas": [...]}}
"""

COLOR_LUZ = {"amor": ["#4D8BFF", "#FF9A4D", "#FF6FAE"], "terror": [None, None, None]}


def _plantilla(texto, genero):
    estructura = ESTRUCTURA_TERROR if genero == "terror" else ESTRUCTURA_AMOR
    return texto.format(leyes=LEYES, estructura=estructura, dopamina=DOPAMINA_FICCION).replace("GENERO", genero.upper())


def escribir_ficcion(tema, genero="terror", api_key=None, aviso=lambda *a: None):
    cliente = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
    base = _llamar(cliente, _plantilla(PASO_FICCION, genero), f"Idea del corto: {tema}", 6000)
    lineas = [l for l in base.get("lineas") or [] if str(l.get("texto", "")).strip()]
    if len(lineas) < 4:
        raise ValueError("El guionista no devolvió el corto completo. Intenta de nuevo.")
    base["lineas"] = lineas
    aviso("Auditando el guion con el método Zepfilms")
    try:
        aud = _llamar(cliente, _plantilla(PASO_AUDITORIA, genero), json.dumps(
            {k: base.get(k) for k in ("premisa", "personajes", "escaleta", "plantar_cosechar", "lineas", "resaltar", "cierre")},
            ensure_ascii=False), 5000)
        nuevas = [l for l in aud.get("lineas") or [] if str(l.get("texto", "")).strip()]
        ids = {p["id"] for p in base.get("personajes") or []} | {"narrador"}
        palabras = sum(len(l["texto"].split()) for l in nuevas)
        if nuevas and all(l.get("quien") in ids for l in nuevas) and 100 <= palabras <= 240:
            base["lineas_original"], base["lineas"] = base["lineas"], nuevas
            base["resaltar"] = aud.get("resaltar") or base.get("resaltar")
            if aud.get("cierre"):
                base["cierre"] = aud["cierre"]
        base["auditoria"] = {k: aud.get(k) for k in ("calificacion", "problemas", "funciona")}
    except Exception as err:
        base["auditoria"] = {"error": str(err)[:200]}
    aviso("Dirigiendo las escenas 3D")
    try:
        from . import catalogo
        palabras_clave = " ".join(l["texto"] for l in base["lineas"])
        cats = catalogo.categorias_para(base.get("objetos") or [], palabras_clave)
    except Exception:
        cats = []
    lista = ("CATEGORÍAS DISPONIBLES PARA \"catalogo\": " + ", ".join(cats)) if cats else \
        "El catálogo de modelos no está listo: no uses \"catalogo\"; usa personajes, cuartos, luces y formas simples de utilería."
    numeradas = "\n".join(f"{i + 1}. [{l['quien']}] {l['texto']}" for i, l in enumerate(base["lineas"]))
    dire = _llamar(cliente, _plantilla(PASO_DIRECCION, genero),
                   f"{lista}\n\nPERSONAJES\n{json.dumps(base.get('personajes'), ensure_ascii=False)}\n\n"
                   f"LUGAR {base.get('lugar', '')}  HORA {base.get('hora_inicio', '')}\n\nLÍNEAS\n{numeradas}", 20000)
    if len(dire.get("escenas") or []) < 4:
        raise ValueError("El director no armó suficientes escenas. Intenta de nuevo.")
    voces = {p["id"]: p.get("voz", "hombre_joven") for p in base.get("personajes") or []}
    voces["narrador"] = base.get("narrador_voz") or ("narrador_suspenso" if genero == "terror" else "narradora_drama")
    base["guion"] = " ".join(l["texto"] for l in base["lineas"])
    return dict(base, genero=genero, modo=genero, sets=dire.get("sets") or {}, escenas=dire["escenas"],
                voces=voces, formato="vertical")
