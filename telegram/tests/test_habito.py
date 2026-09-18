"""Pruebas de handlers/habito.py."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dobles import CasoBot  # noqa: E402  (instala el telegram falso)

from handlers.habito import comando_habito, comando_habitos  # noqa: E402


class TestHabito(CasoBot):
    def test_hecho_y_no_hecho(self):
        self.assertEqual(self.enviar(comando_habito, "deporte", "2026-09-05"),
                         "✅ deporte — 2026-09-05 · subido")
        self.assertEqual(self.enviar(comando_habito, "no", "meditar", "2026-09-05"),
                         "❌ meditar — 2026-09-05 · subido")

    def test_valor_del_uno_al_diez(self):
        self.assertEqual(self.enviar(comando_habito, "energia", "7", "2026-09-05"),
                         "7 energia — 2026-09-05 · subido")

    def test_valor_y_fecha_a_la_vez(self):
        self.assertIn("6 foco — 2026-09-04", self.enviar(comando_habito, "foco", "6", "2026-09-04"))

    def test_el_numero_y_el_si_o_no_conviven_en_los_totales(self):
        self.enviar(comando_habito, "deporte", "2026-09-05")
        self.enviar(comando_habito, "energia", "7", "2026-09-05")
        self.enviar(comando_habito, "energia", "9", "2026-09-04")
        semana = self.enviar(comando_habitos, "semana", "2026-09-05")
        self.assertIn("energia: media 8.0 en 2 de 7 días", semana)
        self.assertIn("deporte: 1/1 días apuntados", semana)

    def test_resumen_de_un_dia(self):
        self.enviar(comando_habito, "deporte", "2026-09-05")
        self.enviar(comando_habito, "energia", "7", "2026-09-05")
        r = self.enviar(comando_habitos, "2026-09-05")
        self.assertIn("✅ deporte", r)
        self.assertIn("7 energia", r)

    def test_un_dia_sin_habitos_lo_dice(self):
        self.assertIn("Sin hábitos apuntados", self.enviar(comando_habitos, "2026-09-05"))

    def test_sin_argumentos_enseña_la_ayuda(self):
        self.assertIn("❌ Uso:", self.enviar(comando_habito))
        self.assertIn("❌ Uso:", self.enviar(comando_habito, "no"))

    def test_valor_fuera_de_rango_no_toca_el_fichero(self):
        self.assertIn("valor fuera de rango: 77", self.enviar(comando_habito, "energia", "77"))
        self.assertEqual(self.habitos.cargar(), {})

    def test_nombre_no_valido(self):
        self.assertIn("nombre de hábito no válido", self.enviar(comando_habito, "x!y"))

    def test_fecha_no_valida(self):
        # Tiene forma de fecha (AAAA-MM-DD) pero ese día no existe. Antes
        # valía cualquier último argumento; ahora, si no tiene forma de
        # fecha, es parte del nombre — ver TestNombreDeVariasPalabras.
        self.assertIn("fecha no válida", self.enviar(comando_habito, "deporte", "2026-13-45"))


class TestNombreDeVariasPalabras(CasoBot):
    """«/habito Leer Libro» moría con «fecha no válida: \'Libro\'».

    El handler tomaba el último argumento como fecha SIEMPRE, así que un
    hábito de dos palabras —de lo más normal— no se podía apuntar de ninguna
    manera. Ahora el final se lee por descarte: fecha solo si tiene forma
    AAAA-MM-DD, valor solo si es un entero, y el resto es el nombre.
    """

    def test_dos_palabras_sin_nada_mas(self):
        r = self.enviar(comando_habito, "Leer", "Libro")
        self.assertIn("✅ leer-libro", r)
        self.assertNotIn("fecha no válida", r)

    def test_dos_palabras_con_fecha(self):
        self.assertEqual(self.enviar(comando_habito, "Leer", "Libro", "2026-09-03"),
                         "✅ leer-libro — 2026-09-03 · subido")

    def test_dos_palabras_con_valor_y_fecha(self):
        self.assertEqual(self.enviar(comando_habito, "Beber", "agua", "3", "2026-09-03"),
                         "3 beber-agua — 2026-09-03 · subido")

    def test_dos_palabras_negadas(self):
        r = self.enviar(comando_habito, "no", "Leer", "Libro")
        self.assertIn("❌ leer-libro", r)

    def test_una_palabra_con_valor_sigue_funcionando(self):
        r = self.enviar(comando_habito, "energia", "7")
        self.assertIn("7 energia", r)

    def test_tres_palabras_o_mas(self):
        self.assertEqual(self.enviar(comando_habito, "Salir", "a", "correr", "2026-09-03"),
                         "✅ salir-a-correr — 2026-09-03 · subido")

    def test_un_numero_solo_es_el_nombre_y_no_un_valor_suelto(self):
        # Sin esto, «/habito 7» se quedaría sin nombre al que pegar el valor.
        # Es un hábito con nombre raro, no un error, y así lo dice habitos.py.
        r = self.enviar(comando_habito, "7")
        self.assertIn("✅ 7", r)

    def test_el_nombre_se_guarda_normalizado_una_sola_vez(self):
        # «Leer Libro» y «leer libro» son el mismo hábito: si se guardaran
        # como dos, la media semanal saldría partida en dos filas.
        self.enviar(comando_habito, "Leer", "Libro", "2026-09-03")
        self.enviar(comando_habito, "leer", "libro", "2026-09-04")
        guardados = {h for dia in self.habitos.cargar().values() for h in dia}
        self.assertEqual(guardados, {"leer-libro"})

    def test_sale_en_el_resumen_del_dia(self):
        self.enviar(comando_habito, "Leer", "Libro", "2026-09-05")
        self.assertIn("✅ leer-libro", self.enviar(comando_habitos, "2026-09-05"))


if __name__ == "__main__":
    unittest.main()
