"""Voz de FRONTERAS con ElevenLabs: una sola toma, con el segundo exacto de cada palabra.

Usa el endpoint "with-timestamps", así no hace falta transcribir después (ahorra créditos y tiempo).
"""
import base64, json, logging, os
import requests

VOZ = os.environ.get("FRONTERAS_VOZ", "tBkfgTXKnmHoYewBvh7e")  # Eduardo, español mexicano
VOZ_RESPALDO = os.environ.get("FRONTERAS_VOZ_RESPALDO", "JBFqnCBsd6RMkjVDRZzb")  # voz base de ElevenLabs, multilingüe
MODELO = os.environ.get("FRONTERAS_MODELO_VOZ", "eleven_multilingual_v2")


def generar(texto, ruta_mp3, ruta_palabras, api_key=None):
    key = api_key or os.environ["ELEVENLABS_API_KEY"]
    intentos = [
        {"stability": 0.55, "similarity_boost": 0.8, "style": 0.15, "speed": 0.95},
        {"stability": 0.55, "similarity_boost": 0.8},
    ]
    r = None
    combinaciones = [(VOZ, a) for a in intentos] + [(VOZ_RESPALDO, intentos[1])]
    for voz_id, ajustes in combinaciones:
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voz_id}/with-timestamps",
            headers={"xi-api-key": key, "Content-Type": "application/json"},
            params={"output_format": "mp3_44100_128"},
            json={"text": texto, "model_id": MODELO, "voice_settings": ajustes},
            timeout=300,
        )
        if r.ok:
            break
        logging.warning("ElevenLabs rechazó %s %s: %s", voz_id, r.status_code, r.text[:500])
    if not r.ok:
        try:
            detalle = r.json().get("detail", r.text)
        except Exception:
            detalle = r.text
        if isinstance(detalle, dict):
            detalle = detalle.get("message") or detalle.get("status") or str(detalle)
        raise RuntimeError(f"ElevenLabs dijo {r.status_code}: {str(detalle)[:300]}")
    d = r.json()
    open(ruta_mp3, "wb").write(base64.b64decode(d["audio_base64"]))
    al = d.get("normalized_alignment") or d["alignment"]
    palabras = a_palabras(al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"])
    duracion = palabras[-1]["t1"] + 0.3 if palabras else 0
    json.dump({"duracion": duracion, "palabras": palabras}, open(ruta_palabras, "w"), ensure_ascii=False)
    return ruta_mp3, ruta_palabras


def a_palabras(chars, ini, fin):
    """Junta los caracteres con su tiempo en palabras."""
    palabras, act, t0, t1 = [], "", None, None
    for ch, a, b in zip(chars, ini, fin):
        if ch.isspace():
            if act:
                palabras.append({"p": act, "t0": round(t0, 3), "t1": round(t1, 3)})
            act, t0 = "", None
            continue
        if t0 is None:
            t0 = a
        act += ch
        t1 = b
    if act:
        palabras.append({"p": act, "t0": round(t0, 3), "t1": round(t1, 3)})
    return palabras
