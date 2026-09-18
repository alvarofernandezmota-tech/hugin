"""Pruebas de hugin/personal/fechas.py. Correr: make pruebas

Copia byte a byte de diario/tests/test_fechas.py de midgaror: el modulo que
prueban es una copia byte a byte de diario/fechas.py (ver hugin/personal,
"Por que hay dos parsers"). Solo cambia el preambulo de import; ni una regla
de las pruebas se ha tocado.
"""

import unittest
from datetime import datetime

import entorno  # noqa: F401

from hugin.personal import fechas

# Viernes 4 de septiembre de 2026, 20:00. Fijo a propósito: sin referencia
# estable, «mañana» o «el próximo lunes» darían un resultado distinto cada día
# y las pruebas dejarían de significar nada.
AHORA = datetime(2026, 9, 4, 20, 0)


class TestCasosDeLaAuditoria(unittest.TestCase):
    """Los siete casos con los que se midió el parser de thea-ia.

    Están en docs/ecosistema/auditoria-thea-ia.md con el resultado que daba
    aquel. Tres los fallaba; los siete tienen que pasar aquí.
    """

    def test_manana_a_las_10(self):
        self.assertEqual(fechas.interpretar("quedada mañana a las 10", AHORA),
                         ("2026-09-05", "10:00", False, "quedada"))

    def test_pasado_manana_son_dos_dias_no_uno(self):
        # thea-ia devolvía 2026-09-05, que es «mañana».
        self.assertEqual(fechas.interpretar("médico pasado mañana", AHORA),
                         ("2026-09-06", None, False, "médico"))

    def test_el_15_de_octubre_respeta_el_mes(self):
        # thea-ia se comía el mes y devolvía 2026-09-15.
        self.assertEqual(fechas.interpretar("cita el 15 de octubre a las 9:30", AHORA),
                         ("2026-10-15", "09:30", False, "cita"))

    def test_el_proximo_lunes_por_la_tarde(self):
        # thea-ia acertaba el día pero ignoraba «por la tarde» y ponía 09:00.
        self.assertEqual(fechas.interpretar("reunión el próximo lunes por la tarde", AHORA),
                         ("2026-09-07", "16:00", True, "reunión"))

    def test_en_3_dias_no_deja_la_expresion_en_el_resto(self):
        # thea-ia acertaba la fecha pero metía «3 días» como ubicación.
        self.assertEqual(fechas.interpretar("gimnasio en 3 días", AHORA),
                         ("2026-09-07", None, False, "gimnasio"))

    def test_hoy_a_las_3_de_la_tarde(self):
        self.assertEqual(fechas.interpretar("llamar a Ana hoy a las 3 de la tarde", AHORA),
                         ("2026-09-04", "15:00", True, "llamar a Ana"))

    def test_sin_fecha_no_se_inventa_ninguna(self):
        self.assertIsNone(fechas.interpretar("comprar el pan", AHORA))


class TestRelativas(unittest.TestCase):
    def test_ayer(self):
        self.assertEqual(fechas.interpretar("ayer", AHORA), ("2026-09-03", None, False, ""))

    def test_hoy(self):
        self.assertEqual(fechas.interpretar("hoy", AHORA), ("2026-09-04", None, False, ""))

    def test_manana(self):
        self.assertEqual(fechas.interpretar("mañana", AHORA), ("2026-09-05", None, False, ""))

    def test_anteayer_y_antes_de_ayer(self):
        self.assertEqual(fechas.interpretar("anteayer", AHORA)[0], "2026-09-02")
        self.assertEqual(fechas.interpretar("antes de ayer", AHORA)[0], "2026-09-02")

    def test_en_n_semanas(self):
        self.assertEqual(fechas.interpretar("en 2 semanas", AHORA)[0], "2026-09-18")

    def test_en_n_dias_cruza_el_mes(self):
        self.assertEqual(fechas.interpretar("en 30 días", AHORA)[0], "2026-10-04")


