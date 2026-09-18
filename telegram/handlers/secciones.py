"""Handlers de /siento, /aprendo y /plan: cada uno a su sección del diario.

De las cuatro secciones de la plantilla, «Qué ha pasado hoy» está rellena el
100 % de los días y las otras tres entre el 30 y el 40 %. La diferencia no es
la disciplina: es que en la primera escribe el bot y en las otras hay que
abrir un editor (ADR-012, apartado 5). Estos tres comandos igualan eso.

Como el resto de bifrost, esto es solo interfaz: quién escribe dónde y con
qué formato lo decide `organizar_diario.SECCIONES` en midgaror.
"""

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from utils.mensajes import texto_tras_comando
from utils.midgaror import modulo
from utils.respuestas import breve, responder, responder_si_puedo

fechas = modulo("fechas")
organizar_texto = modulo("organizar_diario").organizar_texto
sincronizar = modulo("sincronizar").sincronizar

logger = logging.getLogger(__name__)

# comando -> (clave de sección en midgaror, cómo se confirma, ejemplo de uso)
DESTINOS = {
    "siento": ("siento", "💬 Apuntado en «Cómo me siento»",
               "/siento hoy estoy contento, he dormido bien"),
    "aprendo": ("aprendo", "💡 Apuntado en «Avances / aprendizajes»",
                "/aprendo lo de filters.COMMAND de Telegram"),
    "plan": ("plan", "🌅 Apuntado en «Para mañana»",
             "/plan seguir con el portfolio"),
}


async def _escribir(update: Update, context: ContextTypes.DEFAULT_TYPE, comando: str) -> None:
    seccion, confirmacion, ejemplo = DESTINOS[comando]
    texto = texto_tras_comando(update)
    if not texto.strip():
        await responder(update, 
            f"❌ Escribe el texto detrás del comando, sin < ni >:\n{ejemplo}")
        return
    # «cené con mi hermana ayer» va al día de ayer, sin el «ayer». Solo el
    # pasado sin ambigüedad cuenta (fechas.fecha_detras): «tengo examen
    # mañana» es una frase de hoy y se queda entera.
    texto, fecha = fechas.fecha_detras(texto)
    try:
        ruta = organizar_texto(texto, seccion=seccion, fecha=fecha)
        # sincronizar() hace git commit y git push: hasta 90 s con mala red.
        # Dentro de una corrutina eso congela el bot entero para todos los
        # chats, no solo para quien mando el mensaje. to_thread lo saca del
        # hilo del bucle de eventos, que sigue atendiendo lo demas.
        subido = breve(await asyncio.to_thread(sincronizar, ruta))
        cuando = f" del {fecha}" if fecha else ""
        await responder(update, f"{confirmacion}{cuando} · {subido}")
    except ValueError as e:
        await responder(update, f"⚠️ {e}")
    except Exception as e:
        logger.exception("Error escribiendo en la sección %s", seccion)
        await responder_si_puedo(update, f"❌ Error: {e}")


async def comando_siento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/siento <texto> — va a «## Cómo me siento», con la hora delante."""
    await _escribir(update, context, "siento")


async def comando_aprendo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/aprendo <texto> — va a «## Avances / aprendizajes», como viñeta."""
    await _escribir(update, context, "aprendo")


async def comando_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/plan <texto> — va a «## Para mañana», como viñeta."""
    await _escribir(update, context, "plan")
