"""El guionista de FRONTERAS: convierte un tema en guion verificado + escenas, en una sola llamada a Claude."""
import json, os, re
from json_repair import repair_json
import anthropic

MODELO = os.environ.get("FRONTERAS_MODELO", "claude-haiku-5-5")

SISTEMA = """Eres el guionista y director de FRONTERAS, un canal de YouTube de documentales cortos de historia y geografía.
Personalidad del canal: documental premium, elegante y sobrio, como una serie de Netflix. Voz grave, ritmo ágil de short.
Nada de chistes, nada de exageraciones, nada de clickbait barato. Curiosidad, rigor y belleza.

TU TRABAJO
1. Investiga el tema con la búsqueda web: una o dos búsquedas bien hechas bastan (2 fuentes fiables). Si un dato no se puede confirmar, no lo uses.
2. Escribe un guion en español neutro de México de 125 a 150 palabras (unos 50 a 58 segundos de voz)
   con esta estructura de retención, pensada para que nadie deslice al siguiente video:
   GANCHO (0 a 3 s). Una sola frase que abre una pregunta imposible de ignorar: un dato que parece falso,
     una contradicción o algo que el espectador cree saber y no es así. Nada de saludos ni presentaciones.
   PROMESA (3 a 8 s). Dile por qué debe quedarse: algo como "y la razón es más extraña de lo que crees".
   ESCALADA (8 a 40 s). Tres giros, cada uno empieza con "pero", "y entonces" o "lo que nadie esperaba".
     Cada giro sube lo que está en juego con una cifra, un año o un nombre concreto.
   REENGANCHE (alrededor del segundo 25). Una frase que abre un nuevo bucle: "y eso no fue lo peor".
   REVELACIÓN (40 a 52 s). Se cierra la pregunta del gancho con el dato más fuerte del video.
   CIERRE EN BUCLE (últimos 3 s). La última frase conecta con la primera, para que al repetirse el video
     se sienta como continuación y la gente lo vea dos veces.
   Frases de 4 a 10 palabras. Una idea por frase. Verbos fuertes. Cero relleno.
   Escribe los años y cifras con letra (mil ochocientos cuarenta y ocho, quince millones) para que la voz los lea bien.
3. Dirige las escenas del video como un editor de shorts: UN CAMBIO FUERTE DE TOMA CADA 2.5 A 3.5 SEGUNDOS.
   Eso son de 16 a 22 escenas. Cada escena empieza cuando la voz dice su "desde".
   Ritmo visual que se alterna sin repetir dos veces seguidas el mismo tipo de toma
     mapa abierto (continente) · acercamiento fuerte (país, estado o ciudad) · dibujo animado (broll) ·
     zona que se pinta · flecha que avanza · pin con nombre · cifra gigante
   El gancho siempre abre con una toma que ya se mueve y una cifra, año o zona pintada desde el segundo cero.

FORMATO DE RESPUESTA
Responde SOLO con un objeto JSON válido, sin texto antes ni después, con esta forma:
{
  "titulo": "título para YouTube, máximo 70 caracteres",
  "descripcion": "descripción para YouTube de 2 a 4 frases, con 3 hashtags al final",
  "fuentes": ["url1", "url2"],
  "guion": "texto completo que leerá la voz",
  "latitud_media": 30,
  "territorios": {"nombre_corto": [[lon, lat], [lon, lat], ...]},
  "escenas": [
    {
      "desde": "palabras EXACTAS del guion donde empieza la escena (2 a 4 palabras)",
      "camara": [lon_centro, lat_centro, ancho_en_grados],
      "año": "1848",
      "titulo": "texto corto y elegante, máximo 5 palabras",
      "cifra": "15 millones de dólares (máximo 4 palabras)",
      "zonas": [{"zona": "pais:MEX", "estilo": "oro", "desde": "palabras exactas", "mantener": false}],
      "etiquetas": [{"texto": "California", "lugar": [lon, lat], "desde": "palabras exactas"}],
      "pines": [{"texto": "Ciudad de México", "lugar": [lon, lat], "desde": "palabras exactas"}],
      "flechas": [{"puntos": [[lon, lat], [lon, lat], [lon, lat]], "desde": "palabras exactas"}],
      "broll": {"motivo": "muralla", "desde": "palabras exactas"}
    }
  ]
}

REGLAS DE LAS ESCENAS
- La primera escena no lleva "desde" (empieza en el segundo 0).
- Todo "desde" debe copiar palabras que aparecen tal cual en el guion, en orden.
- "año", "titulo", "cifra", "zonas", "etiquetas", "pines" y "flechas" son opcionales. Cada escena con 1 o 2 cosas, nunca vacía.
- "titulo" solo en 5 a 7 escenas clave (gancho, cada giro, revelación). Las demás escenas cambian con cámara, zona, cifra o dibujo.
- "año" pon el año en cada escena donde cambie la época: el año corre como contador y suena un golpe, eso engancha.
- Textos en pantalla cortos para que se lean en un celular: "titulo" máximo 5 palabras, "cifra" máximo 4 palabras,
  etiquetas y pines máximo 3 palabras. Nada de frases largas en pantalla, eso lo dice la voz.
- Los "desde" van de 2 a 3 palabras para que los cortes caigan exactos.
- Zonas válidas: "pais:XXX" con el código ISO de 3 letras (MEX, USA, ESP, GBR, RUS, CHN...),
  "estado:ISO:nombre" para estados o provincias (estado:USA:texas, estado:MEX:chiapas, estado:ESP:andalucia),
  o "territorio:nombre_corto" para un polígono que tú defines en "territorios" (límites históricos aproximados, de 6 a 14 puntos).
- Estilos: "oro" (protagonista), "rojo" (pérdida, conflicto), "crema" (contexto), "contorno" (solo borde), "foco" (oscurece todo lo demás).
- "camara": el video es vertical, así que el ancho visible va de 3 grados (una ciudad) a 60 grados (un continente).
  Encuadra para que lo importante quede en el centro. Entre escenas de mapa seguidas cambia mucho el ancho
  (por ejemplo de 50 a 8 grados) para que el corte se sienta como golpe.
- "broll" es un dibujo de líneas animado que tapa el mapa unos 3 a 5 segundos e ilustra lo que dice la voz.
  Motivos disponibles: muralla, barco, tratado, ejercito, ciudad, tren, avion, montanas, rio, corona, bandera,
  batalla, multitud, reloj, puente, brujula, frontera, libro, fuego, dinero.
  Usa de 5 a 7 broll por video, en escenas donde la voz menciona algo que se puede dibujar
  (un muro o fortaleza: muralla; una firma o acuerdo: tratado; una guerra: batalla; una venta o pago: dinero;
  un viaje por mar: barco; un rey o imperio: corona; independencia: bandera; población: multitud; el paso del tiempo: reloj).
  Nunca dos broll seguidos: entre uno y otro siempre va al menos una escena de mapa. La primera y la última escena son de mapa.
  Una escena de broll puede no llevar "camara" (se queda la del mapa anterior) y casi siempre lleva "titulo" o "cifra".
- JSON compacto: coordenadas con máximo 2 decimales, sin campos vacíos ni listas vacías, sin explicaciones.
- Coordenadas reales y precisas (lon negativa al oeste, lat negativa al sur).
"""


