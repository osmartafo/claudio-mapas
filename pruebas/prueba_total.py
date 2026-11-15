"""Auditoría anti errores: produce un video de cada tipo de punta a punta, sin gastar créditos.

Simula a Claude (guion, auditoría, dirección), a ElevenLabs (voz con silencio y tiempos por palabra) y al catálogo 3D,
y corre el camino real de la fábrica: guion, voces, música, escenas 3D, efectos y render. También revisa el menú del bot.

    python -m pruebas.prueba_total            # los cuatro tipos
    python -m pruebas.prueba_total terror     # solo uno
Termina con código 1 si algo falla.
"""
import json, os, shutil, subprocess, sys, tempfile, time, traceback

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.environ.setdefault("FRONTERAS_RELIEVE", "0")
os.environ.setdefault("FRONTERAS_3D_PROCESOS", "2")
SALIDA = tempfile.mkdtemp(prefix="prueba_total_")
os.environ["FRONTERAS_SALIDA"] = SALIDA


def cargar(n):
    return json.load(open(os.path.join(RAIZ, "pruebas", n)))


def voz_falsa(texto, ruta_mp3, ruta_palabras, **_):
    """Silencio del largo de la frase y tiempos parejos por palabra, como si hablara ElevenLabs."""
    pal, t = [], 0.1
    for w in texto.split():
        if "[" in w or "]" in w:
            continue
        pal.append({"p": w, "t0": round(t, 3), "t1": round(t + 0.27, 3)})
        t += 0.32
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", f"{t + 0.2:.2f}",
                    "-b:a", "64k", ruta_mp3], check=True)
    json.dump({"duracion": t + 0.2, "palabras": pal}, open(ruta_palabras, "w"), ensure_ascii=False)
    return ruta_mp3, ruta_palabras


def claude_falso(cliente, sistema, contenido, max_tokens, buscar=False, busquedas=None):
    s = sistema[:400]
    if "cortometrajes" in s or "script doctor con el método de Zepfilms. Recibes un cortometraje" in s or "director de animación 3D de cortometrajes" in s:
        corto = cargar("corto_terror.json") if "TERROR" in sistema[:600] else cargar("corto_amor.json")
        if "director de animación" in s:
            return {"sets": corto["sets"], "escenas": corto["escenas"]}
        if "script doctor" in s:
            return {"calificacion": 8, "problemas": ["prueba"], "funciona": ["prueba"], "lineas": corto["lineas"],
                    "resaltar": corto.get("resaltar", []), "cierre": corto.get("cierre")}
        return {k: corto[k] for k in corto if k not in ("sets", "escenas")} | {"narrador_voz": "narrador_suspenso"}
    spec = json.load(open(os.path.join(RAIZ, "ejemplos", "guitarra", "spec_cat.json")))
    if "director de animación 3D" in s:
        return {"escenas": spec["escenas"]}
    if "script doctor" in s:
        return {"calificacion": 8, "problemas": [], "funciona": [], "guion": spec["guion"]}
    return {"titulo": spec.get("titulo", "Prueba"), "descripcion": "prueba", "fuentes": [], "esqueleto": {},
            "guion": spec["guion"], "objetos": ["radio", "fox", "lantern"]}


def preparar_simulacion():
    from fronteras import guionista, guion_ficcion, voz, motor
    guionista._llamar = claude_falso
    guion_ficcion._llamar = claude_falso
    voz.generar = voz_falsa
    mapa = json.load(open(os.path.join(RAIZ, "ejemplos", "mexico-perdido", "spec.json")))
    mapa["guion"] = " ".join(w["p"] for w in json.load(open(os.path.join(RAIZ, "ejemplos", "mexico-perdido", "palabras.json")))["palabras"])
    guionista._escribir = lambda tema, api_key=None, estilo_texto="", modo="mapas", busquedas=None: dict(mapa, modo="mapas")
    os.environ.setdefault("ANTHROPIC_API_KEY", "prueba")
    motor.FPS_3D = int(os.environ.get("PRUEBA_FPS_3D", "6"))  # menos cuadros 3D para que la prueba sea rápida


def revisar_video(ruta, minimo=5.0):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height", "-of", "json", ruta],
                       capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    dur = float(d["format"]["duration"])
    tipos = {s["codec_type"] for s in d["streams"]}
    assert dur >= minimo, f"el video dura solo {dur:.1f} s"
    assert {"video", "audio"} <= tipos, f"le falta audio o video: {tipos}"
    return dur


