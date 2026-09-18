"""El menú de botones: /menu.

Tocar un comando en el menú «/» de Telegram lo envía tal cual, sin dejar
escribir nada detrás: /siento llega vacío y el bot contesta con la ayuda. No
es un fallo nuestro, es cómo funciona Telegram, y no tiene arreglo desde ese
menú. Por eso existe este.

/menu enseña botones. Los de escribir preguntan («💬 ¿Cómo te sientes?») con
un ForceReply, que abre el teclado solo; lo que se escriba llega como
respuesta a esa pregunta y se enruta al handler de siempre. Los de mirar
(«👁 Hoy») se ejecutan directamente.

No hay estado por chat: **la pregunta misma es la clave**. Si dentro de tres
días se contesta a una pregunta vieja, se apunta igual, que es lo que uno
esperaría. Y cada botón acaba en el mismo handler que su comando, así que lo
que entiende /siento lo entiende el botón —fechas, valores, todo— y no hay
dos caminos que mantener.
"""

import logging

from telegram import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from handlers.apunte import comando_apunte, comando_dia, comando_semana
from handlers.cita import comando_agenda, comando_cita
from handlers.diario import comando_diario
from handlers.habito import comando_habito, comando_habitos
from handlers.hoy import comando_hoy
from handlers.secciones import comando_aprendo, comando_plan, comando_siento
from handlers.tarea import comando_tarea, comando_tareas
from handlers.texto import mensaje_libre
from utils.auth import chat_autorizado
from utils.respuestas import responder

logger = logging.getLogger(__name__)

# clave del botón -> (texto del botón, pregunta, handler, ejemplo)
#
# Con pregunta, el botón pregunta y espera texto; con None, ejecuta el handler
# directamente. El ejemplo sale en gris dentro de la caja de escribir. La clave
# viaja en el callback_data de Telegram, que admite 64 bytes: sobra.
ACCIONES = {
    "diario": ("📔 Diario", "📔 ¿Qué ha pasado?", comando_diario, "hoy he dormido fatal"),
    "siento": ("💬 Me siento", "💬 ¿Cómo te sientes?", comando_siento, "contento, he dormido bien"),
    "aprendo": ("💡 Aprendo", "💡 ¿Qué has aprendido?", comando_aprendo, "lo de to_thread"),
    "plan": ("🌅 Mañana", "🌅 ¿Qué hay para mañana?", comando_plan, "seguir con el portfolio"),
    "tarea": ("📋 Tarea", "📋 ¿Qué tarea? Con cuándo, si lo tiene", comando_tarea,
              "comprar el pan mañana"),
    "cita": ("📅 Cita", "📅 ¿Qué cita, y cuándo?", comando_cita, "médico mañana a las 10"),
    "habito": ("🔁 Hábito", "🔁 ¿Qué hábito?", comando_habito, "deporte · no meditar · energia 7"),
    "apunte": ("📝 Apunte", "📝 ¿Qué apuntas? Con cuánto, si lo tiene", comando_apunte,
               "tele 3h · agua 1,5 l · deporte"),
    "hoy": ("👁 Hoy", None, comando_hoy, None),
    "tareas": ("📋 Tareas", None, comando_tareas, None),
    "agenda": ("📅 Agenda", None, comando_agenda, None),
    "habitos": ("🔁 Hábitos", None, comando_habitos, None),
    "dia": ("📊 Día", None, comando_dia, None),
    "semana": ("📆 Semana", None, comando_semana, None),
}

# Cómo se reparten en el teclado: primero lo que escribe, debajo lo que mira.
FILAS = (
    ("diario", "siento"),
    ("aprendo", "plan"),
    ("tarea", "cita", "habito", "apunte"),
    ("hoy", "tareas", "agenda", "habitos"),
    ("dia", "semana"),
)


def teclado() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(ACCIONES[clave][0], callback_data=clave) for clave in fila]
        for fila in FILAS
    ])


def _autorizado(update: Update) -> bool:
    """El filtro de chat de los CommandHandler no llega a los botones.

    Un `callback_query` **no es un mensaje** y `filters.Chat` no lo mira, así
    que la autorización de los botones se comprueba aquí a mano. La respuesta
    sale de `auth.chat_autorizado`, la misma que usan los comandos: si cada
    superficie escribiera su propia condición, acabarían con reglas distintas
    y una de las dos abierta sin que nadie se enterase.

    Esa era justamente la versión anterior de esta función —`not ids or …`,
    o sea, abierta si el `.env` no tenía ids—, que sobrevivió al cambio de
    «cerrado por defecto» del 2026-09-08 porque vivía en otra rama.
    """
    return chat_autorizado(update.effective_chat.id)


async def comando_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/menu — los botones."""
    await responder(update, "¿Qué apuntamos?", reply_markup=teclado())


async def boton(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Se ha tocado un botón del menú."""
    consulta = update.callback_query
    if not _autorizado(update):
        return  # como con los comandos: a quien no está autorizado, ni respuesta
    await consulta.answer()  # quita el relojito del botón
    accion = ACCIONES.get(consulta.data)
    if accion is None:
        logger.warning("Botón desconocido: %r", consulta.data)
        return
    _, pregunta, handler, ejemplo = accion
    try:
        if pregunta is None:
            # Con un botón no hay argumentos; los handlers hacen list(context.args).
            context.args = []
            await handler(update, context)
            return
        await responder(update, pregunta,
                        reply_markup=ForceReply(input_field_placeholder=ejemplo))
    except Exception:
        logger.exception("Error en el botón %r", consulta.data)


def _handler_de(pregunta: str | None):
    for _, (_, candidata, handler, _) in ACCIONES.items():
        if candidata is not None and pregunta == candidata:
            return handler
    return None


async def respuesta_al_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Un texto que responde a otro mensaje.

    Si responde a una pregunta del menú, va al handler de esa pregunta con el
    texto como argumentos: exactamente lo que habría pasado escribiendo el
    comando. Si responde a cualquier otra cosa, es texto libre y sigue el
    camino de siempre.
    """
    original = update.effective_message.reply_to_message
    handler = _handler_de(original.text if original else None)
    texto = (update.effective_message.text or "").strip()
    if handler is None or texto.startswith("/"):
        # O no es una respuesta nuestra, o es un comando pegado sin marca de
        # comando, y de avisar de eso ya sabe texto.py.
        await mensaje_libre(update, context)
        return
    context.args = texto.split()
    await handler(update, context)
