"""Pruebas de handlers/texto.py: lo que entiende entender() y lo que no.

`diario/entender.py` ya tiene las suyas (la clasificación en sí, la red de
seguridad). Aquí lo que se prueba es la costura: que un mensaje suelto
clasificado con alta confianza acaba en la MISMA función que su comando de
verdad —`tareas.agregar`, `agenda.agregar`, `habitos.marcar`,
`registro.apuntar`— con los mismos datos, y que cualquier otra cosa (sin
clasificar, confianza media, un fallo al aplicarlo) sigue yendo al diario
exactamente como antes de que esto existiera.
"""

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dobles import CasoBot  # noqa: E402  (instala el telegram falso)

from handlers import texto  # noqa: E402
from hugin.personal import fechas as fechas_personal  # noqa: E402

HOY = "## Qué ha pasado hoy"


def _preguntar(**campos):
    """Un `preguntar` falso: nunca se llama a la API de verdad en pruebas."""
    base = {"intencion": "diario", "texto": None, "nombre": None,
            "hecho": True, "valor": None, "unidad": None, "cuando": None,
            "confianza": "baja"}
    base.update(campos)
    return lambda frase: base


class TestSeEnrutaConAltaConfianza(CasoBot):
    # Fechas absolutas a propósito, como en test_tarea.py ("el 15 de
    # octubre"): agregar()/marcar()/apuntar() usan fechas.ahora() de verdad
    # cuando no se les inyecta un reloj, así que "mañana" dependería del día
    # en que corra la prueba.
    def test_tarea_va_a_tareas_agregar_no_al_diario(self):
        texto._preguntar = _preguntar(intencion="tarea", texto="llamar al médico el 15 de octubre",
                                      confianza="alta")
        respuesta = self.texto_libre("recuérdame llamar al médico el 15 de octubre")
        self.assertIn("✅", respuesta)
        self.assertIn("llamar al médico", respuesta)
        self.assertEqual(self.seccion(HOY), "")  # no cayó en el diario
        activas = self.tareas.activas(self.tareas.cargar())
        self.assertEqual(len(activas), 1)
        self.assertEqual(activas[0]["texto"], "llamar al médico")
        self.assertEqual(activas[0]["fecha"], "2026-10-15")

    def test_cita_va_a_agenda_agregar(self):
        texto._preguntar = _preguntar(intencion="cita", texto="dentista el 15 de octubre a las 17",
                                      confianza="alta")
        respuesta = self.texto_libre("tengo dentista el 15 de octubre a las 17")
        self.assertIn("📅", respuesta)
        citas = self.agenda.activas(self.agenda.cargar())
        self.assertEqual(len(citas), 1)
        self.assertEqual(citas[0]["texto"], "dentista")
        self.assertEqual(self.seccion(HOY), "")

    def test_habito_hecho_va_a_habitos_marcar(self):
        texto._preguntar = _preguntar(intencion="habito", nombre="deporte", hecho=True,
                                      cuando="2026-09-05", confianza="alta")
        respuesta = self.texto_libre("he hecho deporte")
        self.assertIn("deporte", respuesta)
        datos = self.habitos.cargar()
        self.assertTrue(datos["2026-09-05"]["deporte"])
        self.assertEqual(self.seccion(HOY), "")

    def test_habito_negado_marca_false(self):
        texto._preguntar = _preguntar(intencion="habito", nombre="meditar", hecho=False,
                                      cuando="2026-09-05", confianza="alta")
        self.texto_libre("no he meditado")
        datos = self.habitos.cargar()
        self.assertFalse(datos["2026-09-05"]["meditar"])

    def test_apunte_con_valor_va_a_registro_apuntar(self):
        texto._preguntar = _preguntar(intencion="apunte", nombre="tele", valor=3, unidad="h",
                                      cuando="2026-09-05", confianza="alta")
        respuesta = self.texto_libre("tele 3h")
        self.assertIn("📝", respuesta)
        apuntes = self.registro.del_dia("2026-09-05", inq=self.inquilino)
        self.assertEqual(apuntes, [{"fecha": "2026-09-05", "que": "tele", "valor": 3, "unidad": "h"}])
        self.assertEqual(self.seccion(HOY), "")

    def test_apunte_con_fecha_en_espanol_no_revienta_ni_cae_al_diario(self):
        # Bug real, encontrado midiendo la fase 4 del ADR-024: `e.cuando`
        # llega en español tal cual lo dijo quien escribe ("ayer", "el
        # lunes"; entender.py:119), y hugin.apuntes.apuntar() espera
        # AAAA-MM-DD. Sin resolverlo antes, normalizar_fecha('ayer') lanza
        # ValueError, el except de _enrutar se lo traga y el apunte se
        # pierde como una línea suelta del diario — sin apuntarse donde
        # tocaba y sin que nadie se entere.
        ayer = (date.fromisoformat(fechas_personal.hoy()) - timedelta(days=1)).isoformat()
        texto._preguntar = _preguntar(intencion="apunte", nombre="agua", valor=2, unidad="l",
                                      cuando="ayer", confianza="alta")
        respuesta = self.texto_libre("2 litros de agua ayer")
        self.assertIn("📝", respuesta)
        self.assertNotIn("Error", respuesta)
        apuntes = self.registro.del_dia(ayer, inq=self.inquilino)
        self.assertEqual(apuntes, [{"fecha": ayer, "que": "agua", "valor": 2, "unidad": "l"}])
        # Y sobre todo: NO cae al diario como prosa suelta.
        self.assertEqual(self.seccion(HOY), "")


