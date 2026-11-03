"""La plática del bot. Entiende lo que le escribes (o le dices por audio) y decide si platicar o hacer un video."""
import os
from collections import defaultdict, deque

import anthropic
import requests
from json_repair import repair_json
import json

MODELO = os.environ.get("FRONTERAS_MODELO_CHARLA", "claude-haiku-5-5")

SISTEMA = """Eres el asistente de FRONTERAS, un canal de YouTube de documentales cortos de historia y geografía con mapas.
Hablas con el dueño del canal por Telegram, en español de México, como un colega amable y directo.

REGLAS
- Respuestas CORTAS. Máximo 4 líneas, salvo que te pidan una lista.
- Sin markdown, sin asteriscos, sin negritas. Texto plano.
- Si te piden ideas o temas, pon de 6 a 8 en la lista "ideas": preguntas cortas (máximo 9 palabras cada una), sin explicación.
  Temas sencillos y populares que cualquiera entiende, sobre por qué un país, frontera, ciudad o ruta es como es.
  Que no se repitan con ideas que ya diste en esta plática. En "respuesta" pon solo una frase corta de introducción.
- Si el usuario pide un video sobre un tema concreto, o elige uno de la lista ("el 3", "hazme ese", "va con el de Alaska"),
  decide hacer el video. Si es ambiguo o el mensaje no tiene sentido, pregunta en una línea qué tema quiere.
- Si pide formato horizontal o "video largo", el video va horizontal.

FORMATO
Responde SIEMPRE solo con JSON
{"respuesta": "lo que le dices", "ideas": [], "video": null}
con ideas
{"respuesta": "Aquí van unas que funcionan muy bien", "ideas": ["¿Por qué Bolivia no tiene mar?", "..."], "video": null}
o, cuando toca hacer un video
{"respuesta": "Va, empiezo con ...", "video": {"tema": "pregunta clara del tema", "horizontal": false}}
"""

historial = defaultdict(lambda: deque(maxlen=16))


def responder(chat_id, texto):
    h = historial[chat_id]
    h.append({"role": "user", "content": texto})
    c = anthropic.Anthropic()
    r = c.messages.create(model=MODELO, max_tokens=1500, messages=list(h),
                         system=[{"type": "text", "text": SISTEMA, "cache_control": {"type": "ephemeral"}}])
    salida = "".join(b.text for b in r.content if b.type == "text").strip()
    try:
        datos = json.loads(repair_json(salida))
        if not isinstance(datos, dict):
            raise ValueError
    except Exception:
        datos = {"respuesta": salida or "No te entendí, ¿me lo repites?", "video": None}
    h.append({"role": "assistant", "content": json.dumps(datos, ensure_ascii=False)})
    ideas = [str(i).strip() for i in (datos.get("ideas") or []) if str(i).strip()][:8]
    return datos.get("respuesta") or "Va.", datos.get("video"), ideas


def transcribir(audio_bytes):
    """Convierte una nota de voz en texto con ElevenLabs."""
    r = requests.post("https://api.elevenlabs.io/v1/speech-to-text",
                      headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
                      data={"model_id": "scribe_v1", "language_code": "spa"},
                      files={"file": ("nota.ogg", audio_bytes, "audio/ogg")}, timeout=120)
    r.raise_for_status()
    return r.json().get("text", "").strip()