class TestDiasDeLaSemana(unittest.TestCase):
    def test_el_lunes_es_el_lunes_que_viene(self):
        self.assertEqual(fechas.interpretar("el lunes", AHORA)[0], "2026-09-07")

    def test_el_viernes_no_es_hoy_sino_el_siguiente(self):
        # AHORA es viernes. «El viernes» mirando al futuro es dentro de siete
        # días, no dentro de cero: nadie apunta para hoy diciendo «el viernes».
        self.assertEqual(fechas.interpretar("el viernes", AHORA)[0], "2026-09-11")

    def test_el_jueves_que_viene(self):
        self.assertEqual(fechas.interpretar("cena el jueves que viene", AHORA),
                         ("2026-09-10", None, False, "cena"))

    def test_con_tilde_y_sin_tilde(self):
        self.assertEqual(fechas.interpretar("el miércoles", AHORA)[0],
                         fechas.interpretar("el miercoles", AHORA)[0])


class TestFechasExplicitas(unittest.TestCase):
    def test_dia_y_mes_ya_pasados_saltan_al_ano_siguiente(self):
        # El 3 de marzo de 2026 ya pasó cuando se escribe esto.
        self.assertEqual(fechas.interpretar("el 3 de marzo", AHORA)[0], "2027-03-03")

    def test_dia_mes_y_ano(self):
        self.assertEqual(fechas.interpretar("el 1 de enero de 2030", AHORA)[0], "2030-01-01")

    def test_formato_iso(self):
        self.assertEqual(fechas.interpretar("revisión 2026-12-25 a las 8", AHORA),
                         ("2026-12-25", "08:00", False, "revisión"))

    def test_formato_con_barras(self):
        self.assertEqual(fechas.interpretar("15/10", AHORA)[0], "2026-10-15")

    def test_fecha_imposible_no_cuela(self):
        self.assertIsNone(fechas.interpretar("el 31 de febrero", AHORA))


class TestHoras(unittest.TestCase):
    def test_hora_con_minutos_sin_fecha_es_hoy(self):
        self.assertEqual(fechas.interpretar("a las 16:30", AHORA),
                         ("2026-09-04", "16:30", False, ""))

    def test_hora_suelta(self):
        self.assertEqual(fechas.interpretar("a las 5", AHORA),
                         ("2026-09-04", "05:00", False, ""))

    def test_la_hora_suelta_es_literal(self):
        # «a las 5» son las 5:00, no las 17:00. Es la única lectura coherente
        # con «mañana a las 10», que nadie entiende como las 22:00. Para las
        # 17:00 hay que escribir «a las 5 de la tarde».
        self.assertEqual(fechas.interpretar("a las 5 de la tarde", AHORA)[1], "17:00")

    def test_las_12_de_la_manana_es_mediodia_y_de_la_noche_medianoche(self):
        self.assertEqual(fechas.interpretar("a las 12 de la mañana", AHORA)[1], "12:00")
        self.assertEqual(fechas.interpretar("a las 12 de la noche", AHORA)[1], "00:00")
        self.assertEqual(fechas.interpretar("a las 12 de la madrugada", AHORA)[1], "00:00")
        self.assertEqual(fechas.interpretar("a las 1 de la madrugada", AHORA)[1], "01:00")

    def test_hora_imposible_no_cuela(self):
        self.assertIsNone(fechas.interpretar("a las 99", AHORA))
        self.assertIsNone(fechas.interpretar("a las 10:75", AHORA))

    def test_formato_con_h(self):
        self.assertEqual(fechas.interpretar("entreno 20h", AHORA),
                         ("2026-09-04", "20:00", False, "entreno"))


class TestFranjas(unittest.TestCase):
    def test_esta_noche(self):
        self.assertEqual(fechas.interpretar("esta noche", AHORA),
                         ("2026-09-04", "21:00", True, ""))

    def test_esta_manana(self):
        self.assertEqual(fechas.interpretar("esta mañana", AHORA),
                         ("2026-09-04", "09:00", True, ""))

    def test_manana_por_la_manana_son_dos_cosas_distintas(self):
        # El caso que más se presta a confusión: el primer «mañana» es el día
        # siguiente y el segundo es la franja horaria.
        self.assertEqual(fechas.interpretar("correr mañana por la mañana", AHORA),
                         ("2026-09-05", "09:00", True, "correr"))

    def test_ayer_por_la_noche(self):
        self.assertEqual(fechas.interpretar("ayer por la noche", AHORA),
                         ("2026-09-03", "21:00", True, ""))

    def test_la_hora_explicita_gana_a_la_franja(self):
        self.assertEqual(fechas.interpretar("mañana por la tarde a las 18:45", AHORA),
                         ("2026-09-05", "18:45", False, ""))

    def test_al_mediodia(self):
        self.assertEqual(fechas.interpretar("comida el sábado al mediodía", AHORA),
                         ("2026-09-05", "14:00", True, "comida"))