class TestCaeAlDiarioComoAntes(CasoBot):
    """Todo lo que no es «alta confianza y no diario» tiene que seguir
    escribiendo la línea suelta, exactamente igual que si esto no existiera.
    """

    def test_sin_clasificar_va_al_diario(self):
        # texto._preguntar sigue en None (lo deja CasoBot.setUp): sin clave
        # en el entorno, entender() no llega ni a intentarlo.
        self.texto_libre("he dormido fatal")
        self.assertIn("he dormido fatal", self.seccion(HOY))

    def test_confianza_media_va_al_diario(self):
        texto._preguntar = _preguntar(intencion="tarea", texto="algo", confianza="media")
        self.texto_libre("a lo mejor tengo que hacer algo")
        self.assertIn("a lo mejor tengo que hacer algo", self.seccion(HOY))

    def test_intencion_diario_va_al_diario(self):
        texto._preguntar = _preguntar(intencion="diario", confianza="alta")
        self.texto_libre("hoy ha sido un día raro")
        self.assertIn("hoy ha sido un día raro", self.seccion(HOY))

    def test_cita_sin_fecha_que_agenda_entienda_cae_al_diario(self):
        # entender() dice "cita" con alta confianza pero agenda.agregar()
        # exige un cuándo que fechas.py sepa leer: agenda.agregar lanza
        # ValueError, y el mensaje no se pierde, cae al diario.
        texto._preguntar = _preguntar(intencion="cita", texto="dentista", confianza="alta")
        respuesta = self.texto_libre("algo del dentista")
        self.assertIn("Apuntado en el diario", respuesta)
        self.assertIn("algo del dentista", self.seccion(HOY))

    def test_habito_sin_nombre_cae_al_diario(self):
        texto._preguntar = _preguntar(intencion="habito", nombre=None, confianza="alta")
        respuesta = self.texto_libre("algo de un hábito")
        self.assertIn("Apuntado en el diario", respuesta)


