"""Pruebas de hugin/guardado/ajustes.py: leer el .env de quien despliega.

No había fichero de pruebas propio para este módulo. Nace con el bug real
que lo justifica: una línea sin nombre de variable ("=algo") no puede
quedarse fuera sin más, porque el .env lo escribe una persona a mano.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent

import entorno  # noqa: E402,F401

from hugin.guardado import ajustes  # noqa: E402


class CasoAjustes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fich = Path(self.tmp.name) / ".env"

    def escribir(self, texto: str) -> None:
        self.fich.write_text(texto, encoding="utf-8")


class TestUnaLineaSinClaveNoRevienta(CasoAjustes):
    """Bug real: os.environ no acepta una clave vacía, y leer() la pasaba
    tal cual a os.environ.setdefault() sin comprobar nada — OSError crudo.
    """

    def test_una_linea_sin_nombre_se_ignora(self):
        self.escribir("=algo\nCLAVE_BUENA=valor\n")
        self.assertEqual(ajustes._pares(self.fich), [("CLAVE_BUENA", "valor")])

    def test_con_espacios_antes_del_igual_tambien_se_ignora(self):
        self.escribir("   =valor\nOTRA=bien\n")
        self.assertEqual(ajustes._pares(self.fich), [("OTRA", "bien")])

    def test_leer_no_revienta_con_una_clave_vacia(self):
        self.escribir("=algo\n")
        ajustes.leer(self.fich)   # no debe lanzar OSError


class TestLaUltimaClaveGana(CasoAjustes):
    def test_repetida_vale_la_ultima(self):
        self.escribir("CLAVE=una\nCLAVE=otra\n")
        self.assertEqual(dict(ajustes._pares(self.fich))["CLAVE"], "otra")

    def test_leer_no_pisa_lo_que_ya_esta_en_el_entorno(self):
        import os
        self.escribir("CLAVE_DE_PRUEBA_AJUSTES=del_fichero\n")
        with mock.patch.dict(os.environ, {"CLAVE_DE_PRUEBA_AJUSTES": "del_entorno"}):
            ajustes.leer(self.fich)
            self.assertEqual(os.environ["CLAVE_DE_PRUEBA_AJUSTES"], "del_entorno")


if __name__ == "__main__":
    unittest.main()
