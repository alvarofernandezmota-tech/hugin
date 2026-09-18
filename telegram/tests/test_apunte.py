"""Pruebas de /apunte, /dia y /semana.

Los tres son la cara en Telegram de midgaror/diario/registro/registro.py, el
modelo del ADR-012. Lo que se prueba aquí es la cara: que el comando entienda
lo que escribe Álvaro desde el móvil y que el resumen se lea bien. Que la
suma esté bien ya lo prueba diario/tests/test_registro.py.
"""

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dobles import CasoBot  # noqa: E402  (instala el telegram falso)

from handlers.apunte import (comando_apunte, comando_dia,  # noqa: E402
                             comando_semana, pintar)
from utils.midgaror import modulo  # noqa: E402

fechas = modulo("fechas")

# El doble fija en 2026-09-05 la ENTRADA del diario, pero registro.py resuelve
# «hoy» de verdad: son dos cosas distintas y conviene no confundirlas. Estas
# pruebas van contra el día real.
#
# Y ese «hoy» es el de `Europe/Madrid`, no el del reloj de la máquina. Antes
# esto era `date.today()` y en Madre daba igual —está en esa zona—, pero en
# una máquina en UTC estas pruebas fallaban **dos horas cada noche**: entre
# las 22:00 y las 00:00 UTC ya es el día siguiente en Madrid, así que «ayer»
# caía en el mismo día que el `date.today()` del sistema. Pasó el 2026-09-10,
# y lo que destapó fue real: el modelo y `fechas.py` usaban dos relojes.
HOY = fechas.hoy()
LUNES = date.fromisoformat(HOY) - timedelta(days=date.fromisoformat(HOY).weekday())
DOMINGO = LUNES + timedelta(days=6)


class TestApunte(CasoBot):
    def apuntes(self):
        return self.registro.cargar()

    def test_algo_sin_cantidad_es_hecho(self):
        self.assertIn("📝 deporte", self.enviar(comando_apunte, "deporte"))
        apunte = self.apuntes()[0]
        self.assertEqual(apunte["que"], "deporte")
        self.assertNotIn("valor", apunte)      # ausente = hecho, no 0

    def test_cantidad_y_unidad_pegadas(self):
        self.enviar(comando_apunte, "tele", "3h")
        self.assertEqual(self.apuntes()[0], {"fecha": HOY, "que": "tele",
                                             "valor": 3, "unidad": "h"})

    def test_la_confirmacion_dice_la_cantidad_no_un_error(self):
        # Bug real: `_cantidad()` está pensada para una línea de RESUMEN
        # (trae `total`), y se llamaba con el apunte recién creado (trae
        # `valor`, no `total`). El dato se guardaba bien —lo comprueba
        # `test_cantidad_y_unidad_pegadas`, que solo mira el JSON— pero la
        # respuesta al chat moría con «❌ Error: 'total'» en cuanto el
        # apunte llevaba cantidad, que es el caso normal.
        respuesta = self.enviar(comando_apunte, "tele", "3h")
        self.assertEqual(respuesta, f"📝 tele 3 h — {HOY} · subido")

    def test_cantidad_y_unidad_separadas(self):
        self.enviar(comando_apunte, "agua", "1,5", "l")
        apunte = self.apuntes()[0]
        self.assertEqual((apunte["valor"], apunte["unidad"]), (1.5, "l"))

    def test_el_nombre_puede_llevar_espacios(self):
        self.enviar(comando_apunte, "ver", "la", "tele", "2h")
        self.assertEqual(self.apuntes()[0]["que"], "ver la tele")

    def test_con_acentos(self):
        # El motivo de tocar NOMBRE_RE en midgaror: se escribe en español.
        self.enviar(comando_apunte, "café", "2")
        self.assertEqual(self.apuntes()[0]["que"], "café")

    def test_en_otro_dia_dicho_en_espanol(self):
        self.enviar(comando_apunte, "tele", "1h", "ayer")
        self.assertLess(self.apuntes()[0]["fecha"], HOY)

    def test_un_numero_solo_es_el_nombre_no_un_valor_suelto(self):
        # Igual que en /habito: siempre queda al menos una palabra de nombre.
        self.enviar(comando_apunte, "7")
        self.assertEqual(self.apuntes()[0]["que"], "7")
        self.assertNotIn("valor", self.apuntes()[0])

    def test_dos_apuntes_del_mismo_dia_no_se_pisan(self):
        self.enviar(comando_apunte, "tele", "3h")
        self.enviar(comando_apunte, "tele", "2h")
        self.assertEqual(len(self.apuntes()), 2)          # la regla del ADR-012

    def test_sin_argumentos_ensena_la_ayuda(self):
        self.assertIn("/apunte", self.enviar(comando_apunte))

    def test_un_nombre_imposible_avisa_y_no_escribe(self):
        self.assertIn("⚠️", self.enviar(comando_apunte, "¿qué?"))
        self.assertEqual(self.apuntes(), [])


