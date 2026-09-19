"""Pruebas de hugin/motores.py — el selector de motor LLM compartido entre
mente/cerebro.py y personal/entender.py (primer paso de la fusión de los
dos, ver docs/adr/).
"""

import os
import unittest

import entorno  # noqa: E402,F401

from hugin import motores


class TestSelectorDeMotor(unittest.TestCase):
    def setUp(self):
        self.antes = {k: os.environ.get(k) for k in
                      ("MIA_LLM", "MIA_LLM_MODELO", "MIA_OLLAMA",
                       "ANTHROPIC_API_KEY", "GROQ_API_KEY", "GOOGLE_API_KEY")}
        self.addCleanup(self.devolver)
        for clave in self.antes:
            os.environ.pop(clave, None)
        self.selector = motores.SelectorDeMotor(variable="MIA_LLM", prefijo="MIA")

    def devolver(self):
        for clave, valor in self.antes.items():
            if valor is None:
                os.environ.pop(clave, None)
            else:
                os.environ[clave] = valor

    def test_sin_nada_no_hay_motor(self):
        self.assertEqual(self.selector.proveedor(), "")
        self.assertFalse(self.selector.configurado())

    def test_con_clave_y_sin_elegir_es_claude(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-de-mentira"
        self.assertEqual(self.selector.proveedor(), "anthropic")
        self.assertEqual(self.selector.modelo(), self.selector.modelo_por_defecto)

    def test_ollama_no_necesita_clave(self):
        os.environ["MIA_LLM"] = "ollama"
        self.assertEqual(self.selector.proveedor(), "ollama")
        self.assertEqual(self.selector.modelo(), self.selector.modelo_local_por_defecto)

    def test_auto_es_un_motor_propio(self):
        os.environ["MIA_LLM"] = "auto"
        self.assertEqual(self.selector.proveedor(), "auto")
        self.assertTrue(self.selector.configurado())

    def test_el_modelo_se_puede_fijar(self):
        os.environ["MIA_LLM"] = "ollama"
        os.environ["MIA_LLM_MODELO"] = "gemma3:4b"
        self.assertEqual(self.selector.modelo(), "gemma3:4b")

    def test_ollama_usa_su_propia_variable_no_la_del_modelo(self):
        # MIA_OLLAMA, no MIA_LLM_OLLAMA: comparten "MIA", no "MIA_LLM".
        os.environ["MIA_OLLAMA"] = "http://otra-maquina:11434"
        self.assertEqual(self.selector.ollama(), "http://otra-maquina:11434")

    def test_motores_nube_en_orden_claude_groq_google(self):
        os.environ["GOOGLE_API_KEY"] = "AI-de-mentira"
        os.environ["ANTHROPIC_API_KEY"] = "sk-de-mentira"
        os.environ["GROQ_API_KEY"] = "gsk-de-mentira"
        self.assertEqual(self.selector.motores_nube(), ["anthropic", "groq", "google"])

    def test_dos_selectores_no_se_pisan(self):
        # mente/cerebro.py y personal/entender.py, cada uno con su variable.
        otro = motores.SelectorDeMotor(variable="OTRA_LLM", prefijo="OTRA")
        os.environ["MIA_LLM"] = "ollama"
        self.assertEqual(self.selector.proveedor(), "ollama")
        self.assertEqual(otro.proveedor(), "")


if __name__ == "__main__":
    unittest.main()
