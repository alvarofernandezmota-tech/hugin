"""Que el diario de alguien no se publique por un descuido.

Este repo es publico. `inquilino.carpeta()` y `negocio.carpeta_negocios()`
devuelven `cwd()/inquilinos` y `cwd()/negocios` cuando nadie les dice otra
cosa, y ahi dentro va el nombre de una persona, sus precios, su agenda y su
diario. Los dos modulos lo avisan en su docstring.

Un docstring no para un `git add -A`. Estas pruebas si.

Es la misma forma de `tests/test_libreria.py`: una regla que solo vive en un
comentario se rompe el dia que alguien tiene prisa, asi que se convierte en algo
que se cae. Y no es hipotetico: el 2026-09-18, con `MIDGAROR_DATOS` sin definir,
un script de respaldo volco el diario dentro del repo de codigo y lo subio. No
dio ni un error.
"""

import subprocess
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

import entorno  # noqa: E402,F401

from hugin import inquilino  # noqa: E402
from hugin.negocio import negocio  # noqa: E402


def ignorado(relativa: str) -> bool | None:
    """Si git ignoraria esa ruta. None si aqui no se puede preguntar."""
    try:
        hecho = subprocess.run(
            ["git", "check-ignore", "-q", relativa],
            cwd=RAIZ, capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    # 0 = ignorado, 1 = no ignorado, 128 = no es un repo o no hay git.
    if hecho.returncode == 128:
        return None
    return hecho.returncode == 0


class TestLosDatosDeAlguienNoSePublican(unittest.TestCase):
    def setUp(self):
        if ignorado(".gitignore") is None:
            self.skipTest("aqui no hay un repo git al que preguntar")

    def test_las_carpetas_por_defecto_estan_ignoradas(self):
        # Se preguntan por el nombre que devuelve el codigo, no por uno escrito
        # a mano: si alguien cambia el valor por defecto, esta prueba lo sigue
        # y avisa de que el .gitignore se ha quedado atras.
        for carpeta in (inquilino.carpeta(), negocio.carpeta_negocios()):
            nombre = carpeta.name
            dentro = f"{nombre}/alguien/diario.md"
            self.assertTrue(
                ignorado(dentro),
                f"«{dentro}» NO esta ignorado, y ahi aterriza el diario de "
                f"alguien por defecto. Anade «/{nombre}/» al .gitignore")

    def test_los_negocios_de_mentira_siguen_versionados(self):
        # El otro lado de la regla. Con «negocios/» sin barra delante, el
        # patron casa a cualquier profundidad y se lleva por delante
        # tests/negocios/, que es la entrada de casi toda la suite: dejaria de
        # versionarse sin que nada se pusiera en rojo hasta el siguiente clon.
        self.assertFalse(
            ignorado("tests/negocios/peluqueria/negocio.toml"),
            "tests/negocios/ se ha quedado ignorado: al patron del .gitignore "
            "le falta la barra de delante («/negocios/», no «negocios/»)")

    def test_no_hay_datos_de_nadie_versionados_ya(self):
        # Por si el descuido fue antes de que existiera esta prueba: que no
        # haya ya ficheros dentro de esas carpetas en el indice de git.
        for carpeta in (inquilino.carpeta(), negocio.carpeta_negocios()):
            hecho = subprocess.run(
                ["git", "ls-files", f"{carpeta.name}/"],
                cwd=RAIZ, capture_output=True, text=True, timeout=10)
            self.assertEqual(
                hecho.stdout.strip(), "",
                f"hay ficheros versionados dentro de «{carpeta.name}/»:\n"
                f"{hecho.stdout}\nEso es un repo publico. Sacalos con "
                f"«git rm --cached -r {carpeta.name}/»")


if __name__ == "__main__":
    unittest.main()
