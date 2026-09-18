"""Fechas en español en los handlers: «ayer», «antes de ayer», «el lunes»…

Lo que se prueba es el enganche, no el parser: `diario/fechas.py` tiene sus
74 pruebas en midgaror. Aquí, que cada comando le pase lo que toca y haga
con la fecha lo que debe.

La referencia es hoy de verdad (los handlers no admiten un `ahora`), así que
las fechas se calculan en cada prueba. `CasoBot` apunta `ruta_de_fecha` a un
temporal, y por eso escribir en «ayer» crea `<temporal>/<ayer>.md` y no toca
el diario de nadie.
"""

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dobles import CasoBot  # noqa: E402  (instala el telegram falso)

from handlers.cita import comando_agenda  # noqa: E402
from handlers.diario import comando_diario  # noqa: E402
from handlers.entrada import comando_entrada  # noqa: E402
from handlers.habito import comando_habito, comando_habitos  # noqa: E402
from handlers.hoy import comando_hoy  # noqa: E402
from handlers.secciones import comando_aprendo, comando_siento  # noqa: E402
from utils.midgaror import modulo  # noqa: E402

fechas = modulo("fechas")

HOY_SEC = "## Qué ha pasado hoy"
SIENTO = "## Cómo me siento"
APRENDO = "## Avances / aprendizajes"


class CasoConFechas(CasoBot):
    def setUp(self):
        super().setUp()
        hoy = datetime.now(fechas.ZONA).date()
        self.hoy_iso = hoy.isoformat()
        self.ayer = (hoy - timedelta(days=1)).isoformat()
        self.anteayer = (hoy - timedelta(days=2)).isoformat()
        self.manana = (hoy + timedelta(days=1)).isoformat()

    def entrada_de(self, fecha: str) -> Path:
        return self.base / f"{fecha}.md"


class TestElDiarioConFechaDetras(CasoConFechas):
    def test_diario_con_ayer_al_final_va_a_ayer_sin_el_ayer(self):
        r = self.enviar(comando_diario, "cené", "con", "mi", "hermana", "ayer")
        self.assertIn(f"del {self.ayer}", r)
        cuerpo = self.seccion(HOY_SEC, self.entrada_de(self.ayer))
        self.assertIn("cené con mi hermana", cuerpo)
        self.assertFalse(cuerpo.rstrip().endswith("ayer"))

    def test_el_texto_suelto_tambien(self):
        r = self.texto_libre("he comido bien antes de ayer")
        self.assertIn(f"del {self.anteayer}", r)
        self.assertIn("he comido bien", self.seccion(HOY_SEC, self.entrada_de(self.anteayer)))

    def test_siento_y_aprendo_van_a_su_seccion_de_ese_dia(self):
        r = self.enviar(comando_siento, "reventado", "ayer")
        self.assertIn("Cómo me siento", r)
        self.assertIn(f"del {self.ayer}", r)
        self.assertIn("reventado", self.seccion(SIENTO, self.entrada_de(self.ayer)))
        self.enviar(comando_aprendo, "lo", "de", "to_thread", "hace", "2", "días")
        self.assertIn("lo de to_thread", self.seccion(APRENDO, self.entrada_de(self.anteayer)))

    def test_manana_al_final_es_parte_de_la_frase_y_se_queda_en_hoy(self):
        # Es la regla que separa el diario de /tarea: «tengo examen mañana»
        # es una frase de hoy sobre mañana, no una entrada de mañana.
        r = self.enviar(comando_diario, "tengo", "examen", "mañana")
        self.assertIn("de hoy", r)
        self.assertFalse(self.entrada_de(self.manana).exists())
        self.assertIn("tengo examen mañana", self.seccion(HOY_SEC))

    def test_hoy_al_final_se_queda_en_la_frase(self):
        self.enviar(comando_diario, "he", "dormido", "fatal", "hoy")
        self.assertIn("he dormido fatal hoy", self.seccion(HOY_SEC))

    def test_el_lunes_al_final_es_ambiguo_y_se_queda_en_hoy(self):
        r = self.enviar(comando_diario, "quedo", "con", "Ana", "el", "lunes")
        self.assertIn("de hoy", r)
        self.assertIn("quedo con Ana el lunes", self.seccion(HOY_SEC))

    def test_ayer_en_medio_no_cuenta(self):
        r = self.enviar(comando_diario, "ayer", "cené", "con", "Ana")
        self.assertIn("de hoy", r)
        self.assertIn("ayer cené con Ana", self.seccion(HOY_SEC))

    def test_la_hora_se_queda_en_la_frase(self):
        self.enviar(comando_diario, "cené", "a", "las", "10", "ayer")
        self.assertIn("cené a las 10", self.seccion(HOY_SEC, self.entrada_de(self.ayer)))


