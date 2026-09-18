"""Pruebas de los handlers que escriben en el diario.

/diario, /entrada, el texto suelto y los tres de sección (/siento, /aprendo,
/plan). Aquí vive la prueba del bug del 2026-09-05, que es la razón de que
este fichero exista.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dobles import CasoBot, Entidad  # noqa: E402  (instala el telegram falso)

from handlers.diario import comando_diario  # noqa: E402
from handlers.entrada import comando_entrada  # noqa: E402
from handlers.secciones import comando_aprendo, comando_plan, comando_siento  # noqa: E402

HOY = "## Qué ha pasado hoy"
SIENTO = "## Cómo me siento"
APRENDO = "## Avances / aprendizajes"
PLAN = "## Para mañana"


class TestEscrituraEnElDiario(CasoBot):
    def test_texto_suelto_va_a_que_ha_pasado_hoy(self):
        self.assertIn("Apuntado en el diario de hoy", self.texto_libre("he dormido fatal"))
        self.assertIn("he dormido fatal", self.seccion(HOY))

    def test_diario_hace_lo_mismo_que_el_texto_suelto(self):
        self.enviar(comando_diario, "paseo", "con", "Thea")
        self.assertIn("paseo con Thea", self.seccion(HOY))

    def test_cada_comando_escribe_en_su_seccion_y_solo_en_la_suya(self):
        self.texto_libre("he trabajado en el bot")
        self.enviar(comando_siento, "contento")
        self.enviar(comando_aprendo, "lo", "de", "filters.COMMAND")
        self.enviar(comando_plan, "seguir", "con", "el", "portfolio")
        self.assertIn("he trabajado en el bot", self.seccion(HOY))
        self.assertIn("contento", self.seccion(SIENTO))
        self.assertEqual(self.seccion(APRENDO), "- lo de filters.COMMAND")
        self.assertEqual(self.seccion(PLAN), "- seguir con el portfolio")

    def test_siento_lleva_la_hora_y_aprendo_no(self):
        self.enviar(comando_siento, "contento")
        self.enviar(comando_aprendo, "algo")
        # "Cómo me siento" es un momento del día: lleva HH:MM delante.
        self.assertRegex(self.seccion(SIENTO), r"^\d{2}:\d{2}\ncontento$")
        # "Avances" son elementos sueltos: viñeta, sin hora.
        self.assertEqual(self.seccion(APRENDO), "- algo")

    def test_varias_viñetas_van_seguidas(self):
        self.enviar(comando_aprendo, "primera")
        self.enviar(comando_aprendo, "segunda")
        self.assertEqual(self.seccion(APRENDO), "- primera\n- segunda")

    def test_entrada_escribe_en_otro_dia(self):
        self.enviar(comando_entrada, "2026-09-04", "se", "me", "olvidó", "esto")
        otro = self.base / "2026-09-04.md"
        self.assertTrue(otro.exists())
        self.assertIn("se me olvidó esto", self.seccion(HOY, otro))
        self.assertEqual(self.seccion(HOY), "")   # el de hoy, intacto

    def test_sin_texto_enseñan_el_ejemplo(self):
        for handler, ejemplo in ((comando_siento, "/siento"), (comando_aprendo, "/aprendo"),
                                 (comando_plan, "/plan"), (comando_diario, "/diario")):
            r = self.enviar(handler)
            self.assertIn("Escribe el texto detrás del comando", r)
            self.assertIn(ejemplo, r)


class TestNoSeTragaComandos(CasoBot):
    """El bug del 2026-09-05: treinta comandos escritos en el diario.

    Telegram no marca como bot_command un comando pegado con formato de
    código: llega con la entidad `code`, el CommandHandler no lo coge y cae
    en el handler de texto libre. Estas pruebas son las que impiden que
    vuelva a pasar.
    """

    def test_un_comando_con_entidad_code_no_se_escribe_en_el_diario(self):
        r = self.texto_libre("/tareas", [Entidad("code")])
        self.assertIn("parece un comando", r)
        self.assertIn("/tareas", r)          # lo devuelve, para reenviarlo
        self.assertEqual(self.seccion(HOY), "")

    def test_da_igual_el_comando_y_da_igual_la_entidad(self):
        for texto in ("/cita médico mañana a las 10", "/habito deporte", "/hoy", "/loquesea"):
            self.assertIn("parece un comando", self.texto_libre(texto))
        self.assertEqual(self.seccion(HOY), "")

    def test_una_barra_dentro_del_texto_no_es_un_comando(self):
        self.assertIn("Apuntado en el diario", self.texto_libre("me he leído 3/4 del libro"))
        self.assertIn("3/4", self.seccion(HOY))

    def test_un_mensaje_vacio_no_escribe_nada(self):
        self.assertEqual(self.texto_libre("   "), "")
        self.assertEqual(self.seccion(HOY), "")


class TestSaltosDeLinea(CasoBot):
    """El bug del 2026-09-08: escribir varias líneas y que lleguen aplastadas.

    En Telegram varias líneas son shift+enter, no un truco, y `context.args`
    viene ya partido por ellas: recomponerlo con `" ".join` deja un párrafo
    corrido y el original no se puede recuperar. Cada prueba de aquí manda el
    mensaje entero, como lo manda la librería.
    """

    DOS_LINEAS = "me he levantado tarde\nluego he ido al gimnasio"

    def test_diario_conserva_los_saltos(self):
        self.enviar_texto(comando_diario, f"/diario {self.DOS_LINEAS}")
        self.assertIn(self.DOS_LINEAS, self.seccion(HOY))

    def test_una_seccion_conserva_los_saltos(self):
        self.enviar_texto(comando_siento, f"/siento {self.DOS_LINEAS}")
        self.assertIn(self.DOS_LINEAS, self.seccion(SIENTO))

    def test_entrada_conserva_los_saltos_y_la_fecha_sigue_delante(self):
        self.enviar_texto(comando_entrada, f"/entrada 2026-09-04 {self.DOS_LINEAS}")
        otro = self.base / "2026-09-04.md"
        self.assertIn(self.DOS_LINEAS, self.seccion(HOY, otro))
        self.assertEqual(self.seccion(HOY), "")   # el de hoy, intacto

    def test_el_boton_del_menu_tambien_los_conserva(self):
        # El botón acaba en el mismo handler que el comando, así que si el
        # comando los conserva y el botón no, es que se pierden por el camino.
        from handlers.menu import ACCIONES
        self.contestar(ACCIONES["diario"][1], self.DOS_LINEAS)
        self.assertIn(self.DOS_LINEAS, self.seccion(HOY))

    def test_el_texto_puede_empezar_en_la_linea_de_abajo(self):
        self.enviar_texto(comando_diario, "/diario\nempieza abajo del todo")
        self.assertIn("empieza abajo del todo", self.seccion(HOY))

    def test_el_nombre_del_bot_pegado_al_comando_no_entra_en_el_diario(self):
        # En un grupo, Telegram manda «/diario@midgaror_bot texto».
        self.enviar_texto(comando_diario, "/diario@midgaror_bot cena con Thea")
        self.assertIn("cena con Thea", self.seccion(HOY))
        self.assertNotIn("midgaror_bot", self.seccion(HOY))


if __name__ == "__main__":
    unittest.main()
