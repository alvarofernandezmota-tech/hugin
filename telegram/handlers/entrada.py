"""Handler para el comando /entrada."""

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from utils.mensajes import texto_tras_comando
from utils.midgaror import modulo
from utils.respuestas import breve, responder, responder_si_puedo

fechas = modulo("fechas")
escribir_entrada = modulo("bifrost_bridge").escribir_entrada
sincronizar = modulo("sincronizar").sincronizar

logger = logging.getLogger(__name__)

AYUDA = (
    "❌ Empieza por el día y sigue con el texto, sin < ni >:\n"
    "/entrada ayer se me olvidó apuntar esto\n"
    "/entrada antes de ayer cené fuera\n"
    "/entrada el lunes fui al médico   (el lunes que ya pasó)\n"
    "/entrada 2026-09-03 se me olvidó apuntar esto"
)


async def comando_entrada(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/entrada <día> <texto> — el día en español o AAAA-MM-DD."""
    # La fecha va delante y puede ser varias palabras («antes de ayer»);
    # fechas.fecha_delante prueba primero el trozo más largo y resuelve hacia
    # atrás: lo que se apunta con fecha delante ya pasó.
    fecha, texto = fechas.fecha_delante(texto_tras_comando(update))
    if fecha is None or not texto:
        await responder(update, AYUDA)
        return

    try:
        ruta = escribir_entrada(texto, fecha)
        # sincronizar() hace git commit y git push: hasta 90 s con mala red.
        # Dentro de una corrutina eso congela el bot entero para todos los
        # chats, no solo para quien mando el mensaje. to_thread lo saca del
        # hilo del bucle de eventos, que sigue atendiendo lo demas.
        subido = breve(await asyncio.to_thread(sincronizar, ruta))
        await responder(update, f"📔 Apuntado en el diario del {fecha} · {subido}")
    except Exception as e:
        logger.exception("Error escribiendo la entrada del %s", fecha)
        await responder_si_puedo(update, f"❌ Error: {e}")