class TestAcotada(unittest.TestCase):
    """¿Vino la hora con mañana/tarde/noche, o es un número suelto?

    «acotada» es lo que separa una hora de verdad de una que solo lo parece:
    «a las 5» son las 05:00 tal cual (ver TestHoras), pero sin saber si quien
    lo escribió quería decir las 17:00. `hora_ambigua()` es la que decide si
    eso hay que preguntarlo.
    """

    def test_hora_suelta_no_esta_acotada(self):
        self.assertEqual(fechas.interpretar("a las 5", AHORA)[2], False)

    def test_hora_con_de_la_tarde_esta_acotada(self):
        self.assertEqual(fechas.interpretar("a las 5 de la tarde", AHORA)[2], True)

    def test_hora_de_24h_no_esta_acotada_pero_tampoco_hace_falta(self):
        # «a las 17» no lleva mañana/tarde/noche, así que acotada es False —
        # pero 17 ya no admite dos lecturas, así que da igual.
        self.assertEqual(fechas.interpretar("a las 17", AHORA)[2], False)

    def test_franja_sola_esta_acotada(self):
        # «por la tarde» no es un número suelto: es la hora canónica de la
        # franja, explícita por construcción.
        self.assertEqual(fechas.interpretar("por la tarde", AHORA)[2], True)

    def test_sin_hora_no_esta_acotada(self):
        self.assertEqual(fechas.interpretar("mañana", AHORA)[2], False)


class TestHoraAmbigua(unittest.TestCase):
    """`hora_ambigua()`: lo que decide si hay que preguntar."""

    def test_hora_suelta_por_debajo_de_doce_es_ambigua(self):
        self.assertTrue(fechas.hora_ambigua("05:00", False))
        self.assertTrue(fechas.hora_ambigua("11:59", False))

    def test_acotada_nunca_es_ambigua(self):
        self.assertFalse(fechas.hora_ambigua("05:00", True))

    def test_a_partir_de_las_doce_no_hay_duda(self):
        self.assertFalse(fechas.hora_ambigua("12:00", False))
        self.assertFalse(fechas.hora_ambigua("17:00", False))

    def test_sin_hora_no_hay_nada_que_confirmar(self):
        self.assertFalse(fechas.hora_ambigua(None, False))


class TestAcotar(unittest.TestCase):
    """`acotar()`: aplicar la franja que faltaba a una hora ya guardada."""

    def test_tarde_suma_doce(self):
        self.assertEqual(fechas.acotar("05:00", "tarde"), "17:00")

    def test_noche_suma_doce(self):
        self.assertEqual(fechas.acotar("09:30", "noche"), "21:30")

    def test_manana_no_toca_nada(self):
        self.assertEqual(fechas.acotar("05:00", "manana"), "05:00")

    def test_mediodia_solo_si_es_madrugada(self):
        self.assertEqual(fechas.acotar("02:00", "mediodia"), "14:00")
        self.assertEqual(fechas.acotar("09:00", "mediodia"), "09:00")

    def test_hora_ya_de_tarde_no_se_dobla(self):
        self.assertEqual(fechas.acotar("17:00", "tarde"), "17:00")

    def test_sin_franja_no_cambia(self):
        self.assertEqual(fechas.acotar("05:00", None), "05:00")


class TestFranjaRespondida(unittest.TestCase):
    """`franja_respondida()`: entender la respuesta a «¿mañana o tarde?»."""

    def test_una_palabra_sola_basta(self):
        self.assertEqual(fechas.franja_respondida("tarde"), "tarde")
        self.assertEqual(fechas.franja_respondida("mañana"), "manana")
        self.assertEqual(fechas.franja_respondida("noche"), "noche")

    def test_con_preposicion_tambien(self):
        self.assertEqual(fechas.franja_respondida("de la tarde"), "tarde")
        self.assertEqual(fechas.franja_respondida("por la mañana"), "manana")

    def test_sin_tildes_tambien(self):
        self.assertEqual(fechas.franja_respondida("manana"), "manana")

    def test_lo_que_no_es_una_franja(self):
        self.assertIsNone(fechas.franja_respondida("vale"))
        self.assertIsNone(fechas.franja_respondida(""))
        self.assertIsNone(fechas.franja_respondida(None))


