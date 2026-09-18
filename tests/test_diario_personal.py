"""Pruebas de hugin/personal/diario.py.

Portadas de diario/tests/test_organizar.py y diario/tests/test_bridge.py de
midgaror: mismo cuerpo, `organizar_diario`/`bifrost_bridge` (dos ficheros)
fundidos en el único `hugin.personal.diario` que reemplaza a los dos.
"""

import tempfile
import unittest
from pathlib import Path

import entorno  # noqa: E402,F401

from hugin.personal import diario

PLANTILLA = """---
tipo: diario
fecha: 2026-09-06
repo: midgaror
---

# 2026-09-06

## Qué ha pasado hoy


## Cómo me siento


## Avances / aprendizajes


## Para mañana
"""


class TestSecciones(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name) / "2026-09-06.md"
        self.ruta.write_text(PLANTILLA, encoding="utf-8")

    def _seccion(self, titulo: str) -> str:
        """El cuerpo de una sección, sin su título."""
        t = self.ruta.read_text(encoding="utf-8")
        cuerpo = t.split(titulo, 1)[1]
        fin = cuerpo.find("\n## ")
        return (cuerpo if fin == -1 else cuerpo[:fin]).strip()

    def test_por_defecto_sigue_yendo_a_que_ha_pasado_hoy(self):
        diario.organizar_texto("he dormido fatal", self.ruta, hora="09:00")
        self.assertEqual(self._seccion("## Qué ha pasado hoy"), "09:00\nhe dormido fatal")
        for otra in ("## Cómo me siento", "## Avances / aprendizajes", "## Para mañana"):
            self.assertEqual(self._seccion(otra), "")

    def test_siento_lleva_la_hora_porque_es_un_momento_del_dia(self):
        diario.organizar_texto("contento", self.ruta, hora="09:00", seccion="siento")
        diario.organizar_texto("cansado", self.ruta, hora="22:00", seccion="siento")
        self.assertEqual(self._seccion("## Cómo me siento"),
                         "09:00\ncontento\n\n22:00\ncansado")
        self.assertEqual(self._seccion("## Qué ha pasado hoy"), "")

    def test_aprendo_y_plan_son_viñetas_porque_son_elementos_sueltos(self):
        diario.organizar_texto("lo de filters.COMMAND", self.ruta, seccion="aprendo")
        diario.organizar_texto("git worktree no deja dos veces la misma rama", self.ruta, seccion="aprendo")
        self.assertEqual(self._seccion("## Avances / aprendizajes"),
                         "- lo de filters.COMMAND\n"
                         "- git worktree no deja dos veces la misma rama")
        diario.organizar_texto("seguir con el portfolio", self.ruta, seccion="plan")
        self.assertEqual(self._seccion("## Para mañana"), "- seguir con el portfolio")

    def test_una_viñeta_es_una_linea(self):
        diario.organizar_texto("primera\nsegunda\n\ntercera", self.ruta, seccion="plan")
        self.assertEqual(self._seccion("## Para mañana"), "- primera segunda tercera")

    def test_cada_seccion_es_independiente(self):
        diario.organizar_texto("pasó esto", self.ruta, hora="10:00")
        diario.organizar_texto("bien", self.ruta, hora="10:00", seccion="siento")
        diario.organizar_texto("aprendí aquello", self.ruta, seccion="aprendo")
        diario.organizar_texto("mañana lo otro", self.ruta, seccion="plan")
        self.assertEqual(self._seccion("## Qué ha pasado hoy"), "10:00\npasó esto")
        self.assertEqual(self._seccion("## Cómo me siento"), "10:00\nbien")
        self.assertEqual(self._seccion("## Avances / aprendizajes"), "- aprendí aquello")
        self.assertEqual(self._seccion("## Para mañana"), "- mañana lo otro")

    def test_no_pisa_lo_que_ya_habia_escrito_a_mano(self):
        t = self.ruta.read_text(encoding="utf-8").replace(
            "## Cómo me siento\n", "## Cómo me siento\n\nescrito a mano\n")
        self.ruta.write_text(t, encoding="utf-8")
        diario.organizar_texto("y ahora esto", self.ruta, hora="12:00", seccion="siento")
        self.assertEqual(self._seccion("## Cómo me siento"),
                         "escrito a mano\n\n12:00\ny ahora esto")

    def test_entrada_antigua_sin_esa_seccion_la_crea_al_final(self):
        self.ruta.write_text("# 2026-09-06\n\ntexto viejo suelto\n", encoding="utf-8")
        diario.organizar_texto("aprendí algo", self.ruta, seccion="aprendo")
        t = self.ruta.read_text(encoding="utf-8")
        self.assertIn("texto viejo suelto", t)
        self.assertTrue(t.rstrip().endswith("## Avances / aprendizajes\n- aprendí algo"))

    def test_seccion_desconocida_y_texto_vacio_fallan_sin_tocar_el_fichero(self):
        antes = self.ruta.read_text(encoding="utf-8")
        with self.assertRaises(ValueError):
            diario.organizar_texto("algo", self.ruta, seccion="ansiedad")
        with self.assertRaises(ValueError):
            diario.organizar_texto("   ", self.ruta, seccion="siento")
        self.assertEqual(self.ruta.read_text(encoding="utf-8"), antes)

    def test_una_entrada_nueva_lleva_las_cuatro_secciones(self):
        # La plantilla es una constante (nunca `__file__`, prohibido en todo
        # el cerebro): no puede "faltar" como en midgaror, así que esto
        # reemplaza a aquella prueba de "sin plantilla.md en disco".
        ruta = Path(self.tmp.name) / "nueva.md"
        diario.organizar_texto("algo", ruta, seccion="plan")
        t = ruta.read_text(encoding="utf-8")
        for titulo, _ in diario.SECCIONES.values():
            self.assertIn(titulo, t)

    def test_la_plantilla_lleva_la_fecha_sustituida(self):
        ruta = Path(self.tmp.name) / "nueva.md"
        diario.organizar_texto("algo", ruta, fecha="2026-03-14", seccion="plan")
        t = ruta.read_text(encoding="utf-8")
        self.assertIn("fecha: 2026-03-14", t)
        self.assertIn("# 2026-03-14", t)
        self.assertNotIn("{{FECHA}}", t)


