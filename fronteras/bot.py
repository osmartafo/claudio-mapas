"""Bot de Telegram de FRONTERAS.

Platica contigo por texto o nota de voz, te propone ideas como botones y produce los videos.
"""
import asyncio, html, logging, os, time

from telegram import (Update, InlineKeyboardButton as Boton, InlineKeyboardMarkup as Botones,
                      ReplyKeyboardMarkup, BotCommand)
from telegram.constants import ParseMode, ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

from .fabrica import hacer_video
from . import youtube, facebook, charla, ajustes, monitor, estilos, looks, tiktok

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # no imprimir el token del bot en los registros

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANNER = f"{RAIZ}/assets/bot/bienvenida.jpg"
PERMITIDOS = {int(x) for x in os.environ.get("TELEGRAM_USUARIOS", "").replace(" ", "").split(",") if x}

cola = asyncio.Lock()
estado = {"ahora": None, "inicio": 0.0, "en_fila": 0}
formato = {}          # chat_id -> "vertical" | "horizontal"
ideas_guardadas = {}  # id -> tema
# los videos hechos se guardan en el disco permanente para que sus botones sigan sirviendo tras una actualización
_HECHOS = "/data/hechos.json" if os.path.isdir("/data") else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hechos.json")


def _cargar_hechos():
    try:
        import json as _j
        d = {int(k): tuple(v) for k, v in _j.load(open(_HECHOS)).items()}
        return {k: v for k, v in d.items() if os.path.exists(v[0])}
    except Exception:
        return {}


def _guardar_hechos():
    try:
        import json as _j
        ultimos = dict(sorted(hechos.items())[-30:])
        _j.dump({str(k): list(v) for k, v in ultimos.items()}, open(_HECHOS, "w"), ensure_ascii=False)
    except Exception:
        logging.exception("guardar hechos")


hechos = _cargar_hechos()  # id -> (video, texto, tema, horizontal)
contador = {"idea": 0, "video": max(hechos, default=0)}

# botones del teclado de abajo
B_IDEAS, B_NUEVO, B_FORMATO, B_ESTADO, B_AYUDA = "💡 Ideas", "🎬 Nuevo video", "📐 Formato", "📊 Estado", "❓ Ayuda"
B_ESTILO, B_PILOTO = "🎨 Estilo y narrador", "🤖 Piloto automático"
TECLADO = ReplyKeyboardMarkup([[B_IDEAS, B_NUEVO], [B_ESTILO, B_PILOTO], [B_FORMATO, B_ESTADO, B_AYUDA]], resize_keyboard=True,
                              input_field_placeholder="Escríbeme o mándame un audio…")

PASOS = ["Guion investigado y verificado", "Voz grabada", "Música original", "Mapas animados"]
PASOS_AHORA = ["Investigando y escribiendo el guion", "Grabando la voz", "Componiendo la música", "Animando los mapas"]


def e(t):
    return html.escape(str(t))


def autorizado(update: Update) -> bool:
    return not PERMITIDOS or update.effective_user.id in PERMITIDOS


def es_horizontal(chat_id):
    return formato.get(chat_id) == "horizontal"


def explica(err):
    t = str(err)
    if "credit balance is too low" in t:
        return "💳 Tu cuenta de Claude API se quedó sin saldo. Recarga en platform.claude.com, en Billing."
    if "authentication" in t.lower() or "invalid x-api-key" in t.lower():
        return "🔑 La llave de Claude no es válida. Revisa ANTHROPIC_API_KEY en Railway."
    if "elevenlabs" in t.lower() and ("quota" in t.lower() or "credits" in t.lower() or "401" in t):
        return "🎙️ ElevenLabs rechazó la voz. Revisa tus créditos o la llave ELEVENLABS_API_KEY."
    return f"⚠️ Algo falló\n<code>{e(type(err).__name__)}: {e(t[:400])}</code>"


def barra(fraccion, largo=12):
    fraccion = max(0.0, min(1.0, fraccion))
    llenos = round(fraccion * largo)
    return "▰" * llenos + "▱" * (largo - llenos) + f"  {round(fraccion * 100)}%"


def tarjeta_progreso(tema, paso, sub=0.0, horizontal=False):
    lineas = []
    for i, nombre in enumerate(PASOS, start=1):
        if i < paso:
            lineas.append(f"✅ {nombre}")
        elif i == paso:
            lineas.append(f"⏳ <b>{PASOS_AHORA[i - 1]}…</b>")
        else:
            lineas.append(f"▫️ {nombre}")
    pesos = [0.25, 0.10, 0.05, 0.60]  # cuánto tarda cada paso, más o menos
    total = sum(pesos[:paso - 1]) + pesos[paso - 1] * sub
    seg = int(time.time() - estado["inicio"])
    fmt = "Horizontal 16:9" if horizontal else "Vertical 9:16"
    return (f"🎬 <b>{e(tema)}</b>\n<i>{fmt}</i>\n\n" + "\n".join(lineas) +
            f"\n\n<code>{barra(total)}</code>\n⏱️ {seg // 60}:{seg % 60:02d}")


