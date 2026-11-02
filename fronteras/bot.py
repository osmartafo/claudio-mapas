"""Bot de Telegram de FRONTERAS.

Le escribes un tema y te regresa el video listo con su título y descripción para YouTube.

Órdenes
  /video tema        short vertical (por defecto también si solo escribes el tema)
  /horizontal tema   video 16:9 para YouTube normal
  /ideas             diez temas nuevos verificables
  /estado            qué está haciendo ahora
"""
import asyncio, os, logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from .fabrica import hacer_video
from . import guionista

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
PERMITIDOS = {int(x) for x in os.environ.get("TELEGRAM_USUARIOS", "").replace(" ", "").split(",") if x}
cola = asyncio.Lock()
estado = {"ahora": "libre"}


def autorizado(update: Update) -> bool:
    return not PERMITIDOS or update.effective_user.id in PERMITIDOS


async def inicio(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"FRONTERAS listo.\nTu número de usuario es {update.effective_user.id}\n\n"
        "Escríbeme un tema, por ejemplo\npor qué Bolivia no tiene mar\n\n"
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
            with open(video, "rb") as f:
                await update.message.reply_video(f, caption=texto[:1000], supports_streaming=True,
                                                 read_timeout=600, write_timeout=600)
            if len(texto) > 1000:
                await update.message.reply_text(texto)
        except Exception as e:  # el bot nunca se cae por un video fallido
            logging.exception("falló")
            await update.message.reply_text(f"No salió «{tema}»\n{type(e).__name__}: {e}")
        finally:
            estado["ahora"] = "libre"


async def video(update, ctx):
    await _producir(update, ctx, " ".join(ctx.args))


async def horizontal(update, ctx):
    await _producir(update, ctx, " ".join(ctx.args), horizontal=True)


async def texto_libre(update, ctx):
    await _producir(update, ctx, update.message.text)


async def ideas(update, ctx):
    if not autorizado(update):
        return
    await update.message.reply_text("Buscando temas…")

    def pedir():
        import anthropic
        c = anthropic.Anthropic()
        r = c.messages.create(model=guionista.MODELO, max_tokens=1500, messages=[{"role": "user", "content":
            "Dame 10 temas para FRONTERAS, un canal de documentales cortos de historia y geografía con mapas. "
            "Cada tema es una pregunta intrigante sobre por qué un territorio, frontera o ruta es como es, "
            "con un dato real y verificable. Mezcla México, Latinoamérica y el mundo. Solo la lista numerada."}])
        return "".join(b.text for b in r.content if b.type == "text")

    await update.message.reply_text(await asyncio.to_thread(pedir))


async def ver_estado(update, ctx):
    if autorizado(update):
        await update.message.reply_text(f"Ahora: {estado['ahora']}")


def main():
    app = Application.builder().token(os.environ["TELEGRAM_TOKEN"]).build()
    app.add_handler(CommandHandler("start", inicio))
    app.add_handler(CommandHandler("video", video))
    app.add_handler(CommandHandler("horizontal", horizontal))
    app.add_handler(CommandHandler("ideas", ideas))
    app.add_handler(CommandHandler("estado", ver_estado))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, texto_libre))
    app.run_polling()


if __name__ == "__main__":
    main()