class TestUnSaludoNoEsDiario(CasoBot):
    """El fallo real de Madre (2026-09-18): un simple «hola» se escribía
    como entrada de diario. Este es el nivel de arriba del que prueba
    `tests/test_entender_personal.py::TestElSaludoNoEsDiario` — aquí se
    comprueba que el handler de verdad usa ese chequeo, no solo que la
    función existe.
    """

    def test_hola_no_se_apunta_en_el_diario(self):
        respuesta = self.texto_libre("hola")
        self.assertIn("Hola", respuesta)
        self.assertEqual(self.seccion(HOY), "")

    def test_gracias_tampoco(self):
        self.texto_libre("gracias")
        self.assertEqual(self.seccion(HOY), "")

    def test_ni_siquiera_llega_a_preguntarle_al_motor(self):
        # es_saludo() va ANTES de entender(): si algún día alguien mueve el
        # orden, esto lo dice explotando en vez de dejarlo pasar en verde.
        def explota(frase):
            raise AssertionError("no debería preguntarse nada para un saludo")
        texto._preguntar = explota
        self.texto_libre("hola")

    def test_un_saludo_con_mas_texto_si_es_diario(self):
        # El caso que justo hay que evitar: no vale con "empieza por hola".
        self.texto_libre("hola, hoy ha sido un día raro")
        self.assertIn("hola, hoy ha sido un día raro", self.seccion(HOY))


class TestUnaPreguntaSeContesta(CasoBot):
    """La rama que NO escribe: lee los resúmenes y contesta en prosa.

    Que no escriba es lo importante, y aquí se comprueba por donde duele:
    mirando el diario y los JSON después. `diario/tests/test_conversar.py`
    lo vigila además sobre el código de `conversar.py`, que es lo que
    impide que alguien abra la puerta sin darse cuenta.
    """

    def test_contesta_y_no_escribe_nada(self):
        texto._preguntar = _preguntar(intencion="pregunta", confianza="alta")
        texto._responder_pregunta = lambda pregunta, contexto: "Dos tareas y ninguna cita."
        respuesta = self.texto_libre("¿qué tengo hoy?")
        self.assertIn("Dos tareas y ninguna cita.", respuesta)
        # Ni al diario, ni a tareas.
        self.assertNotIn("¿qué tengo hoy?", self.seccion(HOY))
        self.assertEqual(self.tareas.cargar(), [])

    def test_le_llega_la_pregunta_entera(self):
        # `texto` lo rellena entender() copiando la frase: si algún día se
        # le pide al modelo que la repita y se le olvida, esto se cae.
        visto = {}
        texto._preguntar = _preguntar(intencion="pregunta", confianza="alta")

        def espiar(pregunta, contexto):
            visto["pregunta"] = pregunta
            return "vale"

        texto._responder_pregunta = espiar
        self.texto_libre("¿voy al dentista el jueves?")
        self.assertEqual(visto["pregunta"], "¿voy al dentista el jueves?")

    def test_si_no_se_puede_contestar_cae_al_diario(self):
        # Sin clave, red caída o respuesta vacía: `responder()` da None y
        # esto se comporta como si la función no existiera. Nunca se pierde
        # el mensaje por no poder contestarlo.
        texto._preguntar = _preguntar(intencion="pregunta", confianza="alta")
        texto._responder_pregunta = lambda pregunta, contexto: None
        respuesta = self.texto_libre("¿qué tengo hoy?")
        self.assertIn("Apuntado en el diario", respuesta)
        self.assertIn("¿qué tengo hoy?", self.seccion(HOY))

    def test_una_pregunta_con_dudas_ni_se_intenta(self):
        # Confianza media: entender() devuelve None y no se llega a
        # `conversar`. Mejor apuntarlo que contestar a lo que no era.
        texto._preguntar = _preguntar(intencion="pregunta", confianza="media")

        def explota(*_):
            raise AssertionError("no debería preguntarse nada")

        texto._responder_pregunta = explota
        self.texto_libre("me pregunto si irá bien")
        self.assertIn("me pregunto si irá bien", self.seccion(HOY))


if __name__ == "__main__":
    unittest.main()
