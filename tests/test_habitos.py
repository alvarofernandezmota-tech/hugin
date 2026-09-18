"""Pruebas de hugin/personal/habitos.py.

Portadas de diario/tests/test_habitos.py de midgaror: mismo cuerpo, con
`ruta=` cambiado por `inq=` (un Inquilino de mentira, sin backend Postgres)
y sin el bloque `TestHabitos.test_cli`, porque esta versión es librería —
no tiene `main()` de terminal (`hugin/apuntes.py` tampoco lo tiene).
"""

import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

import entorno  # noqa: E402,F401

from hugin import inquilino as hugin_inquilino
from hugin.personal import fechas
from hugin.personal import habitos


def _inq(ruta: Path) -> hugin_inquilino.Inquilino:
    ruta.mkdir(parents=True, exist_ok=True)
    return hugin_inquilino.Inquilino(
        nombre="prueba", ruta=ruta, capacidades=frozenset({"habitos"}), base=None)


class TestHabitos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.inq = _inq(Path(self.tmp.name) / "inquilino")
        self.ruta = self.inq.ruta / habitos.FICHERO

    def test_marcar_crea_el_fichero_por_fecha(self):
        self.assertEqual(habitos.marcar("deporte", fecha="2026-09-04", inq=self.inq),
                         ("2026-09-04", "deporte", True))
        habitos.marcar("meditar", hecho=False, fecha="2026-09-04", inq=self.inq)
        # En disco va envuelto con su versión de esquema (ADR-012, apartado 7).
        self.assertEqual(
            json.loads(self.ruta.read_text(encoding="utf-8")),
            {"schemaVersion": habitos.VERSION,
             "datos": {"2026-09-04": {"deporte": True, "meditar": False}}})

    def test_el_nombre_se_normaliza(self):
        self.assertEqual(habitos.marcar(" Deporte ", fecha="2026-09-04", inq=self.inq)[1], "deporte")
        self.assertEqual(habitos.marcar("leer libro", fecha="2026-09-04", inq=self.inq)[1], "leer-libro")
        self.assertEqual(set(habitos.cargar(self.inq)["2026-09-04"]), {"deporte", "leer-libro"})

    def test_nombre_o_fecha_malos_fallan(self):
        with self.assertRaises(ValueError):
            habitos.marcar("¿qué?", fecha="2026-09-04", inq=self.inq)
        # «04/09/2026» ya vale: desde el 2026-09-06 es una fecha válida
        # (fechas.py la entiende). Lo que sigue sin valer es un día que no
        # existe y una palabra que no es una fecha.
        with self.assertRaises(ValueError):
            habitos.marcar("deporte", fecha="2026-13-45", inq=self.inq)
        with self.assertRaises(ValueError):
            habitos.marcar("deporte", fecha="loquesea", inq=self.inq)
        self.assertFalse(self.ruta.exists())

    def test_marcar_dos_veces_pisa_el_valor(self):
        habitos.marcar("deporte", fecha="2026-09-04", inq=self.inq)
        habitos.marcar("deporte", hecho=False, fecha="2026-09-04", inq=self.inq)
        self.assertFalse(habitos.cargar(self.inq)["2026-09-04"]["deporte"])

    def test_resumen_dia(self):
        self.assertIn("Sin hábitos", habitos.resumen_dia("2026-09-04", self.inq))
        habitos.marcar("deporte", fecha="2026-09-04", inq=self.inq)
        habitos.marcar("meditar", hecho=False, fecha="2026-09-04", inq=self.inq)
        texto = habitos.resumen_dia("2026-09-04", self.inq)
        self.assertIn("✅ deporte", texto)
        self.assertIn("❌ meditar", texto)

    def test_resumen_semana_cuenta_solo_los_siete_dias(self):
        habitos.marcar("deporte", fecha="2026-08-28", inq=self.inq)  # fuera de la ventana
        for d in ("2026-08-29", "2026-08-31", "2026-09-04"):
            habitos.marcar("deporte", fecha=d, inq=self.inq)
        habitos.marcar("deporte", hecho=False, fecha="2026-09-02", inq=self.inq)
        habitos.marcar("meditar", fecha="2026-09-04", inq=self.inq)
        texto = habitos.resumen_semana("2026-09-04", self.inq)
        self.assertIn("Semana del 2026-08-29 al 2026-09-04", texto)
        self.assertNotIn("2026-08-28", texto)
        self.assertIn("deporte: 3/4 días apuntados", texto)
        self.assertIn("meditar: 1/1 días apuntados", texto)

    def test_resumen_semana_vacia(self):
        self.assertIn("Sin hábitos", habitos.resumen_semana("2026-09-04", self.inq))

    def test_valor_numerico(self):
        fecha, nombre, marca = habitos.marcar("energia", fecha="2026-09-05", inq=self.inq, valor=7)
        self.assertEqual((nombre, marca), ("energia", 7))
        self.assertEqual(habitos.cargar(self.inq)["2026-09-05"]["energia"], 7)
        self.assertIn("  7 energia", habitos.resumen_dia("2026-09-05", self.inq))

    def test_valor_fuera_de_rango_o_no_numerico(self):
        for malo in (0, 11, "siete", ""):
            with self.assertRaises(ValueError):
                habitos.marcar("energia", fecha="2026-09-05", inq=self.inq, valor=malo)
        self.assertEqual(habitos.cargar(self.inq), {})

    def test_el_valor_convive_con_el_si_o_no(self):
        habitos.marcar("deporte", fecha="2026-09-05", inq=self.inq)
        habitos.marcar("animo", fecha="2026-09-05", inq=self.inq, valor=8)
        habitos.marcar("animo", fecha="2026-09-04", inq=self.inq, valor=6)
        semana = habitos.resumen_semana("2026-09-05", self.inq)
        self.assertIn("animo:8", semana)
        self.assertIn("deporte:✅", semana)
        self.assertIn("animo: media 7.0 en 2 de 7 días", semana)
        self.assertIn("deporte: 1/1 días apuntados", semana)

    def test_un_habito_de_si_o_no_puede_pasar_a_valor(self):
        habitos.marcar("foco", fecha="2026-09-04", inq=self.inq)
        habitos.marcar("foco", fecha="2026-09-05", inq=self.inq, valor=9)
        self.assertIn("foco: media 9.0 en 1 de 7 días",
                      habitos.resumen_semana("2026-09-05", self.inq))

    def test_true_no_cuenta_como_valor_uno(self):
        self.assertFalse(habitos.es_valor(True))
        self.assertFalse(habitos.es_valor(False))
        self.assertTrue(habitos.es_valor(1))

    def test_sin_inquilino_falla_claro(self):
        with self.assertRaises(ValueError):
            habitos.marcar("deporte", fecha="2026-09-04")


