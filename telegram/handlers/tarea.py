"""Handlers de /tarea y /tareas.

La lógica vive en `hugin.personal.tareas` (el cerebro, ADR-024 fase 4);
aquí solo se traduce el mensaje de Telegram a una llamada y la respuesta a
texto. Movido del canal al cerebro en la fase 5, comando por comando, como
ya hizo `/apunte`.
"""

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from hugin.personal import tareas
from hugin.guardado.sincronizar import sincronizar
from utils.inquilino import actual as inquilino_actual
from utils.respuestas import breve, responder, responder_si_puedo

logger = logging.getLogger(__name__)

AYUDA = (
    "❌ Uso:\n"
    "/tarea médico mañana a las 10 — apunta una tarea, con fecha si la dices\n"
    "/tarea empezar 3 — la pone en proceso\n"
    "/tarea hecha 3 — la marca hecha\n"
    "/tarea reabrir 3 — la devuelve a pendiente\n"
    "/tarea editar 3 comprar pan y leche — le cambia el texto\n"
    "/tarea aplazar 3 el lunes por la tarde — le cambia la fecha\n"
    "/tarea confirmar 3 17:00 — fija la hora si se guardó sin franja\n"
    "/tarea borrar 3 — la retira de la lista\n"
    "/tareas — las abiertas y las últimas hechas"
)

# Los que solo necesitan el id, y el icono con el que se confirma cada uno.
SOLO_ID = {"empezar": tareas.empezar, "hecha": tareas.hecha,
           "reabrir": tareas.reabrir, "borrar": tareas.borrar}
ICONO = {"empezar": "◐", "hecha": "✅", "reabrir": "○", "borrar": "🗑️",
         "editar": "✏️", "aplazar": "📅", "confirmar": "🕐"}
# Y los que además necesitan texto detrás del id.
CON_TEXTO = {"editar": tareas.editar, "aplazar": tareas.aplazar,
             "confirmar": tareas.confirmar_hora}


async def _subir(inq) -> str:
    # sincronizar() hace git commit y git push si el inquilino guarda en
    # fichero (con Postgres no hay nada que subir). Hasta 90 s con mala
    # red: dentro de una corrutina eso congela el bot entero para todos
    # los chats, no solo para quien mando el mensaje. to_thread lo saca
    # del hilo del bucle de eventos, que sigue atendiendo lo demas.
    return breve(await asyncio.to_thread(
        sincronizar, inq.ruta / tareas.FICHERO, f"tareas: {inq.nombre}"))


def _cuando(t: dict) -> str:
    """« · mañana 10:00» si la tarea tiene fecha; nada si no."""
    if not t.get("fecha"):
        return ""
    return f" · {t['fecha']}" + (f" {t['hora']}" if t.get("hora") else "")


async def comando_tarea(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/tarea <texto> | /tarea <acción> <id> [texto]"""
    args = context.args
    if not args:
        await responder(update, AYUDA)
        return
    accion, resto = args[0], args[1:]
    try:
        inq = inquilino_actual()
        if accion in SOLO_ID or accion in CON_TEXTO:
            if not resto or not resto[0].isdigit():
                await responder(update, f"❌ Falta el número de la tarea.\n\n{AYUDA}")
                return
            id_tarea, resto = int(resto[0]), resto[1:]
            if accion in SOLO_ID:
                t = SOLO_ID[accion](id_tarea, inq)
            else:
                if not resto:
                    falta = {"editar": "el texto nuevo", "confirmar": "la hora (HH:MM)"}.get(
                        accion, "el cuándo")
                    await responder(update, f"❌ Falta {falta}.\n\n{AYUDA}")
                    return
                t = CON_TEXTO[accion](id_tarea, " ".join(resto), inq)
            subido = await _subir(inq)
            await responder(update,
                f"{ICONO[accion]} [{t['id']}] {t['texto']}{_cuando(t)} · {subido}")
            return
        t = tareas.agregar(" ".join(args), inq)
        subido = await _subir(inq)
        aviso = (f"\n🕐 ¿{t['hora']} de la mañana o de la tarde? "
                f"/tarea confirmar {t['id']} <hora>") if t.get("sin_franja") else ""
        await responder(update, f"✅ [{t['id']}] {t['texto']}{_cuando(t)} · {subido}{aviso}")
    except ValueError as e:
        await responder(update, f"⚠️ {e}")
    except Exception as e:
        logger.exception("Error en /tarea")
        await responder_si_puedo(update, f"❌ Error: {e}")


async def comando_tareas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/tareas — en proceso, pendientes por fecha y últimas hechas."""
    try:
        await responder(update, tareas.resumen(inquilino_actual()))
    except Exception as e:
        logger.exception("Error en /tareas")
        await responder_si_puedo(update, f"❌ Error: {e}")
