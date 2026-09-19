"""Pruebas de hugin/personal/conversar.py. Correr: make pruebas

Portadas de diario/tests/test_conversar.py de midgaror. Lo que se prueba
aquí NO es si el modelo contesta bien —eso es del modelo—. Es lo de
alrededor, que es lo que puede hacer daño: que sin clave no haga nada, que
un fallo nunca llegue al usuario como excepción, y sobre todo que este
camino **no pueda escribir**.

Esa última es la que justifica el módulo entero. Está escrita contra el
texto del fichero, no contra su comportamiento, a propósito: una prueba de
comportamiento solo falla si alguien llama a la función que escribe, y para
entonces ya hay un `agregar` importado esperando a que alguien lo llame.
"""

import ast
import unittest
from pathlib import Path
from unittest import mock

import entorno  # noqa: E402,F401

from hugin.personal import conversar, entender

MODULO = Path(conversar.__file__)

# Lo que escribe. Si alguno de estos nombres aparece importado en
# conversar.py, la puerta está abierta.
ESCRIBEN = {
    "agregar", "marcar", "apuntar", "guardar", "editar", "borrar",
    "aplazar", "hecha", "reabrir", "empezar", "escribir", "sincronizar",
}


class TestNoPuedeEscribir(unittest.TestCase):
    """La regla de la casa, comprobada sobre el código y no sobre la fe."""

    def arbol(self):
        return ast.parse(MODULO.read_text(encoding="utf-8"))

    def nombres_importados(self):
        for nodo in ast.walk(self.arbol()):
            if isinstance(nodo, ast.ImportFrom):
                for alias in nodo.names:
                    yield alias.name
            elif isinstance(nodo, ast.Import):
                for alias in nodo.names:
                    yield alias.name.split(".")[-1]

    def test_no_importa_nada_que_escriba(self):
        colados = sorted(set(self.nombres_importados()) & ESCRIBEN)
        self.assertEqual(colados, [], "\n".join([
            "conversar.py importa funciones que ESCRIBEN: " + ", ".join(colados),
            "",
            "Este camino contesta preguntas. Si además puede escribir, un",
            "«¿tengo dentista el jueves?» se convierte en una cita el jueves",
            "y no se ve hasta que llega el jueves. Lee, y ya está.",
        ]))

    def test_tampoco_las_llama_por_el_modulo(self):
        # `tareas.agregar(...)` no aparece como import, pero escribe igual.
        mal = []
        for nodo in ast.walk(self.arbol()):
            if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute) \
                    and nodo.func.attr in ESCRIBEN:
                mal.append(f"línea {nodo.lineno}: .{nodo.func.attr}(…)")
        self.assertEqual(mal, [], "conversar.py llama a algo que escribe:\n"
                         + "\n".join(mal))

    def test_solo_lee_resumenes(self):
        # Lo que sí puede llamar: los `resumen*`, que son los mismos que
        # pintan `/hoy`. Si esto se queda vacío es que `datos()` dejó de
        # mirar los datos y la prueba de arriba pasaría por no hacer nada.
        llamadas = {nodo.func.attr for nodo in ast.walk(self.arbol())
                    if isinstance(nodo, ast.Call)
                    and isinstance(nodo.func, ast.Attribute)}
        self.assertTrue({"resumen", "resumen_dia"} <= llamadas,
                        f"conversar.datos() ya no lee los resúmenes: {sorted(llamadas)}")


class TestResponder(unittest.TestCase):
    def test_sin_clave_no_hace_nada(self):
        # `preguntar=None` y sin ningún motor: ni siquiera lo intenta.
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(conversar.responder("¿qué tengo hoy?"))

    def test_contesta_lo_que_diga_el_modelo(self):
        dicho = conversar.responder(
            "¿qué tengo hoy?", preguntar=lambda p, c: "  Dos tareas.  ",
            contexto="X")
        self.assertEqual(dicho, "Dos tareas.")

    def test_le_llega_la_pregunta_y_el_contexto(self):
        visto = {}

        def espiar(pregunta, contexto):
            visto["pregunta"], visto["contexto"] = pregunta, contexto
            return "vale"

        conversar.responder("¿y mañana?", preguntar=espiar, contexto="MIS DATOS")
        self.assertEqual(visto["pregunta"], "¿y mañana?")
        self.assertEqual(visto["contexto"], "MIS DATOS")

    def test_una_pregunta_vacia_no_llama_a_nadie(self):
        def explota(*_):
            raise AssertionError("no debería preguntarse nada")

        self.assertIsNone(conversar.responder("   ", preguntar=explota))

    def test_un_fallo_no_sale_como_excepcion(self):
        # Cae al diario, como todo lo demás. Nunca revienta hacia el usuario.
        def rompe(*_):
            raise RuntimeError("se cayó la red")

        self.assertIsNone(conversar.responder("¿qué tal?", preguntar=rompe,
                                              contexto="X"))

    def test_una_respuesta_vacia_cuenta_como_no_haber_contestado(self):
        # Una burbuja en blanco en Telegram parece que se ha tragado el
        # mensaje. Mejor que caiga al diario, que al menos lo guarda.
        self.assertIsNone(conversar.responder("hola", preguntar=lambda p, c: "   ",
                                              contexto="X"))


