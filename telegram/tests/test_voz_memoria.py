"""Pruebas de que Whisper no se queda en memoria para siempre.

Medido en Madre el 2026-09-18: el bot pasó de 47 MB a 968 MB en cuanto
transcribió la primera nota, y ese casi giga se quedaba puesto. `_cargar()`
guardaba el motor y nadie lo soltaba nunca.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.voz import MINUTOS_EN_MEMORIA, Whisper  # noqa: E402


class MotorDeMentira:
    """Lo que devolvería faster-whisper, sin descargar un modelo."""

    def transcribe(self, ruta, language=None):
        return iter(()), None


class TestSoltarElModelo(unittest.TestCase):
    def whisper_cargado(self, hace_segundos: float = 0.0) -> Whisper:
        w = Whisper()
        w._motor = MotorDeMentira()
        w._ultimo_uso = 1000.0
        self.ahora = 1000.0 + hace_segundos
        return w

    def test_recien_usado_no_se_suelta(self):
        w = self.whisper_cargado(hace_segundos=60)
        self.assertFalse(w.soltar_si_lleva_ocioso(ahora=self.ahora))
        self.assertIsNotNone(w._motor)

    def test_tras_el_rato_se_suelta(self):
        w = self.whisper_cargado(hace_segundos=MINUTOS_EN_MEMORIA * 60 + 1)
        self.assertTrue(w.soltar_si_lleva_ocioso(ahora=self.ahora))
        self.assertIsNone(w._motor)

    def test_justo_en_el_borde_todavia_no(self):
        w = self.whisper_cargado(hace_segundos=MINUTOS_EN_MEMORIA * 60 - 1)
        self.assertFalse(w.soltar_si_lleva_ocioso(ahora=self.ahora))

    def test_sin_nada_cargado_no_hay_nada_que_soltar(self):
        w = Whisper()
        self.assertIsNone(w.ocioso_desde_hace())
        self.assertFalse(w.soltar_si_lleva_ocioso())
        self.assertFalse(w.soltar())

    def test_soltar_dos_veces_seguidas_no_revienta(self):
        w = self.whisper_cargado()
        self.assertTrue(w.soltar())
        self.assertFalse(w.soltar())

    def test_volver_a_usarlo_reinicia_el_contador(self):
        # Varias notas seguidas no pueden soltar el modelo en medio de la
        # conversación: cada una vuelve a poner el reloj a cero.
        w = self.whisper_cargado(hace_segundos=MINUTOS_EN_MEMORIA * 60 + 1)
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".oga") as audio:
            w.transcribir(Path(audio.name))
        self.assertLess(w.ocioso_desde_hace(), 5)
        self.assertFalse(w.soltar_si_lleva_ocioso())


if __name__ == "__main__":
    unittest.main()