class TestTextoRestante(unittest.TestCase):
    def test_se_quita_la_expresion_y_se_cuadran_los_espacios(self):
        self.assertEqual(fechas.interpretar("mañana a las 10 llamar al fontanero", AHORA)[3],
                         "llamar al fontanero")

    def test_la_expresion_en_medio_no_pega_las_palabras(self):
        self.assertEqual(fechas.interpretar("llamar mañana al fontanero", AHORA)[3],
                         "llamar al fontanero")

    def test_se_limpian_los_signos_que_quedan_colgando(self):
        self.assertEqual(fechas.interpretar("comprar pan, mañana", AHORA)[3], "comprar pan")

    def test_el_resto_conserva_mayusculas_y_tildes_del_original(self):
        self.assertEqual(fechas.interpretar("Revisión Médica mañana", AHORA)[3],
                         "Revisión Médica")


class TestCasosLimite(unittest.TestCase):
    def test_texto_vacio(self):
        self.assertIsNone(fechas.interpretar("", AHORA))
        self.assertIsNone(fechas.interpretar("   ", AHORA))
        self.assertIsNone(fechas.interpretar(None, AHORA))

    def test_sin_ahora_usa_la_hora_de_madrid(self):
        hoy = datetime.now(fechas.ZONA).date().isoformat()
        self.assertEqual(fechas.interpretar("hoy")[0], hoy)

    def test_acepta_un_ahora_con_zona(self):
        con_zona = datetime(2026, 9, 4, 20, 0, tzinfo=fechas.ZONA)
        self.assertEqual(fechas.interpretar("mañana", con_zona)[0], "2026-09-05")

    def test_una_frase_larga_sin_nada_temporal(self):
        self.assertIsNone(fechas.interpretar("revisar el informe del trimestre", AHORA))


class TestSaltosDeLinea(unittest.TestCase):
    """Cortar la fecha no puede aplastar el resto del texto.

    Las dos funciones recomponían el resto con `" ".join(palabras)`, así que
    un texto de varias líneas con fecha llegaba al diario en una sola línea y
    sin manera de recuperarlo. Sin fecha nunca falló, porque entonces el texto
    se devuelve tal cual: por eso hacen falta estas pruebas y no las de arriba.
    """

    DOS = "me he levantado tarde\nluego he ido al gimnasio"

    def test_la_fecha_delante_deja_el_resto_intacto(self):
        self.assertEqual(fechas.fecha_delante(f"ayer {self.DOS}", AHORA),
                         ("2026-09-03", self.DOS))

    def test_la_fecha_detras_deja_la_cabeza_intacta(self):
        self.assertEqual(fechas.fecha_detras(f"{self.DOS} ayer", AHORA),
                         (self.DOS, "2026-09-03"))

    def test_tambien_con_una_fecha_de_varias_palabras(self):
        self.assertEqual(fechas.fecha_delante(f"antes de ayer {self.DOS}", AHORA),
                         ("2026-09-02", self.DOS))

    def test_el_salto_puede_ir_pegado_a_la_fecha(self):
        self.assertEqual(fechas.fecha_delante(f"ayer\n{self.DOS}", AHORA),
                         ("2026-09-03", self.DOS))


class TestHaciaAtras(unittest.TestCase):
    """Lo ambiguo, resuelto al último que pasó: lo que quiere el diario."""

    def test_el_lunes_es_el_lunes_pasado(self):
        # AHORA es viernes 4 de septiembre: el lunes pasado es el 31 de agosto.
        self.assertEqual(fechas.interpretar("fui al médico el lunes", AHORA, hacia_atras=True),
                         ("2026-08-31", None, False, "fui al médico"))

    def test_el_mismo_dia_de_la_semana_es_hace_una_semana_no_hoy(self):
        self.assertEqual(fechas.interpretar("el viernes", AHORA, hacia_atras=True)[0], "2026-08-28")

    def test_dia_y_mes_sin_ano_es_la_ultima_vez(self):
        self.assertEqual(fechas.interpretar("el 10 de septiembre", AHORA, hacia_atras=True)[0],
                         "2025-09-10")
        self.assertEqual(fechas.interpretar("el 4 de septiembre", AHORA, hacia_atras=True)[0],
                         "2026-09-04")   # hoy cuenta como «ya pasó»

    def test_lo_explicito_no_cambia(self):
        self.assertEqual(fechas.interpretar("mañana", AHORA, hacia_atras=True)[0], "2026-09-05")
        self.assertEqual(fechas.interpretar("en 3 días", AHORA, hacia_atras=True)[0], "2026-09-07")

    def test_hacia_delante_sigue_siendo_lo_de_siempre(self):
        self.assertEqual(fechas.interpretar("el lunes", AHORA)[0], "2026-09-07")


