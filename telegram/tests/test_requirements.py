"""Pruebas de requirements.txt: que declare lo que hace falta de verdad.

Sale de un fallo en Madre el 2026-09-17: `pip install -r requirements.txt`
terminó con «Successfully installed faster-whisper-1.1.1» y la primera nota
de voz murió con `ModuleNotFoundError: No module named 'requests'`.

faster-whisper hace `import requests` en `utils.py` y **no lo declara**. Se
lo traía `huggingface-hub` de rebote, y la 1.x se pasó a `httpx`. Resultado:
una instalación que dice que fue bien y un fallo en tiempo de uso hablando de
un paquete que nadie había pedido.
"""

import re
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# Lo que faster-whisper importa y NO declara en su metadata. Medido leyendo
# los imports del wheel 1.1.1, no de memoria.
NO_DECLARADOS_POR_FASTER_WHISPER = ("requests",)


def paquetes() -> dict:
    """{nombre: versión} de requirements.txt, sin comentarios ni huecos."""
    fijados = {}
    for linea in (RAIZ / "requirements.txt").read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        if (m := re.match(r"^([A-Za-z0-9._-]+)==(.+)$", linea)):
            fijados[m.group(1).lower()] = m.group(2)
    return fijados


class TestLoQueSeDeclara(unittest.TestCase):
    def test_todo_va_con_version_fijada(self):
        # El fichero lo dice en su cabecera: sin fijar, un pip install en el
        # momento equivocado deja el bot sin arrancar.
        sueltos = [ln.strip() for ln in
                   (RAIZ / "requirements.txt").read_text(encoding="utf-8").splitlines()
                   if ln.strip() and not ln.strip().startswith("#") and "==" not in ln]
        self.assertEqual(sueltos, [])

    def test_estan_las_que_importa_el_bot(self):
        fijados = paquetes()
        for paquete in ("python-telegram-bot", "python-dotenv"):
            with self.subTest(paquete=paquete):
                self.assertIn(paquete, fijados)

    def test_lo_que_faster_whisper_importa_y_no_declara_esta_aqui(self):
        # La regresión de Madre. Si algún día se sube faster-whisper y ya lo
        # declara, esta prueba no estorba: seguirá estando y de sobra.
        fijados = paquetes()
        if "faster-whisper" not in fijados:
            self.skipTest("sin faster-whisper no hay nada que completar")
        for paquete in NO_DECLARADOS_POR_FASTER_WHISPER:
            with self.subTest(paquete=paquete):
                self.assertIn(paquete, fijados,
                              f"faster-whisper importa {paquete} y no lo declara: "
                              "se instala «bien» y revienta al primer uso")


if __name__ == "__main__":
    unittest.main()


class TestLaPlantillaDelEnv(unittest.TestCase):
    """.env.example tiene que nombrar TODAS las variables que el bot lee.

    Hasta el 2026-09-18 documentaba dos y el codigo leia cuatro. La que
    faltaba era `ANTHROPIC_API_KEY`, que es justo la que enciende que el bot
    entienda lo que le escribes — y la mas facil de olvidar, porque sin ella
    no falla nada: simplemente no pasa nada.
    """

    def variables_de_la_plantilla(self) -> set:
        texto = (RAIZ / ".env.example").read_text(encoding="utf-8")
        return {ln.split("=")[0].strip() for ln in texto.splitlines()
                if "=" in ln and not ln.strip().startswith("#")}

    def test_estan_las_dos_obligatorias(self):
        for variable in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
            with self.subTest(variable=variable):
                self.assertIn(variable, self.variables_de_la_plantilla())

    def test_esta_la_que_enciende_entender(self):
        self.assertIn("ANTHROPIC_API_KEY", self.variables_de_la_plantilla())

    def test_estan_las_de_ollama_adr_022(self):
        # Sin estas dos, alguien podia poner MIDGAROR_LLM=ollama en un .env
        # a mano y nunca enterarse de que existen: la plantilla no las
        # nombra, no hay pista de que el bot las lee.
        variables = self.variables_de_la_plantilla()
        for variable in ("MIDGAROR_LLM", "MIDGAROR_OLLAMA"):
            with self.subTest(variable=variable):
                self.assertIn(variable, variables)

    def test_la_plantilla_no_lleva_ningun_valor_de_verdad(self):
        # Una plantilla con una clave dentro es una clave publicada.
        texto = (RAIZ / ".env.example").read_text(encoding="utf-8")
        for pista in ("sk-ant-", "sk-or-v1-", ":AA"):
            with self.subTest(pista=pista):
                self.assertNotIn(pista, texto)


class TestNingunSecretoSePuedeColar(unittest.TestCase):
    """El `.gitignore` tiene que cubrir los primos del `.env`, no solo el `.env`.

    Sale de un susto real. La noche del 2026-09-18, arreglando un `.env` que
    un editor habia estropeado, quedo un `.env.bak` en Madre con el token de
    Telegram dentro. `.env` estaba ignorado; `.env.bak` no, y `estado.sh` lo
    canto como «1 fichero sin commitear». Un `git add -A` lo habria subido a
    un repositorio PUBLICO, y un token en el historial de git no se quita
    borrando el fichero: hay que rotarlo.

    Se prueba por patron y no por nombre a proposito: `.env.bak` es el que
    paso, pero `.env.old`, `.env.2` o `.env.produccion` son el mismo fallo.
    """

    IGNORADOS = (".env", ".env.bak", ".env.old", ".env.local", ".env.produccion")

    def reglas(self) -> list:
        return [ln.strip() for ln
                in (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.strip().startswith("#")]

    def test_el_patron_cubre_los_primos_del_env(self):
        self.assertIn(".env.*", self.reglas(),
                      "sin `.env.*`, un `.env.bak` con el token dentro es "
                      "commiteable en un repo publico")

    def test_pero_el_ejemplo_se_salva(self):
        # `.env.*` tambien taparia `.env.example`, que SI tiene que viajar
        # con el repo: es de donde se copia la plantilla en una maquina nueva.
        self.assertIn("!.env.example", self.reglas())
        self.assertTrue((RAIZ / ".env.example").exists())

    def test_y_la_excepcion_va_despues_del_patron(self):
        # En git manda la ultima regla que casa. Con `!.env.example` ANTES de
        # `.env.*`, el ejemplo quedaria ignorado igual y el fallo no se veria
        # hasta clonar en limpio y no encontrar la plantilla.
        reglas = self.reglas()
        self.assertLess(reglas.index(".env.*"), reglas.index("!.env.example"))
