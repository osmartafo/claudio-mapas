"""Voz de FRONTERAS con ElevenLabs: una sola toma, con el segundo exacto de cada palabra.

Usa el endpoint "with-timestamps", así no hace falta transcribir después (ahorra créditos y tiempo).
"""
import base64, json, logging, os
import requests

VOZ = os.environ.get("FRONTERAS_VOZ", "tBkfgTXKnmHoYewBvh7e")  # Eduardo, español mexicano
VOZ_RESPALDO = os.environ.get("FRONTERAS_VOZ_RESPALDO", "JBFqnCBsd6RMkjVDRZzb")  # voz base de ElevenLabs, multilingüe
MODELO = os.environ.get("FRONTERAS_MODELO_VOZ", "eleven_v3")
MODELOS = [MODELO, "eleven_v4", "eleven_multilingual_v2"]


def generar(texto, ruta_mp3, ruta_palabras, api_key=None, voz_id=None, respaldos=None, ajustes_voz=None):
    """respaldos: voces de reserva propias (por ejemplo otra voz de mujer), en vez de las de siempre."""
    key = api_key or os.environ["ELEVENLABS_API_KEY"]
    intentos = [
        {"stability": 0.55, "similarity_boost": 0.8, "style": 0.15, "speed": 0.95},
        {"stability": 0.55, "similarity_boost": 0.8},
    ]
    r = None
    principal = voz_id or VOZ
    v3 = ajustes_voz or {"stability": 0.5}
    combinaciones = [(principal, m, v3 if m in ("eleven_v3", "eleven_v4") else intentos[1]) for m in dict.fromkeys(MODELOS)]
    combinaciones.append((principal, "eleven_multilingual_v2", intentos[0]))
    if respaldos is not None:
        for r_ in respaldos:
            combinaciones.append((r_, "eleven_v3", v3))
            combinaciones.append((r_, "eleven_multilingual_v2", intentos[1]))
    else:
        if principal != VOZ:
            combinaciones.append((VOZ, "eleven_v3", {"stability": 0.5}))
        combinaciones.append((VOZ_RESPALDO, "eleven_multilingual_v2", intentos[0]))
    for voz_id, modelo, ajustes in combinaciones:
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voz_id}/with-timestamps",
            headers={"xi-api-key": key, "Content-Type": "application/json"},
            params={"output_format": "mp3_44100_128"},
            json={"text": texto, "model_id": modelo, "voice_settings": ajustes},
            timeout=300,
        )
        if r.ok:
            break
        logging.warning("ElevenLabs rechazó %s con %s, %s: %s", voz_id, modelo, r.status_code, r.text[:300])
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
    # las acotaciones de actuación de eleven_v3 ([susurra], [sighs]) no se escriben en pantalla
    palabras = [w for w in palabras if "[" not in w["p"] and "]" not in w["p"]]
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



# ---------------- varias voces: cortometrajes con diálogo ----------------
# reparto por tipo de voz; cada una con reservas del mismo género por si la voz no está en la cuenta
REPARTO = {
    "narrador_suspenso": ["W6Z2FAa578IKOGSVo2sA", "dHGPYv4XsWTepHhOTsGA", "tBkfgTXKnmHoYewBvh7e"],
    "narradora_drama":   ["tBeo5yEkFpJY7qtZJzxf", "S5sGA291a7wLwgXoIAP8", "EXAVITQu4vr4xnSDxMaL"],
    "hombre_joven":      ["pC0w7bOSDTlgiOCrNBX3", "vPrtQbTwtAoP87VnQmID", "tBkfgTXKnmHoYewBvh7e"],
    "hombre_maduro":     ["HIkzxzvsigFIynXHHKhU", "LnGOA2SxH2fX1e1iNzEp", "tBkfgTXKnmHoYewBvh7e"],
    "hombre_joven_b":    ["vPrtQbTwtAoP87VnQmID", "qXvyMc4erc4RzqXLpiiR", "JBFqnCBsd6RMkjVDRZzb"],
    "mujer_joven":       ["KVJNlB9xei0FCE8ekWnI", "spPXlKT5a4JMfbhPRAzA", "EXAVITQu4vr4xnSDxMaL"],
    "mujer_joven_b":     ["spPXlKT5a4JMfbhPRAzA", "JYyJjNPfmNJdaby8LdZs", "XrExE9yKIg1WjnnlVkGX"],
    "mujer_madura":      ["z1ngDYs2H24Xsd8ts3az", "hHjbwzYZW17oh0p05AKv", "XrExE9yKIg1WjnnlVkGX"],
    "nino":              ["kKcRoM4gR6HLJt6Zupbs", "pC0w7bOSDTlgiOCrNBX3", "tBkfgTXKnmHoYewBvh7e"],
}
EXTRA = os.environ.get("FRONTERAS_REPARTO")  # JSON opcional {"mujer_joven": ["id", ...]} para cambiar el reparto sin tocar código
if EXTRA:
    try:
        REPARTO.update(json.loads(EXTRA))
    except Exception:
        pass


def _pcm(ruta):
    import subprocess, numpy as np
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", ruta, "-f", "s16le", "-ac", "1", "-ar", "44100", "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype="<i2")


def generar_dialogo(lineas, voces, ruta_mp3, ruta_palabras, api_key=None):
    """lineas: [{"quien": "narrador", "texto": "..."}]; voces: {"narrador": "narrador_suspenso", ...}.
    Graba cada línea con la voz de su personaje (en paralelo, para tardar menos), las une con pausas naturales
    y guarda el segundo exacto de cada palabra, marcada con quién la dice."""
    import tempfile, subprocess, numpy as np
    from concurrent.futures import ThreadPoolExecutor
    tmp = tempfile.mkdtemp(prefix="dialogo_")
    usadas = {}

    def una(i):
        ln = lineas[i]
        tipo = voces.get(ln["quien"], "narrador_suspenso")
        opciones = REPARTO.get(tipo, REPARTO["narrador_suspenso"])
        ajustes = {"stability": 0.35 if ln.get("emocion") else 0.5}
        generar(ln["texto"], f"{tmp}/{i}.mp3", f"{tmp}/{i}.json", api_key=api_key, voz_id=opciones[0],
                respaldos=opciones[1:], ajustes_voz=ajustes)
        return i

    with ThreadPoolExecutor(3) as ex:
        list(ex.map(una, range(len(lineas))))
    SR = 44100
    partes, palabras, t = [], [], 0.0
    for i, ln in enumerate(lineas):
        audio = _pcm(f"{tmp}/{i}.mp3")
        d = json.load(open(f"{tmp}/{i}.json"))
        for w in d["palabras"]:
            palabras.append({"p": w["p"], "t0": round(w["t0"] + t, 3), "t1": round(w["t1"] + t, 3), "quien": ln["quien"]})
        partes.append(audio)
        t += len(audio) / SR
        siguiente = lineas[i + 1]["quien"] if i + 1 < len(lineas) else None
        pausa = ln.get("pausa", 0.55 if siguiente != ln["quien"] else 0.3)
        partes.append(np.zeros(int(pausa * SR), dtype="<i2"))
        t += pausa
    todo = np.concatenate(partes)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-", "-b:a", "160k", ruta_mp3],
                   input=todo.tobytes(), check=True)
    duracion = palabras[-1]["t1"] + 0.3 if palabras else t
    json.dump({"duracion": duracion, "palabras": palabras}, open(ruta_palabras, "w"), ensure_ascii=False)
    return ruta_mp3, ruta_palabras
