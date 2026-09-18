"""Pruebas del inquilino: alguien a quien se atiende, persona o empresa.

Todo sobre carpetas temporales: nada de esto toca `inquilinos/` de verdad,
que es donde estaria el diario de alguien.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Nada de sys.path: el paquete se instala en editable (`make instalar`).
RAIZ = Path(__file__).resolve().parent.parent

import entorno  # noqa: E402,F401

from hugin import inquilino  # noqa: E402


class CasoConCarpeta(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        parche = mock.patch.dict("os.environ", {inquilino.VARIABLE: str(self.base)})
        parche.start()
        self.addCleanup(parche.stop)

    def alta(self, nombre: str, toml: str | None = None, ficheros=()) -> Path:
        ruta = self.base / nombre
        ruta.mkdir()
        if toml is not None:
            (ruta / inquilino.FICHERO).write_text(toml, encoding="utf-8")
        for f in ficheros:
            destino = ruta / f
            destino.parent.mkdir(parents=True, exist_ok=True)
            if f.endswith("/"):
                destino.mkdir(exist_ok=True)
            else:
                destino.write_text("", encoding="utf-8")
        return ruta


class TestUnaPersonaYUnaEmpresaSonLoMismo(CasoConCarpeta):
    def test_una_persona_con_lo_suyo(self):
        self.alta("alvaro", '''
            nombre = "Álvaro"
            capacidades = ["diario", "tareas", "habitos", "apuntes", "agenda"]
        ''')
        inq = inquilino.cargar("alvaro")
        self.assertEqual(inq.nombre, "Álvaro")
        self.assertTrue(inq.puede("tareas"))
        self.assertTrue(inq.puede("diario"))
        self.assertFalse(inq.puede("tarifas"))

    def test_una_empresa_con_lo_suyo(self):
        self.alta("peluqueria", '''
            nombre = "Peluquería Rosa"
            capacidades = ["agenda", "tarifas", "faq"]
        ''')
        inq = inquilino.cargar("peluqueria")
        self.assertTrue(inq.puede("tarifas"))
        self.assertFalse(inq.puede("habitos"))

    def test_un_autonomo_tiene_de_las_dos(self):
        # El caso que tumba la idea de un `tipo = "persona" | "negocio"`:
        # quiere cobrar Y llevar sus tareas. Con tipos cerrados no cabe.
        self.alta("fontanero", '''
            capacidades = ["agenda", "tarifas", "tareas", "apuntes"]
        ''')
        inq = inquilino.cargar("fontanero")
        self.assertTrue(inq.puede("tarifas"))
        self.assertTrue(inq.puede("tareas"))


class TestSinConfiguracion(CasoConCarpeta):
    def test_sin_toml_se_deduce_de_lo_que_hay_escrito(self):
        # Dar de alta a alguien no puede exigir escribir configuracion antes
        # de tener nada: mismo trato que `negocio.cargar()`.
        self.alta("copia", ficheros=("tarifas.md", "faq.md"))
        inq = inquilino.cargar("copia")
        self.assertEqual(inq.capacidades, frozenset({"tarifas", "faq"}))
        self.assertEqual(inq.nombre, "copia")

    def test_una_carpeta_de_diario_es_la_capacidad_de_diario(self):
        ruta = self.alta("yo")
        (ruta / "diario").mkdir()
        self.assertTrue(inquilino.cargar("yo").puede("diario"))


class TestLaBaseSaleDelInquilino(CasoConCarpeta):
    def test_cada_uno_tiene_la_suya(self):
        self.alta("uno", 'base = "postgresql://x/uno"\ncapacidades = []')
        self.alta("otro", 'base = "postgresql://x/otro"\ncapacidades = []')
        self.assertEqual(inquilino.cargar("uno").base, "postgresql://x/uno")
        self.assertEqual(inquilino.cargar("otro").base, "postgresql://x/otro")

    def test_sin_base_es_None_y_manda_el_entorno(self):
        # Asi es como no rompe nada: el bot de hoy no tiene fichero y sigue
        # usando DIARIO_DATABASE_URL como hasta ahora.
        self.alta("sinbase", 'capacidades = []')
        self.assertIsNone(inquilino.cargar("sinbase").base)

    def test_una_base_en_blanco_cuenta_como_no_puesta(self):
        # En un TOML escrito a mano es facil dejar `base = ""`, y eso debe
        # comportarse como no haberla puesto, no como una URL vacia.
        self.alta("vacia", 'base = "   "\ncapacidades = []')
        self.assertIsNone(inquilino.cargar("vacia").base)


class TestLoQueSeDiceEnVozAlta(CasoConCarpeta):
    def test_una_capacidad_inventada_en_el_toml_se_canta(self):
        self.alta("raro", 'capacidades = ["tareas", "telepatia"]')
        with self.assertRaises(ValueError) as e:
            inquilino.cargar("raro")
        self.assertIn("telepatia", str(e.exception))

    def test_preguntar_por_una_capacidad_que_no_existe_es_un_error(self):
        # Devolver False callaria el fallo: la funcion que la pregunta no se
        # ejecutaria nunca y nadie se enteraria.
        self.alta("alguien", 'capacidades = ["tareas"]')
        with self.assertRaises(ValueError):
            inquilino.cargar("alguien").puede("tareaz")

    def test_un_toml_roto_dice_cual_y_que_le_pasa(self):
        self.alta("roto", 'capacidades = [esto no es toml')
        with self.assertRaises(ValueError) as e:
            inquilino.cargar("roto")
        self.assertIn(inquilino.FICHERO, str(e.exception))

    def test_un_inquilino_que_no_existe_dice_cuales_hay(self):
        self.alta("alvaro", 'capacidades = []')
        with self.assertRaises(ValueError) as e:
            inquilino.cargar("nadie")
        self.assertIn("alvaro", str(e.exception))


class TestListar(CasoConCarpeta):
    def test_los_da_por_orden_y_sin_los_ocultos(self):
        self.alta("peluqueria", 'capacidades = []')
        self.alta("alvaro", 'capacidades = []')
        (self.base / ".git").mkdir()
        self.assertEqual(inquilino.listar(), ["alvaro", "peluqueria"])

    def test_sin_carpeta_no_revienta(self):
        with mock.patch.dict("os.environ", {inquilino.VARIABLE: str(self.base / "nada")}):
            self.assertEqual(inquilino.listar(), [])


if __name__ == "__main__":
    unittest.main()
