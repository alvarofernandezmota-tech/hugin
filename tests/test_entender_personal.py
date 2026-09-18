"""Pruebas de hugin/personal/entender.py. Correr: make pruebas

Portadas de diario/tests/test_entender.py de midgaror: mismo cuerpo, salvo
el import y las pruebas nuevas de `es_saludo()` (el fix del «hola»).

Todas usan un `preguntar` falso: nunca se llama a la API de verdad. Lo que
se prueba es la RED DE SEGURIDAD —qué pasa cuando el modelo duda, se
equivoca de forma o falla—, no si Claude clasifica bien, que no es cosa de
este repo.
"""

import unittest
from unittest import mock

import entorno  # noqa: E402,F401

from hugin.personal import entender


def _preguntar(**campos):
    """Un `preguntar` que devuelve `campos` completado con los que falten."""
    base = {"intencion": "diario", "texto": None, "nombre": None,
            "hecho": True, "valor": None, "unidad": None, "cuando": None,
            "confianza": "baja"}
    base.update(campos)
    return lambda frase: base


class TestConfianza(unittest.TestCase):
    def test_confianza_alta_se_devuelve(self):
        e = entender.entender("llamar al médico mañana",
                              preguntar=_preguntar(intencion="tarea", texto="llamar al médico mañana",
                                                    confianza="alta"))
        self.assertEqual(e.intencion, "tarea")
        self.assertEqual(e.texto, "llamar al médico mañana")

    def test_confianza_media_va_al_diario(self):
        self.assertIsNone(entender.entender(
            "algo", preguntar=_preguntar(intencion="tarea", confianza="media")))

    def test_confianza_baja_va_al_diario(self):
        self.assertIsNone(entender.entender(
            "algo", preguntar=_preguntar(intencion="habito", confianza="baja")))

    def test_intencion_diario_va_al_diario_aunque_la_confianza_sea_alta(self):
        # «diario» con alta confianza es el caso normal: una reflexión
        # cualquiera. No es un fallo, es el resultado correcto.
        self.assertIsNone(entender.entender(
            "hoy ha sido un día raro", preguntar=_preguntar(intencion="diario", confianza="alta")))


