"""Bot de Telegram de FRONTERAS.

Platica contigo por texto o nota de voz, te propone ideas como botones y produce los videos.
"""
import asyncio, html, logging, os, time

from telegram import (Update, InlineKeyboardButton as Boton, InlineKeyboardMarkup as Botones,
                      ReplyKeyboardMarkup, BotCommand)
from telegram.constants import ParseMode, ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

from .fabrica import hacer_video
from . import facebook, charla

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # no imprimir el token del bot en los registros

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANNER = f"{RAIZ}/assets/bot/bienvenida.jpg"
PERMITIDOS = {int(x) for x in os.environ.get("TELEGRAM_USUARIOS", "").replace(" ", "").split(",") if x}

cola = asyncio.Lock()
estado = {"ahora": None, "inicio": 0.0, "en_fila": 0}
formato = {}          # chat_id -> "vertical" | "horizontal"
ideas_guardadas = {}  # id -> tema
hechos = {}           # id -> (video, texto, tema, horizontal)
contador = {"idea": 0, "video": 0}

# botones del teclado de abajo
B_IDEAS, B_NUEVO, B_FORMATO, B_ESTADO, B_AYUDA = "💡 Ideas", "🎬 Nuevo video", "📐 Formato", "📊 Estado", "❓ Ayuda"
TECLADO = ReplyKeyboardMarkup([[B_IDEAS, B_NUEVO], [B_FORMATO, B_ESTADO, B_AYUDA]], resize_keyboard=True,
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
        filas.append([Boton("📘 Publicar en Facebook", callback_data=f"fb:{n}")])
    filas.append([Boton("📋 Texto para YouTube", callback_data=f"txt:{n}"), Boton("🔁 Otra versión", callback_data=f"otra:{n}")])
    filas.append([Boton("💡 Más ideas", callback_data="mas")])
    return Botones(filas)


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
        "📘 <b>Facebook.</b> Al terminar cada video aparece el botón para publicarlo\n\n"
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
    fb = "conectado ✅" if facebook.configurado() else "sin conectar"
    await update.effective_message.reply_text(
        f"<b>📊 Estado</b>\n\n{ahora}{fila}\n📐 Formato {fmt}\n📘 Facebook {fb}\n🎞️ Videos de esta sesión {contador['video']}",
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
    elif t == B_ESTADO:
        await ver_estado(update, ctx)
    elif t == B_AYUDA:
        await ayuda(update, ctx)
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
async def producir(update: Update, ctx: ContextTypes.DEFAULT_TYPE, tema: str, horizontal=False):
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
            video, texto = await asyncio.to_thread(hacer_video, tema, horizontal, aviso)
            contador["video"] += 1
            n = contador["video"]
            hechos[n] = (video, texto, tema, horizontal)
            seg = int(time.time() - estado["inicio"])
            await tarjeta.edit_text(f"🎬 <b>{e(tema)}</b>\n\n" + "\n".join(f"✅ {p}" for p in PASOS) +
                                    f"\n\n<code>{barra(1)}</code>\n⏱️ Listo en {seg // 60}:{seg % 60:02d}",
                                    parse_mode=ParseMode.HTML)
            titulo, _, resto = texto.partition("\n")
            caption = f"<b>{e(titulo)}</b>\n\n{e(resto.strip()[:850])}"
            await ctx.bot.send_chat_action(msg.chat_id, ChatAction.UPLOAD_VIDEO)
            with open(video, "rb") as f:
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
            asyncio.create_task(producir(update, ctx, tema, horizontal))
    elif accion == "fb":
        await q.answer("📘 Publicando…")
        n = int(valor)
        if n not in hechos:
            await q.message.reply_text("Ese video ya no está en el servidor. Pídelo de nuevo.")
            return
        video, texto, _, _ = hechos[n]
        try:
            liga = await asyncio.to_thread(facebook.publicar_reel, video, texto)
            await q.message.reply_text(f"📘 <b>¡Publicado en Facebook!</b>\n{e(liga)}", parse_mode=ParseMode.HTML)
        except Exception as err:
            logging.exception("facebook")
            await q.message.reply_text(explica(err), parse_mode=ParseMode.HTML)
    else:
        await q.answer()


async def al_arrancar(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start", "Menú principal"),
        BotCommand("ideas", "Ideas de temas"),
        BotCommand("video", "Hacer un video sobre un tema"),
        BotCommand("horizontal", "Video 16:9 para YouTube"),
        BotCommand("formato", "Vertical u horizontal"),
        BotCommand("estado", "Qué estoy haciendo"),
        BotCommand("ayuda", "Cómo usarme"),
    ])
    try:
        await app.bot.set_my_short_description("Documentales cortos de historia y geografía con mapas. naked · agencia creativa")
        await app.bot.set_my_description("FRONTERAS. La historia que dibujó el mapa.\n\nPídeme un tema por texto o nota de voz "
                                         "y te regreso un documental corto con mapas en relieve, voz y música, listo para publicar.")
    except Exception:
        logging.exception("descripción")


def main():
    app = (Application.builder().token(os.environ["TELEGRAM_TOKEN"]).post_init(al_arrancar)
           .concurrent_updates(True).build())
    app.add_handler(CommandHandler("start", inicio))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("ideas", cmd_ideas))
    app.add_handler(CommandHandler("video", cmd_video))
    app.add_handler(CommandHandler("horizontal", cmd_horizontal))
    app.add_handler(CommandHandler("formato", cmd_formato))
    app.add_handler(CommandHandler("estado", ver_estado))
    app.add_handler(CallbackQueryHandler(botones))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, voz))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, texto_libre))
    app.run_polling()


if __name__ == "__main__":
    main()