class TestDiaYSemana(CasoBot):
    def test_el_dia_suma_lo_de_ese_dia(self):
        self.enviar(comando_apunte, "tele", "3h")
        self.enviar(comando_apunte, "tele", "2h")
        respuesta = self.enviar(comando_dia)
        self.assertIn("tele 5 h", respuesta)              # 3 + 2, sumados al leer

    def test_un_dia_vacio_lo_dice(self):
        self.assertIn("nada apuntado", self.enviar(comando_dia))

    def test_la_semana_dice_el_tramo(self):
        respuesta = self.enviar(comando_semana)
        self.assertIn(LUNES.isoformat(), respuesta)       # lunes de esa semana
        self.assertIn(DOMINGO.isoformat(), respuesta)     # y su domingo

    def test_la_semana_junta_varios_dias(self):
        # Con el lunes explícito, no con «ayer»: un lunes, «ayer» cae en la
        # semana anterior y la prueba fallaría un día de cada siete.
        self.enviar(comando_apunte, "tele", "1h")
        self.enviar(comando_apunte, "tele", "2h", LUNES.isoformat())
        self.assertIn("tele 3 h", self.enviar(comando_semana))

    def test_un_dia_mal_dicho_avisa_y_no_revienta(self):
        self.assertIn("⚠️", self.enviar(comando_dia, "el", "trigésimo"))


class TestComoSePinta(unittest.TestCase):
    """El icono sale del objetivo, no del nombre (ADR-012: nada es bueno ni malo)."""

    def _linea(self, tipo, valor, total, cumple):
        return {"lineas": [{"que": "x", "total": total, "unidad": "h", "cumple": cumple,
                            "objetivo": {"que": "x", "tipo": tipo, "valor": valor,
                                         "periodo": "dia"}}]}

    def test_al_menos_sin_cumplir_es_te_falta_no_esta_mal(self):
        texto = pintar(self._linea("al_menos", 3, 1, False), "cab")
        self.assertIn("⏳", texto)
        self.assertIn("al menos 3", texto)
        self.assertNotIn("❌", texto)

    def test_como_mucho_pasado_si_es_un_no(self):
        texto = pintar(self._linea("como_mucho", 7, 9, False), "cab")
        self.assertIn("❌", texto)
        self.assertIn("como mucho 7", texto)

    def test_cumplido_es_un_si_en_los_dos_casos(self):
        for tipo, valor, total in (("al_menos", 3, 3), ("como_mucho", 7, 5)):
            with self.subTest(tipo=tipo):
                self.assertIn("✅", pintar(self._linea(tipo, valor, total, True), "cab"))

    def test_sin_objetivo_no_lleva_icono_de_juicio(self):
        texto = pintar({"lineas": [{"que": "tele", "total": 5, "unidad": "h"}]}, "cab")
        self.assertIn("· tele 5 h", texto)
        for icono in ("✅", "❌", "⏳"):
            self.assertNotIn(icono, texto)


if __name__ == "__main__":
    unittest.main()
