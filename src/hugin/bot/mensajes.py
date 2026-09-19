"""Lo que entra y lo que sale, sin una palabra de ningún canal.

El contrato mínimo de la fase 1 del issue #23: un `Mensaje` entra, una
`Respuesta` sale, y la `Sesion` dice de quién es la conversación. Cuatro
dataclasses congeladas — nadie las muta por el camino, así que lo que
contesta el bot no depende del orden en que se hayan mirado los campos.

Aquí también vive el **formato** de lo que se contesta: las frases de
confirmación que hasta ahora estaban incrustadas en
`telegram/handlers/texto.py` y las dos ayudas de
`telegram/utils/respuestas.py` (`breve`, `dia`). No es presentación de
Telegram: es lo que el bot dice. Telegram solo decide cómo lo pinta —si
recorta a 4096 caracteres, si lo manda con teclado— y eso sí se queda allí.
"""

from dataclasses import dataclass
from typing import Literal

from hugin.inquilino import Inquilino


@dataclass(frozen=True)
class Sesion:
    """De quién es esta conversación y por dónde entra.

    `inquilino` es el objeto ya resuelto, no un nombre: quien construye la
    sesión (el canal) es el único que sabe de dónde sacarlo —una variable
    de entorno, el chat que escribe, el número que llama—, y el cerebro no
    tiene por qué volver a buscarlo ni cachearlo. Es la diferencia con
    `telegram/utils/inquilino.py`, que guarda un global de proceso porque
    una copia del bot atiende a uno solo (ADR-014).

    `canal` está para trazas y para que una capacidad pueda decir «esto por
    teléfono no» el día que haga falta. Nada de aquí lo mira todavía, y
    NADA de `hugin/` puede importar el módulo que lo implemente: es una
    etiqueta, no una puerta.
    """

    inquilino: Inquilino
    actor_id: str
    conversacion_id: str
    canal: Literal["cli", "telegram", "telefono"]

    @property
    def inquilino_id(self) -> str:
        """El identificador que pide el contrato del issue #23."""
        return self.inquilino.nombre


@dataclass(frozen=True)
class Mensaje:
    """Lo que ha dicho alguien. Texto, venga de donde venga.

    Una nota de voz ya transcrita es un mensaje como otro cualquiera: eso
    ya era así en `handlers/voz.py`, que llamaba al mismo `procesar()` que
    un mensaje escrito, y aquí se queda igual.
    """

    texto: str
    sesion: Sesion


@dataclass(frozen=True)
class Opcion:
    """Una alternativa que se le ofrece a quien escribe.

    Sin consumidor todavía: los botones de Telegram siguen construyéndose
    en `handlers/menu.py` y el menú neutral es la fase 2. Está declarada
    porque `Respuesta` la nombra en el contrato, no porque algo la use.
    """

    id: str
    etiqueta: str


@dataclass(frozen=True)
class Respuesta:
    """Lo que contesta el bot.

    `espera_respuesta` está declarado y **siempre en False** en la fase 1.
    Lo que lo encenderá —«¿te refieres a las 17:00?», con el «sí» de la
    vuelta siguiente sabiendo a qué contesta— es estado entre mensajes, y
    eso es `sesion.py`/`flujos.py` en la fase 2 del issue #23. Declararlo
    ahora y no cablearlo es a propósito: el contrato no cambia cuando
    llegue, y mientras tanto nadie puede confundirse creyendo que ya
    funciona.
    """

    texto: str
    opciones: tuple[Opcion, ...] = ()
    espera_respuesta: bool = False


# ---- el formato de lo que se dice ----

SALUDO = ("👋 ¡Hola! No he apuntado nada — dime una tarea, un hábito, una "
          "cita, o algo para el diario.")

# El prefijo por el que un canal reconoce que esto salió mal. Telegram lo
# mira para contestar por el camino que no puede reventar
# (`responder_si_puedo`): el `except` que avisa del fallo no puede morir
# por el mismo motivo que acaba de fallar. Es un marcador de texto y no un
# campo de `Respuesta` porque el contrato del issue #23 tiene tres campos y
# no se le añade un cuarto por comodidad de una puerta.
ERROR = "❌ Error: "


def breve(mensaje_sincronizar: str) -> str:
    """Una coletilla corta si fue bien; el aviso completo si no.

    Portada tal cual de `telegram/utils/respuestas.py`. `sincronizar()`
    devuelve frases pensadas para una terminal («escrito y subido a
    GitHub»); en un móvil la mitad es ruido, pero cuando algo falla hace
    falta el aviso entero.
    """
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
