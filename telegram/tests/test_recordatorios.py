"""Pruebas de handlers/recordatorios.py: lo único que habla sin que le hablen.

Lo que decide qué avisar se prueba en midgaror (diario/tests/test_recordatorios.py).
Aquí se prueba lo que puede convertir esto en spam o en silencio: que se
anote DESPUÉS de mandar, que un fallo de Telegram no dé la cita por avisada,
y que nada de esto pueda tirar el bucle.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dobles import CasoBot  # noqa: E402  (instala el telegram falso)

from handlers import recordatorios  # noqa: E402


class BotQueApunta:
    """Un `app.bot` que guarda a quién se le mandó qué."""

    def __init__(self, revienta: bool = False):
        self.mandados: list[tuple[int, str]] = []
        self.revienta = revienta

    async def send_message(self, chat, texto):
        if self.revienta:
            raise RuntimeError("Telegram no contesta")
        self.mandados.append((chat, texto))


class App:
    def __init__(self, bot):
        self.bot = bot


class CasoAvisos(CasoBot):
    def setUp(self):
        super().setUp()
        # El módulo de midgaror escribe su estado donde le digamos.
        self.recordatorios = recordatorios.recordatorios
        self.recordatorios.RUTA_AVISADOS = self.base / "avisados.json"
        # Una cita de aquí a diez minutos: dentro de la ventana, siempre.
        from datetime import timedelta
        fechas = self.recordatorios.fechas
        cuando = fechas.ahora() + timedelta(minutes=10)
        citas = self.agenda.cargar()
        citas.append({"id": 1, "texto": "médico", "fecha": cuando.date().isoformat(),
                      "hora": cuando.strftime("%H:%M"), "duracion": 60,
                      "creada": "2026-09-17 20:00"})
        self.agenda.guardar(citas)

    def avisar(self, bot):
        import asyncio
        return asyncio.run(recordatorios.avisar_una_vez(App(bot)))


class TestAvisar(CasoAvisos):
    def test_avisa_de_una_cita_que_viene(self):
        bot = BotQueApunta()
        self.assertEqual(self.avisar(bot), 1)
        self.assertEqual(len(bot.mandados), 1)
        self.assertIn("médico", bot.mandados[0][1])
        self.assertIn("⏰", bot.mandados[0][1])

    def test_no_avisa_dos_veces_de_la_misma(self):
        # El bucle pregunta cada minuto: sin esto serían treinta mensajes.
        bot = BotQueApunta()
        self.assertEqual(self.avisar(bot), 1)
        self.assertEqual(self.avisar(bot), 0)
        self.assertEqual(len(bot.mandados), 1)

    def test_si_telegram_falla_la_cita_sigue_pendiente(self):
        # Anotar antes de mandar dejaría la cita por avisada sin que nadie
        # la haya leído: es el fallo que no se ve hasta que llegas tarde.
        roto = BotQueApunta(revienta=True)
        self.assertEqual(self.avisar(roto), 0)
        bueno = BotQueApunta()
        self.assertEqual(self.avisar(bueno), 1)
        self.assertEqual(len(bueno.mandados), 1)

    def test_sin_chats_autorizados_no_manda_nada(self):
        import os
        from unittest import mock
        bot = BotQueApunta()
        with mock.patch.dict(os.environ, {"TELEGRAM_CHAT_ID": ""}):
            self.assertEqual(self.avisar(bot), 0)
        self.assertEqual(bot.mandados, [])

    def test_un_fallo_mirando_la_agenda_no_revienta(self):
        # avisar_una_vez() no puede lanzar: quien la llama es un bucle
        # infinito, y una excepción ahí deja el bot mudo para siempre.
        def revienta():
            raise RuntimeError("agenda.json ilegible")
        original = self.recordatorios.pendientes
        self.recordatorios.pendientes = revienta
        self.addCleanup(setattr, self.recordatorios, "pendientes", original)
        self.assertEqual(self.avisar(BotQueApunta()), 0)



class TestElBucleSeRecogeAlApagar(CasoAvisos):
    """El fallo visto en Madre el 2026-09-17, en el primer arranque real."""

    def test_arrancar_guarda_la_referencia_y_parar_la_cancela(self):
        import asyncio

        async def ciclo():
            tarea = recordatorios.arrancar(App(BotQueApunta()))
            # La referencia se guarda en el módulo: sin eso, el recolector
            # de basura puede llevarse el bucle a media ejecución.
            self.assertIs(recordatorios._tarea, tarea)
            self.assertFalse(tarea.done())
            await recordatorios.parar(None)
            # Cancelada y recogida: nada pendiente que asyncio pueda gritar
            # al cerrarse («Task was destroyed but it is pending!»).
            self.assertTrue(tarea.cancelled())
            self.assertIsNone(recordatorios._tarea)

        asyncio.run(ciclo())

    def test_parar_sin_haber_arrancado_no_revienta(self):
        import asyncio
        recordatorios._tarea = None
        asyncio.run(recordatorios.parar(None))

if __name__ == "__main__":
    unittest.main()