class TestFechasEnLenguajeNatural(unittest.TestCase):
    """«ayer», «el lunes», «04/09/2026» valen como fecha.

    Lo que se prueba es que `habitos` delega en `hugin.personal.fechas` y
    hacia atrás: un hábito se apunta después de hacerlo, así que «el
    lunes» es el que ya pasó. La referencia es hoy de verdad, porque
    `marcar()` no admite un `ahora`, así que las fechas se calculan en la
    prueba.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.inq = _inq(Path(self.tmp.name) / "inquilino")
        self.hoy = datetime.now(fechas.ZONA).date()

    def test_ayer(self):
        ayer = (self.hoy - timedelta(days=1)).isoformat()
        self.assertEqual(habitos.marcar("deporte", fecha="ayer", inq=self.inq)[0], ayer)
        self.assertIn("deporte", habitos.cargar(self.inq)[ayer])

    def test_hace_tres_dias_y_antes_de_ayer(self):
        self.assertEqual(habitos.marcar("deporte", fecha="hace 3 días", inq=self.inq)[0],
                         (self.hoy - timedelta(days=3)).isoformat())
        self.assertEqual(habitos.marcar("deporte", fecha="antes de ayer", inq=self.inq)[0],
                         (self.hoy - timedelta(days=2)).isoformat())

    def test_el_dia_de_la_semana_es_el_que_ya_paso(self):
        fecha = habitos.marcar("deporte", fecha="el lunes", inq=self.inq)[0]
        self.assertLess(fecha, self.hoy.isoformat())
        self.assertEqual(date.fromisoformat(fecha).weekday(), 0)

    def test_el_resumen_del_dia_tambien(self):
        ayer = (self.hoy - timedelta(days=1)).isoformat()
        habitos.marcar("deporte", fecha="ayer", inq=self.inq)
        self.assertIn(f"{ayer}:", habitos.resumen_dia("ayer", inq=self.inq))
        self.assertIn("✅ deporte", habitos.resumen_dia("ayer", inq=self.inq))

    def test_la_semana_tambien(self):
        habitos.marcar("deporte", fecha="ayer", inq=self.inq)
        self.assertIn("deporte", habitos.resumen_semana("hoy", inq=self.inq))

    def test_una_fecha_iso_sigue_valiendo_igual(self):
        self.assertEqual(habitos.marcar("deporte", fecha="2026-09-04", inq=self.inq)[0],
                         "2026-09-04")


if __name__ == "__main__":
    unittest.main()
