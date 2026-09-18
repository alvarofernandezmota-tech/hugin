"""Pruebas de `hugin/guardado/postgres.py` contra un Postgres real.

Se saltan enteras sin DIARIO_DATABASE_URL: no todo el mundo tiene Postgres a
mano, y el resto de la suite sigue corriendo siempre. Para correr estas:
`docker compose up -d` y exportar la URL.

Las que NO necesitan base —de donde sale la conexion— corren siempre, porque
es justo la parte nueva de este modulo y la que decide que un inquilino no
lea lo de otro.
"""

import os
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent

import entorno  # noqa: E402,F401

SIN_POSTGRES = not os.environ.get("DIARIO_DATABASE_URL", "").strip()
try:
    from hugin.guardado import postgres
    SIN_PSYCOPG = False
except ImportError:
    SIN_PSYCOPG = True


class Falso:
    """Un inquilino de mentira: aqui solo importan `base` y `nombre`."""

    def __init__(self, base=None, nombre="alguien"):
        self.base = base
        self.nombre = nombre


@unittest.skipIf(SIN_PSYCOPG, "requiere psycopg (pip install -e '.[postgres]')")
class TestDeQueBaseSeLee(unittest.TestCase):
    """Sin tocar ninguna base: solo de donde sale la URL."""

    def test_manda_la_del_inquilino(self):
        with mock.patch.dict("os.environ", {postgres.VARIABLE: "postgresql://x/entorno"}):
            self.assertEqual(postgres.url(Falso("postgresql://x/suya")), "postgresql://x/suya")

    def test_cada_inquilino_la_suya(self):
        # Esto es la separacion del ADR-024: no es un WHERE que se pueda
        # olvidar, son dos bases distintas.
        self.assertNotEqual(postgres.url(Falso("postgresql://x/uno")),
                            postgres.url(Falso("postgresql://x/otro")))

    def test_sin_base_propia_vale_la_del_entorno(self):
        # Asi es como no rompe nada: el bot de hoy no tiene inquilino.toml.
        with mock.patch.dict("os.environ", {postgres.VARIABLE: "postgresql://x/entorno"}):
            self.assertEqual(postgres.url(Falso(None)), "postgresql://x/entorno")
            self.assertEqual(postgres.url(), "postgresql://x/entorno")

    def test_sin_nada_se_dice_de_quien_y_que_falta(self):
        with mock.patch.dict("os.environ", {}, clear=False):
            os.environ.pop(postgres.VARIABLE, None)
            with self.assertRaises(RuntimeError) as e:
                postgres.url(Falso(None, nombre="peluqueria"))
            self.assertIn("peluqueria", str(e.exception))
            self.assertIn(postgres.VARIABLE, str(e.exception))

    def test_una_base_en_blanco_cuenta_como_no_puesta(self):
        with mock.patch.dict("os.environ", {postgres.VARIABLE: "postgresql://x/entorno"}):
            self.assertEqual(postgres.url(Falso("")), "postgresql://x/entorno")


@unittest.skipIf(SIN_PSYCOPG or SIN_POSTGRES, "requiere DIARIO_DATABASE_URL")
class TestIdaYVuelta(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        postgres.inicializar_esquema()

    def setUp(self):
        self._limpiar()
        self.addCleanup(self._limpiar)

    def _limpiar(self):
        with postgres.conectar() as conn:
            for tabla in ("tareas", "citas", "habitos_registro", "apuntes"):
                conn.execute(f"TRUNCATE {tabla}")
            conn.commit()

    def test_tareas(self):
        tareas = [{"id": 1, "texto": "llamar al médico", "estado": "pendiente",
                   "fecha": "2026-09-06", "hora": "10:00",
                   "creada": "2026-09-05 17:10", "hecha_el": None}]
        postgres.guardar_tareas(tareas)
        self.assertEqual(postgres.cargar_tareas(), tareas)

    def test_citas(self):
        citas = [{"id": 1, "texto": "médico", "fecha": "2026-09-06", "hora": "10:00",
                  "duracion": 60, "creada": "2026-09-05 17:10"}]
        postgres.guardar_citas(citas)
        self.assertEqual(postgres.cargar_citas(), citas)

    def test_habitos_booleano_y_valor_conviven(self):
        datos = {"2026-09-04": {"deporte": True, "meditar": False, "energia": 7}}
        postgres.guardar_habitos(datos)
        releido = postgres.cargar_habitos()["2026-09-04"]
        self.assertEqual(releido["deporte"], True)
        self.assertEqual(releido["energia"], 7)

    def test_apuntes(self):
        apuntes = [{"fecha": "2026-09-08", "que": "tele", "valor": 3,
                    "unidad": "h", "hora": "22:10"}]
        postgres.guardar_apuntes(apuntes)
        self.assertEqual(postgres.cargar_apuntes(), apuntes)


if __name__ == "__main__":
    unittest.main()
