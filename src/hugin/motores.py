"""Selección de motor LLM: una sola vez, para `mente/cerebro.py` y
`personal/entender.py`.

Primer paso de la fusión mente/+personal/ (ver `docs/adr/` para el resto del
plan): ambos ficheros tenían el mismo `proveedor()`/`modelo()`/`ollama()`
byte a byte salvo el prefijo de la variable de entorno
(`GJALLARHORN_LLM`/`MIDGAROR_LLM`) y si llaman o no a `ajustes.leer()`
—`mente/cerebro.py` sí, porque es lo que lee el `.env` del negocio;
`personal/entender.py` no, porque el bot personal no tiene ese concepto—.
Todo lo demás —los cinco motores (`anthropic`, `groq`, `google`, `ollama`,
`auto`), el orden de intento de `auto`, los modelos por defecto— es una
decisión de producto, no de negocio ni de persona, así que vive aquí y
ninguno de los dos módulos lo repite.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SelectorDeMotor:
    """Un selector por variable de entorno: `GJALLARHORN_LLM` o `MIDGAROR_LLM`.

    `leer_ajustes`: si `proveedor()` tiene que cargar el `.env` antes de
    mirar el entorno (lo hace `guardado/ajustes.py`). El bot de negocio lo
    necesita; el personal ya lo tiene cargado por otro lado y llamarlo aquí
    también duplicaría trabajo sin cambiar nada.
    """

    variable: str                    # "GJALLARHORN_LLM" o "MIDGAROR_LLM"
    prefijo: str                     # "GJALLARHORN" o "MIDGAROR" — para _OLLAMA
    leer_ajustes: bool = False
    modelo_por_defecto: str = "claude-opus-5"
    modelo_local_por_defecto: str = "qwen3:4b-instruct-2507"
    modelo_groq_por_defecto: str = "llama-3.3-70b-versatile"
    modelo_google_por_defecto: str = "gemini-2.5-flash"
    ollama_por_defecto: str = "http://127.0.0.1:11434"

    def _var(self, sufijo: str) -> str:
        return f"{self.variable}{sufijo}"

    def proveedor(self) -> str:
        """«anthropic», «ollama», «groq», «google», «auto» o «» si no hay ninguno.

        Sin la variable puesta: Claude si hay clave, nada si no la hay. Es
        el mismo criterio en los dos bots, y por eso quien no la tenía
        puesta no tiene que tocar nada al fusionarse esto.
        """
        if self.leer_ajustes:
            from hugin.guardado import ajustes
            ajustes.leer()
        elegido = os.environ.get(self.variable, "").strip().lower()
        if elegido in ("no", "off", "ninguno", "0"):
            return ""
        if elegido == "auto":
            return "auto"
        if elegido in ("ollama", "local"):
            return "ollama"
        if elegido in ("groq",):
            return "groq" if os.environ.get("GROQ_API_KEY", "").strip() else ""
        if elegido in ("google", "gemini"):
            return "google" if os.environ.get("GOOGLE_API_KEY", "").strip() else ""
        return "anthropic" if os.environ.get("ANTHROPIC_API_KEY", "").strip() else ""

    def configurado(self) -> bool:
        return bool(self.proveedor())

    def modelo(self) -> str:
        propio = os.environ.get(self._var("_MODELO"), "").strip()
        if propio:
            return propio
        return {
            "ollama": self.modelo_local_por_defecto,
            "groq": self.modelo_groq_por_defecto,
            "google": self.modelo_google_por_defecto,
        }.get(self.proveedor(), self.modelo_por_defecto)

    def ollama(self) -> str:
        return os.environ.get(f"{self.prefijo}_OLLAMA", "").strip() or self.ollama_por_defecto

    def motores_nube(self) -> list[str]:
        """Los motores en la nube con clave puesta, en el orden en que se prueban.

        Para el modo «auto»: Claude, Groq, Google, en ese orden — el mismo
        en el que `proveedor()` cae cuando no se elige ninguno explícito.
        """
        candidatos = (("anthropic", "ANTHROPIC_API_KEY"),
                      ("groq", "GROQ_API_KEY"),
                      ("google", "GOOGLE_API_KEY"))
        return [motor for motor, var in candidatos if os.environ.get(var, "").strip()]
