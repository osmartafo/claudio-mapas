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

ESTRUCTURA_AMOR = """ESTRUCTURA DE AMOR QUE DUELE (cortos de referencia de 60 a 80 segundos)
Esto tiene que DOLER, como las reflexiones de parejas que ya terminaron. El dolor no sale de palabras bonitas,
sale de detalles chiquitos y de lo que nadie se atreve a decir.

FORMA DE ESCRIBIR (la más importante)
- Frases simples, chiquitas y fáciles de entender. De 2 a 9 palabras. Una idea por frase.
- Palabras de todos los días, como habla la gente en México. Nada de poesía: prohibido "alma", "corazón roto",
  "infinito", "destino", "eternidad", "mariposas", "te amaré por siempre".
- Detalles concretos y cotidianos que duelen: su lado de la cama, el cepillo de dientes que sigue ahí, la sudadera que
  todavía huele, el "¿ya llegaste?" que ya nadie manda, el contacto que no borras, la canción que ya no puedes oír,
  cómo tomaba el café, la foto que no te atreves a archivar.
- Antes y ahora en dos frases: "Antes me esperabas despierta." / "Ahora ni me lees."
- Nadie dice "te extraño" ni "me duele": se nota en lo que hacen y en lo que no dicen.
- Silencios: una línea de una o dos palabras ("Ajá." "Ya." "Bueno.") pesa más que un discurso.
- No uses letras de canciones ni frases famosas: todo es original.

ESTRUCTURAS (elige la que mejor sirva a la idea)
a) Dos ex se encuentran otra vez (una boda, el súper, la fiesta de un amigo) y platican como si nada, pero todo duele.
b) Un amigo o amiga acompaña a quien terminó; uno está apagado y el otro lo hace hablar.
c) La última noche antes de que uno se vaya: hablan de cosas chiquitas para no hablar de lo grande.
d) Una voz en off (narradora o narrador) le habla a quien ya no está, con recuerdos muy concretos, y al final el otro
   personaje dice una sola línea.
- PAREJAS DIVERSAS: hombre y mujer, dos hombres, dos mujeres o amistad. Si la idea no lo dice, alterna. El conflicto es
  el del amor, nunca el de su orientación; sin estereotipos.
- Un objeto o recuerdo concreto se planta al inicio y se cosecha en el golpe final.
- Golpe final: una frase corta que rompe ("Sí la guardé. La playlist." / "Todavía pongo dos tazas.").
- Español de México natural. Líneas de 2 a 12 palabras. 110 a 170 palabras en total.
- Cierre SIEMPRE con una reflexión escrita para la pantalla: 2 o 3 frases cortitas y simples que duelan y se puedan
  mandar a alguien ("Hay gente que no se va de golpe. Se va de a poquito. Y uno se da cuenta tarde.").
  En amor el "cierre" SIEMPRE es {"tipo": "reflexion", "texto": "..."}."""

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
- Prohibido: introducciones, explicar el chiste o el miedo, despedidas, pedir like.
- Expectativa contra realidad: si la siguiente línea es lo que el espectador ya adivinaba, cámbiala por algo que no esperaba.
- Pregunta, anticipación, respuesta no obvia, nueva pregunta: deja pistas antes de cada revelación y págalas todas.
- Que den ganas de mandarlo a alguien ("esto me pasó", "así me dejó") y de comentar (qué harías tú, de qué lado estás)."""

PASO_FICCION = """Eres guionista de cortometrajes animados verticales para un canal de shorts, con el método de guion de Zepfilms.
Escribes un corto de GENERO a partir de la idea que te dan. Si la idea es vaga, elige la premisa más fuerte.

{leyes}

{estructura}

{dopamina}

REGLAS DE ESCRITURA
- Terror 140 a 200 palabras en total; amor 110 a 170 (el corto dura de 60 a 100 segundos).
- Cada línea es lo que dice UNA voz. "quien" es "narrador" o el id de un personaje.
- En terror casi todo es narrador; los otros personajes dicen pocas líneas y cortas.
- En amor casi siempre son solo los dos personajes; si usas la estructura d) puede haber una voz en off ("narrador").
- Números con letra. Sin acotaciones dentro del texto, salvo acotaciones de actuación en inglés entre corchetes
  que la voz sabe interpretar, máximo tres en todo el corto: [whispers], [sighs], [laughs softly], [nervous].