class TestHaceNDias(unittest.TestCase):
    def test_hace_tres_dias(self):
        self.assertEqual(fechas.interpretar("cené fuera hace 3 días", AHORA),
                         ("2026-09-01", None, False, "cené fuera"))

    def test_hace_dos_semanas(self):
        self.assertEqual(fechas.interpretar("hace 2 semanas", AHORA)[0], "2026-08-21")

    def test_hace_un_dia_en_singular(self):
        self.assertEqual(fechas.interpretar("hace 1 dia", AHORA)[0], "2026-09-03")


class TestComoFecha(unittest.TestCase):
    """Un argumento que es SOLO una fecha, o nada."""

    def test_las_que_son_fechas(self):
        for texto, esperada in (("ayer", "2026-09-03"), ("hoy", "2026-09-04"),
                                ("mañana", "2026-09-05"), ("antes de ayer", "2026-09-02"),
                                ("el 15 de octubre", "2026-10-15"), ("2026-09-01", "2026-09-01"),
                                ("04/09/2026", "2026-09-04"), ("hace 3 días", "2026-09-01")):
            with self.subTest(texto=texto):
                self.assertEqual(fechas.como_fecha(texto, AHORA), esperada)

    def test_lo_que_no_es_una_fecha(self):
        for texto in ("deporte", "Leer Libro", "7", "", "   ", "2026-13-45", "semana"):
            with self.subTest(texto=texto):
                self.assertIsNone(fechas.como_fecha(texto, AHORA))

    def test_una_fecha_con_texto_pegado_no_es_solo_una_fecha(self):
        # Es lo que separa «ayer» (argumento) de «cené ayer» (frase).
        self.assertIsNone(fechas.como_fecha("cené ayer", AHORA))

    def test_una_hora_no_es_una_fecha(self):
        # «a las 10» resolvería a hoy con hora, y un hábito llamado «a las 10»
        # tiene que seguir siendo un nombre raro, no una fecha.
        self.assertIsNone(fechas.como_fecha("a las 10", AHORA))
        self.assertIsNone(fechas.como_fecha("ayer por la tarde", AHORA))

    def test_hacia_atras_tambien_aqui(self):
        self.assertEqual(fechas.como_fecha("el lunes", AHORA, hacia_atras=True), "2026-08-31")


class TestNormalizar(unittest.TestCase):
    def test_none_es_hoy(self):
        self.assertEqual(fechas.normalizar(None, AHORA), "2026-09-04")
        self.assertEqual(fechas.normalizar("", AHORA), "2026-09-04")

    def test_lo_que_sea_a_iso(self):
        self.assertEqual(fechas.normalizar("ayer", AHORA), "2026-09-03")
        self.assertEqual(fechas.normalizar("2026-09-01", AHORA), "2026-09-01")

    def test_lo_que_no_es_fecha_avisa_diciendo_que_vale(self):
        with self.assertRaises(ValueError) as e:
            fechas.normalizar("loquesea", AHORA)
        self.assertIn("fecha no válida", str(e.exception))
        self.assertIn("ayer", str(e.exception))   # el aviso enseña qué sí vale