class TestEntradaConElDiaDelante(CasoConFechas):
    def test_ayer(self):
        r = self.enviar(comando_entrada, "ayer", "se", "me", "olvidó", "esto")
        self.assertIn(f"del {self.ayer}", r)
        self.assertIn("se me olvidó esto", self.entrada_de(self.ayer).read_text(encoding="utf-8"))

    def test_antes_de_ayer_son_tres_palabras(self):
        r = self.enviar(comando_entrada, "antes", "de", "ayer", "cené", "fuera")
        self.assertIn(f"del {self.anteayer}", r)
        self.assertIn("cené fuera", self.entrada_de(self.anteayer).read_text(encoding="utf-8"))

    def test_el_lunes_es_el_que_ya_paso(self):
        r = self.enviar(comando_entrada, "el", "lunes", "fui", "al", "médico")
        fecha = r.split("del ")[1].split(" ")[0]
        # Estrictamente en el pasado. No se compara con `ayer` porque si hoy
        # es martes, «el lunes» pasado ES ayer y la prueba fallaría por el día
        # de la semana en que se corra, no por el código.
        self.assertLess(fecha, self.hoy_iso)
        self.assertEqual(datetime.fromisoformat(fecha).weekday(), 0)

    def test_iso_como_siempre(self):
        r = self.enviar(comando_entrada, "2026-09-04", "se", "me", "olvidó", "esto")
        self.assertIn("del 2026-09-04", r)

    def test_sin_dia_o_sin_texto_ensena_la_ayuda(self):
        self.assertIn("❌ Empieza por el día", self.enviar(comando_entrada, "ayer"))
        self.assertIn("❌ Empieza por el día", self.enviar(comando_entrada, "loquesea", "texto"))
        self.assertIn("❌ Empieza por el día", self.enviar(comando_entrada))
        # Nada escrito en ningún sitio. (No se mira si el fichero de ayer
        # existe: CasoBot crea uno fijo y algunos días coincide con «ayer».)
        ayer = self.entrada_de(self.ayer)
        escrito = ayer.read_text(encoding="utf-8") if ayer.exists() else ""
        self.assertNotIn("texto", escrito)
        self.assertNotIn("olvidó", escrito)


class TestHabitoConFecha(CasoConFechas):
    def test_deporte_ayer(self):
        self.assertEqual(self.enviar(comando_habito, "deporte", "ayer"),
                         f"✅ deporte — {self.ayer} · subido")

    def test_nombre_compuesto_y_fecha_de_varias_palabras(self):
        self.assertEqual(self.enviar(comando_habito, "Leer", "Libro", "antes", "de", "ayer"),
                         f"✅ leer-libro — {self.anteayer} · subido")

    def test_nombre_valor_y_fecha(self):
        self.assertEqual(self.enviar(comando_habito, "Beber", "agua", "3", "ayer"),
                         f"3 beber-agua — {self.ayer} · subido")

    def test_no_y_fecha(self):
        self.assertEqual(self.enviar(comando_habito, "no", "meditar", "ayer"),
                         f"❌ meditar — {self.ayer} · subido")

    def test_el_lunes_es_el_que_ya_paso(self):
        r = self.enviar(comando_habito, "deporte", "el", "lunes")
        fecha = r.split("— ")[1].split(" ")[0]
        self.assertLess(fecha, self.hoy_iso)   # en el pasado, sea cual sea hoy
        self.assertEqual(datetime.fromisoformat(fecha).weekday(), 0)

    def test_una_fecha_con_numeros_mal_escrita_avisa_y_no_crea_un_habito_raro(self):
        # Sin esto, «2026-13-45» pasaría a ser parte del nombre y se
        # guardaría un hábito llamado «deporte-2026-13-45».
        r = self.enviar(comando_habito, "deporte", "2026-13-45")
        self.assertIn("fecha no válida", r)
        self.assertEqual(self.habitos.cargar(), {})

    def test_lo_de_antes_sigue_igual(self):
        self.assertIn("7 energia", self.enviar(comando_habito, "energia", "7"))
        self.assertIn("✅ leer-libro", self.enviar(comando_habito, "Leer", "Libro"))
        self.assertIn("✅ 7", self.enviar(comando_habito, "7"))

    def test_habitos_de_ayer(self):
        self.enviar(comando_habito, "deporte", "ayer")
        r = self.enviar(comando_habitos, "ayer")
        self.assertIn(f"{self.ayer}:", r)
        self.assertIn("✅ deporte", r)
        self.assertIn("deporte", self.enviar(comando_habitos, "semana", "hoy"))


class TestHoyYAgendaConFecha(CasoConFechas):
    def test_hoy_ayer(self):
        # Se mira la fecha en la línea de citas y no «Sin entrada»: CasoBot
        # crea la entrada de un día fijo y algunos días ese día es «ayer».
        r = self.enviar(comando_hoy, "ayer")
        self.assertIn(f"Sin citas el {self.ayer}", r)
        self.assertIn("📋 Tareas", r)

    def test_hoy_antes_de_ayer_son_tres_palabras(self):
        self.assertIn(f"Sin citas el {self.anteayer}", self.enviar(comando_hoy, "antes", "de", "ayer"))

    def test_hoy_con_algo_que_no_es_fecha_avisa(self):
        r = self.enviar(comando_hoy, "loquesea")
        self.assertIn("⚠️ fecha no válida", r)
        self.assertIn("ayer", r)   # el aviso enseña qué sí vale

    def test_agenda_manana_y_el_lunes(self):
        self.assertIn(f"Sin citas el {self.manana}", self.enviar(comando_agenda, "mañana"))
        r = self.enviar(comando_agenda, "el", "lunes")
        fecha = r.split("el ")[1].split(".")[0]
        self.assertGreater(fecha, datetime.now(fechas.ZONA).date().isoformat())  # el que viene
        self.assertEqual(datetime.fromisoformat(fecha).weekday(), 0)

    def test_agenda_semana_desde_manana(self):
        self.assertIn(f"entre el {self.manana}", self.enviar(comando_agenda, "semana", "mañana"))


if __name__ == "__main__":
    unittest.main()