- Nada de violencia gráfica ni sangre explícita: el miedo sale de lo que no cuadra y de lo que no se ve.

VOCES DISPONIBLES (campo "voz" de cada personaje)
narrador_suspenso (hombre, narrador de terror), narradora_drama (mujer, narradora), hombre_joven, hombre_joven_b,
hombre_maduro, mujer_joven, mujer_joven_b, mujer_madura, nino.
Dos personajes NUNCA comparten voz: si los dos son hombres jóvenes usa hombre_joven y hombre_joven_b; si son dos mujeres
jóvenes usa mujer_joven y mujer_joven_b.

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
8. Largo total: terror 140 a 200 palabras, amor 110 a 170. Amor: frases de 2 a 9 palabras, simples, sin poesía, que duelan.
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
{{"linea": número de la línea donde empieza la escena (1 a N, el de la lista numerada), "desde": "2 o 3 palabras EXACTAS de esa línea",
  "set": "patio",
  "plano": "general | dos | medio:ID | primer:ID | detalle:ID | hombro:ID_DE_ESPALDAS:ID_DE_FRENTE | pov:ID[:ID_AL_QUE_MIRA] | nuca:ID",
  "ocultar": ["ids que no deben salir en esta toma"], "extra": [objetos solo de esta toma],
  "animar": [{{"id": "", "t0": 0, "t1": 1, "girar": [0,40,0] | "mover": [x,y,z] | "mirar": [0,35,0] | "parpadeo": true | "apagar": true}}],
  "hora": "2:00 a.m. (solo terror, cuando avanza)", "golpe": true (solo en los sustos),
  "pantalla": {{"tipo": "llamada", "nombre": "Tío Beto", "contador": true}} | {{"tipo": "chat", "nombre": "Mamá ❤",
     "mensajes": [{{"de": "yo", "texto": ""}}, {{"de": "ella", "nota_voz": true}}]}} | {{"tipo": "bloqueo", "nombre": "Mamá ❤", "texto": "Nota de voz (0:03)"}},
  "alerta": "texto corto de alerta (opcional, terror)"}}
Una escena con "pantalla" puede ir sin set: se ve el celular sobre la última toma.

CÁMARA AUTOMÁTICA: NO escribas coordenadas de cámara. Elige el "plano" y el motor coloca la cámara a la distancia y altura
correctas, con la cabeza completa y un movimiento suave.
- general: todo el set, para abrir o cerrar. dos: los dos personajes juntos.
- medio:ID de la cintura para arriba. primer:ID cara y pecho, el plano de las emociones.
- hombro:A:B por encima del hombro de A viendo a B (el clásico de diálogo; B es quien habla).
- pov:ID lo que ve ese personaje (en terror, el narrador viendo lo raro); pov:ID:OTRO mirando a otro personaje.
- nuca:ID detrás de alguien, viendo hacia donde mira. detalle:ID un objeto clave (el celular, la puerta, el reloj, la taza).
- En amor: casi siempre primer o hombro de QUIEN HABLA en esa línea; de vez en cuando primer de quien escucha
  callado (la reacción duele más que la frase); dos o general solo para abrir, para un silencio y para cerrar.
- En terror: muchos pov y nuca del narrador; detalle en cada cosa que no cuadra; primer del otro personaje cuando habla.
- Cada línea de diálogo tiene al menos una toma de quien la dice. Cada "plantar" tiene un detalle.
- Los objetos del set van lejos entre sí (al menos 1 m) y los personajes a 1.2 a 2 m uno del otro.
- Nada de letreros, carteles, pantallas con texto ni logos en los objetos.
- El mundo siente lo que siente la historia: la primera idea siempre sale "bonita, de día de campo"; si duele, noche fría y
  pocas luces; si da miedo, oscuridad, niebla y una sola luz práctica. Nada de objetos a menos de 2 m de la cámara
  tapando caras.

REGLAS
- Toda escena lleva "linea" (la primera es la 1). Varias escenas pueden caer en la misma línea larga; van en orden.
- Todo "desde" copia palabras que aparecen tal cual en esa línea.
- PERSONAJES VIVOS: nunca alineados mirando a cámara como en foto. Se miran entre sí (en amor, girados 25 a 45 grados uno
  hacia el otro), están sentados, recargados o caminando según la acción, y cambian de pose entre sets o momentos
  ("pose" distinta en "extra" con el mismo id no se permite: usa otro set o "animar" con "mover", "girar" o "mirar").
