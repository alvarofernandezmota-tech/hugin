"""Pruebas de utils/voz.py: el mensaje de «no carga» tiene que decir la verdad.

Esto sale de un fallo real en Madre el 2026-09-17: `faster-whisper` estaba
instalado en el venv correcto —el log del pip lo decía— y el bot seguía
contestando «falta faster-whisper, instálalo». El `except ImportError` era
demasiado ancho y tapaba el error de uno de los paquetes compilados que
faster-whisper arrastra.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.voz import Whisper  # noqa: E402


class TestElMensajeDiceCualDeLasDosCosasPasa(unittest.TestCase):
    def mensaje(self, error: ImportError) -> str:
        return Whisper._por_que_no_carga(error)

    def test_si_falta_de_verdad_dice_como_instalarlo(self):
        error = ImportError("No module named 'faster_whisper'", name="faster_whisper")
        texto = self.mensaje(error)
        self.assertIn("falta faster-whisper", texto)
        self.assertIn("-m pip install faster-whisper", texto)
        # El pip de ESTE intérprete, que es el matiz que hizo falta la
        # primera vez: había dos venv y se instaló en el que no era.
        self.assertIn(sys.executable, texto)

    def test_si_lo_que_falla_es_una_dependencia_no_dice_que_falte(self):
        # El caso de Madre: el paquete está, pero ctranslate2 no carga.
        error = ImportError("libctranslate2.so.4: cannot open shared object file",
                            name="ctranslate2")
        texto = self.mensaje(error)
        self.assertIn("está instalado", texto)
        self.assertIn("ctranslate2", texto)
        self.assertNotIn("falta faster-whisper", texto)

    def test_el_error_de_verdad_va_siempre_dentro(self):
        # El que no se puede leer es el que no se puede arreglar.
        for error in (ImportError("algo raro", name="faster_whisper"),
                      ImportError("otra cosa", name="onnxruntime")):
            with self.subTest(modulo=error.name):
                self.assertIn(str(error), self.mensaje(error))

    def test_un_importerror_sin_nombre_se_trata_como_que_falta(self):
        # `name` es opcional: sin él no se puede acusar a nadie, así que se
        # da el consejo que más veces acierta, con el error detrás.
        texto = self.mensaje(ImportError("sin nombre"))
        self.assertIn("falta faster-whisper", texto)
        self.assertIn("sin nombre", texto)


if __name__ == "__main__":
    unittest.main()
