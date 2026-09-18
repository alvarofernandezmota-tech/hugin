"""Pruebas de almacen.py — el único sitio que toca el disco.

Esto va a correr atendiendo llamadas, así que lo que se comprueba no es que
sepa leer JSON: es que **no destruya el registro cuando algo sale mal**.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

# Nada de sys.path: el paquete se instala en editable (`make instalar`),
# asi que `import hugin` funciona sin trucos (ADR-024).
RAIZ = Path(__file__).resolve().parent.parent

import entorno  # noqa: E402,F401

from hugin.guardado import almacen  # noqa: E402


class CasoAlmacen(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ruta = Path(self._tmp.name) / "datos" / "cosas.json"


class TestIdaYVuelta(CasoAlmacen):
    def test_lo_guardado_es_lo_que_se_lee(self):
        almacen.guardar(self.ruta, [{"id": 1, "texto": "ñandú"}], 1)
        self.assertEqual(almacen.cargar(self.ruta, 1, vacio=[]),
                         [{"id": 1, "texto": "ñandú"}])

    def test_sin_fichero_devuelve_el_vacio_que_se_pida(self):
        self.assertEqual(almacen.cargar(self.ruta, 1, vacio=[]), [])
        self.assertEqual(almacen.cargar(self.ruta, 1, vacio={}), {})

    def test_el_vacio_no_se_comparte_entre_llamadas(self):
        # Devolver `vacio` en vez de una copia hace que dos lecturas compartan
        # la misma lista y que lo que añada una aparezca en la otra.
        primera = almacen.cargar(self.ruta, 1, vacio=[])
        primera.append("intruso")
        self.assertEqual(almacen.cargar(self.ruta, 1, vacio=[]), [])

    def test_crea_la_carpeta_si_no_existe(self):
        almacen.guardar(self.ruta, [], 1)
        self.assertTrue(self.ruta.exists())


class TestLaVersionDeEsquema(CasoAlmacen):
    def test_lo_escrito_lleva_envoltorio(self):
        almacen.guardar(self.ruta, [1, 2], 3)
        crudo = json.loads(self.ruta.read_text(encoding="utf-8"))
        self.assertEqual(crudo["schemaVersion"], 3)
        self.assertEqual(crudo["datos"], [1, 2])

    def test_un_fichero_mas_nuevo_que_el_codigo_para_en_vez_de_leerlo_mal(self):
        almacen.guardar(self.ruta, [1], 5)
        with self.assertRaises(ValueError) as caso:
            almacen.cargar(self.ruta, 1, vacio=[])
        self.assertIn("esquema 5", str(caso.exception))

    def test_un_fichero_sin_envoltorio_se_lee_igual(self):
        # Formato viejo: una lista a pelo. Se lee y se envolverá al guardar.
        self.ruta.parent.mkdir(parents=True)
        self.ruta.write_text('[{"id": 1}]', encoding="utf-8")
        self.assertEqual(almacen.cargar(self.ruta, 1, vacio=[]), [{"id": 1}])


class TestUnJsonRotoSeExplica(CasoAlmacen):
    def romper(self):
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text('{"schemaVersion": 1, "datos": [1, 2', encoding="utf-8")

    def test_dice_el_fichero_y_donde_esta_roto(self):
        self.romper()
        with self.assertRaises(ValueError) as caso:
            almacen.cargar(self.ruta, 1, vacio=[])
        mensaje = str(caso.exception)
        self.assertIn("cosas.json", mensaje)
        self.assertIn("línea", mensaje)

    def test_no_es_un_jsondecodeerror_pelado(self):
        # JSONDecodeError ya hereda de ValueError, así que assertRaises sola no
        # probaría nada. Lo que se exige es que el error traducido sustituya al
        # crudo y lleve el original como causa.
        self.romper()
        with self.assertRaises(ValueError) as caso:
            almacen.cargar(self.ruta, 1, vacio=[])
        self.assertNotIsInstance(caso.exception, json.JSONDecodeError)
        self.assertIsInstance(caso.exception.__cause__, json.JSONDecodeError)

    def test_deja_copia_del_roto_sin_tocar_el_original(self):
        self.romper()
        original = self.ruta.read_text(encoding="utf-8")
        with self.assertRaises(ValueError):
            almacen.cargar(self.ruta, 1, vacio=[])
        copia = self.ruta.with_name(self.ruta.name + ".corrupto")
        self.assertEqual(copia.read_text(encoding="utf-8"), original)
        self.assertEqual(self.ruta.read_text(encoding="utf-8"), original)


class TestEscrituraAtomica(CasoAlmacen):
    def test_un_fallo_a_mitad_deja_intacto_lo_que_habia(self):
        # Lo que de verdad importa: `open(ruta, "w")` truncaría el fichero
        # antes de escribir, y un fallo ahí deja el registro de llamadas en
        # cero bytes. Con el rename, o está lo viejo o está lo nuevo.
        almacen.guardar(self.ruta, [{"id": 1, "texto": "la llamada buena"}], 1)
        antes = self.ruta.read_text(encoding="utf-8")

        class NoSerializable:
            pass

        with self.assertRaises(TypeError):
            almacen.guardar(self.ruta, [NoSerializable()], 1)
        self.assertEqual(self.ruta.read_text(encoding="utf-8"), antes)

    def test_no_deja_temporales_tirados(self):
        class NoSerializable:
            pass

        with self.assertRaises(TypeError):
            almacen.guardar(self.ruta, [NoSerializable()], 1)
        almacen.guardar(self.ruta, [], 1)
        sobrantes = [p.name for p in self.ruta.parent.iterdir()
                     if p.name.startswith(".cosas.json.")]
        self.assertEqual(sobrantes, [])

    def test_el_temporal_va_en_la_misma_carpeta(self):
        # Un rename entre sistemas de archivos no es atómico. Si el temporal
        # cayera en /tmp, toda la garantía sería mentira.
        vistos = []
        real = almacen.tempfile.mkstemp

        def espia(*args, **kwargs):
            vistos.append(kwargs.get("dir"))
            return real(*args, **kwargs)

        almacen.tempfile.mkstemp = espia
        self.addCleanup(setattr, almacen.tempfile, "mkstemp", real)
        almacen.guardar(self.ruta, [], 1)
        self.assertEqual(vistos, [self.ruta.parent])

    def test_sobrescribir_no_deja_restos_del_anterior(self):
        almacen.guardar(self.ruta, [{"id": 1}], 1)
        almacen.guardar(self.ruta, [{"id": 2}], 1)
        self.assertEqual(almacen.cargar(self.ruta, 1, vacio=[]), [{"id": 2}])
        self.assertEqual(len(list(self.ruta.parent.iterdir())), 1)


class TestEscribirSuelto(CasoAlmacen):
    def test_escribe_texto_tal_cual(self):
        destino = self.ruta.parent / "nota.txt"
        almacen.escribir(destino, "hola\n")
        self.assertEqual(destino.read_text(encoding="utf-8"), "hola\n")
        self.assertTrue(os.path.exists(destino))


class TestMigraciones(CasoAlmacen):
    """Portado de la fase 4 del ADR-024: `_v0_a_v1` de tareas.py migra un
    fichero que hoy está en producción, no es higiene."""

    def _v0_a_v1(self, datos):
        return [dict(t, estado="pendiente") for t in datos]

    def test_un_fichero_v0_se_migra_hasta_la_version_pedida(self):
        almacen.guardar(self.ruta, [{"id": 1}], 0)
        self.assertEqual(
            almacen.cargar(self.ruta, 1, vacio=[], migraciones={0: self._v0_a_v1}),
            [{"id": 1, "estado": "pendiente"}])

    def test_sin_migraciones_no_se_intenta_nada_como_siempre(self):
        # El comportamiento de antes de que existiera el parámetro: un
        # fichero de otra versión se lee tal cual, sin ValueError.
        almacen.guardar(self.ruta, [{"id": 1}], 0)
        self.assertEqual(almacen.cargar(self.ruta, 1, vacio=[]), [{"id": 1}])

    def test_una_migracion_que_falta_lo_dice(self):
        almacen.guardar(self.ruta, [{"id": 1}], 0)
        with self.assertRaises(ValueError) as caso:
            almacen.cargar(self.ruta, 2, vacio=[], migraciones={0: self._v0_a_v1})
        self.assertIn("falta la migración del esquema 1", str(caso.exception))

    def test_un_fichero_sin_envoltorio_tambien_se_migra(self):
        # Formato viejo (versión 0, sin schemaVersion): igual que en
        # midgaror, se reconoce por la forma y se migra igual.
        almacen.escribir(self.ruta, json.dumps([{"id": 1}]))
        self.assertEqual(
            almacen.cargar(self.ruta, 1, vacio=[], migraciones={0: self._v0_a_v1}),
            [{"id": 1, "estado": "pendiente"}])


class TestOrdenarClaves(CasoAlmacen):
    """Portado de la fase 4: sin esto, `habitos.json` cambia entero en cada
    escritura y el commit del bot sale con un diff ilegible (ADR-013)."""

    def test_guardar_dos_veces_da_el_mismo_fichero(self):
        datos = {"2026-09-11": {"gimnasio": 1}, "2026-09-05": {"agua": True}}
        almacen.guardar(self.ruta, datos, 1, ordenar_claves=True)
        primera = self.ruta.read_text(encoding="utf-8")
        almacen.guardar(self.ruta, dict(datos), 1, ordenar_claves=True)
        self.assertEqual(self.ruta.read_text(encoding="utf-8"), primera)

    def test_las_claves_salen_ordenadas_en_el_texto(self):
        almacen.guardar(self.ruta, {"b": 1, "a": 2}, 1, ordenar_claves=True)
        texto = self.ruta.read_text(encoding="utf-8")
        self.assertLess(texto.index('"a"'), texto.index('"b"'))

    def test_por_defecto_no_se_ordena(self):
        # El comportamiento de siempre: nadie lo pide, nadie lo cambia.
        almacen.guardar(self.ruta, {"b": 1, "a": 2}, 1)
        texto = self.ruta.read_text(encoding="utf-8")
        self.assertLess(texto.index('"b"'), texto.index('"a"'))


if __name__ == "__main__":
    unittest.main()
