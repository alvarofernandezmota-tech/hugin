"""El bot habla sin que le hablen: avisa de una cita antes de que llegue.

Todo lo demás en bifrost contesta a algo. Esto es lo único que empieza la
conversación, y por eso es lo único que puede convertirse en spam: un bucle
que se equivoca aquí manda el mismo mensaje cada minuto hasta que alguien
para el bot.

Quién decide qué avisar es `diario/recordatorios.py`, con sus pruebas. Aquí
solo se pregunta cada poco, se manda, y **se anota después de mandar**: si
Telegram falla, la cita sigue pendiente y se reintenta a la vuelta
siguiente, en vez de darse por avisada sin que nadie la haya leído.

## Por qué un bucle de asyncio y no JobQueue

`python-telegram-bot` trae `JobQueue`, pero solo si se instala con el extra
`[job-queue]`, que arrastra APScheduler. Esto son veinte líneas de `asyncio`
sobre el bucle que el bot ya tiene corriendo, sin una dependencia más que
instalar en Madre.
"""

import asyncio
import logging

from telegram.ext import Application

from handlers.voz import soltar_si_esta_ocioso as soltar_voz_si_esta_ociosa
from utils.auth import chats_autorizados
from utils.limites import recortar
from utils.midgaror import modulo

agenda = modulo("agenda")
recordatorios = modulo("recordatorios")

logger = logging.getLogger(__name__)

# Cada cuánto se mira la agenda. Un minuto es de sobra fino para una ventana
# de media hora, y es barato: leer un JSON pequeño.
CADA_SEGUNDOS = 60


def texto_del_aviso(cita: dict) -> str:
    return f"⏰ En un rato: {agenda.linea(cita)}"


async def avisar_una_vez(app: Application) -> int:
    """Mira la agenda y manda lo que toque. Devuelve cuántos avisos mandó.

    No lanza nunca: un fallo aquí no puede tirar el bucle que lo llama, o el
    bot se quedaría mudo para siempre sin que nada lo dijera.
    """
    try:
        pendientes = recordatorios.pendientes()
    except Exception:
        logger.exception("No se pudo mirar la agenda para los recordatorios")
        return 0
    if not pendientes:
        return 0

    chats = chats_autorizados()
    if not chats:
        # Sin ids no se sabe a quién avisar. El bot ya está cerrado por
        # defecto (utils/auth.py lo grita al arrancar); aquí solo se calla.
        return 0

    mandados = []
    for cita in pendientes:
        llego = False
        for chat in chats:
            try:
                await app.bot.send_message(chat, recortar(texto_del_aviso(cita)))
                llego = True
            except Exception:
                logger.exception("No se pudo avisar de la cita %s al chat %s",
                                 cita.get("id"), chat)
        if llego:
            mandados.append(cita)

    if mandados:
        # Anotar DESPUÉS de mandar, y solo lo que llegó a alguien.
        try:
            recordatorios.anotar(mandados)
        except Exception:
            # Si esto falla, el aviso se repetirá. Molesto, pero es el lado
            # bueno del fallo: lo contrario es no avisar de una cita.
            logger.exception("Avisos mandados pero no anotados: se repetirán")
    return len(mandados)


async def bucle(app: Application) -> None:
    """Pregunta cada CADA_SEGUNDOS, para siempre. Se lanza en post_init."""
    while True:
        await asyncio.sleep(CADA_SEGUNDOS)
        await avisar_una_vez(app)
        # De paso, el mantenimiento que necesita un latido: soltar el modelo
        # de voz cuando lleva rato sin usarse (casi un giga de memoria).
        # Vive aquí porque este es el único bucle que late en el bot.
        soltar_voz_si_esta_ociosa()


# La tarea del bucle, guardada aquí a propósito y no solo devuelta.
#
# `asyncio.create_task` NO guarda una referencia fuerte a la tarea: si quien
# la crea tira la suya, el recolector de basura puede llevársela a media
# ejecución y el bucle desaparece sin un solo aviso. Está en la
# documentación de asyncio con esas palabras («save a reference»), y aquí
# pasaba: `bot.py` llamaba a `arrancar(app)` y no guardaba nada.
_tarea: asyncio.Task | None = None


def arrancar(app: Application) -> asyncio.Task:
    """Deja el bucle corriendo junto al bot. Devuelve la tarea, para pruebas."""
    global _tarea
    logger.info("⏰ Recordatorios en marcha (cada %ds, ventana de %d min)",
                CADA_SEGUNDOS, recordatorios.VENTANA_MINUTOS)
    _tarea = asyncio.create_task(bucle(app), name="recordatorios")
    return _tarea


async def parar(app: Application | None = None) -> None:
    """Cancela el bucle al apagar el bot. Se engancha en post_shutdown.

    Sin esto, apagar el bot deja la tarea a medio `sleep` y asyncio lo grita
    al cerrarse: «Task was destroyed but it is pending!». No rompía nada
    —el proceso se iba igual— pero un ERROR en el log en cada reinicio es
    exactamente lo que enseña a no leer los logs. Visto en Madre el
    2026-09-17, en el primer arranque con recordatorios.
    """
    global _tarea
    if _tarea is None:
        return
    _tarea.cancel()
    try:
        await _tarea
    except asyncio.CancelledError:
        pass       # es lo que pedimos al cancelar, no un fallo
    finally:
        _tarea = None