class TestLosDatosQueVe(unittest.TestCase):
    def test_lleva_los_cuatro_bloques_con_su_titulo(self):
        # Sin inquilino, cada resumen* falla y _o_nada lo cubre con su
        # mensaje de "no se pudo leer" — pero los CUATRO títulos son fijos,
        # así que siguen ahí igual.
        texto = conversar.datos()
        for titulo in ("TAREAS", "AGENDA", "HÁBITOS", "APUNTES"):
            with self.subTest(titulo=titulo):
                self.assertIn(titulo, texto)

    def test_un_modelo_que_revienta_no_tira_la_respuesta_entera(self):
        # Si un dato está a medias, la pregunta puede ir de otra cosa.
        def rompe():
            raise KeyError("total")

        self.assertEqual(conversar._o_nada(rompe, "no se pudo leer"),
                         "no se pudo leer")

    def test_lo_que_no_cabe_se_corta_diciendolo(self):
        # Un resumen recortado en silencio es un resumen que miente: el
        # modelo contestaría «no tienes nada más» sobre datos que sí están.
        cortado = conversar._recortar("a" * 100, tope=10)
        self.assertTrue(cortado.startswith("a" * 10))
        self.assertIn("cortado", cortado)

    def test_lo_que_cabe_se_deja_tal_cual(self):
        self.assertEqual(conversar._recortar("corto", tope=10), "corto")


class TestLosDatosConInquilino(unittest.TestCase):
    """A diferencia de midgaror (un solo diario), aquí `datos()` necesita
    saber de quién — se le pasa el `inq`, igual que a cada `resumen*`.
    """

    def test_datos_pasa_el_inq_a_los_cuatro_resumenes(self):
        import tempfile
        from hugin import inquilino as hugin_inquilino

        with tempfile.TemporaryDirectory() as tmp:
            inq = hugin_inquilino.Inquilino(
                nombre="prueba", ruta=Path(tmp),
                capacidades=frozenset({"tareas", "agenda", "habitos", "apuntes"}),
                base=None)
            # Con el inquilino de verdad (carpeta vacía, sin datos), los
            # cuatro resumen* deberían responder sin reventar — nada de
            # "no se pudo leer": una carpeta vacía es un inquilino sin
            # nada apuntado, no un fallo.
            texto = conversar.datos(inq)
            for titulo in ("TAREAS", "AGENDA", "HÁBITOS", "APUNTES"):
                with self.subTest(titulo=titulo):
                    self.assertIn(titulo, texto)
            self.assertNotIn("No se pudieron leer", texto)
            self.assertNotIn("No se pudo leer", texto)

    def test_sin_capacidad_de_negocio_no_hay_bloque_de_servicio(self):
        import tempfile
        from hugin import inquilino as hugin_inquilino

        with tempfile.TemporaryDirectory() as tmp:
            inq = hugin_inquilino.Inquilino(
                nombre="prueba", ruta=Path(tmp),
                capacidades=frozenset({"tareas", "agenda", "habitos", "apuntes"}),
                base=None)
            self.assertNotIn("SERVICIO QUE OFRECES", conversar.datos(inq))

    def test_con_tarifas_el_bloque_de_servicio_lleva_el_precio_real(self):
        import tempfile
        from hugin import inquilino as hugin_inquilino

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tarifas.md").write_text(
                "| Servicio | Precio |\n|---|---|\n| Plan persona | 9 € |\n",
                encoding="utf-8")
            inq = hugin_inquilino.Inquilino(
                nombre="prueba", ruta=Path(tmp),
                capacidades=frozenset({"tareas", "tarifas"}), base=None)
            texto = conversar.datos(inq)
            self.assertIn("SERVICIO QUE OFRECES", texto)
            self.assertIn("Plan persona", texto)
            self.assertIn("9 €", texto)

    def test_con_faq_pero_sin_tarifas_tambien_sale_el_bloque(self):
        import tempfile
        from hugin import inquilino as hugin_inquilino

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "faq.md").write_text("## ¿Qué es esto?\nUn bot.\n",
                                              encoding="utf-8")
            inq = hugin_inquilino.Inquilino(
                nombre="prueba", ruta=Path(tmp),
                capacidades=frozenset({"tareas", "faq"}), base=None)
            self.assertIn("SERVICIO QUE OFRECES", conversar.datos(inq))


