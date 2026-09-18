"""Editar un mensaje en Telegram no debe re-ejecutar nada.

El fallo (auditoría del 2026-09-08, sección «Ahora»): editar un `/diario` para
corregir una errata lo apuntaba DOS veces en el diario y lo subía a git; editar
un texto suelto reventaba el handler porque `update.message` era None.

La defensa de verdad es un filtro en bot.py (`& filters.UpdateType.MESSAGE`),
así que la prueba lo ejerce con la librería REAL del venv.

Complicación: otros ficheros de prueba instalan un `telegram` FALSO en
sys.modules (dobles.py), y con `unittest discover` todo se importa junto. Por
eso aquí no se importa `telegram` a nivel de módulo: cada prueba se salta si
lo que hay cargado es el doble, y lo comprueba con el marcador `_es_doble`.
Con el venv (`venv/bin/python -m unittest tests.test_ediciones`) corren de
verdad; dentro de la suite mezclada, se saltan en vez de romper.
"""

import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _telegram_real():
    """El módulo telegram si es el de verdad; None si es el doble o no está."""
    import telegram
    if getattr(telegram, "_es_doble", False):
        return None
    return telegram


SALTAR = "necesita el python-telegram-bot real; con el doble cargado no aplica"


def _upd(tg, editado: bool, texto: str = "hola", chat_id: int = 1):
    m = tg.Message(message_id=1, date=datetime.datetime.now(datetime.timezone.utc),
                   chat=tg.Chat(id=chat_id, type="private"),
                   from_user=tg.User(id=chat_id, first_name="a", is_bot=False), text=texto)
    return tg.Update(update_id=1, **({"edited_message": m} if editado else {"message": m}))


class TestElFiltroDejaFueraLasEdiciones(unittest.TestCase):
    def setUp(self):
        import os
        from unittest import mock
        self.tg = _telegram_real()
        if self.tg is None:
            self.skipTest(SALTAR)
        self._e = mock.patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "1"})
        self._e.start()
        self.addCleanup(self._e.stop)
        from utils.auth import filtro_autorizado
        from telegram.ext import filters
        self.filters = filters
        self.autorizado = filtro_autorizado() & filters.UpdateType.MESSAGE

    def test_un_mensaje_nuevo_pasa(self):
        self.assertTrue(self.autorizado.check_update(_upd(self.tg, editado=False)))

    def test_un_mensaje_editado_NO_pasa(self):
        self.assertFalse(self.autorizado.check_update(_upd(self.tg, editado=True)))

    def test_un_comando_editado_NO_pasa(self):
        self.assertFalse(self.autorizado.check_update(_upd(self.tg, editado=True, texto="/diario ay")))

    def test_el_texto_libre_editado_NO_pasa(self):
        solo = self.filters.TEXT & ~self.filters.COMMAND & self.autorizado
        self.assertTrue(solo.check_update(_upd(self.tg, editado=False, texto="hoy fatal")))
        self.assertFalse(solo.check_update(_upd(self.tg, editado=True, texto="hoy fatal")))


class TestLosHandlersMiranEffectiveMessage(unittest.TestCase):
    """Esto no toca telegram, así que vale con el doble o sin él: lee el fuente."""

    def test_texto_py_usa_effective_message(self):
        fuente = (Path(__file__).resolve().parent.parent / "handlers" / "texto.py").read_text(encoding="utf-8")
        self.assertNotIn("update.message", fuente)
        self.assertIn("update.effective_message", fuente)

    def test_menu_py_usa_effective_message(self):
        fuente = (Path(__file__).resolve().parent.parent / "handlers" / "menu.py").read_text(encoding="utf-8")
        self.assertNotIn("update.message", fuente)


if __name__ == "__main__":
    unittest.main()
