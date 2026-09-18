"""Pruebas del recorte de mensajes: que nada se pase del límite de Telegram.

El doble de `reply_text` (tests/dobles.py) levanta DemasiadoLargo cuando el
texto pasa de 4096 unidades UTF-16, igual que Telegram. Así estas pruebas
reproducen el fallo de verdad en vez de comparar contra un número calculado
a mano.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dobles import CasoBot, Entidad  # noqa: E402  (instala el telegram falso)

from handlers.cita import comando_agenda  # noqa: E402
from handlers.habito import comando_habito, comando_habitos  # noqa: E402
from handlers.hoy import comando_hoy  # noqa: E402
from handlers.tarea import comando_tarea, comando_tareas  # noqa: E402
from utils.limites import LIMITE, longitud, recortar, recortar_duro  # noqa: E402


class TestMedida(unittest.TestCase):
    def test_se_mide_en_unidades_utf16_como_hace_telegram(self):
        # No es lo mismo que len(): un guardia con len() deja pasar
        # mensajes que Telegram rechaza.
        self.assertEqual((len("📅"), longitud("📅")), (1, 2))
        self.assertEqual((len("🗑️"), longitud("🗑️")), (2, 3))
        self.assertEqual((len("á"), longitud("á")), (1, 1))

    def test_lo_que_cabe_no_se_toca(self):
        self.assertEqual(recortar("hola"), "hola")

    def test_recorta_por_lineas_enteras_y_dice_cuantas_faltan(self):
        largo = "\n".join(f"  ○ [{i}] tarea número {i}" for i in range(1, 400))
        r = recortar(largo)
        self.assertLessEqual(longitud(r), LIMITE)
        self.assertRegex(r.splitlines()[-1], r"^… y \d+ líneas más$")
        # Se conservan las primeras, que el dominio ya ordena por urgencia.
        self.assertTrue(r.startswith("  ○ [1] tarea número 1"))
        # Y ninguna línea queda a medias: cada id sigue siendo utilizable.
        for linea in r.splitlines()[:-1]:
            self.assertRegex(linea, r"^  ○ \[\d+\] tarea número \d+$")

    def test_una_sola_linea_larguisima_se_corta_sin_partir_emojis(self):
        r = recortar_duro("📅" * 5000)
        self.assertLessEqual(longitud(r), 4000)
        self.assertNotIn("�", r)
        self.assertTrue(r.endswith("… (recortado)"))


class TestNingunComandoRevienta(CasoBot):
    """Cada uno de estos desbordaba antes. La precondición lo demuestra."""

    def _cabe_y_es_util(self, respuesta: str) -> None:
        """Que quepa no basta: '❌ Error: Message is too long' también cabe.

        Sin esta segunda mitad, cinco de estas pruebas pasaban en verde con
        el bug puesto, porque el handler cazaba la excepción y contestaba un
        error cortito. Comprobado deshaciendo el arreglo.
        """
        self.assertLessEqual(longitud(respuesta), LIMITE)
        self.assertNotIn("❌ Error", respuesta, "contestó un error en vez del contenido")

    def _muchas_tareas(self, n=200):
        for i in range(n):
            self.tareas.agregar(f"tarea número {i} de la lista de pendientes")

    def test_tareas_con_una_lista_enorme(self):
        self._muchas_tareas()
        self.assertGreater(longitud(self.tareas.resumen()), LIMITE, "precondición")
        self._cabe_y_es_util(self.enviar(comando_tareas))

    def test_hoy_con_una_lista_enorme(self):
        self._muchas_tareas()
        self._cabe_y_es_util(self.enviar(comando_hoy, self.hoy))

    def test_agenda_semana_con_muchas_citas(self):
        for i in range(300):
            self.agenda.agregar(f"cita número {i} el 15 de octubre a las 10")
        self.assertGreater(longitud(self.agenda.resumen("2026-10-15", semana=True)), LIMITE)
        self._cabe_y_es_util(self.enviar(comando_agenda, "semana", "2026-10-15"))

    def test_habitos_semana_con_muchos_habitos(self):
        for i in range(150):
            self.habitos.marcar(f"habito-{i}", fecha=self.hoy)
        self.assertGreater(longitud(self.habitos.resumen_semana(self.hoy)), LIMITE)
        self._cabe_y_es_util(self.enviar(comando_habitos, "semana", self.hoy))

    def test_el_aviso_de_comando_pegado_con_un_texto_enorme(self):
        """Esta era la peor: su reply_text está fuera del try, así que el
        error no llegaba ni al usuario ni a ningún sitio salvo el log."""
        r = self.texto_libre("/tarea " + "x" * 4050, [Entidad("code")])
        self._cabe_y_es_util(r)
        self.assertIn("parece un comando", r)

    def test_una_confirmacion_que_hace_eco_de_un_texto_enorme(self):
        self._cabe_y_es_util(self.enviar(comando_tarea, "x" * 4090))

    def test_un_error_que_hace_eco_de_la_entrada(self):
        self._cabe_y_es_util(self.enviar(comando_habito, "x" * 4090))


if __name__ == "__main__":
    unittest.main()
