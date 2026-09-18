"""Handler de /hoy: el día de un vistazo, sin escribir nada.

Junta la entrada del diario con las citas, tareas y hábitos — todo ya en el
cerebro (`hugin.personal`, ADR-024 fases 4 y 5). Leer nunca escribe: si no
hay entrada del día, lo dice en vez de crearla.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from hugin.personal import citas, fechas, habitos, tareas
from hugin.personal.diario import leer_entrada
from utils.inquilino import actual as inquilino_actual
from utils.respuestas import responder, responder_si_puedo

logger = logging.getLogger(__name__)

# Telegram corta los mensajes en 4096 caracteres; el diario del día puede
# ser largo, así que se recorta él y no las tareas ni los hábitos.
TOPE_DIARIO = 2500


async def comando_hoy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/hoy [ayer | el lunes | AAAA-MM-DD] — diario, citas, tareas y hábitos de ese día."""
    try:
        inq = inquilino_actual()
        # Hacia atrás: un día se revisa después de vivirlo. «/hoy mañana»
        # sigue siendo mañana, que es explícito.
        fecha = fechas.normalizar(" ".join(context.args), hacia_atras=True) if context.args else None
        diario = leer_entrada(fecha)
        if len(diario) > TOPE_DIARIO:
            diario = diario[:TOPE_DIARIO].rstrip() + "\n…(recortado)"
        partes = [
            "📔 Diario\n" + diario,
            "\n📅 Citas\n" + citas.resumen(fecha, inq),
            "\n📋 Tareas\n" + tareas.resumen(inq, hoy=fecha),
            "\n🔁 Hábitos\n" + habitos.resumen_dia(fecha, inq=inq),
        ]
        await responder(update, "\n".join(partes))
    except ValueError as e:
        await responder(update, f"⚠️ {e}")
    except Exception as e:
        logger.exception("Error en /hoy")
        await responder_si_puedo(update, f"❌ Error: {e}")
