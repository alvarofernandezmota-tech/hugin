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
FUERA del paquete — a `telefono/`, que es exactamente por donde se colaba:
`test_libreria.py` solo recorre `src/hugin/<paquete>/`, así que un import de
`hugin.personal` desde `telefono/dueno/agentes.py` quedaba fuera de su
alcance.

## Por qué el contador de abajo dejó de valer (ADR-027, 2026-09-19)

El muro estuvo verde sin mirar `mente/` ni `negocio/` desde que el paquete
se mudó a `src/hugin/`: `PROHIBIDO` seguía apuntando a `hugin/mente`, esa
carpeta ya no existía, y un `if not carpeta.is_dir(): continue` la saltaba
sin decir nada. `test_libreria.py` se cayó en rojo con la misma mudanza y
por eso se arregló; esto no se cayó, así que nadie se enteró.

El `assertGreater(vistos, 0)` que había para justamente evitarlo no llegó a
saltar por dos motivos a la vez, y los dos hay que cerrarlos:

- Contaba el total de las tres carpetas, no cada una. Con `telefono/` viva,
  dos carpetas desaparecidas dan un total perfectamente positivo.
- De los 3283 ficheros que contaba en `telefono/`, 3267 eran de
  `telefono/venv/`. Un contador que mide sobre todo dependencias de terceros
  sigue dando un número grande aunque no quede ni un módulo propio.

Ahora cada carpeta de `PROHIBIDO` tiene que existir y aportar ficheros
PROPIOS, y una que no esté es un fallo, no un salto: si mañana algo se mueve
otra vez, esta prueba se cae en la mudanza en vez de quedarse mirando.
"""

import ast
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

import entorno  # noqa: E402,F401

# Lo que NO puede importar hugin.personal. `guardado/` se excluye a
# proposito: es infraestructura sin opinion de dominio (almacen, postgres,
# sincronizar), y no hay ninguna regla de fechas que proteger ahi.
#
# El paquete vive en `src/hugin/` desde el ADR-027. Escrito con `src` por
# delante y no con un `RAIZ / "hugin"` heredado: es el despiste que dejo
# este muro sin mirar nada durante toda una tarde.
PROHIBIDO = (
    RAIZ / "src" / "hugin" / "mente",
    RAIZ / "src" / "hugin" / "negocio",
    RAIZ / "telefono",
)

# telegram/ SI puede: es el canal personal, el que de verdad usa
# hugin.personal (ADR-024, fase 5). Excluido a proposito, y con el motivo
# escrito para que nadie lo añada sin pensarlo.

# Lo que no es codigo de la casa. `venv/` sobre todo: son las dependencias
# de la puerta de telefono, no se revisan, y contarlas era lo que hacia que
# el contador de mas abajo diera siempre un numero tranquilizador.
IGNORADAS = ("__pycache__", "tests", "venv", ".venv")


def modulos_de(carpeta: Path):
    """Los `.py` propios de una carpeta, sin dependencias ni pruebas."""
    for fich in sorted(carpeta.rglob("*.py")):
        if any(parte in IGNORADAS for parte in fich.parts):
            continue
        yield fich


class TestElMuroDePersonal(unittest.TestCase):
    def test_nada_prohibido_importa_hugin_personal(self):
        for carpeta in PROHIBIDO:
            with self.subTest(carpeta=carpeta.relative_to(RAIZ)):
                # Cada carpeta por separado, y existir no basta: tiene que
                # aportar ficheros. Es lo unico que convierte este muro en
                # una prueba y no en un adorno.
                self.assertTrue(carpeta.is_dir(),
                                f"{carpeta.relative_to(RAIZ)} no existe: el muro "
                                f"no esta mirando lo que dice mirar (se movio "
                                f"de sitio?)")
                vistos = 0
                for fich in modulos_de(carpeta):
                    vistos += 1
                    self._sin_personal(fich)
                self.assertGreater(vistos, 0,
                                   f"ni un fichero propio revisado en "
                                   f"{carpeta.relative_to(RAIZ)}: la prueba no "
                                   f"protege nada ahi")

    def _sin_personal(self, fich: Path) -> None:
        arbol = ast.parse(fich.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ImportFrom):
                nombres = [nodo.module or ""]
            elif isinstance(nodo, ast.Import):
                nombres = [alias.name for alias in nodo.names]
            else:
                continue
            for nombre in nombres:
                self.assertFalse(
                    nombre == "hugin.personal"
                    or nombre.startswith("hugin.personal."),
                    f"{fich.relative_to(RAIZ)} importa «{nombre}»: "
                    f"hugin.personal es del canal personal (telegram/), "
                    f"no de aqui")


if __name__ == "__main__":
    unittest.main()
