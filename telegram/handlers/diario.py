"""Handler para el comando /diario."""

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from utils.mensajes import texto_tras_comando
from utils.midgaror import modulo
from utils.respuestas import breve, dia, responder, responder_si_puedo

fechas = modulo("fechas")
organizar_texto = modulo("organizar_diario").organizar_texto
sincronizar = modulo("sincronizar").sincronizar

logger = logging.getLogger(__name__)


async def comando_diario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /diario."""
    texto = texto_tras_comando(update)
    if not texto:
        await responder(update, 
            "❌ Escribe el texto detrás del comando, sin < ni >:\n"
            "/diario hoy he dormido fatal")
        return

    # «cené con mi hermana ayer» va al día de ayer, sin el «ayer». Solo el
    # pasado sin ambigüedad cuenta (fechas.fecha_detras): «tengo examen
    # mañana» es una frase de hoy y se queda entera.
    texto, fecha = fechas.fecha_detras(texto)
    try:
        ruta = organizar_texto(texto, fecha=fecha)
        # sincronizar() hace git commit y git push: hasta 90 s con mala red.
        # Dentro de una corrutina eso congela el bot entero para todos los
        # chats, no solo para quien mando el mensaje. to_thread lo saca del
        # hilo del bucle de eventos, que sigue atendiendo lo demas.
        subido = breve(await asyncio.to_thread(sincronizar, ruta))
        await responder(update, f"📔 Apuntado en el diario {dia(fecha)} · {subido}")
    except Exception as e:
        logger.exception("Error escribiendo en el diario de hoy")
        await responder_si_puedo(update, f"❌ Error: {e}")
