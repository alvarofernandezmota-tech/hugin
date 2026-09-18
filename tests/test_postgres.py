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
from contextlib import contextmanager
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


class TestSinPsycopgUnInquilinoDeFicheroFunciona(unittest.TestCase):
    """Sin psycopg instalado, un inquilino de FICHERO tiene que ir igual.

    El fallo real, medido en Madre el 2026-09-18 con el bot nuevo recién
    montado: `import psycopg` estaba a la cabeza de `postgres.py`, así que
    `_en_postgres(inq)` —que solo lee `VARIABLE` para saber si hay que
    mirar Postgres siquiera— tumbaba el módulo entero. Resultado: un
    `/tarea` de un inquilino sin `base` y sin Postgres por ningún lado
    reventaba con «los registros en Postgres necesitan psycopg», hablando
    de algo que no se estaba usando. El venv de `telegram/` no lleva el
    extra `[postgres]` a propósito.

    Se simula la ausencia con `sys.modules`, para que la prueba diga lo
    mismo esté psycopg instalado o no en la máquina que la corre.
    """

    @contextmanager
    def _sin_psycopg(self):
        """psycopg fuera, y `postgres.py` sin cargar para que se reimporte.

        Las dos cosas hacen falta. Bloquear solo `psycopg` no prueba nada si
        `hugin.guardado.postgres` ya está en `sys.modules`: su import de
        cabecera ya se ejecutó —con psycopg disponible— y `_en_postgres()`
        se lleva el módulo cacheado sin volver a mirar. Comprobado: con el
        bug de vuelta, la prueba pasaba igual.

        Y hay que quitar el paquete `hugin.guardado` ENTERO, no solo
        `hugin.guardado.postgres`: `from hugin.guardado import postgres`
        mira primero `sys.modules["hugin.guardado.postgres"]`, pero si no
        está tira del **atributo** `postgres` del paquete ya importado, que
        sigue apuntando al módulo viejo. Borrando solo el submódulo, la
        prueba pasaba con el bug puesto — comprobado.

        `patch.dict` deja `sys.modules` como estaba al salir, incluido lo
        que se borre aquí dentro.
        """
        import sys
        fuera = {n: None for n in list(sys.modules)
                 if n == "psycopg" or n.startswith("psycopg.")}
        fuera["psycopg"] = None
        with mock.patch.dict(sys.modules, fuera):
            for cargado in [n for n in list(sys.modules)
                            if n == "hugin.guardado" or n.startswith("hugin.guardado.")
                            or n.startswith("hugin.personal.")
                            or n == "hugin.apuntes"]:
                del sys.modules[cargado]
            yield

    def test_cargar_de_fichero_no_necesita_psycopg(self):
        import tempfile
        from hugin import inquilino as hugin_inquilino
        from hugin.personal import tareas

        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "alvaro"
            ruta.mkdir()
            inq = hugin_inquilino.Inquilino(
                nombre="alvaro", ruta=ruta,
                capacidades=frozenset({"tareas"}), base=None)
            with self._sin_psycopg(), mock.patch.dict(os.environ, {"DIARIO_DATABASE_URL": ""}):
                self.assertEqual(tareas.cargar(inq), [])

    def test_pero_conectar_sigue_diciendo_que_falta_psycopg(self):
        # Lo otro no se pierde: cuando Postgres SÍ hace falta, el aviso
        # tiene que seguir nombrando el extra que hay que instalar.
        from hugin.guardado import postgres as pg
        with self._sin_psycopg():
            with self.assertRaises(ImportError) as caso:
                with pg.conectar(Falso("postgresql://x/y")):
                    pass
        self.assertIn("psycopg", str(caso.exception))
        self.assertIn("[postgres]", str(caso.exception))


if __name__ == "__main__":
    unittest.main()