def botones_ideas(ideas):
    filas = []
    for tema in ideas:
        contador["idea"] += 1
        ideas_guardadas[contador["idea"]] = tema
        filas.append([Boton(f"🎬 {tema}", callback_data=f"idea:{contador['idea']}")])
    filas.append([Boton("🔄 Más ideas", callback_data="mas"), Boton("✍️ Mi propio tema", callback_data="propio")])
    return Botones(filas)


def botones_video(n):
    filas = []
    if facebook.configurado():
        filas.append([Boton("🚀 Publicar en Facebook e Instagram", callback_data=f"meta:{n}")])
        filas.append([Boton("📘 Solo Facebook", callback_data=f"fb:{n}"), Boton("📸 Solo Instagram", callback_data=f"ig:{n}")])
    redes = []
    if youtube.configurado():
        redes.append(Boton("▶️ Subir a YouTube", callback_data=f"yt:{n}"))
    if tiktok.configurado():
        redes.append(Boton("🎵 Subir a TikTok", callback_data=f"tt:{n}"))
    if redes:
        filas.append(redes)
    filas.append([Boton("📋 Texto para YouTube", callback_data=f"txt:{n}"), Boton("🔁 Otra versión", callback_data=f"otra:{n}")])
    filas.append([Boton("🎨 Mismo video, otro look", callback_data=f"look:{n}")])
    filas.append([Boton("💡 Más ideas", callback_data="mas")])
    return Botones(filas)


# ---------------- estilo y narrador ----------------
ICONOS_LOOK = {"satelite": "🛰️", "noche": "🌙", "papel": "📜", "acido": "🟢", "mesa": "✂️", "riso": "🟠", "muro": "🧱", "collage": "🟥"}
ICONOS_CEREBRO = {"documentalista": "🎞️", "cronista": "🌮", "detective": "🔎", "profesor": "🧑‍🏫", "epico": "⚔️", "datos": "📊"}


def _nombre_look(k):
    return f"{ICONOS_LOOK.get(k, '🎨')} {looks.LOOKS[k].get('nombre', k)}" if k in looks.LOOKS else "🎲 Automático"


def _nombre_cerebro(k):
    return f"{ICONOS_CEREBRO.get(k, '🧠')} {estilos.CEREBROS[k]['nombre']}" if k in estilos.CEREBROS else "🎲 Automático"


def _nombre_voz(k):
    return next((f"🎙️ {v['nombre']}" for v in estilos._voces() if v["id"] == k), "🎲 Automática")


def texto_estilo(chat):
    p = ajustes.estilo(chat)
    return ("<b>🎨 Estilo y narrador</b>\n<i>Lo que elijas se usa en los siguientes videos. En Automático cambio en cada video "
            "para que el canal no se vea repetido.</i>\n\n"
            f"🖼️ Look  <b>{e(_nombre_look(p.get('look')))}</b>\n"
            f"🧠 Narrador  <b>{e(_nombre_cerebro(p.get('cerebro')))}</b>\n"
            f"🎙️ Voz  <b>{e(_nombre_voz(p.get('voz')))}</b>")


def botones_estilo(chat, seccion="look", video=None):
    """seccion look, narrador o voz. Con video se usa para rehacer ese video con otro look sin gastar créditos."""
    p = ajustes.estilo(chat)
    filas, par = [], []

    def agrega(texto, datos):
        par.append(Boton(texto, callback_data=datos))
        if len(par) == 2:
            filas.append(list(par))
            par.clear()

    if video is not None:
        for k in looks.LOOKS:
            agrega(_nombre_look(k), f"rlook:{video}:{k}")
    elif seccion == "look":
        agrega(("✅ " if not p.get("look") else "") + "🎲 Automático", "est:look:auto")
        for k in looks.LOOKS:
            agrega(("✅ " if p.get("look") == k else "") + _nombre_look(k), f"est:look:{k}")
    elif seccion == "narrador":
        agrega(("✅ " if not p.get("cerebro") else "") + "🎲 Automático", "est:cerebro:auto")
        for k in estilos.CEREBROS:
            agrega(("✅ " if p.get("cerebro") == k else "") + _nombre_cerebro(k), f"est:cerebro:{k}")
    else:
        agrega(("✅ " if not p.get("voz") else "") + "🎲 Automática", "est:voz:auto")
        for v in estilos._voces():
            agrega(("✅ " if p.get("voz") == v["id"] else "") + f"🎙️ {v['nombre']}", f"est:voz:{v['id']}")
    if par:
        filas.append(list(par))
    if video is None:
        pestanas = [("🖼️ Look", "look"), ("🧠 Narrador", "narrador"), ("🎙️ Voz", "voz")]
        filas.append([Boton(("• " if seccion == k else "") + t, callback_data=f"estsec:{k}") for t, k in pestanas])
        filas.append([Boton("👀 Ver cómo se ve cada look", callback_data="muestras")])
    return Botones(filas)


async def menu_estilo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat.id
    await update.effective_message.reply_text(texto_estilo(chat), parse_mode=ParseMode.HTML, reply_markup=botones_estilo(chat))


# ---------------- piloto automático ----------------
NOMBRES_DESTINO = {"fb": "📘 Facebook", "ig": "📸 Instagram", "yt": "▶️ YouTube", "tt": "🎵 TikTok"}


