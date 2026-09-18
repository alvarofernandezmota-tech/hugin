"""Que el badge del README no pueda mentir.

`estado-pruebas.json` es un fichero commiteado que un badge de shields.io lee
para poner «395 pasando · local 2026-09-18» en el README. Es un numero escrito
a mano en el repo, y esos envejecen solos: alguien anade doce pruebas, el
numero se queda en 395 y el escaparate pasa a decir algo que no es.

Un badge desactualizado es peor que no tener badge. Este fichero lo mide de
verdad y se cae cuando deja de cuadrar; se arregla con `make estado`.

Por que se cuenta cargando y no ejecutando: si esto lanzara `unittest` en un
subproceso, ese subproceso volveria a cargar este fichero, que lanzaria otro
subproceso, y asi hasta quedarse sin memoria. `discover()` construye la suite
sin correr ni un caso.
"""

import json
import re
import unittest
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ESTADO = RAIZ / "estado-pruebas.json"

import entorno  # noqa: E402,F401

# Lo que el badge promete: cuantas pruebas y de que dia es la medida.
FORMATO = re.compile(r"^(\d+) pasando · local (\d{4}-\d{2}-\d{2})$")


def cuantas_pruebas() -> int:
    """Las pruebas del cerebro que hay AHORA, contadas sin ejecutarlas."""
    return unittest.TestLoader().discover(str(RAIZ / "tests")).countTestCases()


class TestElBadgeDiceLaVerdad(unittest.TestCase):
    def setUp(self):
        self.assertTrue(ESTADO.is_file(), f"falta {ESTADO.name}: corre `make estado`")
        self.estado = json.loads(ESTADO.read_text(encoding="utf-8"))

    def test_el_numero_de_pruebas_es_el_de_verdad(self):
        casado = FORMATO.match(self.estado["message"])
        self.assertIsNotNone(
            casado,
            f"«{self.estado['message']}» no tiene la forma «N pasando · local AAAA-MM-DD»")
        commiteadas = int(casado.group(1))
        reales = cuantas_pruebas()
        self.assertEqual(
            commiteadas, reales,
            f"el badge dice {commiteadas} pruebas y hay {reales}. "
            f"Corre `make estado` y commitea {ESTADO.name}")

    def test_la_fecha_de_la_medida_no_esta_en_el_futuro(self):
        # Una fecha por delante de hoy solo sale de escribirla a mano, que es
        # justo lo que este fichero existe para que no pase.
        medida = date.fromisoformat(FORMATO.match(self.estado["message"]).group(2))
        self.assertLessEqual(
            medida, date.today(),
            f"{ESTADO.name} esta fechado el {medida}, que aun no ha llegado")

    def test_el_badge_dice_que_la_medida_es_local(self):
        # No es cosmetico. Hoy no hay CI —Actions no coge runner por un cobro
        # de la cuenta—, asi que un badge que insinue «CI: passing» estaria
        # vendiendo una verificacion automatica que no existe. Lo que hay es
        # alguien que lo corrio en su maquina, y eso es lo que tiene que decir.
        self.assertIn("local", self.estado["message"])
        self.assertNotIn("CI", self.estado["label"])

    def test_shields_entiende_el_fichero(self):
        # Sin `schemaVersion: 1` shields.io devuelve un badge de error, y eso
        # no se ve hasta mirar el README ya subido.
        self.assertEqual(self.estado["schemaVersion"], 1)
        for clave in ("label", "message", "color"):
            self.assertTrue(self.estado.get(clave), f"falta «{clave}» en {ESTADO.name}")


if __name__ == "__main__":
    unittest.main()
