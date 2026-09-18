"""Pruebas del menú de botones (handlers/menu.py).

El menú existe porque tocar un comando en el menú «/» de Telegram lo envía
sin dejar escribir texto detrás. Lo que se prueba aquí es el circuito entero
con dobles: el teclado que se construye, la pregunta que suelta cada botón,
que la respuesta a esa pregunta acabe en el mismo sitio que el comando, y que
lo que no es respuesta a una pregunta nuestra siga yendo al diario.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dobles import Actualizacion, CasoBot, Contexto  # noqa: E402  (instala el telegram falso)

from telegram import ForceReply  # noqa: E402  (el falso de dobles.py)
from handlers.menu import ACCIONES, FILAS, comando_menu, teclado  # noqa: E402

PREGUNTA = {clave: accion[1] for clave, accion in ACCIONES.items()}


class TestElTeclado(CasoBot):
    def test_menu_manda_un_teclado_con_un_boton_por_accion(self):
        upd = Actualizacion()
        self._correr(comando_menu(upd, Contexto()))
        self.assertEqual(upd.message.respuestas, ["¿Qué apuntamos?"])
        botones = [b for fila in upd.message.marcados[-1].inline_keyboard for b in fila]
        self.assertEqual({b.callback_data for b in botones}, set(ACCIONES))

    def test_las_filas_no_repiten_ni_olvidan_ninguna_accion(self):
        planas = [clave for fila in FILAS for clave in fila]
        self.assertEqual(len(planas), len(set(planas)))
        self.assertEqual(set(planas), set(ACCIONES))

    def test_cada_boton_tiene_texto_y_su_dato_cabe_en_telegram(self):
        # callback_data admite 64 bytes; el texto del botón no puede ir vacío.
        for fila in teclado().inline_keyboard:
            for b in fila:
                self.assertTrue(b.text.strip())
                self.assertLessEqual(len(b.callback_data.encode("utf-8")), 64)

    def test_las_preguntas_no_se_repiten(self):
        # La pregunta es la clave del enrutado: dos botones con la misma
        # pregunta mandarían las dos respuestas al mismo sitio.
        preguntas = [p for p in PREGUNTA.values() if p is not None]
        self.assertEqual(len(preguntas), len(set(preguntas)))


class TestBotonesQuePreguntan(CasoBot):
    def test_tocar_me_siento_pregunta_y_abre_el_teclado(self):
        upd = self.pulsar("siento")
        self.assertTrue(upd.callback_query.respondida)   # sin esto el botón se queda con el reloj
        menu = upd.callback_query.message
        self.assertEqual(menu.respuestas[-1], PREGUNTA["siento"])
        self.assertIsInstance(menu.marcados[-1], ForceReply)
        self.assertTrue(menu.marcados[-1].input_field_placeholder)

    def test_la_respuesta_va_a_su_seccion_del_diario(self):
        r = self.contestar(PREGUNTA["siento"], "contento, he dormido bien")
        self.assertIn("Cómo me siento", r)
        self.assertIn("contento, he dormido bien", self.seccion("## Cómo me siento"))
        self.assertNotIn("contento", self.seccion("## Qué ha pasado hoy"))

    def test_cada_pregunta_de_diario_escribe_donde_su_comando(self):
        self.contestar(PREGUNTA["diario"], "he salido a correr")
        self.contestar(PREGUNTA["aprendo"], "lo de to_thread")
        self.contestar(PREGUNTA["plan"], "seguir con el portfolio")
        self.assertIn("he salido a correr", self.seccion("## Qué ha pasado hoy"))
        self.assertIn("lo de to_thread", self.seccion("## Avances / aprendizajes"))
        self.assertIn("seguir con el portfolio", self.seccion("## Para mañana"))

    def test_una_tarea_desde_el_boton_entiende_el_cuando(self):
        # Es el punto del diseño: el botón acaba en el mismo handler que
        # /tarea, así que todo lo que entiende /tarea lo entiende el botón.
        r = self.contestar(PREGUNTA["tarea"], "comprar el pan mañana")
        self.assertIn("[1] comprar el pan", r)
        self.assertIsNotNone(self.tareas.cargar()[0]["fecha"])

    def test_una_cita_desde_el_boton(self):
        r = self.contestar(PREGUNTA["cita"], "médico mañana a las 10")
        self.assertIn("📅 [1] médico", r)
        self.assertIn("10:00", r)

    def test_un_habito_desde_el_boton(self):
        self.assertIn("✅ deporte", self.contestar(PREGUNTA["habito"], "deporte"))
        self.assertIn("❌ meditar", self.contestar(PREGUNTA["habito"], "no meditar"))
        self.assertIn("7 energia", self.contestar(PREGUNTA["habito"], "energia 7"))

    def test_responder_a_otra_cosa_va_al_diario_como_siempre(self):
        r = self.contestar("Un mensaje cualquiera del bot", "he comido bien")
        self.assertIn("Apuntado en el diario de hoy", r)
        self.assertIn("he comido bien", self.seccion("## Qué ha pasado hoy"))

    def test_responder_sin_mensaje_original_tambien(self):
        # reply_to_message puede venir vacío si el original ya no existe.
        from handlers.menu import respuesta_al_menu
        upd = Actualizacion("suelto")
        self._correr(respuesta_al_menu(upd, self._contexto_sin_args()))
        self.assertIn("Apuntado en el diario", upd.message.respuestas[-1])

    def test_un_comando_pegado_como_respuesta_no_se_traga(self):
        # Lo mismo que en texto.py: un «/hoy» pegado con formato llega sin la
        # marca de comando. En una sección del diario sería tragárselo.
        r = self.contestar(PREGUNTA["siento"], "/hoy")
        self.assertIn("parece un comando", r)
        self.assertEqual(self.seccion("## Cómo me siento"), "")


class TestBotonesDirectos(CasoBot):
    def test_hoy_se_ejecuta_sin_preguntar(self):
        menu = self.pulsar("hoy").callback_query.message
        self.assertIn("📔 Diario", menu.respuestas[-1])
        self.assertIsNone(menu.marcados[-1])   # sin ForceReply: no espera texto

    def test_tareas_agenda_y_habitos_tambien(self):
        self.contestar(PREGUNTA["tarea"], "comprar el pan")
        self.contestar(PREGUNTA["cita"], "médico mañana a las 10")
        self.contestar(PREGUNTA["habito"], "deporte")
        self.assertIn("[1] comprar el pan", self.pulsar("tareas").callback_query.message.respuestas[-1])
        agenda = self.pulsar("agenda").callback_query.message.respuestas[-1]
        self.assertTrue(agenda.strip())
        self.assertIn("✅ deporte", self.pulsar("habitos").callback_query.message.respuestas[-1])


class TestLoQueNoDebePasar(CasoBot):
    def test_un_boton_desconocido_no_hace_nada(self):
        menu = self.pulsar("loquesea").callback_query.message
        self.assertEqual(menu.respuestas, [])

    def test_un_chat_no_autorizado_no_recibe_ni_respuesta(self):
        # El filtro de chat de los CommandHandler no llega a los botones: si
        # el handler no lo comprueba, cualquiera con un menú viejo entra.
        with mock.patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "111"}):
            intruso = self.pulsar("siento", chat_id=222)
            dueño = self.pulsar("siento", chat_id=111)
        self.assertEqual(intruso.callback_query.message.respuestas, [])
        self.assertFalse(intruso.callback_query.respondida)
        self.assertEqual(dueño.callback_query.message.respuestas, [PREGUNTA["siento"]])

    def test_todos_los_botones_se_explican_en_el_help(self):
        # Que /menu esté en /help lo mira test_menu; aquí, que ningún botón
        # haga algo que no tenga su comando explicado.
        import inspect
        import bot
        ayuda = inspect.getsource(bot.comando_help)
        for clave in ACCIONES:
            self.assertIn(f"/{clave}", ayuda, f"el botón {clave} no tiene su comando en /help")


if __name__ == "__main__":
    unittest.main()
