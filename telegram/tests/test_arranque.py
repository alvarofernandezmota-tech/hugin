"""Que un corte de red al arrancar no mate el bot.

El fallo (auditoría del 2026-09-08, sección «Ahora»): al reiniciar Madre la
red tarda un minuto, bot.py moría con NetworkError, y systemd gastaba sus 5
reintentos en ~50 s y dejaba la unidad `failed` para siempre. Arreglo en dos
mitades: quitar el tope de systemd (bifrost.service) y que bot.arrancar()
reintente ante NetworkError pero NO ante InvalidToken.

Estas pruebas usan la librería real (NetworkError/InvalidToken de verdad), así
que se saltan si está cargado el telegram falso de dobles.py, igual que
test_ediciones. Corren con `venv/bin/python -m unittest tests.test_arranque`.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _real():
    import telegram
    return None if getattr(telegram, "_es_doble", False) else telegram


SALTAR = "necesita el python-telegram-bot real; con el doble cargado no aplica"


class TestArrancar(unittest.TestCase):
    def setUp(self):
        if _real() is None:
            self.skipTest(SALTAR)
        import bot
        self.bot = bot

    def test_si_hay_red_arranca_una_vez_y_no_duerme(self):
        with mock.patch.object(self.bot, "main") as main, \
             mock.patch.object(self.bot.time, "sleep") as dormir:
            self.bot.arrancar()
        self.assertEqual(main.call_count, 1)
        dormir.assert_not_called()

    def test_sin_red_reintenta_y_acaba_arrancando(self):
        from telegram.error import NetworkError
        # Falla dos veces por red, a la tercera conecta.
        intentos = [NetworkError("sin DNS"), NetworkError("sin DNS"), None]

        def main_falso():
            r = intentos.pop(0)
            if r:
                raise r

        with mock.patch.object(self.bot, "main", side_effect=main_falso) as main, \
             mock.patch.object(self.bot.time, "sleep") as dormir:
            self.bot.arrancar(espera=0)
        self.assertEqual(main.call_count, 3)
        self.assertEqual(dormir.call_count, 2)   # una espera por cada fallo de red

    def test_un_token_invalido_NO_se_reintenta(self):
        from telegram.error import InvalidToken
        with mock.patch.object(self.bot, "main", side_effect=InvalidToken("malo")) as main, \
             mock.patch.object(self.bot.time, "sleep") as dormir:
            with self.assertRaises(InvalidToken):
                self.bot.arrancar(espera=0)
        self.assertEqual(main.call_count, 1)     # ni un reintento
        dormir.assert_not_called()

    def test_si_la_red_no_vuelve_nunca_se_rinde_para_que_systemd_reintente(self):
        from telegram.error import NetworkError
        with mock.patch.object(self.bot, "main", side_effect=NetworkError("sin red")), \
             mock.patch.object(self.bot.time, "sleep"):
            with self.assertRaises(NetworkError):
                self.bot.arrancar(espera=0, tope=3)


class TestLaUnidadSystemd(unittest.TestCase):
    """Esto no toca telegram: vale con doble o sin él."""

    UNIDAD = (Path(__file__).resolve().parent.parent / "systemd" / "bifrost.service").read_text(encoding="utf-8")

    def test_sin_tope_de_reintentos(self):
        # StartLimitIntervalSec=0 desactiva el tope; sin esto, un corte de red
        # largo al arrancar deja la unidad failed para siempre.
        self.assertIn("StartLimitIntervalSec=0", self.UNIDAD)
        self.assertNotIn("StartLimitBurst", self.UNIDAD)

    def test_sigue_volviendo_siempre(self):
        self.assertIn("Restart=always", self.UNIDAD)


if __name__ == "__main__":
    unittest.main()
