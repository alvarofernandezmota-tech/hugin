"""Un mensaje suelto, sin comando: se lo damos a Hugin y se contesta.

Desde la fase 1 del issue #23 aquí **no se decide nada**. Lo que se
contesta a «hoy he dormido fatal», a «recuérdame llamar al médico mañana» o
a «hola» lo decide `hugin.bot.hugin.Hugin.procesar()`, que es el mismo bot
que atiende por consola. Este módulo traduce: un `Update` de Telegram se
convierte en un `Mensaje`, y la `Respuesta` que vuelve se manda al chat.

Lo que queda aquí es lo que de verdad es de Telegram:

- **El filtro de lo que parece un comando y no lo es.** Los comandos tienen
  prioridad porque este handler se registra el último y solo recibe lo que
  Telegram no marca como comando. Ojo: eso no es lo mismo que "no empieza
  por /". Un comando **pegado con formato de código** llega sin la marca
  `bot_command`, cae aquí, y acabaría en el diario en vez de ejecutarse.
  Pasó el 2026-09-05: treinta comandos seguidos al diario, sin un solo
  aviso. Por eso este handler no manda a Hugin nada que empiece por «/».
- **Sacar la llamada del bucle de eventos.** `procesar()` de Hugin es
  síncrona y por dentro puede tardar: clasificar con Ollama en la CPU de
  Madre son segundos (TOPE_SEGUNDOS_OLLAMA), y `sincronizar()` hace `git
  push` —hasta 90 s con mala red—. Dentro de la corrutina eso congela el
  bot entero para todos los chats, no solo para quien mandó el mensaje. Un
  único `to_thread` ahora, donde antes había tres.
- **Quién es el inquilino y cómo se contesta.** Lo primero sale del global
  de proceso de `utils/inquilino.py` (una copia del bot atiende a uno solo,
  ADR-014) y entra en la `Sesion`. Lo segundo es `utils/respuestas.py`, con
  su recorte a la longitud que admite Telegram.
"""

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from hugin.bot.hugin import Hugin
from hugin.bot.mensajes import ERROR, Mensaje, Sesion
from hugin.guardado.sincronizar import sincronizar
from utils.inquilino import actual as inquilino_actual
from utils.respuestas import responder, responder_si_puedo

logger = logging.getLogger(__name__)


AVISO_COMANDO = (
    "⚠️ Esto parece un comando, pero no me ha llegado como tal, así que **no** "
    "lo he ejecutado ni lo he apuntado en el diario.\n\n"
    "Suele pasar al pegarlo con formato (por ejemplo copiado de un bloque de "
    "código). Escríbelo a mano, o pégalo como texto sin formato.\n\n"
    "Lo que me llegó:\n{texto}"
)

# Punto de inyección para las pruebas: un `preguntar` falso para no llamar
# nunca a la API de verdad. En producción es `None`, y `entender()` usa el
# suyo si hay motor configurado.
#
# Siguen aquí, y no en `hugin.bot`, porque son de las PRUEBAS de esta puerta:
# `telegram/tests/dobles.py` los deja en None en cada `setUp` y
# `test_texto.py` los pone caso a caso. Se leen en `_cerebro()`, que corre
# en cada mensaje, así que ponerlos después de importar el módulo funciona
# igual que antes de la extracción.
_preguntar = None

# Lo mismo para el otro lado, el que lee y contesta (`conversar.responder`).
# Van separados porque son dos llamadas distintas con dos firmas distintas:
# `entender` recibe una frase, `conversar` recibe frase y contexto.
_responder_pregunta = None


def _cerebro() -> Hugin:
    """Un Hugin con los motores de ESTE momento.

    Uno por mensaje, a propósito: `dobles.py` reemplaza `_preguntar`,
    `_responder_pregunta` y `sincronizar` en este módulo después de
    importarlo, y los tres se leen aquí dentro. Con un Hugin construido al
    cargar el módulo, una prueba que inyecta su doble no inyectaría nada y
    pasaría en verde por el camino equivocado. Construirlo no abre nada ni
    cuesta nada.
    """
    return Hugin(preguntar=_preguntar,
                 responder_pregunta=_responder_pregunta,
                 # Lambda y no la función a pelo: `dobles.py` hace
                 # `texto.sincronizar = …` para que las pruebas no toquen
                 # git ni la red, y así se resuelve el global en la llamada.
                 sincronizar=lambda ruta, mensaje: sincronizar(ruta, mensaje))


def _sesion() -> Sesion:
    """Quién habla. El chat de Telegram es a la vez el actor y la conversación."""
    inq = inquilino_actual()
    return Sesion(inquilino=inq, actor_id=inq.nombre,
                  conversacion_id=inq.nombre, canal="telegram")


async def procesar(update: Update, texto: str) -> None:
    """Un texto ya en mano —escrito, o dictado y transcrito—: lo atiende Hugin.

    Esto es lo que comparten `mensaje_libre` (texto suelto) y `mensaje_voz`
    (una nota de voz ya pasada por Whisper, en `handlers/voz.py`): a partir
    de aquí da igual de dónde salió el texto. `mensaje_libre` sigue siendo
    quien filtra lo que empieza por «/» —una transcripción nunca puede
    empezar por ahí de casualidad, así que `mensaje_voz` no repite ese aviso.
    """
    mensaje = Mensaje(texto=texto, sesion=_sesion())
    respuesta = await asyncio.to_thread(_cerebro().procesar, mensaje)
    if respuesta.texto.startswith(ERROR):
        # El camino de error va por el que no puede reventar: si el reply
        # falla por red, `responder` volvería a fallar y la excepción
        # saldría del handler para morir en «No error handlers are
        # registered» — con lo escrito ya subido a GitHub y el chat mudo.
        await responder_si_puedo(update, respuesta.texto)
        return
    await responder(update, respuesta.texto)


async def mensaje_libre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cualquier texto que no sea un comando: lo atiende Hugin."""
    texto = (update.effective_message.text or "").strip()
    if not texto:
        return
    if texto.startswith("/"):
        # Un comando de verdad no llega aquí: lo habría cogido su CommandHandler.
        # Si llega, es que Telegram no lo marcó como comando, y meterlo en el
        # diario sería tragárselo en silencio. Se avisa y se devuelve el texto
        # para poder reenviarlo sin volver a escribirlo.
        logger.warning("Texto que parece comando y no lo es (entidades: %s): %r",
                       [e.type for e in (update.effective_message.entities or [])], texto[:80])
        await responder(update, AVISO_COMANDO.format(texto=texto))
        return
    await procesar(update, texto)
