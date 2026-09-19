"""Una conversación entera por consola, sin Telegram y sin teléfono.

Es la prueba que justifica la fase 1 del issue #23: hasta ahora, para saber
qué contesta el bot a «recuérdame llamar al médico» había que construir un
`Update` falso y un paquete `telegram` de mentira (`telegram/tests/dobles.py`
son 400 líneas de eso). Aquí se le pasan frases a `main()` y se lee lo que
contesta.

Por eso NO se reutiliza `telegram/tests/dobles.py`, aunque tenga los dobles
hechos: ese módulo instala un `telegram` falso en `sys.modules` al
importarlo, y meterlo en la suite del cerebro ataría el cerebro a una
puerta. Es justo lo que esta fase viene a deshacer. Lo que hace falta aquí
—un inquilino en un temporal, un diario en un temporal y un clasificador
falso— son quince líneas.

El clasificador y el que contesta preguntas van SIEMPRE inyectados: ninguna
prueba de aquí puede llamar a una API, ni depender de que haya un motor
configurado en la máquina donde corra.
"""

import tempfile
import unittest
from pathlib import Path

import entorno  # noqa: E402,F401

from hugin import inquilino as hugin_inquilino
from hugin.bot import main as consola
from hugin.bot.hugin import Hugin
from hugin.bot.mensajes import Mensaje, Respuesta, Sesion
from hugin.personal import citas, diario, tareas

HOY = "## Qué ha pasado hoy"


def _entendido(**campos):
    """Un `preguntar` falso, igual que el de `telegram/tests/test_texto.py`.

    Devuelve los ocho campos que `entender()` espera de un motor, con
    `diario`/`baja` por defecto — o sea: «no he reconocido nada», que es el
    camino que sigue una frase normal.
    """
    base = {"intencion": "diario", "texto": None, "nombre": None,
            "hecho": True, "valor": None, "unidad": None, "cuando": None,
            "confianza": "baja"}
    base.update(campos)
    return lambda frase: base


