"""Pruebas de handlers/cita.py."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dobles import CasoBot  # noqa: E402  (instala el telegram falso)

from handlers.cita import comando_agenda, comando_cita  # noqa: E402


class TestCita(CasoBot):
    def _cita(self, *args: str) -> str:
        return self.enviar(comando_cita, *args)

    def test_apunta_una_cita_con_su_fecha_y_hora(self):
        self.assertIn("[1] médico · 2026-10-15 10:00",
                      self._cita("médico", "el", "15", "de", "octubre", "a", "las", "10"))

    def test_una_cita_sin_cuando_no_es_una_cita(self):
        self.assertIn("una cita necesita cuándo es", self._cita("comprar", "el", "pan"))
        self.assertEqual(self.agenda.cargar(), [])

    def test_avisa_del_choque_pero_la_guarda_igual(self):
        self._cita("médico", "el", "15", "de", "octubre", "a", "las", "10")
        r = self._cita("dentista", "el", "15", "de", "octubre", "a", "las", "10:30")
        self.assertIn("[2] dentista", r)
        self.assertIn("⚠️ Choca con [1] médico a las 10:00", r)
        self.assertEqual(len(self.agenda.cargar()), 2)   # se guarda igual

    def test_sin_hora_es_de_todo_el_dia_y_no_choca(self):
        self._cita("médico", "el", "15", "de", "octubre", "a", "las", "10")
        r = self._cita("reunión", "el", "15", "de", "octubre")
        self.assertIn("(todo el día)", r)
        self.assertNotIn("Choca", r)

    def test_no_choca_si_no_se_solapan(self):
        self._cita("médico", "el", "15", "de", "octubre", "a", "las", "10")   # 10:00-11:00
        self.assertNotIn("Choca", self._cita("gestoría", "el", "15", "de", "octubre", "a", "las", "11"))

    def test_mover_cambia_el_cuando_y_vuelve_a_avisar(self):
        self._cita("médico", "el", "15", "de", "octubre", "a", "las", "10")
        self._cita("dentista", "el", "16", "de", "octubre", "a", "las", "10")
        r = self._cita("mover", "2", "el", "15", "de", "octubre", "a", "las", "10:30")
        self.assertIn("2026-10-15 10:30", r)
        self.assertIn("Choca con [1] médico", r)

    def test_cancelar_la_retira_y_deja_de_estorbar(self):
        self._cita("médico", "el", "15", "de", "octubre", "a", "las", "10")
        self.assertIn("🗑️", self._cita("cancelar", "1"))
        self.assertNotIn("Choca", self._cita("dentista", "el", "15", "de", "octubre", "a", "las", "10"))

    def test_agenda_del_dia_y_de_la_semana(self):
        self._cita("médico", "el", "15", "de", "octubre", "a", "las", "10")
        self._cita("gestoría", "el", "15", "de", "octubre", "a", "las", "9")
        dia = self.enviar(comando_agenda, "2026-10-15").splitlines()
        self.assertEqual(dia[0], "Citas del 2026-10-15:")
        self.assertIn("[2] 09:00 · gestoría", dia[1])   # por hora, no por id
        self.assertIn("[1] 10:00 · médico", dia[2])
        semana = self.enviar(comando_agenda, "semana", "2026-10-15")
        self.assertIn("Citas del 2026-10-15 al 2026-10-21:", semana)
        self.assertIn("2026-10-15:", semana)

    def test_un_dia_sin_citas_lo_dice(self):
        self.assertIn("Sin citas el 2026-10-15", self.enviar(comando_agenda, "2026-10-15"))

    def test_errores_de_uso(self):
        self.assertIn("❌ Uso:", self._cita())
        self.assertIn("Falta el número", self._cita("cancelar"))
        self.assertIn("Falta el cuándo", self._cita("mover", "1"))
        self.assertIn("no hay ninguna cita con id 99", self._cita("cancelar", "99"))


if __name__ == "__main__":
    unittest.main()
