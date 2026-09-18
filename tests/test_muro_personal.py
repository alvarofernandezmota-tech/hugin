"""Que `hugin.personal` no se cuele donde no toca — antes de que haya nada
que proteger.

`hugin/personal/` es el parser de fechas de UNA PERSONA: «el lunes» puede
mirar hacia atrás (ver `hugin/personal/__init__.py`). `hugin/mente/` es el
motor de la reserva de un negocio: las fechas van siempre hacia delante.
Mezclarlos es la fusión que se refutó tres veces en la fase 4 del ADR-024 —
construida, no razonada, y las tres rompían algo real al ejecutarlas.

Esta prueba lee el **árbol de sintaxis**, igual que `test_libreria.py` con
los canales: una regla que solo vive en un comentario se salta el día que
alguien tiene prisa.

Va en su propio fichero y no dentro de `test_libreria.py` porque mira hacia
FUERA de `hugin/` — a `telefono/`, que es exactamente por donde se colaba:
`tests/test_libreria.py:32` solo recorre `hugin/<paquete>/`, así que un
import de `hugin.personal` desde `telefono/dueno/agentes.py` quedaba fuera de
su alcance.
"""

import ast
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

import entorno  # noqa: E402,F401

# Lo que NO puede importar hugin.personal. hugin/guardado/ se excluye a
# proposito: es infraestructura sin opinion de dominio (almacen, postgres,
# sincronizar), y no hay ninguna regla de fechas que proteger ahi.
PROHIBIDO = (
    RAIZ / "hugin" / "mente",
    RAIZ / "hugin" / "negocio",
    RAIZ / "telefono",
)

# telegram/ SI puede: es el canal personal, el que de verdad usa
# hugin.personal (ADR-024, fase 5). Excluido a proposito, y con el motivo
# escrito para que nadie lo añada sin pensarlo.


def modulos():
    for carpeta in PROHIBIDO:
        if not carpeta.is_dir():
            continue
        for fich in sorted(carpeta.rglob("*.py")):
            if "__pycache__" in fich.parts or "tests" in fich.parts:
                continue
            yield fich


class TestElMuroDePersonal(unittest.TestCase):
    def test_nada_prohibido_importa_hugin_personal(self):
        vistos = 0
        for fich in modulos():
            vistos += 1
            arbol = ast.parse(fich.read_text(encoding="utf-8"))
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.ImportFrom):
                    modulo = nodo.module or ""
                    self.assertFalse(
                        modulo == "hugin.personal" or modulo.startswith("hugin.personal."),
                        f"{fich.relative_to(RAIZ)} importa «{modulo}»: "
                        f"hugin.personal es del canal personal (telegram/), "
                        f"no de aqui")
                elif isinstance(nodo, ast.Import):
                    for alias in nodo.names:
                        self.assertFalse(
                            alias.name == "hugin.personal"
                            or alias.name.startswith("hugin.personal."),
                            f"{fich.relative_to(RAIZ)} importa «{alias.name}»: "
                            f"hugin.personal es del canal personal (telegram/), "
                            f"no de aqui")
        # Si esto da 0, la prueba pasa sin haber mirado nada: silenciosamente
        # inutil si `telefono/` cambiara de sitio o se vaciara.
        self.assertGreater(vistos, 0, "no se ha revisado ni un fichero: la "
                            "prueba no protege nada")


if __name__ == "__main__":
    unittest.main()