- Cada escena lleva "plano" y ninguna dura más de 4 segundos.
- Las escenas van en el orden del guion. 18 a 30 escenas.
- JSON compacto, números con máximo 2 decimales.

Responde SOLO con JSON {{"sets": {{...}}, "escenas": [...]}}
"""

COLOR_LUZ = {"amor": ["#4D8BFF", "#FF9A4D", "#FF6FAE"], "terror": [None, None, None]}


def _plantilla(texto, genero):
    estructura = ESTRUCTURA_TERROR if genero == "terror" else ESTRUCTURA_AMOR
    return texto.format(leyes=LEYES, estructura=estructura, dopamina=DOPAMINA_FICCION).replace("GENERO", genero.upper())


def _normalizar_lineas(datos):
    """La IA a veces llama distinto a las cosas ("dialogo", "personaje", "linea" o "Nombre: texto").
    Se aceptan todas las formas y se convierten a {"quien", "texto"} con el id de cada personaje."""
    personajes = datos.get("personajes") or []
    por_nombre = {}
    for p in personajes:
        if isinstance(p, dict) and p.get("id"):
            por_nombre[str(p["id"]).lower()] = p["id"]
            if p.get("nombre"):
                por_nombre[str(p["nombre"]).lower()] = p["id"]
    crudas = None
    for k in ("lineas", "líneas", "dialogo", "diálogo", "dialogos", "guion", "script", "lines"):
        if isinstance(datos.get(k), list) and datos[k]:
            crudas = datos[k]
            break
    lineas = []
    for x in crudas or []:
        quien, texto = None, None
        if isinstance(x, dict):
            quien = x.get("quien") or x.get("personaje") or x.get("speaker") or x.get("nombre") or x.get("voz")
            texto = x.get("texto") or x.get("linea") or x.get("línea") or x.get("dialogo") or x.get("text")
        elif isinstance(x, str) and ":" in x:
            quien, _, texto = x.partition(":")
        elif isinstance(x, str):
            quien, texto = "narrador", x
        texto = str(texto or "").strip().strip('"')
        if not texto:
            continue
        q = str(quien or "narrador").strip().lower()
        q = "narrador" if q.startswith("narra") else por_nombre.get(q, q.replace(" ", "_"))
        lineas.append({"quien": q, "texto": texto})
    # todo "quien" que no exista como personaje se agrega, para que tenga voz y color
    ids = {p.get("id") for p in personajes if isinstance(p, dict)}
    for l in lineas:
        if l["quien"] != "narrador" and l["quien"] not in ids:
            personajes.append({"id": l["quien"], "nombre": l["quien"].replace("_", " ").title(), "voz": "hombre_joven"})
            ids.add(l["quien"])
    datos["personajes"] = personajes
    return lineas


def escribir_ficcion(tema, genero="terror", api_key=None, aviso=lambda *a: None):
    cliente = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
    base, lineas = {}, []
    for intento in range(2):  # si la primera respuesta llega incompleta, se pide otra vez y más directa
        pedido = f"Idea del corto: {tema}" + ("" if not intento else
                 "\n\nIMPORTANTE: tu respuesta anterior llegó incompleta. Responde SOLO el JSON, con escaleta breve y "
                 "la lista \"lineas\" completa de 12 a 22 líneas.")
        try:
            base = _llamar(cliente, _plantilla(PASO_FICCION, genero), pedido, 12000)
        except ValueError:
            base = {}
        lineas = _normalizar_lineas(base)
        if len(lineas) >= 4:
            break
        print("Corto incompleto, claves recibidas:", list(base.keys())[:15], "líneas:", len(lineas))
    if len(lineas) < 4:
        raise ValueError("El guionista no devolvió el corto completo. Intenta de nuevo.")
    base["lineas"] = lineas
    aviso("Auditando el guion con el método Zepfilms")
    try:
        aud = _llamar(cliente, _plantilla(PASO_AUDITORIA, genero), json.dumps(
            {k: base.get(k) for k in ("premisa", "personajes", "escaleta", "plantar_cosechar", "lineas", "resaltar", "cierre")},
            ensure_ascii=False), 5000)
        aud.setdefault("personajes", base.get("personajes"))
        nuevas = _normalizar_lineas(aud)
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