def destino_listo(d):
    return {"fb": facebook.configurado, "ig": facebook.configurado, "yt": youtube.configurado, "tt": tiktok.configurado}[d]()


def texto_piloto():
    p = ajustes.piloto()
    horas = ", ".join(f"{h}:00" for h in sorted(p["horas"][:p["por_dia"]]))
    dest = "  ".join(NOMBRES_DESTINO[d] for d, si in p["destinos"].items() if si) or "ninguno"
    yt = "público" if p["yt_publico"] else "privado"
    return ("<b>🤖 Piloto automático</b>\n\n"
            f"{'🟢 <b>Encendido</b>' if p['activo'] else '⚪ <b>Apagado</b>'}\n\n"
            f"🎬 Videos al día  <b>{p['por_dia']}</b>\n🕒 Horas de México  <b>{horas}</b>\n🚀 Publica en  {dest}\n"
            f"▶️ YouTube en <b>{yt}</b>\n\n"
            "<i>Yo elijo el tema sin repetir, escribo, grabo, animo y publico solo. Te mando aquí cada video con sus ligas. "
            "Cada video gasta créditos de Claude y ElevenLabs, como si lo pidieras tú.</i>")


def botones_piloto():
    p = ajustes.piloto()
    d = p["destinos"]
    return Botones([
        [Boton("⏸️ Apagar" if p["activo"] else "▶️ Encender", callback_data="pil:onoff")],
        [Boton(("✅ " if p["por_dia"] == n else "") + f"{n} al día", callback_data=f"pil:n:{n}") for n in (1, 2, 3)],
        [Boton(("✅ " if d.get(k) else "⬜ ") + NOMBRES_DESTINO[k], callback_data=f"pil:d:{k}") for k in ("fb", "ig")],
        [Boton(("✅ " if d.get(k) else "⬜ ") + NOMBRES_DESTINO[k], callback_data=f"pil:d:{k}") for k in ("yt", "tt")],
        [Boton("▶️ Pedir YouTube público" if not p["yt_publico"] else "▶️ Dejar YouTube en privado", callback_data="pil:ytpub")],
        [Boton("🎬 Hacer uno ahorita", callback_data="pil:ya")],
    ])


async def menu_piloto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(texto_piloto(), parse_mode=ParseMode.HTML, reply_markup=botones_piloto())


async def publicar_en(destinos, video, texto, yt_publico=False):
    """Publica en los destinos y regresa (líneas de texto, botones de ligas)."""
    lineas, ligas = [], []
    for d in destinos:
        nombre = NOMBRES_DESTINO[d]
        try:
            if d == "fb":
                liga = await asyncio.to_thread(facebook.publicar_reel, video, texto)
            elif d == "ig":
                liga = await asyncio.to_thread(facebook.publicar_instagram, video, texto)
            elif d == "tt":
                liga = await asyncio.to_thread(tiktok.subir, video, texto)
            else:
                liga = await asyncio.to_thread(youtube.subir, video, texto, "public" if yt_publico else None)
            lineas.append(f'✅ {nombre}\n<a href="{e(liga)}">{e(liga)}</a>')
            ligas.append((f"Ver en {nombre}", liga))
        except Exception as err:
            logging.exception(f"publicar {d}")
            lineas.append(f"❌ {nombre}\n<code>{e(str(err)[:300])}</code>")
    return lineas, ligas


