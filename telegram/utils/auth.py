"""Autorizacion del bot: quien puede darle ordenes.

Sin esto el bot obedece a cualquiera que lo encuentre, y este bot escribe en
el diario personal. La lista de chats autorizados sale de TELEGRAM_CHAT_ID en
el .env, separando por comas si hay varios.

Si no hay ningun id valido, el bot **no autoriza a nadie** y lo grita por el
log al arrancar. Antes hacia lo contrario -sin la variable respondia a todo el
mundo, para no romper una instalacion al actualizar- y ese es el modo de fallo
al reves: una errata al escribir el id (una letra O por un cero) dejaba el bot
ABIERTO en vez de cerrado, y el aviso se perdia entre el resto del arranque.
Un bot mudo se nota en un minuto; uno abierto puede tardar semanas en notarse,
y para entonces alguien ha escrito en el diario.

Los no autorizados no reciben respuesta. Es deliberado: contestarles confirma
que el bot existe y que estan hablando con algo vivo.
"""

import logging
import os

from telegram.ext import filters

logger = logging.getLogger(__name__)

VARIABLE = "TELEGRAM_CHAT_ID"


def chats_autorizados() -> list[int]:
    """Ids de chat que pueden usar el bot. Lista vacia = sin restriccion."""
    crudo = os.getenv(VARIABLE, "").strip()
    if not crudo:
        return []
    ids = []
    for trozo in crudo.split(","):
        trozo = trozo.strip()
        if not trozo:
            continue
        try:
            ids.append(int(trozo))
        except ValueError:
            logger.warning("%s: '%s' no es un id de chat valido, se ignora", VARIABLE, trozo)
    return ids


def chat_autorizado(chat_id: int) -> bool:
    """Si ese chat puede darle ordenes al bot.

    Existe para las vias de entrada que no pasan por un filtro: un
    callback_query (los botones de /menu) no es un mensaje, asi que
    `filters.Chat` no lo mira y hay que preguntar a mano. La respuesta tiene
    que salir de aqui y no de una condicion escrita otra vez, o las dos
    superficies acaban con reglas distintas.
    """
    return chat_id in chats_autorizados()


def filtro_autorizado():
    """Filtro para los CommandHandler. Nunca None: sin ids, no pasa nadie.

    `filters.Chat(chat_id=[])` bloquea a todo el mundo, comprobado contra
    python-telegram-bot 22.8. Es lo que convierte una errata en el .env en un
    bot mudo -que se nota enseguida- en vez de en un bot abierto.
    """
    ids = chats_autorizados()
    if not ids:
        logger.error(
            "%s no tiene ni un id valido: el bot NO va a responder a nadie. "
            "Revisa el .env; si acabas de editarlo, busca una errata en el id.",
            VARIABLE,
        )
    else:
        logger.info("Autorizacion activa para %d chat(s)", len(ids))
    return filters.Chat(chat_id=ids)