def revisar_bot():
    from fronteras import bot, fabrica
    textos = [b for fila in bot.TECLADO.keyboard for b in fila]
    assert len(textos) == len({b.text for b in textos}), "botones repetidos en el menú"
    for b in (bot.B_CURIOSIDAD, bot.B_MAPA, bot.B_TERROR, bot.B_AMOR):
        assert b in bot.TIPOS
    casos = {"Corto de terror: el taquero que cierra a las dos": "terror", "Corto de amor: la playlist": "amor",
             "¿Por qué Bolivia no tiene mar?": "mapas", "Los billetes de Canadá son de plástico": "curiosidades",
             "Esa ranura de tu llave no está de adorno": "curiosidades"}
    for tema, esperado in casos.items():
        assert fabrica.modo_de(tema) == esperado, f"modo_de({tema!r}) dio {fabrica.modo_de(tema)}, esperaba {esperado}"
    from fronteras import banco_temas
    for lista, modo in ((banco_temas.TERROR, "terror"), (banco_temas.AMOR, "amor")):
        for t in lista:
            assert fabrica.modo_de(t) == modo, t


class _Msj:
    def __init__(self, registro):
        self.registro = registro

    async def edit_text(self, texto, **k):
        self.registro.append(("editar", texto))

    async def delete(self):
        self.registro.append(("borrar", ""))


class _BotFalso:
    """Lo mínimo de Telegram que usa el piloto: mandar textos y el video."""
    def __init__(self):
        self.registro = []

    async def send_message(self, chat, texto, **k):
        self.registro.append(("mensaje", texto))
        return _Msj(self.registro)

    async def send_video(self, chat, archivo, **k):
        self.registro.append(("video", k.get("caption", "")))
        return _Msj(self.registro)

    async def send_chat_action(self, *a, **k):
        pass


class _AppFalsa:
    def __init__(self):
        self.bot = _BotFalso()


def revisar_piloto():
    """El piloto completo: elige tema, produce, 'publica' (simulado) y manda el video al chat."""
    import asyncio
    from fronteras import bot, ajustes, charla
    for n in ajustes.OPCIONES_POR_DIA:  # horarios válidos para cada opción de videos al día
        h = ajustes.horario(n)
        assert len(h) == n and h == sorted(h) and all(0 <= m < 24 * 60 for m in h), (n, h)
    charla.responder = lambda clave, texto: ("ideas", None, ["Corto de terror: el taquero que cierra a las dos", "Por qué bostezamos"])

    async def publicar_falso(destinos, video, texto, yt_publico=False, chat=None, app=None):
        assert os.path.exists(video)
        return [f"✅ {d} (simulado)" for d in destinos], []
    bot.publicar_en = publicar_falso
    bot.destino_listo = lambda d: True
    app = _AppFalsa()
    asyncio.run(bot.piloto_uno(app, 12345))
    tipos = [r[0] for r in app.bot.registro]
    assert "video" in tipos, f"el piloto no mandó video: {app.bot.registro}"
    return app.bot.registro


def main():
    preparar_simulacion()
    from fronteras import fabrica
    pedidos = {"curiosidades": "Esa tapita de tu guitarra no está de adorno", "mapas": "México perdido",
               "terror": "Corto de terror: el taquero que cierra a las dos", "amor": "Corto de amor: la playlist"}
    solo = sys.argv[1:] or list(pedidos) + ["piloto"]
    fallas = []
    try:
        revisar_bot()
        print("✅ menú y tipos del bot")
    except Exception:
        fallas.append("bot")
        traceback.print_exc()
    if "piloto" in solo:
        solo = [m for m in solo if m != "piloto"]
        try:
            t0 = time.time()
            reg = revisar_piloto()
            print(f"✅ piloto automático: produjo y entregó en {time.time() - t0:.0f} s  {reg[-1][1][:80]}")
        except Exception:
            fallas.append("piloto")
            print("❌ piloto")
            traceback.print_exc()
    for modo in solo:
        t0 = time.time()
        try:
            video, texto = fabrica.hacer_video(pedidos[modo], aviso=lambda *a: None, nuevo=True, forzar={"modo": modo})
            dur = revisar_video(video)
            assert texto.strip(), "sin descripción"
            print(f"✅ {modo}: {dur:.1f} s de video en {time.time() - t0:.0f} s  {video}")
        except Exception:
            fallas.append(modo)
            print(f"❌ {modo}")
            traceback.print_exc()
    print("\nSALIDA", SALIDA)
    if fallas:
        print("FALLARON:", ", ".join(fallas))
        sys.exit(1)
    print("TODO BIEN")


if __name__ == "__main__":
    main()