async def piloto_ciclo(app: Application):
    """Revisa cada minuto si toca producir. Las horas son de la Ciudad de México."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    await asyncio.sleep(60)
    while True:
        try:
            p = ajustes.piloto()
            ahora = datetime.now(ZoneInfo("America/Mexico_City"))
            clave = ahora.strftime("%Y-%m-%d ") + str(ahora.hour)
            if (p["activo"] and p["chat"] and ahora.hour in p["horas"][:p["por_dia"]]
                    and clave not in p["ultimo"] and not cola.locked()):
                ajustes.fijar_piloto(ultimo=dict(list(p["ultimo"].items())[-20:], **{clave: "hecho"}))
                await piloto_uno(app, p["chat"])
        except Exception:
            logging.exception("piloto")
        await asyncio.sleep(60)


async def piloto_uno(app: Application, chat):
    """Un video completo sin intervención: tema nuevo, producción y publicación."""
    p = ajustes.piloto()
    hechos_antes = ajustes.temas_hechos()
    pedido = ("Dame 8 ideas nuevas de temas para el canal, variadas en región y época. No repitas ninguno de estos: "
              + "; ".join(hechos_antes[-60:]))
    _, _, ideas = await asyncio.to_thread(charla.responder, f"piloto-{time.time()}", pedido)
    tema = next((i for i in ideas if i not in hechos_antes), None)
    if not tema:
        await app.bot.send_message(chat, "🤖 El piloto no encontró un tema nuevo esta vez. Lo intento en la siguiente hora programada.")
        return
    ajustes.anotar_tema(tema)
    aviso = await app.bot.send_message(chat, f"🤖 <b>Piloto automático</b>\nProduciendo <b>{e(tema)}</b>…", parse_mode=ParseMode.HTML)
    async with cola:
        estado["ahora"], estado["inicio"] = tema, time.time()
        monitor.estado_bot["ahora"] = tema
        try:
            video, texto = await asyncio.to_thread(hacer_video, tema, False, lambda *a: None, True, ajustes.estilo(chat))
        except Exception as err:
            logging.exception("piloto video")
            await aviso.edit_text(f"🤖 <b>{e(tema)}</b>\n\n{explica(err)}", parse_mode=ParseMode.HTML)
            return
        finally:
            estado["ahora"] = None
            monitor.estado_bot["ahora"] = None
            monitor.estado_bot["ahora"] = None
    contador["video"] += 1
    n = contador["video"]
    hechos[n] = (video, texto, tema, False)
    _guardar_hechos()
    destinos = [d for d in ("fb", "ig", "yt", "tt") if p["destinos"].get(d) and destino_listo(d)]
    await aviso.edit_text(f"🤖 <b>Piloto automático</b>\n<b>{e(tema)}</b> listo, publicando…", parse_mode=ParseMode.HTML)
    lineas, ligas = await publicar_en(destinos, video, texto, p["yt_publico"])
    titulo = texto.partition("\n")[0]
    envio = await asyncio.to_thread(copia_telegram, video)
    with open(envio, "rb") as f:
        await app.bot.send_video(chat, f, caption=f"🤖 <b>{e(titulo)}</b>", parse_mode=ParseMode.HTML,
                                 supports_streaming=True, reply_markup=botones_video(n), read_timeout=600, write_timeout=600)
    await app.bot.send_message(chat, "📍 <b>Dónde quedó publicado</b>\n\n" +
                               ("\n\n".join(lineas) or "No publiqué en ningún lado, revisa los destinos del piloto."),
                               parse_mode=ParseMode.HTML, disable_web_page_preview=True,
                               reply_markup=Botones([[Boton(t, url=u)] for t, u in ligas]) if ligas else None)
    try:
        await aviso.delete()
    except Exception:
        pass


# ---------------- pantallas ----------------
async def inicio(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = ("<b>Bienvenido a FRONTERAS</b>\n<i>La historia que dibujó el mapa</i>\n\n"
             "Soy tu fábrica de documentales cortos. Platica conmigo por texto o 🎙️ nota de voz.\n\n"
             "💡 Te propongo ideas y las eliges con un toque\n"
             "🎬 Investigo, escribo, grabo la voz y animo los mapas\n"
             "📘 Lo publicas en Facebook con un botón\n\n"
             f"Tu número de usuario es <code>{update.effective_user.id}</code>")
    menu = Botones([[Boton("💡 Dame ideas", callback_data="mas"), Boton("✍️ Tengo un tema", callback_data="propio")]])
    try:
        with open(BANNER, "rb") as f:
            await update.message.reply_photo(f, caption=texto, parse_mode=ParseMode.HTML, reply_markup=TECLADO)
    except FileNotFoundError:
        await update.message.reply_text(texto, parse_mode=ParseMode.HTML, reply_markup=TECLADO)
    await update.message.reply_text("¿Por dónde empezamos?", reply_markup=menu)


async def ayuda(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "<b>❓ Cómo usarme</b>\n\n"
        "💬 <b>Platica normal.</b> \"Dame ideas de Sudamérica\", \"hazme el de Alaska\", \"uno sobre Gibraltar\"\n"
        "🎙️ <b>Notas de voz.</b> Te escucho igual que por texto\n"
        "💡 <b>Ideas.</b> Toca una y empiezo el video\n"
        "📐 <b>Formato.</b> Vertical para Shorts y Reels, horizontal para YouTube normal\n"
        "🎨 <b>Estilo y narrador.</b> Elige look, forma de narrar y voz, o déjalo en automático\n"
        "🤖 <b>Piloto automático.</b> Hago y publico videos solo, a las horas que elijas\n"
        "🚀 <b>Redes.</b> Al terminar cada video aparece el botón para publicarlo en Facebook e Instagram\n\n"
        "Cada video tarda unos 5 minutos. Mientras, puedes seguir platicando conmigo.",
        parse_mode=ParseMode.HTML, reply_markup=TECLADO)


async def ver_estado(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat.id
    if estado["ahora"]:
        seg = int(time.time() - estado["inicio"])
        ahora = f"🎬 Produciendo <b>{e(estado['ahora'])}</b> desde hace {seg // 60}:{seg % 60:02d}"
    else:
        ahora = "😴 Libre, listo para el siguiente video"
    fila = f"\n🕒 En fila {estado['en_fila']}" if estado["en_fila"] else ""
    fmt = "Horizontal 16:9" if es_horizontal(chat) else "Vertical 9:16"
    fb = "conectados ✅" if facebook.configurado() else "sin conectar"
    await update.effective_message.reply_text(
        f"<b>📊 Estado</b>\n\n{ahora}{fila}\n📐 Formato {fmt}\n📘 Facebook e Instagram {fb}\n🎞️ Videos de esta sesión {contador['video']}",
        parse_mode=ParseMode.HTML)


async def elegir_formato(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat.id
    v = "✅ " if not es_horizontal(chat) else ""
    h = "✅ " if es_horizontal(chat) else ""
    await update.effective_message.reply_text(
        "<b>📐 ¿En qué formato hago los videos?</b>", parse_mode=ParseMode.HTML,
        reply_markup=Botones([[Boton(f"{v}📱 Vertical 9:16  Shorts y Reels", callback_data="fmt:vertical")],
                              [Boton(f"{h}🖥️ Horizontal 16:9  YouTube", callback_data="fmt:horizontal")]]))


async def pedir_tema(update: Update):
    await update.effective_message.reply_text(
        "✍️ <b>¿De qué quieres el video?</b>\nEscríbelo o mándame un audio. Por ejemplo\n<i>por qué Alaska es de Estados Unidos</i>",
        parse_mode=ParseMode.HTML)


# ---------------- plática ----------------
async def platicar(update: Update, ctx: ContextTypes.DEFAULT_TYPE, texto: str):
    if not autorizado(update):
        return
    chat = update.effective_chat.id
    try:
        await ctx.bot.send_chat_action(chat, ChatAction.TYPING)
        respuesta, pedido, ideas = await asyncio.to_thread(charla.responder, chat, texto)
        if ideas:
            await update.effective_message.reply_text(
                f"💡 <b>{e(respuesta)}</b>\n<i>Toca una para producirla</i>", parse_mode=ParseMode.HTML,
                reply_markup=botones_ideas(ideas))
        else:
            await update.effective_message.reply_text(respuesta)
        if pedido and pedido.get("tema"):
            horizontal = bool(pedido.get("horizontal")) or es_horizontal(chat)
            asyncio.create_task(producir(update, ctx, pedido["tema"], horizontal))
    except Exception as err:
        logging.exception("charla")
        await update.effective_message.reply_text(explica(err), parse_mode=ParseMode.HTML)


async def texto_libre(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not autorizado(update):
        return
    t = update.message.text.strip()
    if t == B_IDEAS:
        await platicar(update, ctx, "Dame ideas nuevas de temas sencillos")
    elif t == B_NUEVO:
        await pedir_tema(update)
    elif t == B_FORMATO:
        await elegir_formato(update, ctx)
    elif t == B_ESTILO:
        await menu_estilo(update, ctx)
    elif t == B_PILOTO:
        await menu_piloto(update, ctx)
    elif t == B_ESTADO:
        await ver_estado(update, ctx)
    elif t == B_AYUDA:
        await ayuda(update, ctx)
    elif tiktok.parece_respuesta(t):
        try:
            nombre = await asyncio.to_thread(tiktok.conectar, t)
            await update.message.reply_text(f"✅ TikTok conectado con <b>{e(nombre)}</b>. Desde ahora cada video trae el botón 🎵 Subir a TikTok.",
                                            parse_mode=ParseMode.HTML)
        except Exception as err:
            logging.exception("tiktok")
            await update.message.reply_text(f"❌ No pude conectar TikTok\n<code>{e(str(err)[:300])}</code>", parse_mode=ParseMode.HTML)
    elif youtube.parece_respuesta(t):
        try:
            nombre = await asyncio.to_thread(youtube.conectar, t)
            await update.message.reply_text(f"✅ YouTube conectado con <b>{e(nombre)}</b>. Desde ahora cada video trae el botón ▶️ Subir a YouTube.",
                                            parse_mode=ParseMode.HTML)
        except Exception as err:
            logging.exception("youtube")
            await update.message.reply_text(f"❌ No pude conectar YouTube\n<code>{e(str(err)[:300])}</code>", parse_mode=ParseMode.HTML)
    else:
        await platicar(update, ctx, t)


async def voz(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not autorizado(update):
        return
    try:
        await ctx.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
        archivo = await (update.message.voice or update.message.audio).get_file()
        datos = bytes(await archivo.download_as_bytearray())
        texto = await asyncio.to_thread(charla.transcribir, datos)
        if not texto:
            await update.message.reply_text("🎙️ No alcancé a oír nada, ¿me lo repites?")
            return
        await update.message.reply_text(f"🎙️ <i>{e(texto)}</i>", parse_mode=ParseMode.HTML)
        await platicar(update, ctx, texto)
    except Exception as err:
        logging.exception("voz")
        await update.message.reply_text(explica(err), parse_mode=ParseMode.HTML)


# ---------------- producción ----------------
async def producir(update: Update, ctx: ContextTypes.DEFAULT_TYPE, tema: str, horizontal=False, nuevo=False, forzar=None):
    msg = update.effective_message
    tema = (tema or "").strip()
    if not tema:
        await pedir_tema(update)
        return
    if cola.locked():
        estado["en_fila"] += 1
        await msg.reply_text(f"🕒 <b>{e(tema)}</b> quedó en fila. Empiezo en cuanto termine el video actual.",
                             parse_mode=ParseMode.HTML)
    async with cola:
        if estado["en_fila"]:
            estado["en_fila"] -= 1
        estado["ahora"], estado["inicio"] = tema, time.time()
        monitor.estado_bot["ahora"] = tema
        if forzar is None:
            forzar = ajustes.estilo(update.effective_chat.id)
        tarjeta = await msg.reply_text(tarjeta_progreso(tema, 1, 0, horizontal), parse_mode=ParseMode.HTML)
        loop = asyncio.get_running_loop()
        ultimo = {"t": 0.0, "texto": ""}

        def aviso(paso, _texto="", sub=0.0):
            nuevo = tarjeta_progreso(tema, paso, sub, horizontal)
            if nuevo == ultimo["texto"] or time.time() - ultimo["t"] < 2.5:
                return
            ultimo.update(t=time.time(), texto=nuevo)
            asyncio.run_coroutine_threadsafe(tarjeta.edit_text(nuevo, parse_mode=ParseMode.HTML), loop)

        try:
            video, texto = await asyncio.to_thread(hacer_video, tema, horizontal, aviso, nuevo, forzar)
            ajustes.anotar_tema(tema)
            contador["video"] += 1
            n = contador["video"]
            hechos[n] = (video, texto, tema, horizontal)
            _guardar_hechos()
            seg = int(time.time() - estado["inicio"])
            await tarjeta.edit_text(f"🎬 <b>{e(tema)}</b>\n\n" + "\n".join(f"✅ {p}" for p in PASOS) +
                                    f"\n\n<code>{barra(1)}</code>\n⏱️ Listo en {seg // 60}:{seg % 60:02d}",
                                    parse_mode=ParseMode.HTML)
            titulo, _, resto = texto.partition("\n")
            caption = f"<b>{e(titulo)}</b>\n\n{e(resto.strip()[:850])}"
            await ctx.bot.send_chat_action(msg.chat_id, ChatAction.UPLOAD_VIDEO)
            envio = await asyncio.to_thread(copia_telegram, video)
            with open(envio, "rb") as f:
                await msg.reply_video(f, caption=caption, parse_mode=ParseMode.HTML, supports_streaming=True,
                                      reply_markup=botones_video(n), read_timeout=600, write_timeout=600)
        except Exception as err:
            logging.exception("video")
            contador["idea"] += 1
            ideas_guardadas[contador["idea"]] = tema
            await tarjeta.edit_text(f"🎬 <b>{e(tema)}</b>\n\n{explica(err)}", parse_mode=ParseMode.HTML,
                                    reply_markup=Botones([[Boton("🔁 Intentar de nuevo", callback_data=f"idea:{contador['idea']}")]]))
        finally:
            estado["ahora"] = None


def copia_telegram(video, limite=48 * 1024 * 1024):
    """Telegram no deja mandar videos de más de 50 MB. Si el original pesa más, se manda una copia más ligera;
    el original de alta calidad se queda para YouTube, Facebook e Instagram."""
    if os.path.getsize(video) <= limite:
        return video
    import subprocess
    copia = video[:-4] + "_tg.mp4"
    if os.path.exists(copia) and os.path.getsize(copia) <= limite:
        return copia
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                               capture_output=True, text=True).stdout.strip() or 90)
    kbps = int(limite * 8 / 1024 * 0.92 / dur) - 160
    for k in (kbps, int(kbps * 0.75)):
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video, "-c:v", "libx264", "-preset", "veryfast",
                        "-b:v", f"{k}k", "-maxrate", f"{int(k * 1.3)}k", "-bufsize", f"{k * 2}k", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", copia], check=True)
        if os.path.getsize(copia) <= limite:
            break
    return copia


async def cmd_video(update, ctx):
    if autorizado(update):
        await producir(update, ctx, " ".join(ctx.args), es_horizontal(update.effective_chat.id))


async def cmd_horizontal(update, ctx):
    if autorizado(update):
        await producir(update, ctx, " ".join(ctx.args), True)


async def cmd_ideas(update, ctx):
    await platicar(update, ctx, "Dame ideas nuevas de temas sencillos")


async def cmd_formato(update, ctx):
    if autorizado(update):
        await elegir_formato(update, ctx)


# ---------------- botones ----------------
async def botones(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not autorizado(update):
        await q.answer()
        return
    accion, _, valor = q.data.partition(":")
    chat = update.effective_chat.id

    if accion == "idea":
        tema = ideas_guardadas.get(int(valor))
        if not tema:
            await q.answer()
            await q.message.reply_text("🔄 Ese botón es de antes de una actualización y ya no funciona. Toca Más ideas o escríbeme el tema.",
                                       reply_markup=Botones([[Boton("💡 Más ideas", callback_data="mas"),
                                                              Boton("✍️ Mi propio tema", callback_data="propio")]]))
            return
        await q.answer("🎬 ¡Va!")
        if tema:
            await q.message.reply_text(f"👌 Elegiste <b>{e(tema)}</b>", parse_mode=ParseMode.HTML)
            asyncio.create_task(producir(update, ctx, tema, es_horizontal(chat)))
    elif accion == "mas":
        await q.answer("💡 Buscando…")
        await platicar(update, ctx, "Dame más ideas, distintas a las anteriores")
    elif accion == "propio":
        await q.answer()
        await pedir_tema(update)
    elif accion == "fmt":
        formato[chat] = valor
        await q.answer("Listo")
        nombre = "📱 Vertical 9:16" if valor == "vertical" else "🖥️ Horizontal 16:9"
        await q.edit_message_text(f"📐 Los siguientes videos salen en <b>{nombre}</b>", parse_mode=ParseMode.HTML)
    elif accion == "est":
        clave, _, val = valor.partition(":")
        ajustes.fijar_estilo(chat, clave, val)
        await q.answer("Listo")
        seccion = {"look": "look", "cerebro": "narrador", "voz": "voz"}.get(clave, "look")
        await q.edit_message_text(texto_estilo(chat), parse_mode=ParseMode.HTML, reply_markup=botones_estilo(chat, seccion))
    elif accion == "estsec":
        await q.answer()
        await q.edit_message_reply_markup(reply_markup=botones_estilo(chat, valor))
    elif accion == "muestras":
        await q.answer("👀")
        ruta = f"{RAIZ}/assets/bot/looks.jpg"
        if os.path.exists(ruta):
            with open(ruta, "rb") as f:
                await q.message.reply_photo(f, caption="Así se ve cada look con la misma escena, en el orden de los botones.")
    elif accion == "look":
        await q.answer()
        n = int(valor)
        if n not in hechos:
            await q.message.reply_text("🔄 Ese video es de antes de una actualización. Pídelo de nuevo.")
            return
        await q.message.reply_text("🎨 <b>¿Con qué look lo rehago?</b>\n<i>Uso el mismo guion y la misma voz, así que no gasta créditos.</i>",
                                   parse_mode=ParseMode.HTML, reply_markup=botones_estilo(chat, video=n))
    elif accion == "rlook":
        n, _, k = valor.partition(":")
        n = int(n)
        await q.answer("🎨 Va")
        if n in hechos and k in looks.LOOKS:
            _, _, tema, horizontal = hechos[n]
            forzar = dict(ajustes.estilo(chat), look=k)
            asyncio.create_task(producir(update, ctx, tema, horizontal, nuevo=False, forzar=forzar))
    elif accion == "pil":
        p = ajustes.piloto()
        partes = valor.split(":")
        if partes[0] == "onoff":
            p = ajustes.fijar_piloto(activo=not p["activo"], chat=chat)
            await q.answer("🟢 Piloto encendido" if p["activo"] else "⚪ Piloto apagado")
        elif partes[0] == "n":
            ajustes.fijar_piloto(por_dia=int(partes[1]), chat=chat)
            await q.answer("Listo")
        elif partes[0] == "d":
            ajustes.fijar_piloto(destinos=dict(p["destinos"], **{partes[1]: not p["destinos"].get(partes[1])}), chat=chat)
            await q.answer("Listo")
        elif partes[0] == "ytpub":
            ajustes.fijar_piloto(yt_publico=not p["yt_publico"], chat=chat)
            await q.answer("Listo")
        elif partes[0] == "ya":
            ajustes.fijar_piloto(chat=chat)
            await q.answer("🎬 Empiezo uno")
            asyncio.create_task(piloto_uno(ctx.application, chat))
            return
        try:
            await q.edit_message_text(texto_piloto(), parse_mode=ParseMode.HTML, reply_markup=botones_piloto())
        except Exception:
            pass
    elif accion == "txt":
        await q.answer()
        n = int(valor)
        if n not in hechos:
            await q.message.reply_text("🔄 Ese video es de antes de una actualización. Pídelo de nuevo.")
        else:
            titulo, _, resto = hechos[n][1].partition("\n")
            await q.message.reply_text(f"📋 <b>Título</b>  toca para copiar\n<code>{e(titulo)}</code>\n\n"
                                       f"<b>Descripción</b>  toca para copiar\n<pre>{e(resto.strip())}</pre>",
                                       parse_mode=ParseMode.HTML)
    elif accion == "otra":
        await q.answer("🔁 Hago otra versión")
        n = int(valor)
        if n in hechos:
            _, _, tema, horizontal = hechos[n]
            asyncio.create_task(producir(update, ctx, tema, horizontal, nuevo=True))
    elif accion == "yt":
        await q.answer("▶️ Subiendo…")
        n = int(valor)
        if n not in hechos:
            await q.message.reply_text("🔄 Ese video es de antes de una actualización. Pídelo de nuevo.")
            return
        video, texto, _, _ = hechos[n]
        aviso = await q.message.reply_text("▶️ Subiendo a YouTube…")
        try:
            liga = await asyncio.to_thread(youtube.subir, video, texto)
            privado = os.environ.get("YOUTUBE_PRIVACIDAD", "private") != "public"
            nota = "\n<i>Quedó en privado. Revísalo en YouTube Studio y hazlo público cuando quieras.</i>" if privado else ""
            await aviso.edit_text(f'📍 <b>Dónde quedó publicado</b>\n\n✅ ▶️ YouTube\n<a href="{e(liga)}">{e(liga)}</a>{nota}',
                                  parse_mode=ParseMode.HTML, disable_web_page_preview=True,
                                  reply_markup=Botones([[Boton("Ver en ▶️ YouTube", url=liga)]]))
        except Exception as err:
            logging.exception("yt")
            await aviso.edit_text(f"❌ ▶️ YouTube\n<code>{e(str(err)[:300])}</code>", parse_mode=ParseMode.HTML)
    elif accion in ("fb", "ig", "meta", "tt"):
        await q.answer("🚀 Publicando…")
        n = int(valor)
        if n not in hechos:
            await q.message.reply_text("🔄 Ese video es de antes de una actualización. Pídelo de nuevo.")
            return
        video, texto, _, _ = hechos[n]
        destinos = {"fb": ["fb"], "ig": ["ig"], "meta": ["fb", "ig"], "tt": ["tt"]}[accion]
        aviso = await q.message.reply_text("🚀 Publicando…" + ("\n<i>Instagram puede tardar unos minutos.</i>" if "ig" in destinos else ""),
                                           parse_mode=ParseMode.HTML)
        lineas, ligas = await publicar_en(destinos, video, texto)
        await aviso.edit_text("📍 <b>Dónde quedó publicado</b>\n\n" + "\n\n".join(lineas), parse_mode=ParseMode.HTML,
                              disable_web_page_preview=True,
                              reply_markup=Botones([[Boton(t, url=u)] for t, u in ligas]) if ligas else None)
    else:
        await q.answer()


async def cmd_youtube(update, ctx):
    if not autorizado(update):
        return
    if not youtube.tiene_cliente():
        await update.message.reply_text("Falta poner YOUTUBE_CLIENT_ID y YOUTUBE_CLIENT_SECRET en Railway.")
        return
    await update.message.reply_text(
        "▶️ <b>Conectar YouTube</b>\n\n"
        "1. Abre el enlace y entra con la cuenta dueña del canal de FRONTERAS\n"
        "2. Si Google dice que la app no está verificada, toca <b>Continuar</b>\n"
        "3. Acepta los permisos\n"
        "4. Vas a llegar a una página que no carga. Copia la dirección completa de esa página y pégamela aquí\n\n"
        f'<a href="{e(youtube.enlace_conexion())}">👉 Conectar mi canal</a>',
        parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def al_arrancar(app: Application):
    app.create_task(piloto_ciclo(app))
    await app.bot.set_my_commands([
        BotCommand("start", "Menú principal"),
        BotCommand("ideas", "Ideas de temas"),
        BotCommand("video", "Hacer un video sobre un tema"),
        BotCommand("horizontal", "Video 16:9 para YouTube"),
        BotCommand("formato", "Vertical u horizontal"),
        BotCommand("estilo", "Elegir look, narrador y voz"),
        BotCommand("piloto", "Piloto automático"),
        BotCommand("estado", "Qué estoy haciendo"),
        BotCommand("youtube", "Conectar el canal de YouTube"),
        BotCommand("tiktok", "Conectar TikTok"),
        BotCommand("ayuda", "Cómo usarme"),
    ])
    try:
        await app.bot.set_my_short_description("Documentales cortos de historia y geografía con mapas. naked · agencia creativa")
        await app.bot.set_my_description("FRONTERAS. La historia que dibujó el mapa.\n\nPídeme un tema por texto o nota de voz "
                                         "y te regreso un documental corto con mapas en relieve, voz y música, listo para publicar.")
    except Exception:
        logging.exception("descripción")


async def cmd_tiktok(update, ctx):
    if not autorizado(update):
        return
    if not tiktok.tiene_cliente():
        await update.message.reply_text("Falta poner TIKTOK_CLIENT_KEY y TIKTOK_CLIENT_SECRET en Railway.")
        return
    await update.message.reply_text(
        "🎵 <b>Conectar TikTok</b>\n\n1. Abre el enlace y entra con la cuenta de TikTok del canal\n2. Acepta los permisos\n"
        "3. Vas a llegar a una página de FRONTERAS. Toca Copiar y pégame aquí lo que copiaste\n\n"
        f'<a href="{e(tiktok.enlace_conexion())}">👉 Conectar mi TikTok</a>',
        parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def cmd_estilo(update, ctx):
    if autorizado(update):
        await menu_estilo(update, ctx)


async def cmd_piloto(update, ctx):
    if autorizado(update):
        await menu_piloto(update, ctx)


def main():
    monitor.arrancar()
    # tiempos largos: subir un video de 30 MB o bajar un audio tarda más que los 5 s de fábrica
    app = (Application.builder().token(os.environ["TELEGRAM_TOKEN"]).post_init(al_arrancar)
           .connect_timeout(30).read_timeout(120).write_timeout(300).pool_timeout(60)
           .media_write_timeout(300).get_updates_read_timeout(60)
           .concurrent_updates(True).build())
    app.add_handler(CommandHandler("start", inicio))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("ideas", cmd_ideas))
    app.add_handler(CommandHandler("video", cmd_video))
    app.add_handler(CommandHandler("horizontal", cmd_horizontal))
    app.add_handler(CommandHandler("formato", cmd_formato))
    app.add_handler(CommandHandler("estado", ver_estado))
    app.add_handler(CommandHandler("youtube", cmd_youtube))
    app.add_handler(CommandHandler("estilo", cmd_estilo))
    app.add_handler(CommandHandler("tiktok", cmd_tiktok))
    app.add_handler(CommandHandler("piloto", cmd_piloto))
    app.add_handler(CallbackQueryHandler(botones))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, voz))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, texto_libre))
    app.run_polling()


if __name__ == "__main__":
    main()
