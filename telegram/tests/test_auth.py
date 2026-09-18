"""Pruebas de utils/auth.py: quién puede darle órdenes al bot.

Esto no es un detalle de comodidad: el bot escribe en el diario personal,
así que un fallo aquí no es «responde de más», es que un desconocido escribe
en el diario de Álvaro.

Todo se prueba sobre `TELEGRAM_CHAT_ID` puesto a mano en el entorno de cada
prueba, nunca sobre el `.env` real: las pruebas no dependen de cómo esté
configurada la máquina donde corren.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dobles import logs_visibles  # noqa: E402  (instala el telegram falso)

from telegram.ext import filters  # noqa: E402  (el falso de dobles.py)
from utils.auth import (VARIABLE, chat_autorizado, chats_autorizados,  # noqa: E402
                        filtro_autorizado)


def con_variable(valor):
    """El entorno con TELEGRAM_CHAT_ID a `valor`, o sin ella si es None."""
    if valor is None:
        return mock.patch.dict(os.environ, {}, clear=True)
    return mock.patch.dict(os.environ, {VARIABLE: valor})


class TestChatsAutorizados(unittest.TestCase):
    def test_sin_la_variable_no_hay_restriccion(self):
        with con_variable(None):
            self.assertEqual(chats_autorizados(), [])

    def test_la_variable_vacia_es_lo_mismo_que_no_tenerla(self):
        # El .env.example la trae puesta y vacía: sin esto, un `.env` recién
        # copiado daría una lista rota en vez de «sin restricción».
        for vacia in ("", "   ", "\n"):
            with self.subTest(valor=repr(vacia)), con_variable(vacia):
                self.assertEqual(chats_autorizados(), [])

    def test_un_solo_id(self):
        with con_variable("123456789"):
            self.assertEqual(chats_autorizados(), [123456789])

    def test_varios_ids_con_espacios_alrededor(self):
        # Copiar y pegar ids de Telegram deja espacios detrás de las comas.
        with con_variable(" 111 , 222,333 "):
            self.assertEqual(chats_autorizados(), [111, 222, 333])

    def test_un_id_negativo_es_valido(self):
        # Los grupos y canales de Telegram tienen id negativo. Si se colara
        # un `isdigit()` en vez del `int()`, esto lo cazaría.
        with con_variable("-1001234567890"):
            self.assertEqual(chats_autorizados(), [-1001234567890])

    def test_un_trozo_no_numerico_se_ignora_y_avisa(self):
        with logs_visibles(), con_variable("111,@alvaro,222"):
            with self.assertLogs("utils.auth", level="WARNING") as registro:
                ids = chats_autorizados()
        self.assertEqual(ids, [111, 222])
        # El aviso tiene que decir *cuál* es el trozo malo: si solo dijera
        # «hay un id inválido», con cinco ids en la variable no serviría.
        self.assertIn("@alvaro", "\n".join(registro.output))

    def test_las_comas_de_mas_no_avisan_de_nada(self):
        # "111,,222" y "111,222," son erratas al editar el .env, no ids
        # inválidos: se saltan en silencio.
        with logs_visibles(), con_variable("111,,222,"):
            with self.assertNoLogs("utils.auth", level="WARNING"):
                ids = chats_autorizados()
        self.assertEqual(ids, [111, 222])


class TestFiltroAutorizado(unittest.TestCase):
    def test_sin_ids_el_filtro_no_deja_pasar_a_nadie(self):
        # Cerrado por defecto desde el 2026-09-08. Antes devolvía None, que
        # deja pasar a cualquiera, y ese es el modo de fallo al revés: una
        # errata en el .env (una letra O por un cero) abría el bot en vez de
        # cerrarlo, y el aviso se perdía entre el resto del arranque.
        with logs_visibles(), con_variable(""):
            with self.assertLogs("utils.auth", level="ERROR") as registro:
                filtro = filtro_autorizado()
        self.assertIsInstance(filtro, filters.Chat)
        self.assertEqual(filtro.chat_id, [])   # un filtro vacío bloquea a todos
        self.assertIn(VARIABLE, "\n".join(registro.output))

    def test_un_id_con_una_errata_deja_el_bot_MUDO_no_abierto(self):
        # El caso concreto: «780124O254», con una letra O donde va un cero.
        # Antes de este cambio, esto abría el bot a cualquiera.
        with logs_visibles(), con_variable("780124O254"):
            with self.assertLogs("utils.auth", level="ERROR"):
                filtro = filtro_autorizado()
        self.assertEqual(filtro.chat_id, [])

    def test_el_aviso_de_sin_ids_es_de_nivel_error_no_warning(self):
        # Un WARNING más entre los del arranque no se lee. Este tiene que
        # destacar, porque significa que el bot no va a contestar a nadie.
        with logs_visibles(), con_variable(""):
            with self.assertNoLogs("utils.auth", level="CRITICAL"):
                with self.assertLogs("utils.auth", level="ERROR"):
                    filtro_autorizado()

    def test_con_ids_devuelve_un_filtro_de_chat_con_esos_ids(self):
        # filters.Chat autoriza **chats, no personas**: si el id es el de un
        # grupo, cualquiera de ese grupo puede mandar al bot. Autorizar el
        # chat privado de uno mismo es lo único que autoriza a una persona.
        with con_variable("111,222"):
            filtro = filtro_autorizado()
        self.assertIsInstance(filtro, filters.Chat)
        self.assertEqual(filtro.chat_id, [111, 222])

    def test_chat_autorizado_responde_lo_mismo_que_el_filtro(self):
        # Es la función que usan las vías sin filtro (los botones de /menu:
        # un callback_query no es un mensaje y filters.Chat no lo mira). Si
        # las dos superficies no dan la misma respuesta, una de ellas está
        # abierta sin que nadie lo sepa.
        with con_variable("111,222"):
            self.assertTrue(chat_autorizado(111))
            self.assertTrue(chat_autorizado(222))
            self.assertFalse(chat_autorizado(333))

    def test_chat_autorizado_sin_ids_no_autoriza_a_nadie(self):
        with con_variable(""):
            self.assertFalse(chat_autorizado(111))
        with con_variable(None):
            self.assertFalse(chat_autorizado(111))

    def test_con_ids_no_avisa(self):
        # El aviso del caso anterior es util porque es raro. Si saltara
        # tambien con la autorizacion bien puesta, se volveria ruido de
        # arranque y dejaria de leerse.
        with logs_visibles(), con_variable("111"):
            with self.assertNoLogs("utils.auth", level="WARNING"):
                filtro = filtro_autorizado()
        self.assertIsNotNone(filtro)


if __name__ == "__main__":
    unittest.main()
