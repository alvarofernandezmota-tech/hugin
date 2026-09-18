"""Handlers de /cita y /agenda.

Como el resto de bifrost, esto es solo interfaz: la lógica vive en
midgaror/diario/agenda/agenda.py y aquí solo se traduce el mensaje de
Telegram a una llamada y la respuesta a texto.
"""

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from utils.midgaror import modulo
from utils.respuestas import breve, responder, responder_si_puedo

agenda = modulo("agenda")
sincronizar = modulo("sincronizar").sincronizar

logger = logging.getLogger(__name__)

AYUDA = (
    "❌ Uso:\n"
    "/cita médico mañana a las 10 — apunta una cita\n"
    "/cita mover 3 el lunes a las 17 — la cambia de hora\n"
    "/cita cancelar 3 — la retira\n"
    "/agenda — las citas de hoy\n"
    "/agenda semana — los siete días desde hoy"
)


async def _subir() -> str:
    # sincronizar() hace git commit y git push: hasta 90 s con mala red.
    # Dentro de una corrutina eso congela el bot entero para todos los
    # chats, no solo para quien mando el mensaje. to_thread lo saca del
    # hilo del bucle de eventos, que sigue atendiendo lo demas.
    return breve(await asyncio.to_thread(
        sincronizar, agenda.RUTA_DATOS, "diario: citas desde bifrost"))


def _confirmacion(cita: dict, solapan: list[dict], subido: str) -> str:
    """La cita guardada y, si choca con otra, el aviso debajo."""
    cuando = f"{cita['fecha']} {cita['hora']}" if cita.get("hora") else f"{cita['fecha']} (todo el día)"
    texto = f"📅 [{cita['id']}] {cita['texto']} · {cuando} · {subido}"
    aviso = agenda.aviso_choques(solapan)
    return f"{texto}\n{aviso}" if aviso else texto


async def comando_cita(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/cita <texto con cuándo> | /cita mover <id> <cuándo> | /cita cancelar <id>"""
    args = context.args
    if not args:
        await responder(update, AYUDA)
        return
    try:
        if args[0] in ("mover", "cancelar"):
            if len(args) < 2 or not args[1].isdigit():
                await responder(update, f"❌ Falta el número de la cita.\n\n{AYUDA}")
                return
            id_cita = int(args[1])
            if args[0] == "cancelar":
                cita = agenda.cancelar(id_cita)
                subido = await _subir()
                await responder(update, 
                    f"🗑️ [{cita['id']}] {cita['texto']} · {cita['fecha']} · {subido}")
                return
            if len(args) < 3:
                await responder(update, f"❌ Falta el cuándo.\n\n{AYUDA}")
                return
            cita, solapan = agenda.mover(id_cita, " ".join(args[2:]))
            await responder(update, _confirmacion(cita, solapan, await _subir()))
            return
        cita, solapan = agenda.agregar(" ".join(args))
        await responder(update, _confirmacion(cita, solapan, await _subir()))
    except ValueError as e:
        await responder(update, f"⚠️ {e}")
    except Exception as e:
        logger.exception("Error en /cita")
        await responder_si_puedo(update, f"❌ Error: {e}")


async def comando_agenda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/agenda [semana] [mañana | el lunes | AAAA-MM-DD]"""
    args = list(context.args)
    semana = bool(args) and args[0] == "semana"
    if semana:
        args = args[1:]
    try:
        # El día puede ser varias palabras («el lunes que viene»); lo entiende agenda.
        await responder(update, 
            agenda.resumen(" ".join(args) or None, semana=semana))
    except ValueError as e:
        await responder(update, f"⚠️ {e}")
    except Exception as e:
        logger.exception("Error en /agenda")
        await responder_si_puedo(update, f"❌ Error: {e}")