class TestFechaDelante(unittest.TestCase):
    """/entrada ayer se me olvidó esto"""

    def test_ayer_delante(self):
        self.assertEqual(fechas.fecha_delante("ayer se me olvidó esto", AHORA),
                         ("2026-09-03", "se me olvidó esto"))

    def test_el_trozo_mas_largo_gana(self):
        # «antes de ayer cené fuera»: sin probar el más largo primero saldría
        # «antes» como fecha (que no lo es) o «ayer» perdido en el texto.
        self.assertEqual(fechas.fecha_delante("antes de ayer cené fuera", AHORA),
                         ("2026-09-02", "cené fuera"))

    def test_iso_delante_como_siempre(self):
        self.assertEqual(fechas.fecha_delante("2026-09-01 se me olvidó esto", AHORA),
                         ("2026-09-01", "se me olvidó esto"))

    def test_el_lunes_delante_es_el_pasado(self):
        self.assertEqual(fechas.fecha_delante("el lunes fui al médico", AHORA),
                         ("2026-08-31", "fui al médico"))

    def test_sin_fecha_delante_no_se_inventa(self):
        self.assertEqual(fechas.fecha_delante("se me olvidó esto", AHORA),
                         (None, "se me olvidó esto"))

    def test_una_fecha_sola_no_deja_texto(self):
        # Todo el texto es la fecha: no hay nada que apuntar, y no se recorta.
        self.assertEqual(fechas.fecha_delante("ayer", AHORA), (None, "ayer"))


class TestFechaDetras(unittest.TestCase):
    """«cené con Ana ayer» → al día de ayer, sin el «ayer». Solo pasado."""

    def test_ayer_al_final(self):
        self.assertEqual(fechas.fecha_detras("cené con Ana ayer", AHORA),
                         ("cené con Ana", "2026-09-03"))

    def test_antes_de_ayer_y_hace_n_dias(self):
        self.assertEqual(fechas.fecha_detras("fui al médico antes de ayer", AHORA),
                         ("fui al médico", "2026-09-02"))
        self.assertEqual(fechas.fecha_detras("cené fuera hace 3 días", AHORA),
                         ("cené fuera", "2026-09-01"))

    def test_el_lunes_al_final_es_ambiguo_y_no_cuenta(self):
        # «fui al médico el lunes» es pasado para quien lo escribe, pero «el
        # lunes» a secas no lo dice: leído hacia atrás, «quedo con Ana el
        # lunes» se iría a la semana pasada. Se deja en hoy; para eso está
        # «/entrada el lunes fui al médico», con la fecha delante y a posta.
        self.assertEqual(fechas.fecha_detras("fui al médico el lunes", AHORA),
                         ("fui al médico el lunes", None))

    def test_una_fecha_completa_pasada_si_cuenta(self):
        self.assertEqual(fechas.fecha_detras("cené fuera 2026-09-01", AHORA),
                         ("cené fuera", "2026-09-01"))
        self.assertEqual(fechas.fecha_detras("cené fuera el 1 de septiembre de 2026", AHORA),
                         ("cené fuera", "2026-09-01"))

    def test_hoy_al_final_se_queda_en_el_texto(self):
        # «hoy» no es pasado: no se recorta y se escribe en hoy.
        self.assertEqual(fechas.fecha_detras("he dormido fatal hoy", AHORA),
                         ("he dormido fatal hoy", None))

    def test_el_futuro_es_parte_de_la_frase(self):
        # «tengo examen mañana» es una frase de hoy sobre mañana, no una
        # entrada de mañana. Aquí está la diferencia con /tarea y /cita.
        for texto in ("tengo examen mañana", "quedo con Ana el lunes",
                      "me voy en 3 días", "vuelvo el 15 de octubre"):
            with self.subTest(texto=texto):
                self.assertEqual(fechas.fecha_detras(texto, AHORA), (texto, None))

    def test_la_hora_se_queda_en_la_frase(self):
        # Lo que se recorta es la fecha a secas; la hora es contenido.
        self.assertEqual(fechas.fecha_detras("cené a las 10 ayer", AHORA),
                         ("cené a las 10", "2026-09-03"))

    def test_ayer_por_la_tarde_no_se_toca(self):
        # La franja es parte de la frase, y con ella pegada «ayer» ya no es
        # una fecha a secas. Se queda entero y en hoy.
        self.assertEqual(fechas.fecha_detras("dormí ayer por la tarde", AHORA),
                         ("dormí ayer por la tarde", None))

    def test_ayer_en_medio_no_cuenta(self):
        self.assertEqual(fechas.fecha_detras("ayer cené con Ana", AHORA),
                         ("ayer cené con Ana", None))

    def test_una_fecha_sola_no_es_una_entrada(self):
        self.assertEqual(fechas.fecha_detras("ayer", AHORA), ("ayer", None))


if __name__ == "__main__":
    unittest.main()