ENTRADA = """---
tipo: diario
fecha: 2026-09-04
repo: midgaror
---

# 2026-09-04

## Qué ha pasado hoy

19:40
Primera prueba real del bot.

## Cómo me siento


## Avances / aprendizajes

El bot sube lo que escribe.

## Para mañana

"""


class TestLeerEntrada(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name) / "2026-09-04.md"

    def test_sin_fichero(self):
        self.assertEqual(diario.leer_entrada("2026-09-04", ruta=self.ruta),
                         "Sin entrada el 2026-09-04.")

    def test_quita_frontmatter_y_secciones_vacias(self):
        self.ruta.write_text(ENTRADA, encoding="utf-8")
        texto = diario.leer_entrada("2026-09-04", ruta=self.ruta)
        self.assertTrue(texto.startswith("# 2026-09-04"))
        self.assertNotIn("tipo: diario", texto)
        self.assertIn("Primera prueba real del bot.", texto)
        self.assertIn("## Avances / aprendizajes", texto)
        self.assertNotIn("## Cómo me siento", texto)
        self.assertNotIn("## Para mañana", texto)

    def test_entrada_sin_secciones_se_devuelve_tal_cual(self):
        self.ruta.write_text("# Diario — 12 julio\n\nUn día tranquilo.\n", encoding="utf-8")
        self.assertEqual(diario.leer_entrada("2026-07-12", ruta=self.ruta),
                         "# Diario — 12 julio\n\nUn día tranquilo.")


class TestLeerNoEscribe(unittest.TestCase):
    """`leer_entrada` promete que leer nunca escribe. Ahora es verdad.

    Antes, preguntar por un día sin entrada dejaba creada la carpeta del año
    y la del mes en `diario/personal/`, que es el diario real de Álvaro.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.carpeta = Path(self._tmp.name)
        self._personal_original = diario.CARPETA_PERSONAL
        diario.CARPETA_PERSONAL = self.carpeta
        self.addCleanup(setattr, diario, "CARPETA_PERSONAL", self._personal_original)

    def test_preguntar_por_un_dia_sin_entrada_no_crea_carpetas(self):
        respuesta = diario.leer_entrada("2019-03-07")
        self.assertIn("Sin entrada", respuesta)
        self.assertEqual(list(self.carpeta.iterdir()), [])

    def test_escribir_si_crea_la_carpeta(self):
        # El otro lado del trato: quien escribe la sigue necesitando.
        diario.ruta_de_fecha("2019-03-07")
        self.assertTrue((self.carpeta / "2019" / "03-marzo").is_dir())


if __name__ == "__main__":
    unittest.main()
