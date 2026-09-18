"""Que herramientas/auditoria.py detecte de verdad lo que dice detectar.

No basta con que pase hoy contra el repo real —eso solo dice que hoy no hay
el problema, no que el codigo lo reconocería si volviera—. Cada comprobación
lleva dos pruebas: una contra el repo de verdad (regresión: que siga en
verde) y una contra un repo de mentira construido a próposito con el fallo
metido, para probar que la función de verdad lo ve y no solo que hoy calla.
"""

import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from herramientas import auditoria  # noqa: E402


class TestPaquetesCompletosContraElRepoReal(unittest.TestCase):
    def test_hoy_no_falta_ninguno(self):
        self.assertEqual(auditoria.paquetes_completos(), [])


class TestPaquetesCompletosDetectaUnoQueFalta(unittest.TestCase):
    def _repo_de_mentira(self, declarados: list[str], carpetas: list[str]) -> Path:
        raiz = Path(tempfile.mkdtemp(prefix="auditoria-pruebas-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(raiz, ignore_errors=True))
        (raiz / "pyproject.toml").write_text(
            "[tool.setuptools]\npackages = " + repr(declarados).replace("'", '"') + "\n",
            encoding="utf-8")
        for punto in carpetas:
            carpeta = raiz / Path(*punto.split("."))
            carpeta.mkdir(parents=True, exist_ok=True)
            (carpeta / "__init__.py").write_text("", encoding="utf-8")
        return raiz

    def test_una_carpeta_con_init_y_sin_declarar_se_ve(self):
        raiz = self._repo_de_mentira(
            declarados=["hugin"],
            carpetas=["hugin", "hugin.fantasma"])
        with mock.patch.object(auditoria, "RAIZ", raiz):
            problemas = auditoria.paquetes_completos()
        self.assertTrue(problemas, "una carpeta con __init__.py sin declarar no se vio")
        self.assertIn("hugin.fantasma", problemas[0])

    def test_con_todo_declarado_no_hay_nada_que_decir(self):
        raiz = self._repo_de_mentira(
            declarados=["hugin", "hugin.completo"],
            carpetas=["hugin", "hugin.completo"])
        with mock.patch.object(auditoria, "RAIZ", raiz):
            self.assertEqual(auditoria.paquetes_completos(), [])

    def test_de_verdad_lee_pyproject_toml_de_verdad(self):
        # Sujeta el formato del fichero de mentira contra el parser real: si
        # tomllib no lo entendiera, las pruebas de arriba pasarian por una
        # excepcion silenciada, no porque el codigo funcione.
        raiz = self._repo_de_mentira(declarados=["hugin"], carpetas=["hugin"])
        config = tomllib.loads((raiz / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(config["tool"]["setuptools"]["packages"], ["hugin"])


class TestWorkflowsEnSuSitioContraElRepoReal(unittest.TestCase):
    def test_hoy_ninguno_esta_huerfano(self):
        self.assertEqual(auditoria.workflows_en_su_sitio(), [])


class TestWorkflowsEnSuSitioDetectaUnoHuerfano(unittest.TestCase):
    def _raiz_temporal(self) -> Path:
        raiz = Path(tempfile.mkdtemp(prefix="auditoria-pruebas-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(raiz, ignore_errors=True))
        return raiz

    def test_uno_fuera_de_la_raiz_se_ve(self):
        raiz = self._raiz_temporal()
        huerfano = raiz / "telegram" / ".github" / "workflows" / "lint.yml"
        huerfano.parent.mkdir(parents=True)
        huerfano.write_text("name: Lint\n", encoding="utf-8")
        with mock.patch.object(auditoria, "RAIZ", raiz):
            problemas = auditoria.workflows_en_su_sitio()
        self.assertTrue(problemas, "un workflow fuera de la raiz no se vio")
        self.assertIn("telegram", problemas[1])

    def test_uno_en_la_raiz_de_verdad_no_cuenta(self):
        raiz = self._raiz_temporal()
        bueno = raiz / ".github" / "workflows" / "pruebas.yml"
        bueno.parent.mkdir(parents=True)
        bueno.write_text("name: Pruebas\n", encoding="utf-8")
        with mock.patch.object(auditoria, "RAIZ", raiz):
            self.assertEqual(auditoria.workflows_en_su_sitio(), [])


if __name__ == "__main__":
    unittest.main()