class TestElEnrutado(unittest.TestCase):
    """`entender` tiene que saber decir «esto es una pregunta»."""

    def test_pregunta_es_una_intencion(self):
        self.assertIn("pregunta", entender.INTENCIONES)
        self.assertIn("pregunta", entender.ESQUEMA["properties"]["intencion"]["enum"])

    def test_pregunta_no_esta_entre_las_que_escriben(self):
        # Es la garantía de enrutado: ninguna rama que escriba la alcanza.
        self.assertNotIn("pregunta", entender.ESCRIBEN)
        self.assertEqual(set(entender.ESCRIBEN) | {"pregunta", "diario"},
                         set(entender.INTENCIONES))

    def test_sale_de_entender_con_la_frase_original(self):
        entendido = entender.entender("¿qué tengo hoy?", preguntar=lambda f: {
            "intencion": "pregunta", "texto": None, "nombre": None,
            "hecho": True, "valor": None, "unidad": None, "cuando": None,
            "confianza": "alta"})
        self.assertIsNotNone(entendido)
        self.assertEqual(entendido.intencion, "pregunta")
        self.assertEqual(entendido.texto, "¿qué tengo hoy?")
        self.assertIsNone(entendido.nombre)

    def test_ni_siquiera_un_modelo_que_la_resume_la_cambia(self):
        entendido = entender.entender("¿voy al dentista el jueves?",
                                      preguntar=lambda f: {
            "intencion": "pregunta", "texto": "dentista jueves", "nombre": None,
            "hecho": True, "valor": None, "unidad": None, "cuando": None,
            "confianza": "alta"})
        self.assertEqual(entendido.texto, "¿voy al dentista el jueves?")

    def test_una_pregunta_dudosa_sigue_yendo_al_diario(self):
        self.assertIsNone(entender.entender("¿?", preguntar=lambda f: {
            "intencion": "pregunta", "texto": None, "nombre": None,
            "hecho": True, "valor": None, "unidad": None, "cuando": None,
            "confianza": "media"}))

    def test_el_modelo_sabe_que_existe(self):
        self.assertIn("pregunta:", entender.INSTRUCCIONES)


class TestElEnrutadoDelMotor(unittest.TestCase):
    """`responder()` sin `preguntar` tiene que usar el mismo motor que
    `entender.proveedor()` diga, y ninguno de los dos.
    """

    def limpio(self, **variables):
        return mock.patch.dict("os.environ", variables, clear=True)

    def test_con_ollama_elegido_se_llama_a_ollama_no_a_claude(self):
        def falso_ollama(pregunta, contexto):
            return "contestado en local"

        def explota_si_se_llama(pregunta, contexto):
            raise AssertionError("se ha llamado a Claude con Ollama elegido")

        with self.limpio(MIDGAROR_LLM="ollama"), \
             mock.patch.object(conversar, "_preguntar_ollama", falso_ollama), \
             mock.patch.object(conversar, "_preguntar_claude", explota_si_se_llama):
            self.assertEqual(conversar.responder("¿qué tengo hoy?"),
                            "contestado en local")

    def test_con_claude_elegido_se_llama_a_claude_no_a_ollama(self):
        def falso_claude(pregunta, contexto):
            return "contestado en la nube"

        def explota_si_se_llama(pregunta, contexto):
            raise AssertionError("se ha llamado a Ollama con Claude elegido")

        with self.limpio(ANTHROPIC_API_KEY="sk-algo"), \
             mock.patch.object(conversar, "_preguntar_claude", falso_claude), \
             mock.patch.object(conversar, "_preguntar_ollama", explota_si_se_llama):
            self.assertEqual(conversar.responder("¿qué tengo hoy?"),
                            "contestado en la nube")

    def test_sin_ninguno_no_se_llama_a_nadie(self):
        with self.limpio():
            self.assertIsNone(conversar.responder("¿qué tengo hoy?"))

    def test_con_groq_elegido_se_llama_a_groq(self):
        def falso_groq(pregunta, contexto):
            return "contestado por Groq"

        def explota(pregunta, contexto):
            raise AssertionError("no debería haberse llamado a este motor")

        with self.limpio(MIDGAROR_LLM="groq", GROQ_API_KEY="gsk-algo"), \
             mock.patch.object(conversar, "_preguntar_groq", falso_groq), \
             mock.patch.object(conversar, "_preguntar_claude", explota), \
             mock.patch.object(conversar, "_preguntar_ollama", explota), \
             mock.patch.object(conversar, "_preguntar_google", explota):
            self.assertEqual(conversar.responder("¿qué tengo hoy?"), "contestado por Groq")

    def test_con_google_elegido_se_llama_a_google(self):
        def falso_google(pregunta, contexto):
            return "contestado por Google"

        def explota(pregunta, contexto):
            raise AssertionError("no debería haberse llamado a este motor")

        with self.limpio(MIDGAROR_LLM="google", GOOGLE_API_KEY="AI-algo"), \
             mock.patch.object(conversar, "_preguntar_google", falso_google), \
             mock.patch.object(conversar, "_preguntar_claude", explota), \
             mock.patch.object(conversar, "_preguntar_ollama", explota), \
             mock.patch.object(conversar, "_preguntar_groq", explota):
            self.assertEqual(conversar.responder("¿qué tengo hoy?"), "contestado por Google")


if __name__ == "__main__":
    unittest.main()