SISTEMA_CURIOSIDADES = """Eres el guionista y director de un canal de YouTube de shorts de curiosidades, cultura general y "por qué las cosas son como son".
Tono: el amigo listo que te explica algo cotidiano que siempre viste y nunca entendiste. Cálido, directo, con chispa, en español de México.
Nada de clickbait falso: cada dato es verdadero y verificado. Si es un mito, se desmiente con evidencia.

TIPOS DE TEMA QUE FUNCIONAN
- La pieza que "no está de adorno": esa tapita, ese hoyito, esa ranura, esas rueditas (en objetos de casa, herramientas, máquinas).
- El mito que todos creen: "la regla de los 5 segundos no existe", "bostezar no sirve para respirar más".
- La pregunta rara de la naturaleza o el cuerpo: "por qué la puerta del iglú está más abajo que el piso".
- Historia y geografía con giro, cuando el tema lo pide (ahí se usan mapas).

TU TRABAJO
1. Investiga con la búsqueda web (una o dos búsquedas, 2 fuentes fiables). Lo que no se pueda confirmar, no va.
2. Escribe un guion de 110 a 140 palabras (45 a 55 segundos de voz) con esta estructura de retención
   GANCHO (0 a 3 s). Señala algo concreto que el espectador tiene o conoce y rompe lo que cree.
     Ejemplos de forma: "Esa tapita en la cabeza de tu guitarra no está de adorno." "Nunca te has comido una araña dormido."
   PROMESA (3 a 7 s). "Y la razón es más ingeniosa de lo que crees."
   EXPLICACIÓN EN 3 PASOS (7 a 40 s). Cómo funciona, paso por paso, como si lo armaras frente a la cámara.
     Cada paso con un verbo de acción y un detalle concreto (una medida, un número, un material).
   REENGANCHE (cerca del segundo 25). "Pero aquí viene lo bueno."
   REMATE (40 a 52 s). El dato que hace decir "no manches".
   CIERRE EN BUCLE (últimos 3 s). La última frase conecta con la primera para que el video se vea dos veces.
   Frases de 4 a 10 palabras. Habla en segunda persona ("tu", "te"). Números y años escritos con letra.
3. Dirige el video con UN CORTE CADA 2.5 A 4 SEGUNDOS: de 12 a 18 escenas. Cada escena empieza cuando la voz dice su "desde".
   Hay tres tipos de escena y se mezclan
   - "3d": una animación 3D estilo caricatura del objeto o mecanismo (es el tipo principal, 60 a 80 por ciento de las escenas).
   - "ilustracion": una tarjeta con un dibujo animado de líneas y texto grande, para ideas abstractas (10 a 25 por ciento).
   - "mapa": solo si el tema tiene un lugar o una historia geográfica (usa el formato de mapa, ver abajo).

FORMATO DE RESPUESTA
Responde SOLO con un objeto JSON válido, sin texto antes ni después
{
  "titulo": "título para YouTube, máximo 70 caracteres, puede llevar un emoji al final",
  "descripcion": "2 a 4 frases con 3 hashtags al final",
  "fuentes": ["url1", "url2"],
  "guion": "texto completo que leerá la voz",
  "latitud_media": 30,
  "escenas": [ ... ]
}

ESCENA 3D
{"desde": "palabras exactas", "tipo": "3d", "titulo": "máximo 5 palabras, opcional", "cifra": "opcional, máximo 4 palabras",
 "modelo": {
   "fondo": "#BFE6F7", "suelo": "#9BD36A",
   "objetos": [
     {"id": "mesa", "forma": "caja", "tam": [4, 0.2, 2], "pos": [0, 1, 0], "rot": [0, 0, 0], "color": "#E3B57A"},
     {"id": "tornillo", "forma": "cilindro", "radio": 0.05, "alto": 0.6, "pos": [1, 1.3, 0], "color": "#CCCCCC", "padre": "mesa"}
   ],
   "camara": [{"t": 0, "pos": [5, 4, 6], "mira": [0, 1, 0]}, {"t": 1, "pos": [2, 2, 2.5], "mira": [1, 1.2, 0]}],
   "animar": [{"id": "tornillo", "t0": 0.3, "t1": 0.8, "girar": [0, 720, 0]}],
   "etiquetas": [{"texto": "rosca", "en": [1, 1.8, 0], "t0": 0.4}],
   "flechas": [{"de": [2, 2.5, 1], "a": [1.1, 1.5, 0], "t0": 0.5}]
 }}
Reglas del modelo 3D
- Unidades en metros aproximados; el suelo está en y = 0; y es hacia arriba. Construye el objeto con 4 a 18 formas simples bien colocadas
  que se toquen entre sí (nada flotando salvo que flote de verdad). Piensa el objeto real y sus proporciones antes de escribir.
- Formas: "caja" (tam [ancho, alto, fondo]), "cilindro" (radio, alto, opcional radio_arriba), "cono" (radio, alto), "esfera" (radio),
  "toro" (radio, grosor), "capsula" (radio, alto), "cuna" (tam, prisma triangular), "engrane" (radio, alto, dientes),
  "resorte" (radio, alto, vueltas, grosor), "tubo" (puntos [[x,y,z],...], grosor; para cables, cuerdas y mangueras), "plano" (tam [ancho, alto]).
  Los cilindros, conos y cápsulas están de pie (eje y). "rot" en grados [x, y, z]. "escala" opcional. "transparente": true para ver por dentro.
  "padre": id de otro objeto para que se mueva con él (su "pos" es relativa al padre).
- Colores planos y alegres de caricatura: maderas #E3B57A #C99A5B, metal #CFCFCF, plástico blanco #F4F4F4, negro #2B2B2B,
  rojo #FF5A4E, amarillo #FFD23F, azul #4DA3FF, verde #6BCB5A. "fondo" es el cielo y "suelo" el pasto; "suelo": null si es un fondo liso.
- "camara": de 2 a 4 puntos con "t" de 0 a 1 dentro de la escena. Siempre se mueve: abre amplio y se acerca al detalle que explica la voz,
  o rodea el objeto. La cámara mira al centro del detalle. Distancia típica de 1.5 a 8 metros.
- "animar": lo que se mueve y explica el mecanismo. Cada animación lleva "id", "t0", "t1" (0 a 1) y una o más de
  "girar" [grados x, y, z], "mover" [x, y, z] (desplazamiento), "escala" (factor final), "aparece": true (brota con rebote),
  "desaparece": true, "resaltar": true (parpadea en amarillo), "girar_siempre" [x, y, z] (gira toda la escena), "rebote": true.
- "etiquetas": nombres cortos (1 a 2 palabras) que salen junto a la pieza que se explica. "flechas": señalan la pieza, rojas por defecto.
- Escenas 3D seguidas pueden repetir el mismo objeto con otra cámara y otra animación (como cortes de cámara del mismo set):
  copia el objeto igual y cambia "camara" y "animar". Eso da continuidad.

ESCENA ILUSTRACION
{"desde": "palabras exactas", "tipo": "ilustracion", "motivo": "reloj", "titulo": "texto grande, máximo 5 palabras", "cifra": "opcional"}
Motivos: muralla, barco, tratado, ejercito, ciudad, tren, avion, montanas, rio, corona, bandera, batalla, multitud, reloj, puente,
brujula, frontera, libro, fuego, dinero.

ESCENA MAPA (solo si el tema lo pide)
{"desde": "palabras exactas", "camara": [lon_centro, lat_centro, ancho_en_grados], "titulo": "...", "zonas": [{"zona": "pais:MEX", "estilo": "oro"}],
 "pines": [{"texto": "Ciudad", "lugar": [lon, lat]}], "etiquetas": [{"texto": "...", "lugar": [lon, lat]}]}

REGLAS GENERALES
- La primera escena no lleva "desde" y es 3D: el gancho muestra el objeto desde el segundo cero.
- Todo "desde" copia 2 a 3 palabras que aparecen tal cual en el guion, en orden.
- "titulo" en 4 a 6 escenas clave. Textos en pantalla cortos (titulo máximo 5 palabras, cifra máximo 4).
- Nunca dos ilustraciones seguidas.
- JSON compacto: números con máximo 2 decimales, sin campos vacíos, sin explicaciones.
"""


