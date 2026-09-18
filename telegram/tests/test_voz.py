"""Pruebas de handlers/voz.py: una nota de voz, transcrita, sigue el mismo
camino que un mensaje escrito.

Nunca se carga Whisper de verdad: `voz._transcriptor` es el punto de
inyección, igual que `texto._preguntar` para el clasificador.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dobles import CasoBot  # noqa: E402  (instala el telegram falso)

from handlers import voz  # noqa: E402
from utils.voz import TranscriptorFalso  # noqa: E402

HOY = "## Qué ha pasado hoy"


class TestSeOyeYVaAlDiario(CasoBot):
    """Sin clasificador activo (texto._preguntar en None): al diario, como
    cualquier mensaje suelto — la nota de voz no es más que texto de camino."""

    def test_lo_oido_se_dice_antes_de_apuntar(self):
        voz._transcriptor = TranscriptorFalso("he dormido fatal")
        respuestas = self.nota_de_voz()
        self.assertEqual(len(respuestas), 2)
        self.assertIn("Te he oído", respuestas[0])
        self.assertIn("he dormido fatal", respuestas[0])
        self.assertIn("Apuntado en el diario", respuestas[1])
        self.assertIn("he dormido fatal", self.seccion(HOY))

    def test_silencio_no_apunta_nada_y_lo_dice(self):
        voz._transcriptor = TranscriptorFalso("")
        respuestas = self.nota_de_voz()
        self.assertEqual(len(respuestas), 1)
        self.assertIn("No he oído nada", respuestas[0])
        self.assertEqual(self.seccion(HOY), "")

    def test_una_nota_demasiado_larga_no_se_transcribe(self):
        voz._transcriptor = TranscriptorFalso("esto no debería usarse")
        respuestas = self.nota_de_voz(duration=voz.DURACION_MAXIMA + 1)
        self.assertEqual(len(respuestas), 1)
        self.assertIn(str(voz.DURACION_MAXIMA), respuestas[0])
        self.assertEqual(self.seccion(HOY), "")

    def test_un_fallo_transcribiendo_no_tira_el_bot(self):
        class Revienta:
            def transcribir(self, audio):
                raise RuntimeError("el modelo no está instalado")
        voz._transcriptor = Revienta()
        respuestas = self.nota_de_voz()
        self.assertEqual(len(respuestas), 1)
        self.assertIn("No he podido oír", respuestas[0])


class TestSeEnrutaComoElTexto(CasoBot):
    """Con el clasificador activo, una nota de voz puede acabar en una tarea,
    igual que si se hubiera escrito: es la misma función, `texto.procesar`."""

    def test_una_nota_clasificada_como_tarea_va_a_tareas_agregar(self):
        from handlers import texto

        def preguntar(frase):
            return {"intencion": "tarea", "texto": "llamar al médico el 15 de octubre",
                    "nombre": None, "hecho": True, "valor": None, "unidad": None,
                    "cuando": None, "confianza": "alta"}
        texto._preguntar = preguntar
        voz._transcriptor = TranscriptorFalso("recuérdame llamar al médico el 15 de octubre")

        respuestas = self.nota_de_voz()
        self.assertIn("Te he oído", respuestas[0])
        self.assertIn("✅", respuestas[1])
        self.assertEqual(self.seccion(HOY), "")
        self.assertEqual(len(self.tareas.activas(self.tareas.cargar())), 1)


if __name__ == "__main__":
    unittest.main()
