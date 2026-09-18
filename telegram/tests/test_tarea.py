"""Pruebas de handlers/tarea.py."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dobles import CasoBot  # noqa: E402  (instala el telegram falso)

from handlers.tarea import comando_tarea, comando_tareas  # noqa: E402


class TestTarea(CasoBot):
    def test_apunta_una_tarea_y_devuelve_su_numero(self):
        self.assertEqual(self.enviar(comando_tarea, "comprar", "el", "pan"),
                         "✅ [1] comprar el pan · subido")

    def test_la_fecha_sale_del_texto(self):
        r = self.enviar(comando_tarea, "médico", "el", "15", "de", "octubre", "a", "las", "10")
        self.assertIn("[1] médico · 2026-10-15 10:00", r)

    def test_las_cinco_acciones_sobre_una_tarea(self):
        self.enviar(comando_tarea, "comprar", "el", "pan")
        self.assertTrue(self.enviar(comando_tarea, "empezar", "1").startswith("◐"))
        self.assertTrue(self.enviar(comando_tarea, "hecha", "1").startswith("✅"))
        self.assertTrue(self.enviar(comando_tarea, "reabrir", "1").startswith("○"))
        self.assertIn("pan y leche", self.enviar(comando_tarea, "editar", "1", "pan", "y", "leche"))
        self.assertIn("2026-10-15", self.enviar(comando_tarea, "aplazar", "1", "el", "15", "de", "octubre"))
        self.assertTrue(self.enviar(comando_tarea, "borrar", "1").startswith("🗑️"))

    def test_tareas_ordena_por_estado_y_fecha(self):
        self.enviar(comando_tarea, "sin", "fecha")
        self.enviar(comando_tarea, "con", "fecha", "el", "15", "de", "octubre")
        self.enviar(comando_tarea, "en", "marcha")
        self.enviar(comando_tarea, "empezar", "3")
        lineas = self.enviar(comando_tareas).splitlines()
        self.assertEqual(lineas[0], "◐ En proceso (1):")
        self.assertIn("[3] en marcha", lineas[1])
        self.assertEqual(lineas[2], "○ Pendientes (2):")
        self.assertIn("[2] con fecha", lineas[3])   # la fechada, antes
        self.assertIn("[1] sin fecha", lineas[4])   # la que no tiene, después

    def test_sin_argumentos_enseña_la_ayuda(self):
        self.assertIn("❌ Uso:", self.enviar(comando_tarea))

    def test_falta_el_numero_de_la_tarea(self):
        for accion in ("hecha", "empezar", "reabrir", "borrar", "editar", "aplazar"):
            self.assertIn("Falta el número", self.enviar(comando_tarea, accion),
                          f"con /tarea {accion}")

    def test_una_accion_sin_numero_no_se_confunde_con_una_tarea_nueva(self):
        # "/tarea hecha mañana" se rechaza en vez de crear una tarea llamada
        # "hecha mañana": si escribes una acción, lo que falta es el número.
        r = self.enviar(comando_tarea, "hecha", "mañana")
        self.assertIn("Falta el número", r)
        self.assertEqual(self.tareas.cargar(), [])

    def test_falta_el_texto_o_el_cuando(self):
        self.enviar(comando_tarea, "algo")
        self.assertIn("Falta el texto nuevo", self.enviar(comando_tarea, "editar", "1"))
        self.assertIn("Falta el cuándo", self.enviar(comando_tarea, "aplazar", "1"))

    def test_id_que_no_existe(self):
        self.assertIn("no hay ninguna tarea con id 99", self.enviar(comando_tarea, "hecha", "99"))

    def test_un_cuando_que_no_se_entiende(self):
        self.enviar(comando_tarea, "algo")
        self.assertIn("no entiendo cuándo es", self.enviar(comando_tarea, "aplazar", "1", "cuando", "pueda"))

    def test_sin_tareas_lo_dice(self):
        self.assertIn("No hay tareas", self.enviar(comando_tareas))


if __name__ == "__main__":
    unittest.main()
