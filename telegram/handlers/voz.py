"""Una nota de voz: se transcribe con Whisper y se trata como si se hubiera
escrito.

A partir de la transcripción, esto es un mensaje suelto de toda la vida:
pasa por `texto.procesar()`, el mismo camino que usa un mensaje escrito.
`entender()` puede convertirlo en una tarea, un hábito, una cita o un
apunte, o caer al diario — exactamente igual, porque ya no sabe si la frase
se escribió o se dijo.

Local, con Whisper (`utils/voz.py`), no una API de terceros: por aquí pasa
lo que dictas a tu propio diario.
"""

import asyncio
import logging
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from handlers.texto import procesar
from utils.respuestas import responder, responder_si_puedo
from utils.voz import MINUTOS_EN_MEMORIA, Whisper, escuchar

logger = logging.getLogger(__name__)

# Una nota de tres minutos tarda un buen rato en transcribirse en una máquina
# sin GPU. Más que eso y sale más a cuenta escribirlo. El número es una
# defensa, no una medida: se ajusta si Madre aguanta más.
DURACION_MAXIMA = 180

# Punto de inyección para las pruebas, igual que `texto._preguntar`: un
# transcriptor falso para no cargar Whisper ni tocar audio de verdad.
_transcriptor = None


def _whisper():
    global _transcriptor
    if _transcriptor is None:
        _transcriptor = Whisper()
    return _transcriptor


def soltar_si_esta_ocioso() -> bool:
    """Suelta el modelo de Whisper si lleva rato sin usarse.

    Lo llama el bucle de `handlers/recordatorios.py`, que ya late cada
    minuto. Montar un segundo temporizador solo para esto sería maquinaria
    por maquinaria: hay un latido, y se aprovecha.

    Un transcriptor de pruebas no sabe soltar nada, y no pasa nada: se
    pregunta antes de pedírselo.
    """
    soltar = getattr(_transcriptor, "soltar_si_lleva_ocioso", None)
    if soltar is None or not soltar():
        return False
    logger.info("🎙️ Whisper suelto: llevaba %d min sin usarse (vuelve casi "
                "un giga de memoria)", MINUTOS_EN_MEMORIA)
    return True


async def mensaje_voz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Una nota de voz de Telegram: se oye y se trata como un mensaje escrito."""
    voz = update.effective_message.voice
    if voz.duration > DURACION_MAXIMA:
        await responder(update,
            f"⚠️ Nota de voz de {voz.duration}s, más de los {DURACION_MAXIMA}s que "
            "atiendo de una vez. Mándala más corta, o escríbelo.")
        return
    try:
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "nota.oga"
            fichero = await context.bot.get_file(voz.file_id)
            await fichero.download_to_drive(ruta)
            # Transcribir es CPU y tarda: igual que sincronizar(), se saca del
            # hilo del bucle de eventos para no congelar el bot para todos
            # los chats mientras oye una nota de uno solo.
            texto = await asyncio.to_thread(escuchar, ruta, _whisper())
    except Exception as e:
        logger.exception("Error transcribiendo una nota de voz")
        await responder_si_puedo(update, f"❌ No he podido oír la nota de voz: {e}")
        return
    if not texto:
        await responder(update, "🎙️ No he oído nada ahí. Prueba a escribirlo, o manda otra nota.")
        return
    # Se dice SIEMPRE lo que se ha entendido, antes de actuar. Whisper se
    # come tildes y palabras sueltas, y esto escribe en un diario que no se
    # relee línea a línea: si oye mal, tiene que verse, no colarse callado.
    await responder(update, f"🎙️ Te he oído: «{texto}»")
    await procesar(update, texto)
