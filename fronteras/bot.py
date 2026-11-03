"""Bot de Telegram de FRONTERAS.

Le escribes un tema y te regresa el video listo con su título y descripción para YouTube.

Órdenes
  /video tema        short vertical (por defecto también si solo escribes el tema)
  /horizontal tema   video 16:9 para YouTube normal
  /ideas             diez temas nuevos verificables
  /estado            qué está haciendo ahora
"""
import asyncio, os, logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

from .fabrica import hacer_video
from . import guionista, facebook, charla

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # no imprimir el token del bot en los registros
PERMITIDOS = {int(x) for x in os.environ.get("TELEGRAM_USUARIOS", "").replace(" ", "").split(",") if x}
cola = asyncio.Lock()
estado = {"ahora": "libre"}
hechos = {}  # videos listos para publicar, por número


def explica(e):
    """Traduce los errores comunes a algo que se entienda."""
    t = str(e)
    if "credit balance is too low" in t:
        return "Tu cuenta de Claude API se quedó sin saldo. Recarga en platform.claude.com, en Billing."
    if "authentication" in t.lower() or "invalid x-api-key" in t.lower():
        return "La llave de Claude no es válida. Revisa ANTHROPIC_API_KEY en Railway."
    if "quota" in t.lower() and "eleven" in t.lower():
        return "Se acabaron los créditos de ElevenLabs."
    return f"Algo falló\n{type(e).__name__}: {t[:500]}"


def autorizado(update: Update) -> bool:
    return not PERMITIDOS or update.effective_user.id in PERMITIDOS


async def inicio(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"FRONTERAS listo.\nTu número de usuario es {update.effective_user.id}\n\n"
        "Platica conmigo por texto o nota de voz. Pídeme ideas o dime un tema, por ejemplo\nhazme uno de por qué Bolivia no tiene mar\n\n"
        "/horizontal tema para video 16:9\n/ideas para diez temas nuevos")


async def _producir(update: Update, ctx: ContextTypes.DEFAULT_TYPE, tema: str, horizontal=False):
    if not autorizado(update):
        return
    tema = tema.strip()
    if not tema:
        await update.message.reply_text("Dime el tema. Ejemplo /video por qué Alaska es de Estados Unidos")
        return
    if cola.locked():
        await update.message.reply_text("Hay un video en proceso. El tuyo entra en cuanto termine.")
    async with cola:
        estado["ahora"] = tema
        msg = await update.message.reply_text(f"Arrancando «{tema}»")
        loop = asyncio.get_running_loop()

        def aviso(texto):
            asyncio.run_coroutine_threadsafe(msg.edit_text(f"«{tema}»\n{texto}"), loop)

        try:
            video, texto = await asyncio.to_thread(hacer_video, tema, horizontal, aviso)
            n = len(hechos) + 1
            hechos[n] = (video, texto)
            botones = None
            if facebook.configurado():
                botones = InlineKeyboardMarkup([[InlineKeyboardButton("Publicar en Facebook", callback_data=f"fb:{n}")]])
            with open(video, "rb") as f:
                await update.message.reply_video(f, caption=texto[:1000], supports_streaming=True, reply_markup=botones,
                                                 read_timeout=600, write_timeout=600)
            if len(texto) > 1000:
                await update.message.reply_text(texto)
        except Exception as e:  # el bot nunca se cae por un video fallido
            logging.exception("falló")
            await update.message.reply_text(f"No salió «{tema}»\n{explica(e)}")
        finally:
            estado["ahora"] = "libre"


async def video(update, ctx):
    await _producir(update, ctx, " ".join(ctx.args))


async def horizontal(update, ctx):
    await _producir(update, ctx, " ".join(ctx.args), horizontal=True)


async def _platicar(update, ctx, texto):
    if not autorizado(update):
        return
    try:
        await ctx.bot.send_chat_action(update.effective_chat.id, "typing")
        respuesta, pedido = await asyncio.to_thread(charla.responder, update.effective_chat.id, texto)
        await update.message.reply_text(respuesta)
        if pedido and pedido.get("tema"):
            asyncio.create_task(_producir(update, ctx, pedido["tema"], bool(pedido.get("horizontal"))))
    except Exception as e:
        logging.exception("charla")
        await update.message.reply_text(explica(e))


async def texto_libre(update, ctx):
    await _platicar(update, ctx, update.message.text)


async def voz(update, ctx):
    if not autorizado(update):
        return
    try:
        archivo = await (update.message.voice or update.message.audio).get_file()
        datos = bytes(await archivo.download_as_bytearray())
        texto = await asyncio.to_thread(charla.transcribir, datos)
        if not texto:
            await update.message.reply_text("No alcancé a oír nada, ¿me lo repites?")
            return
        await update.message.reply_text(f"Escuché: {texto}")
        await _platicar(update, ctx, texto)
    except Exception as e:
        logging.exception("voz")
        await update.message.reply_text(explica(e))


async def ideas(update, ctx):
    await _platicar(update, ctx, "Dame 10 ideas de temas sencillos para videos")


async def ver_estado(update, ctx):
    if autorizado(update):
        await update.message.reply_text(f"Ahora: {estado['ahora']}")


async def boton(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not autorizado(update):
        await q.answer()
        return
    await q.answer("Publicando…")
    n = int(q.data.split(":")[1])
    if n not in hechos:
        await q.message.reply_text("Ese video ya no está en el servidor. Pídelo de nuevo.")
        return
    video, texto = hechos[n]
    try:
        liga = await asyncio.to_thread(facebook.publicar_reel, video, texto)
        await q.edit_message_reply_markup(None)
        await q.message.reply_text(f"Publicado en Facebook\n{liga}")
    except Exception as e:
        logging.exception("facebook")
        await q.message.reply_text(f"No se pudo publicar en Facebook\n{type(e).__name__}: {e}")


def main():
    app = Application.builder().token(os.environ["TELEGRAM_TOKEN"]).build()
    app.add_handler(CommandHandler("start", inicio))
    app.add_handler(CommandHandler("video", video))
    app.add_handler(CommandHandler("horizontal", horizontal))
    app.add_handler(CommandHandler("ideas", ideas))
    app.add_handler(CommandHandler("estado", ver_estado))
    app.add_handler(CallbackQueryHandler(boton, pattern=r"^fb:"))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, voz))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, texto_libre))
    app.run_polling()


if __name__ == "__main__":
    main()
