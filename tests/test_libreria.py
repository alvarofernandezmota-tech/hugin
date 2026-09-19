"""Que hugin siga siendo una libreria y no se vuelva media aplicacion.

Estas pruebas no miran lo que el codigo hace: miran su **forma**. Son las
unicas que se caen el dia que alguien —yo, dentro de seis meses, con prisa—
mete aqui un import de un canal porque «total, es una linea».
"""

import ast
import os
import unittest
from pathlib import Path

# Nada de sys.path: el paquete se instala en editable (`make instalar`).
RAIZ = Path(__file__).resolve().parent.parent
CEREBRO = RAIZ / "src" / "hugin"

import entorno  # noqa: E402,F401

from hugin.guardado import ajustes  # noqa: E402

PAQUETES = ("mente", "negocio", "guardado", "personal")

# Un canal es por donde entra la conversacion. El cerebro no sabe cual es, y
# esa es toda la razon de que sea un paquete aparte.
#
# Desde el ADR-024 los canales viven en este mismo repo (`telegram/`,
# `telefono/`), asi que esta prueba es lo UNICO que sujeta el corte: antes
# tambien lo sujetaba la frontera entre repositorios, y ya no.
CANALES = {"telefono", "dueno", "twilio", "telnyx", "signalwire", "flask"}


def modulos():
    for paquete in PAQUETES:
        yield from sorted((CEREBRO / paquete).glob("*.py"))


class TestNoSabeDeNingunCanal(unittest.TestCase):
    def test_ningun_modulo_importa_un_canal(self):
        for fich in modulos():
            arbol = ast.parse(fich.read_text(encoding="utf-8"))
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Import):
                    nombres = [a.name.split(".")[0] for a in nodo.names]
                elif isinstance(nodo, ast.ImportFrom):
                    nombres = [(nodo.module or "").split(".")[0]]
                else:
                    continue
                for nombre in nombres:
                    self.assertNotIn(
                        nombre, CANALES,
                        f"{fich.name} importa «{nombre}»: eso es un canal, y el "
                        f"cerebro no tiene que enterarse de por donde le hablan")

    def test_los_imports_de_casa_van_por_el_nombre_del_paquete(self):
        # `from mente import fechas` funciona al correr las pruebas desde la
        # raiz y se cae montado como submodulo, que es donde de verdad se usa.
        # El fallo saldria en la aplicacion, no aqui, si no se comprueba.
        for fich in modulos():
            for i, linea in enumerate(fich.read_text(encoding="utf-8").splitlines(), 1):
                pelada = linea.strip()
                for paquete in PAQUETES:
                    self.assertFalse(
                        pelada.startswith(f"from {paquete} import ")
                        or pelada == f"import {paquete}",
                        f"{fich.name}:{i} → «{pelada}»; tiene que ser hugin.{paquete}")


    def test_ninguna_carpeta_de_la_aplicacion_sale_de_file(self):
        """El fallo que casi se cuela al partir el repo.

        `Path(__file__).parent.parent / "datos"` apuntaba a la raiz del repo
        mientras esto vivia dentro de la aplicacion. Sacado a libreria apunta
        a `hugin/`, que no es de nadie: la agenda, el conocimiento y los
        negocios se habrian escrito dentro del submodulo y el bot habria
        seguido diciendo que todo va bien.

        Se resuelven desde el directorio de trabajo, que las unidades de
        systemd fijan en la raiz de la aplicacion.
        """
        # Se mira el arbol, no el texto: los comentarios y los docstrings de
        # aqui **explican** por que no se usa `__file__`, y buscando la
        # cadena a pelo saltaria justo la documentacion de la regla.
        for fich in modulos():
            arbol = ast.parse(fich.read_text(encoding="utf-8"))
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Name) and nodo.id == "__file__":
                    self.fail(f"{fich.name}:{nodo.lineno} → una ruta desde "
                              f"__file__ cae dentro de hugin/, y esa carpeta "
                              f"es de la aplicacion")


class TestSeUsaComoSeDice(unittest.TestCase):
    def test_el_cerebro_es_un_paquete_dentro_del_repo(self):
        # Desde el ADR-024 el repo es el producto y el cerebro es `hugin/`
        # dentro de el. Antes el paquete era la carpeta del repo, lo que
        # obligaba a clonarlo con ese nombre exacto para que `import hugin`
        # encontrara algo; ahora lo que va al sys.path es la raiz.
        self.assertTrue(CEREBRO.is_dir(), "falta el paquete hugin/")
        self.assertTrue((CEREBRO / "__init__.py").exists())

    def test_cada_paquete_existe_y_dice_para_que_es(self):
        for paquete in PAQUETES:
            inicio = CEREBRO / paquete / "__init__.py"
            self.assertTrue(inicio.exists(), f"falta {paquete}/__init__.py")
            self.assertTrue(ast.get_docstring(ast.parse(inicio.read_text(encoding="utf-8"))),
                            f"{paquete}/__init__.py no dice para que es")


class TestLaSuiteNoLeeTusSecretos(unittest.TestCase):
    """Lo mismo que en gjallarhorn: correr las pruebas no carga tu .env."""

    def test_las_credenciales_no_estan_en_el_entorno(self):
        for variable in entorno.CREDENCIALES:
            self.assertIsNone(os.environ.get(variable), f"{variable} esta puesta")

    def test_el_env_de_la_suite_no_existe(self):
        self.assertFalse(ajustes.fichero().exists())

    def test_el_env_se_busca_desde_el_directorio_de_trabajo(self):
        # Nunca desde `__file__`: esta libreria vive dentro de la aplicacion
        # que la usa, y el .env es de quien despliega, no de quien programa.
        fuente = (CEREBRO / "guardado" / "ajustes.py").read_text(encoding="utf-8")
        cuerpo = fuente.split("def fichero", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("Path.cwd()", cuerpo)
        self.assertNotIn("__file__", cuerpo)


if __name__ == "__main__":
    unittest.main()
