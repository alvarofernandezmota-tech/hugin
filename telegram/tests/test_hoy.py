"""Pruebas de handlers/hoy.py: el día de un vistazo."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dobles import CasoBot  # noqa: E402  (instala el telegram falso)

from handlers.cita import comando_cita  # noqa: E402
from handlers.habito import comando_habito  # noqa: E402
from handlers.hoy import TOPE_DIARIO, comando_hoy  # noqa: E402
from handlers.secciones import comando_siento  # noqa: E402
from handlers.tarea import comando_tarea  # noqa: E402


class TestHoy(CasoBot):
    def test_junta_las_cuatro_partes_en_un_mensaje(self):
        r = self.enviar(comando_hoy, self.hoy)
        for cabecera in ("📔 Diario", "📅 Citas", "📋 Tareas", "🔁 Hábitos"):
            self.assertIn(cabecera, r)

    def test_enseña_lo_que_hay_en_cada_parte(self):
        self.texto_libre("he trabajado en el bot")
        self.enviar(comando_siento, "contento")
        self.enviar(comando_tarea, "comprar", "el", "pan")
        self.enviar(comando_cita, "médico", "el", "15", "de", "octubre", "a", "las", "10")
        self.enviar(comando_habito, "deporte", self.hoy)
        r = self.enviar(comando_hoy, self.hoy)
        self.assertIn("he trabajado en el bot", r)
        self.assertIn("contento", r)
        self.assertIn("[1] comprar el pan", r)
        self.assertIn("✅ deporte", r)

    def test_no_escribe_nada(self):
        antes = self.entrada.read_text(encoding="utf-8")
        self.enviar(comando_hoy, self.hoy)
        self.assertEqual(self.entrada.read_text(encoding="utf-8"), antes)
        self.assertFalse(self.tareas.RUTA_DATOS.exists())
        self.assertFalse(self.agenda.RUTA_DATOS.exists())

    def test_un_dia_sin_entrada_lo_dice_en_vez_de_crearla(self):
        r = self.enviar(comando_hoy, "2026-01-01")
        self.assertIn("Sin entrada el 2026-01-01", r)
        self.assertFalse((self.base / "2026-01-01.md").exists())

    def test_las_secciones_vacias_no_salen(self):
        self.texto_libre("algo")
        r = self.enviar(comando_hoy, self.hoy)
        self.assertNotIn("Avances / aprendizajes", r)   # vacía: es ruido en el chat
        self.assertIn("algo", r)

    def test_un_diario_larguisimo_se_recorta_y_no_se_come_lo_demas(self):
        self.texto_libre("x" * (TOPE_DIARIO + 500))
        r = self.enviar(comando_hoy, self.hoy)
        self.assertIn("…(recortado)", r)
        self.assertIn("📋 Tareas", r)     # las tareas siguen ahí
        self.assertIn("🔁 Hábitos", r)


if __name__ == "__main__":
    unittest.main()
