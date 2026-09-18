"""Pruebas de los apuntes: lo que pasa en el dia de un inquilino.

Las reglas que se comprueban vienen del ADR-012 y son las que cuestan dinero
si se rompen: que los apuntes se sumen en vez de pisarse, que «hecho» valga 1,
y que la direccion la ponga el objetivo y no una etiqueta.

Todo sobre carpetas temporales: ni un apunte de verdad se toca.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent

import entorno  # noqa: E402,F401

from hugin import apuntes, inquilino  # noqa: E402


class CasoConInquilino(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        (base / "alvaro").mkdir()
        (base / "alvaro" / inquilino.FICHERO).write_text(
            'capacidades = ["apuntes"]\n', encoding="utf-8")
        parche = mock.patch.dict("os.environ", {inquilino.VARIABLE: str(base)})
        parche.start()
        self.addCleanup(parche.stop)
        # Sin base de datos en el entorno: estas pruebas son de ficheros.
        sin_pg = mock.patch.dict("os.environ", {"DIARIO_DATABASE_URL": ""})
        sin_pg.start()
        self.addCleanup(sin_pg.stop)
        self.inq = inquilino.cargar("alvaro")


class TestSeSumanEnVezDePisarse(CasoConInquilino):
    def test_dos_ratos_de_tele_son_dos_apuntes(self):
        # La regla del ADR-012: dos ratos son dos apuntes, no uno que corregir.
        apuntes.apuntar("tele", 2, "h", fecha="2026-09-08", inq=self.inq)
        apuntes.apuntar("tele", 1, "h", fecha="2026-09-08", inq=self.inq)
        self.assertEqual(len(apuntes.del_dia("2026-09-08", self.inq)), 2)
        self.assertEqual(apuntes.total("tele", "2026-09-08", self.inq), 3)

    def test_sin_valor_es_hecho_y_vale_uno(self):
        apuntes.apuntar("deporte", fecha="2026-09-08", inq=self.inq)
        guardado = apuntes.del_dia("2026-09-08", self.inq)[0]
        self.assertNotIn("valor", guardado)
        self.assertEqual(apuntes.total("deporte", "2026-09-08", self.inq), 1)

    def test_valor_cero_no_es_hecho(self):
        apuntes.apuntar("agua", 0, fecha="2026-09-08", inq=self.inq)
        self.assertEqual(apuntes.total("agua", "2026-09-08", self.inq), 0)

    def test_un_decimal_se_conserva(self):
        apuntes.apuntar("agua", "1,5", "l", fecha="2026-09-08", inq=self.inq)
        self.assertEqual(apuntes.total("agua", "2026-09-08", self.inq), 1.5)


class TestLaDireccionLaPoneElObjetivo(CasoConInquilino):
    def test_al_menos_cumple_por_arriba(self):
        objetivo = apuntes.fijar_objetivo("ejercicio", "al_menos", 3, "semana", "h", self.inq)
        self.assertTrue(apuntes.cumple(objetivo, 3))
        self.assertFalse(apuntes.cumple(objetivo, 2))

    def test_como_mucho_cumple_por_abajo(self):
        objetivo = apuntes.fijar_objetivo("tele", "como_mucho", 7, "semana", "h", self.inq)
        self.assertTrue(apuntes.cumple(objetivo, 7))
        self.assertFalse(apuntes.cumple(objetivo, 8))

    def test_un_objetivo_por_que_se_pisa(self):
        apuntes.fijar_objetivo("tele", "como_mucho", 7, inq=self.inq)
        apuntes.fijar_objetivo("tele", "como_mucho", 5, inq=self.inq)
        self.assertEqual(len(apuntes.cargar_objetivos(self.inq)), 1)
        self.assertEqual(apuntes.objetivo_de("tele", self.inq)["valor"], 5)

    def test_un_tipo_inventado_se_canta(self):
        with self.assertRaises(ValueError):
            apuntes.fijar_objetivo("tele", "estaria_bien", 7, inq=self.inq)


class TestInformes(CasoConInquilino):
    def test_un_objetivo_sin_apuntes_sale_con_cero(self):
        # El "llevas 0 de 3 h" es justo lo que hay que ver, no un hueco.
        apuntes.fijar_objetivo("ejercicio", "al_menos", 3, "dia", "h", self.inq)
        lineas = apuntes.resumen_dia("2026-09-08", self.inq)["lineas"]
        self.assertEqual(lineas[0]["que"], "ejercicio")
        self.assertEqual(lineas[0]["total"], 0)
        self.assertFalse(lineas[0]["cumple"])

    def test_la_semana_es_natural_de_lunes_a_domingo(self):
        # Un miercoles: la semana va del lunes de esa semana a su domingo, no
        # los siete dias anteriores.
        self.assertEqual(apuntes.semana_de("2026-09-09"), ("2026-09-07", "2026-09-13"))

    def test_el_resumen_semanal_suma_el_tramo(self):
        apuntes.apuntar("tele", 2, "h", fecha="2026-09-07", inq=self.inq)
        apuntes.apuntar("tele", 3, "h", fecha="2026-09-13", inq=self.inq)
        apuntes.apuntar("tele", 9, "h", fecha="2026-09-14", inq=self.inq)  # fuera
        lineas = apuntes.resumen_semana("2026-09-09", self.inq)["lineas"]
        self.assertEqual(lineas[0]["total"], 5)


class TestNoSeInventaNada(CasoConInquilino):
    def test_no_interpreta_lenguaje_natural(self):
        # A proposito: "el lunes" significa cosas distintas para un apunte y
        # para una cita, y esa decision no es de este modulo.
        with self.assertRaises(ValueError):
            apuntes.apuntar("tele", fecha="el lunes", inq=self.inq)

    def test_sin_fecha_es_hoy(self):
        from hugin.mente import fechas
        apunte = apuntes.apuntar("cafe", inq=self.inq)
        self.assertEqual(apunte["fecha"], fechas.hoy())

    def test_un_nombre_con_acentos_vale(self):
        self.assertEqual(apuntes.normalizar_que("Meditación"), "meditación")

    def test_sin_inquilino_se_dice(self):
        with self.assertRaises(ValueError) as e:
            apuntes.cargar()
        self.assertIn("inquilino", str(e.exception))


class TestCadaInquilinoLoSuyo(CasoConInquilino):
    def test_los_apuntes_de_uno_no_salen_en_el_otro(self):
        base = Path(self._tmp.name)
        (base / "peluqueria").mkdir()
        (base / "peluqueria" / inquilino.FICHERO).write_text(
            'capacidades = ["apuntes"]\n', encoding="utf-8")
        otro = inquilino.cargar("peluqueria")

        apuntes.apuntar("tele", 3, "h", fecha="2026-09-08", inq=self.inq)
        self.assertEqual(apuntes.del_dia("2026-09-08", otro), [])
        self.assertEqual(apuntes.total("tele", "2026-09-08", otro), 0)


if __name__ == "__main__":
    unittest.main()
