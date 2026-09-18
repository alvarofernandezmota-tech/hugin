"""Cómo se le contesta al usuario.

Todo lo que sale del bot pasa por `responder`. Es un punto único a
propósito: hasta el 2026-09-05 había 47 llamadas sueltas a `reply_text`, y
cualquiera de ellas podía pasarse del límite de Telegram y morir. Algunas
ni siquiera estaban dentro de un `try`, así que el error no llegaba al
usuario: se quedaba en el log.

`diario/sincronizar.py` devuelve frases pensadas para la terminal ("escrito y
subido a GitHub", "⚠️ commiteado en local, sin subir: …"). En el móvil, la
mitad de eso es ruido: cuando todo va bien basta con saber que se subió, y
cuando algo falla hace falta el aviso entero.
"""

import logging

from utils.limites import longitud, recortar

logger = logging.getLogger(__name__)


def breve(mensaje_sincronizar: str) -> str:
    """Una coletilla corta si fue bien; el aviso completo si no."""
    if mensaje_sincronizar.startswith("⚠️"):
        return mensaje_sincronizar
    if "sin cambios" in mensaje_sincronizar:
        return "sin cambios que subir"
    if "reordenar" in mensaje_sincronizar:
        return "subido (había cambios nuevos en GitHub)"
    return "subido"


def dia(fecha: str | None) -> str:
    """«de hoy», o «del 2026-09-05» cuando lo escrito fue a otro día."""
    return "de hoy" if fecha is None else f"del {fecha}"


async def responder(update, texto: str, reply_markup=None) -> None:
    """Contesta, recortando si no cabe en un mensaje de Telegram.

    Se avisa por el log cuando recorta: un recorte silencioso esconde un
    presupuesto mal calculado, y lo que interesa es enterarse.

    `reply_markup` es para el menú de botones (handlers/menu.py): el teclado
    que va pegado al mensaje, o el ForceReply que abre la caja de escribir.

    Se contesta sobre `effective_message` y no sobre `message` porque al tocar
    un botón no hay `message`: Telegram manda un callback_query, y el mensaje
    que hay es el del menú. En un mensaje normal son lo mismo.
    """
    recortado = recortar(texto)
    if recortado is not texto:
        logger.warning("Respuesta recortada: %d → %d unidades UTF-16",
                       longitud(texto), longitud(recortado))
    await update.effective_message.reply_text(recortado, reply_markup=reply_markup)


async def responder_si_puedo(update, texto: str, reply_markup=None) -> None:
    """Como `responder`, pero no revienta si Telegram no coge el mensaje.

    Es para el camino de error, y por eso existe: los `except` de los handlers
    llamaban a `responder`, que es lo que acababa de fallar. Si el reply falla
    por red, el except vuelve a intentarlo, vuelve a fallar, y la excepción
    sale del handler. Sin error handler eso terminaba en «No error handlers
    are registered»: el texto se había escrito y subido a GitHub, y al usuario
    no le llegaba nada.

    Aquí el fallo del reply se queda en el log. Perder el aviso es malo;
    perder además la excepción original y la confirmación es peor.

    En el camino normal se sigue usando `responder`: si ahí falla el envío,
    interesa que se note.
    """
    try:
        await responder(update, texto, reply_markup)
    except Exception:
        logger.exception("No se pudo avisar al chat (el aviso se pierde, no lo escrito): %r",
                         texto[:80])