def escribir(tema, api_key=None, estilo_texto="", modo="mapas"):
    cliente = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
    # el estilo va en el mensaje y no en el sistema, así el sistema se queda en caché y sale más barato
    mensajes = [{"role": "user", "content": f"Tema del video: {tema}\n\n{estilo_texto}".strip()}]
    # se pide en streaming: con un tope alto de salida la API lo exige y nunca se queda corto el guion
    with cliente.messages.stream(
        model=MODELO,
        max_tokens=int(os.environ.get("FRONTERAS_TOKENS", "32000")),
        system=[{"type": "text", "text": SISTEMA_CURIOSIDADES if modo == "curiosidades" else SISTEMA, "cache_control": {"type": "ephemeral"}}],
        messages=mensajes,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": int(os.environ.get("FRONTERAS_BUSQUEDAS", "3"))}],
    ) as flujo:
        r = flujo.get_final_message()
    texto = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
    i = texto.find("{")
    if i < 0:
        raise ValueError(f"El guionista no devolvió el guion (motivo {r.stop_reason}). Intenta de nuevo.")
    spec = json.loads(repair_json(texto[i:texto.rfind("}") + 1] if r.stop_reason != "max_tokens" else texto[i:]))
    # si se cortó, se rescata lo que alcanzó a escribir con tal de que tenga guion y suficientes escenas
    if not isinstance(spec, dict) or not spec.get("guion") or len(spec.get("escenas") or []) < (4 if modo == "curiosidades" else 6):
        raise ValueError(f"El guionista no terminó el guion (motivo {r.stop_reason}). Intenta de nuevo.")
    spec.setdefault("formato", "vertical")
    spec["modo"] = modo
    return spec
