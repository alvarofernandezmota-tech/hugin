"""Que un fallo del bot no acabe en silencio.

Hasta el 2026-09-09 no había ningún error handler registrado, y los `except`
de los handlers contestaban con `responder`, que es justo lo que acababa de
fallar. Comprobado con python-telegram-bot 22.8: si el reply moría por red, el
except lo reintentaba, moría otra vez, y la excepción salía del handler para
morir en «No error handlers are registered». Lo escrito ya estaba en el diario
Y subido a GitHub, y al chat no le llegaba nada: ni la confirmación ni el error.
"""

import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dobles import CasoBot, logs_visibles  # noqa: E402  (instala el telegram falso)

import bot  # noqa: E402
from handlers.diario import comando_diario  # noqa: E402
from utils.respuestas import responder, responder_si_puedo  # noqa: E402

HOY = "## Qué ha pasado hoy"


class RedCaida(Exception):
    """Lo que lanza reply_text cuando Telegram no coge el mensaje."""


def _reventar(*args, **kwargs):
    raise RedCaida("Timed out")


class TestResponderSiPuedo(CasoBot):
    async def _llamar(self, funcion, upd):
        await funcion(upd, "algo que decir")

    def test_responder_normal_deja_salir_el_fallo(self):
        # En el camino bueno interesa enterarse: no se tapa.
        upd = self._actualizacion_rota()
        with self.assertRaises(RedCaida):
            self._correr(responder(upd, "hola"))

    def test_responder_si_puedo_se_lo_traga_y_lo_deja_en_el_log(self):
        upd = self._actualizacion_rota()
        # logs_visibles: dobles.py apaga el logging para todas las pruebas, y sin
        # encenderlo assertLogs falla siempre aunque el aviso esté ahí.
        with logs_visibles(), self.assertLogs("utils.respuestas", level="ERROR") as registro:
            self._correr(responder_si_puedo(upd, "hola"))   # no revienta
        self.assertIn("No se pudo avisar al chat", "\n".join(registro.output))

    def _actualizacion_rota(self):
        from dobles import Actualizacion
        upd = Actualizacion("da igual")
        upd.message.reply_text = _reventar
        return upd


class TestElCaminoDeErrorNoRevienta(CasoBot):
    def test_si_el_aviso_de_error_falla_la_excepcion_no_sale_del_handler(self):
        # El caso real: el reply falla, el except lo reintenta y volvía a fallar.
        from dobles import Actualizacion, Contexto
        upd = Actualizacion("/diario lo que sea")
        upd.message.reply_text = _reventar
        with logs_visibles(), self.assertLogs("utils.respuestas", level="ERROR"):
            self._correr(comando_diario(upd, Contexto("lo", "que", "sea")))
        # Y lo importante: lo escrito sigue escrito.
        self.assertIn("lo que sea", self.seccion(HOY))


class TestErrorHandlerRegistrado(unittest.TestCase):
    """Con ast, como test_menu.py: que nadie lo quite sin que salte una prueba."""

    def test_bot_py_registra_un_error_handler(self):
        arbol = ast.parse(Path(bot.__file__).read_text(encoding="utf-8"))
        llamadas = [n for n in ast.walk(arbol)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "add_error_handler"]
        self.assertEqual(len(llamadas), 1,
                         "sin add_error_handler, lo que se escape de un handler muere en silencio")

    def test_el_handler_avisa_por_el_camino_que_no_puede_reventar(self):
        fuente = Path(bot.__file__).read_text(encoding="utf-8")
        cuerpo = fuente.split("async def error_no_atrapado", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("responder_si_puedo", cuerpo)
        self.assertNotIn("await responder(", cuerpo)


if __name__ == "__main__":
    unittest.main()