class TestRedDeSeguridad(unittest.TestCase):
    def test_sin_clave_no_intenta_nada(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(entender.entender("llamar al médico mañana"))

    def test_un_error_al_preguntar_cae_al_diario(self):
        def revienta(frase):
            raise TimeoutError("la API no contestó")
        self.assertIsNone(entender.entender("algo", preguntar=revienta))

    def test_una_intencion_que_no_existe_cae_al_diario(self):
        self.assertIsNone(entender.entender(
            "algo", preguntar=_preguntar(intencion="comprar_lotto", confianza="alta")))

    def test_una_confianza_que_no_existe_cae_al_diario(self):
        self.assertIsNone(entender.entender(
            "algo", preguntar=_preguntar(intencion="tarea", confianza="segura del todo")))

    def test_json_incompleto_no_revienta(self):
        self.assertIsNone(entender.entender(
            "algo", preguntar=lambda frase: {"intencion": "tarea"}))


class TestCamposPorIntencion(unittest.TestCase):
    def test_tarea_lleva_la_frase_entera(self):
        e = entender.entender("comprar pan y leche", preguntar=_preguntar(
            intencion="tarea", texto="comprar pan y leche", confianza="alta"))
        self.assertEqual(e.texto, "comprar pan y leche")
        self.assertIsNone(e.nombre)

    def test_cita_lleva_la_frase_entera(self):
        e = entender.entender("dentista el jueves a las 5", preguntar=_preguntar(
            intencion="cita", texto="dentista el jueves a las 5", confianza="alta"))
        self.assertEqual(e.intencion, "cita")
        self.assertEqual(e.texto, "dentista el jueves a las 5")

    def test_habito_hecho_lleva_nombre_y_hecho_true(self):
        e = entender.entender("he hecho deporte", preguntar=_preguntar(
            intencion="habito", nombre="deporte", hecho=True, confianza="alta"))
        self.assertEqual((e.nombre, e.hecho), ("deporte", True))

    def test_habito_negado_lleva_hecho_false(self):
        e = entender.entender("no he meditado", preguntar=_preguntar(
            intencion="habito", nombre="meditar", hecho=False, confianza="alta"))
        self.assertEqual((e.nombre, e.hecho), ("meditar", False))

    def test_habito_con_valor(self):
        e = entender.entender("energia 7", preguntar=_preguntar(
            intencion="habito", nombre="energia", valor=7, confianza="alta"))
        self.assertEqual((e.nombre, e.valor), ("energia", 7))

    def test_apunte_con_valor_y_unidad(self):
        e = entender.entender("tele 3h", preguntar=_preguntar(
            intencion="apunte", nombre="tele", valor=3, unidad="h", confianza="alta"))
        self.assertEqual((e.nombre, e.valor, e.unidad), ("tele", 3, "h"))

    def test_cuando_se_conserva_tal_cual(self):
        e = entender.entender("ayer hice deporte", preguntar=_preguntar(
            intencion="habito", nombre="deporte", cuando="ayer", confianza="alta"))
        self.assertEqual(e.cuando, "ayer")


class TestReglasSinMotor(unittest.TestCase):
    """«recuérdame X» y los apuntes con número resuelven solos, sin motor."""

    def _sin_motor(self, frase):
        with mock.patch.dict("os.environ", {}, clear=True):
            return entender.entender(frase)

    def test_recuerdame_es_tarea_con_alta_confianza(self):
        e = self._sin_motor("recuérdame llamar al médico el jueves")
        self.assertEqual(e.intencion, "tarea")
        self.assertEqual(e.texto, "llamar al médico el jueves")
        self.assertEqual(e.confianza, "alta")

    def test_recuerdame_sin_acento_tambien_vale(self):
        self.assertEqual(self._sin_motor("recuerdame sacar la basura").texto,
                         "sacar la basura")

    def test_recuerdame_que_tambien_se_reconoce(self):
        e = self._sin_motor("recuérdame que hay que pagar el alquiler")
        self.assertEqual(e.texto, "hay que pagar el alquiler")

    def test_mayusculas_da_igual(self):
        self.assertEqual(self._sin_motor("RECUÉRDAME llamar al médico").intencion, "tarea")

    def test_recuerdame_solo_sin_nada_detras_no_cuela(self):
        self.assertIsNone(self._sin_motor("recuérdame"))
        self.assertIsNone(self._sin_motor("recuérdame   "))

    def test_recordar_a_mitad_de_frase_no_activa_la_regla(self):
        self.assertIsNone(self._sin_motor("hoy no consigo recordarme de nada"))

    def test_apunte_con_unidad(self):
        e = self._sin_motor("tele 3h")
        self.assertEqual(e.intencion, "apunte")
        self.assertEqual(e.nombre, "tele")
        self.assertEqual(e.valor, 3.0)
        self.assertEqual(e.unidad, "h")

    def test_apunte_con_decimal_y_coma(self):
        e = self._sin_motor("agua 1,5 litros")
        self.assertEqual(e.nombre, "agua")
        self.assertEqual(e.valor, 1.5)
        self.assertEqual(e.unidad, "litros")

    def test_sin_unidad_no_cuela_por_ser_habito_no_apunte(self):
        self.assertIsNone(self._sin_motor("energia 7"))
        self.assertIsNone(self._sin_motor("ánimo 8"))

    def test_dos_palabras_de_nombre_no_cuelan(self):
        self.assertIsNone(self._sin_motor("he dormido 8"))
        self.assertIsNone(self._sin_motor("son las 5"))
        self.assertIsNone(self._sin_motor("he corrido 5"))

    def test_una_frase_de_diario_con_numero_no_activa_el_apunte(self):
        self.assertIsNone(self._sin_motor("hoy he corrido 5km y ha ido genial"))
        self.assertIsNone(self._sin_motor("vi la tele 3h y estuvo bien"))

    def test_las_reglas_no_pisan_un_preguntar_puesto_a_mano(self):
        visto = {}

        def preguntar(frase):
            visto["llamado"] = True
            return {"intencion": "diario", "texto": None, "nombre": None,
                    "hecho": True, "valor": None, "unidad": None,
                    "cuando": None, "confianza": "alta"}

        e = entender.entender("recuérdame llamar al médico", preguntar=preguntar)
        self.assertTrue(visto.get("llamado"))
        self.assertIsNone(e)  # "diario" con alta confianza -> None, como siempre


class TestConfigurado(unittest.TestCase):
    def test_configurado_es_falso_sin_clave(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertFalse(entender.configurado())

    def test_configurado_es_verdad_con_clave(self):
        with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-algo"}, clear=True):
            self.assertTrue(entender.configurado())

    def test_modelo_por_defecto_sin_variable(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(entender.modelo(), entender.MODELO_POR_DEFECTO)

    def test_modelo_se_puede_forzar(self):
        with mock.patch.dict("os.environ", {"MIDGAROR_LLM_MODELO": "otro-modelo"}, clear=True):
            self.assertEqual(entender.modelo(), "otro-modelo")


class TestProveedor(unittest.TestCase):
    """El mismo patrón que `hugin/mente/cerebro.py::proveedor`, misma
    variable con otro prefijo (`MIDGAROR_LLM` en vez de `GJALLARHORN_LLM`),
    a propósito: son dos ecosistemas separados pero hablan igual.
    """

    def limpio(self, **variables):
        return mock.patch.dict("os.environ", variables, clear=True)

    def test_sin_nada_no_hay_motor(self):
        with self.limpio():
            self.assertEqual(entender.proveedor(), "")
            self.assertFalse(entender.configurado())

    def test_con_clave_y_sin_elegir_es_claude(self):
        with self.limpio(ANTHROPIC_API_KEY="sk-algo"):
            self.assertEqual(entender.proveedor(), "anthropic")

    def test_ollama_no_necesita_clave(self):
        with self.limpio(MIDGAROR_LLM="ollama"):
            self.assertEqual(entender.proveedor(), "ollama")
            self.assertTrue(entender.configurado())

    def test_local_es_sinonimo_de_ollama(self):
        with self.limpio(MIDGAROR_LLM="local"):
            self.assertEqual(entender.proveedor(), "ollama")

    def test_se_puede_apagar_teniendo_clave(self):
        with self.limpio(ANTHROPIC_API_KEY="sk-algo", MIDGAROR_LLM="no"):
            self.assertEqual(entender.proveedor(), "")
            self.assertFalse(entender.configurado())

    def test_elegir_claude_sin_clave_no_enciende_nada(self):
        with self.limpio(MIDGAROR_LLM="anthropic"):
            self.assertEqual(entender.proveedor(), "")

    def test_el_modelo_local_por_defecto_es_el_de_hugin(self):
        with self.limpio(MIDGAROR_LLM="ollama"):
            self.assertEqual(entender.modelo(), entender.MODELO_LOCAL_POR_DEFECTO)
            self.assertEqual(entender.MODELO_LOCAL_POR_DEFECTO, "qwen3:4b-instruct-2507")

    def test_el_modelo_local_se_puede_forzar(self):
        with self.limpio(MIDGAROR_LLM="ollama", MIDGAROR_LLM_MODELO="gemma3:4b"):
            self.assertEqual(entender.modelo(), "gemma3:4b")

    def test_ollama_url_por_defecto(self):
        with self.limpio():
            self.assertEqual(entender.ollama(), entender.OLLAMA_POR_DEFECTO)

    def test_ollama_url_se_puede_forzar(self):
        with self.limpio(MIDGAROR_OLLAMA="http://otra-maquina:11434"):
            self.assertEqual(entender.ollama(), "http://otra-maquina:11434")


class TestElEnrutadoDelMotor(unittest.TestCase):
    """`entender()` sin `preguntar` tiene que llamar al motor que toque."""

    def limpio(self, **variables):
        return mock.patch.dict("os.environ", variables, clear=True)

    def test_sin_motor_no_se_intenta_nada(self):
        with self.limpio():
            self.assertIsNone(entender.entender("qué tal el día"))

    def test_con_ollama_elegido_se_llama_a_ollama_no_a_claude(self):
        llamado = {}

        def falso_ollama(frase):
            llamado["cual"] = "ollama"
            return {"intencion": "diario", "texto": None, "nombre": None,
                    "hecho": True, "valor": None, "unidad": None,
                    "cuando": None, "confianza": "baja"}

        def explota_si_se_llama(frase):
            raise AssertionError("se ha llamado a Claude con Ollama elegido")

        with self.limpio(MIDGAROR_LLM="ollama"), \
             mock.patch.object(entender, "_preguntar_ollama", falso_ollama), \
             mock.patch.object(entender, "_preguntar_claude", explota_si_se_llama):
            entender.entender("qué tal el día")
        self.assertEqual(llamado.get("cual"), "ollama")


class TestElSaludoNoEsDiario(unittest.TestCase):
    """El fallo real de Madre (2026-09-18): un simple «hola» se escribía
    como entrada de diario. No pasa por `entender()` —ni por ningún motor—,
    es un chequeo previo, estricto y cerrado.
    """

    def test_saludos_sueltos_se_reconocen(self):
        for frase in ("hola", "Hola", "HOLA", "hola!", "¡hola!", "hey",
                      "buenas", "buenos dias", "buenas noches", "gracias",
                      "vale", "ok", "adiós", "adios"):
            with self.subTest(frase=frase):
                self.assertTrue(entender.es_saludo(frase), f"{frase!r} debería ser saludo")

    def test_con_espacios_alrededor_tambien_cuela(self):
        self.assertTrue(entender.es_saludo("   hola   "))

    def test_una_frase_de_diario_que_empieza_igual_no_es_saludo(self):
        # El caso que justo hay que evitar: no vale con "empieza por hola".
        self.assertFalse(entender.es_saludo("hola, hoy ha sido un día raro"))
        self.assertFalse(entender.es_saludo("hola a todos en la reunión"))

    def test_un_habito_de_una_palabra_no_es_saludo(self):
        # "cansado" es una entrada de diario válida de una palabra: el
        # chequeo no puede confundir "corto" con "saludo".
        self.assertFalse(entender.es_saludo("cansado"))
        self.assertFalse(entender.es_saludo("bien"))

    def test_vacio_no_es_saludo(self):
        self.assertFalse(entender.es_saludo(""))
        self.assertFalse(entender.es_saludo("   "))


if __name__ == "__main__":
    unittest.main()