class CasoConsola(unittest.TestCase):
    """Un inquilino y un diario en un temporal. Sin git, sin red, sin motor."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)

        carpeta = base / "inquilino"
        carpeta.mkdir()
        self.inq = hugin_inquilino.Inquilino(
            nombre="prueba", ruta=carpeta,
            capacidades=frozenset({"apuntes", "tareas", "habitos", "agenda"}),
            base=None)

        # El diario se resuelve desde el directorio de trabajo, así que se
        # desvía por su constante de módulo —que está pensada justo para
        # esto— y no tocando `os.chdir`, que le cambiaría el suelo a toda la
        # suite.
        self.diario = base / "diario"
        anterior = diario.CARPETA_PERSONAL
        diario.CARPETA_PERSONAL = self.diario
        self.addCleanup(lambda: setattr(diario, "CARPETA_PERSONAL", anterior))

        self.sesion = Sesion(inquilino=self.inq, actor_id="prueba",
                             conversacion_id="consola", canal="cli")

    def contestar(self, texto: str, **motores) -> Respuesta:
        """Lo que contesta Hugin a una frase. Sin sincronizar, como la consola."""
        cerebro = Hugin(**motores)
        return cerebro.procesar(Mensaje(texto=texto, sesion=self.sesion))

    def seccion_de_hoy(self) -> str:
        """Lo escrito hoy en «Qué ha pasado hoy», o cadena vacía."""
        entradas = sorted(self.diario.rglob("*.md"))
        if not entradas:
            return ""
        texto = entradas[-1].read_text(encoding="utf-8")
        cuerpo = texto.split(HOY, 1)[1] if HOY in texto else ""
        return cuerpo.split("\n## ", 1)[0].strip()


class TestUnaPreguntaSeContesta(CasoConsola):
    """«qué tengo hoy» — la rama que lee y NO escribe.

    El caso del ejemplo del issue #23, y el que más importa que no escriba:
    un modelo que pueda leer y escribir en la misma vuelta convierte «¿tengo
    dentista el jueves?» en una cita nueva el jueves, y eso no se ve hasta
    que llega el jueves.
    """

    def test_contesta_en_prosa_y_no_apunta_nada(self):
        respuesta = self.contestar(
            "qué tengo hoy",
            preguntar=_entendido(intencion="pregunta", texto="qué tengo hoy",
                                 confianza="alta"),
            responder_pregunta=lambda pregunta, contexto: "Dos tareas y ninguna cita.")
        self.assertEqual(respuesta.texto, "Dos tareas y ninguna cita.")
        # Ni al diario, ni a tareas, ni a la agenda.
        self.assertEqual(self.seccion_de_hoy(), "")
        self.assertEqual(tareas.cargar(self.inq), [])
        self.assertEqual(citas.cargar(self.inq), [])

    def test_le_llega_la_pregunta_entera(self):
        visto = {}

        def espiar(pregunta, contexto):
            visto["pregunta"] = pregunta
            return "vale"

        self.contestar("qué tengo hoy",
                       preguntar=_entendido(intencion="pregunta", texto="qué tengo hoy",
                                            confianza="alta"),
                       responder_pregunta=espiar)
        self.assertEqual(visto["pregunta"], "qué tengo hoy")

    def test_si_no_se_puede_contestar_cae_al_diario(self):
        # Sin motor, red caída o respuesta vacía: `conversar.responder()` da
        # None y la frase no se pierde, se apunta. Nunca se traga un mensaje
        # por no poder contestarlo.
        respuesta = self.contestar(
            "qué tengo hoy",
            preguntar=_entendido(intencion="pregunta", texto="qué tengo hoy",
                                 confianza="alta"),
            responder_pregunta=lambda pregunta, contexto: None)
        self.assertIn("Apuntado en el diario", respuesta.texto)
        self.assertIn("qué tengo hoy", self.seccion_de_hoy())


class TestSeCreaUnaTarea(CasoConsola):
    """«recuérdame llamar al médico el 15 de octubre» — la rama que escribe.

    Fecha absoluta a propósito, como en `telegram/tests/test_texto.py`:
    `tareas.agregar()` usa el reloj de verdad si no se le inyecta otro, así
    que «mañana» dependería del día en que corra la prueba.
    """

    def test_va_a_tareas_agregar_y_no_al_diario(self):
        respuesta = self.contestar(
            "recuérdame llamar al médico el 15 de octubre",
            preguntar=_entendido(intencion="tarea",
                                 texto="llamar al médico el 15 de octubre",
                                 confianza="alta"))
        self.assertIn("✅", respuesta.texto)
        self.assertIn("llamar al médico", respuesta.texto)
        self.assertEqual(self.seccion_de_hoy(), "")

        activas = tareas.activas(tareas.cargar(self.inq))
        self.assertEqual(len(activas), 1)
        self.assertEqual(activas[0]["texto"], "llamar al médico")
        self.assertEqual(activas[0]["fecha"], "2026-10-15")

    def test_sin_sincronizar_la_confirmacion_no_lleva_coletilla(self):
        # La consola no hace `git push` por línea escrita, así que no hay
        # nada que decir sobre subir — y un « · » suelto al final sería
        # basura en la pantalla. `coletilla()` es lo único que no venía tal
        # cual de `handlers/texto.py`, así que se prueba.
        respuesta = self.contestar(
            "recuérdame llamar al médico el 15 de octubre",
            preguntar=_entendido(intencion="tarea",
                                 texto="llamar al médico el 15 de octubre",
                                 confianza="alta"))
        self.assertNotIn(" · subido", respuesta.texto)
        self.assertFalse(respuesta.texto.rstrip().endswith("·"))

    def test_con_sincronizar_la_confirmacion_la_lleva(self):
        # El mismo texto que sale por Telegram. `sincronizar` inyectado: la
        # suite no toca git ni la red por accidente.
        cerebro = Hugin(preguntar=_entendido(intencion="tarea",
                                             texto="llamar al médico el 15 de octubre",
                                             confianza="alta"),
                        sincronizar=lambda ruta, mensaje: "escrito y subido a GitHub")
        respuesta = cerebro.procesar(Mensaje(
            texto="recuérdame llamar al médico el 15 de octubre", sesion=self.sesion))
        self.assertIn(" · subido", respuesta.texto)


class TestLoDemasVaAlDiario(CasoConsola):
    def test_una_frase_normal_se_apunta(self):
        # Sin `preguntar`: sin motor configurado, `entender()` devuelve None
        # antes de intentar nada, igual que en producción sin clave.
        respuesta = self.contestar("he dormido fatal")
        self.assertIn("Apuntado en el diario", respuesta.texto)
        self.assertIn("he dormido fatal", self.seccion_de_hoy())

    def test_un_saludo_no_se_apunta(self):
        # El fallo real de Madre (2026-09-18): «hola» se escribía como
        # entrada de diario.
        respuesta = self.contestar("hola")
        self.assertIn("Hola", respuesta.texto)
        self.assertEqual(self.seccion_de_hoy(), "")

    def test_un_saludo_no_llega_a_preguntarle_al_motor(self):
        def explota(frase):
            raise AssertionError("no debería preguntarse nada para un saludo")

        self.contestar("hola", preguntar=explota)

    def test_la_respuesta_nunca_espera_respuesta_en_la_fase_1(self):
        # `espera_respuesta` está declarado y no cableado: el diálogo de
        # confirmación («¿te refieres a las 17:00?») es la fase 2. Si algún
        # día alguien lo enciende a medias, esto lo dice.
        for frase in ("hola", "he dormido fatal"):
            with self.subTest(frase=frase):
                respuesta = self.contestar(frase)
                self.assertFalse(respuesta.espera_respuesta)
                self.assertEqual(respuesta.opciones, ())


class TestElBucleDeConsola(CasoConsola):
    """`python -m hugin`: que el bucle lea, conteste y sepa salir.

    `main()` recibe `entrada`/`salida` inyectadas justo para esto: se le
    pasa una lista de frases y se lee lo que ha ido contestando, sin
    terminal y sin tocar `sys.stdin`.
    """

    def _correr(self, frases, argv=None):
        dichas, salidas = list(frases), []

        def entrada(prompt):
            if not dichas:
                raise EOFError
            return dichas.pop(0)

        codigo = consola.main(argv=argv or [], entrada=entrada, salida=salidas.append)
        return codigo, salidas

    def setUp(self):
        super().setUp()
        # `main()` resuelve el inquilino desde el entorno, como
        # `telegram/utils/inquilino.py`. Se le da el de mentira.
        import os
        from unittest import mock
        self._entorno = mock.patch.dict(os.environ, {consola.VARIABLE: "prueba"})
        self._entorno.start()
        self.addCleanup(self._entorno.stop)
        anterior = hugin_inquilino.cargar
        hugin_inquilino.cargar = lambda nombre: self.inq
        self.addCleanup(lambda: setattr(hugin_inquilino, "cargar", anterior))

    def test_una_conversacion_de_dos_frases(self):
        codigo, salidas = self._correr(["hola", "he dormido fatal"])
        self.assertEqual(codigo, 0)
        dicho = "\n".join(salidas)
        self.assertIn("atendiendo a prueba", dicho)
        self.assertIn("Hola", dicho)
        self.assertIn("Apuntado en el diario", dicho)
        # Y lo que tenía que quedar escrito, está escrito.
        self.assertIn("he dormido fatal", self.seccion_de_hoy())

    def test_ctrl_d_sale_con_cero(self):
        codigo, _ = self._correr([])
        self.assertEqual(codigo, 0)

    def test_una_linea_vacia_no_se_apunta(self):
        # Dar Enter sin escribir nada no es una entrada de diario en blanco.
        self._correr(["", "   "])
        self.assertEqual(self.seccion_de_hoy(), "")

    def test_avisa_de_que_no_sincroniza(self):
        _, salidas = self._correr(["hola"])
        self.assertIn("no se sube", "\n".join(salidas))

    def test_con_la_bandera_lo_dice_tambien(self):
        _, salidas = self._correr(["hola"], argv=["--sincronizar"])
        self.assertIn("se sube con git", "\n".join(salidas))

    def test_sin_inquilino_no_arranca_y_lo_dice(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {consola.VARIABLE: ""}):
            codigo, salidas = self._correr(["hola"])
        self.assertEqual(codigo, 2)
        self.assertIn(consola.VARIABLE, "\n".join(salidas))

    def test_un_argumento_que_no_entiende_no_se_traga(self):
        codigo, salidas = self._correr([], argv=["--subir-todo"])
        self.assertEqual(codigo, 2)
        self.assertIn("No entiendo", "\n".join(salidas))


if __name__ == "__main__":
    unittest.main()
