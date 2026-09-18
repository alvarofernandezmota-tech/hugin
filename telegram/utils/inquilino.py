"""Quién es el inquilino al que atiende ESTA copia del bot.

Un proceso atiende a un bot (ADR-014, ADR-024): la copia que corre para
Álvaro no elige entre varios inquilinos, solo necesita saber cuál es el
suyo. Eso es justo lo que separa esto de `hugin.inquilino.listar()`, que
lista TODOS los que hay dados de alta — útil para gestionar, no para que
un proceso se pregunte quién es.

Se lee una vez y se guarda: no es una decisión que pueda cambiar a mitad
de una llamada de Telegram.
"""

import os

from hugin import inquilino as _inq

VARIABLE = "INQUILINO"

_actual: _inq.Inquilino | None = None


def actual() -> _inq.Inquilino:
    """El inquilino de este proceso. Falla claro si nadie lo ha dicho."""
    global _actual
    if _actual is None:
        nombre = os.environ.get(VARIABLE, "").strip()
        if not nombre:
            raise RuntimeError(
                f"no sé para quién es este bot: falta {VARIABLE}. "
                f"Dilo con, por ejemplo: export {VARIABLE}=alvaro")
        _actual = _inq.cargar(nombre)
    return _actual


def _reiniciar() -> None:
    """Solo para pruebas: olvida el inquilino cacheado."""
    global _actual
    _actual = None
