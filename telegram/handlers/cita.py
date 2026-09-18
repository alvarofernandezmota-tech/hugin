"""Handlers de /cita y /agenda.

La lógica vive en `hugin.personal.citas` (el cerebro, ADR-024 fase 4).
Se llama `citas`, no `agenda`: ya existe `hugin.negocio.agenda`, la
agenda de reserva de un negocio, y un nombre que no puede colisionar por
accidente no se funde por descuido — pero los comandos de Telegram
siguen siendo /cita y /agenda, que es como Álvaro ya los conoce.
"""

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from hugin.personal import citas
from hugin.guardado.sincronizar import sincronizar
from utils.inquilino import actual as inquilino_actual
from utils.respuestas import breve, responder, responder_si_puedo

logger = logging.getLogger(__name__)

AYUDA = (
    "❌ Uso:\n"
    "/cita médico mañana a las 10 — apunta una cita\n"
    "/cita mover 3 el lunes a las 17 — la cambia de hora\n"
    "/cita cancelar 3 — la retira\n"
    "/agenda — las citas de hoy\n"
    "/agenda semana — los siete días desde hoy"
)


async def _subir(inq) -> str:
    # sincronizar() hace git commit y git push si el inquilino guarda en
    # fichero. Hasta 90 s con mala red: dentro de una corrutina eso
    # congela el bot entero para todos los chats, no solo para quien
    # mando el mensaje. to_thread lo saca del hilo del bucle de eventos,
    # que sigue atendiendo lo demas.
    return breve(await asyncio.to_thread(
        sincronizar, inq.ruta / citas.FICHERO, f"citas: {inq.nombre}"))


def _cuando(cita: dict) -> str:
    """«2026-09-18 10:00», o sin hora si la cita es de todo el día."""
    return f"{cita['fecha']} {cita['hora']}" if cita.get("hora") else f"{cita['fecha']} (todo el día)"


def _confirmacion(cita: dict, solapan: list[dict], subido: str) -> str:
    """La cita guardada y, si choca con otra, el aviso debajo."""
    texto = f"📅 [{cita['id']}] {cita['texto']} · {_cuando(cita)} · {subido}"
    aviso = citas.aviso_choques(solapan)
    return f"{texto}\n{aviso}" if aviso else texto


async def comando_cita(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/cita <texto con cuándo> | /cita mover <id> <cuándo> | /cita cancelar <id>"""
    args = context.args
    if not args:
        await responder(update, AYUDA)
        return
    try:
        inq = inquilino_actual()
        if args[0] in ("mover", "cancelar"):
            if len(args) < 2 or not args[1].isdigit():
                await responder(update, f"❌ Falta el número de la cita.\n\n{AYUDA}")
                return
            id_cita = int(args[1])
            if args[0] == "cancelar":
                cita = citas.cancelar(id_cita, inq)
                subido = await _subir(inq)
                await responder(update,
                    f"🗑️ [{cita['id']}] {cita['texto']} · {_cuando(cita)} · {subido}")
                return
            if len(args) < 3:
                await responder(update, f"❌ Falta el cuándo.\n\n{AYUDA}")
                return
            cita, solapan = citas.mover(id_cita, " ".join(args[2:]), inq)
            await responder(update, _confirmacion(cita, solapan, await _subir(inq)))
            return
        cita, solapan = citas.agregar(" ".join(args), inq)
        await responder(update, _confirmacion(cita, solapan, await _subir(inq)))
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
        # El día puede ser varias palabras («el lunes que viene»); lo entiende citas.
        await responder(update, 
            citas.resumen(" ".join(args) or None, inquilino_actual(), semana=semana))
    except ValueError as e:
        await responder(update, f"⚠️ {e}")
    except Exception as e:
        logger.exception("Error en /agenda")
        await responder_si_puedo(update, f"❌ Error: {e}")
