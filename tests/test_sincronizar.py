"""Pruebas de hugin/guardado/sincronizar.py.

Portadas de las de midgaror (diario/tests/test_sincronizar.py), con un
cambio: aquí la raíz del repo se DESCUBRE con `git rev-parse
--show-toplevel` en vez de ser una global que la prueba pisa, así que no
hace falta guardar ni restaurar `S.RAIZ`.

Son las únicas pruebas de este repo que usan git de verdad: montan un
remoto local con `git init --bare` y clonan, así que prueban el push, el
rechazo y el rebase sin salir a internet. Por eso tardan segundos y no
milisegundos como el resto.

El entorno de git se aísla entero (GIT_CONFIG_GLOBAL, identidad, sin
prompts): sin eso, la configuración de la máquina haría fallar los
commits aquí y en CI.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import entorno  # noqa: F401

from hugin.guardado import sincronizar as S

ENTORNO = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_AUTHOR_NAME": "prueba", "GIT_AUTHOR_EMAIL": "prueba@ejemplo",
    "GIT_COMMITTER_NAME": "prueba", "GIT_COMMITTER_EMAIL": "prueba@ejemplo",
}


@unittest.skipIf(shutil.which("git") is None, "no hay git en esta máquina")
class CasoGit(unittest.TestCase):
    """Un remoto bare, un clon que hace de copia del bot, y otro para divergir."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)

        for clave, valor in ENTORNO.items():
            anterior = os.environ.get(clave)
            os.environ[clave] = valor
            self.addCleanup(
                lambda c=clave, a=anterior: os.environ.__setitem__(c, a)
                if a is not None else os.environ.pop(c, None))

        self.origen = base / "origen.git"
        self._git_en(base, "init", "-q", "--bare", "-b", "main", str(self.origen))
        self._git_en(base, "clone", "-q", str(self.origen), "inquilino")
        self.repo = base / "inquilino"
        self.fichero = self.repo / "datos" / "apuntes.json"
        self.fichero.parent.mkdir(parents=True)
        self.fichero.write_text('{"linea base": true}\n', encoding="utf-8")
        self._git_en(self.repo, "add", "-A")
        self._git_en(self.repo, "commit", "-qm", "base")
        self._git_en(self.repo, "push", "-qu", "origin", "main")

    def _git_en(self, cwd: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)

    def _diverge(self, texto: str) -> None:
        base = Path(self._tmp.name)
        otro = base / "otro"
        if not otro.exists():
            self._git_en(base, "clone", "-q", str(self.origen), "otro")
        (otro / "datos" / "apuntes.json").write_text('{"linea base": true}\n' + texto, encoding="utf-8")
        self._git_en(otro, "add", "-A")
        self._git_en(otro, "commit", "-qm", "desde otra copia")
        self._git_en(otro, "push", "-q")

    def _rama(self) -> str:
        return self._git_en(self.repo, "branch", "--show-current").stdout.strip()

    def _en_el_remoto(self) -> str:
        return self._git_en(self.origen, "show", "main:datos/apuntes.json").stdout


class TestCaminoNormal(CasoGit):
    def test_escribe_commitea_y_sube(self):
        self.fichero.write_text('{"linea base": true}\n"agua"\n', encoding="utf-8")
        self.assertEqual(S.sincronizar(self.fichero), "escrito y subido a GitHub")
        self.assertIn("agua", self._en_el_remoto())

    def test_solo_sube_el_fichero_que_se_le_pasa(self):
        (self.repo / "trabajo_a_medias.py").write_text("a medias\n", encoding="utf-8")
        self.fichero.write_text('{"linea base": true}\n"agua"\n', encoding="utf-8")
        S.sincronizar(self.fichero)
        pendiente = self._git_en(self.repo, "status", "--short").stdout
        self.assertIn("trabajo_a_medias.py", pendiente)
        self.assertNotIn("trabajo_a_medias", self._git_en(self.repo, "show", "--stat", "HEAD").stdout)

    def test_sin_cambios_no_commitea(self):
        antes = self._git_en(self.repo, "rev-parse", "HEAD").stdout
        self.assertEqual(S.sincronizar(self.fichero), "escrito (sin cambios que subir)")
        self.assertEqual(self._git_en(self.repo, "rev-parse", "HEAD").stdout, antes)

    def test_un_fichero_fuera_de_cualquier_repo_no_toca_git(self):
        # Distinto del original de midgaror: aquí no hay una RAIZ fija que
        # comparar, así que "fuera del repo" es "no hay ningún repo".
        base = Path(self._tmp.name)
        suelto = base / "sin_repo" / "apuntes.json"
        suelto.parent.mkdir()
        suelto.write_text("[]\n", encoding="utf-8")
        llamadas = []
        real = S._git
        S._git = lambda *a, **k: (llamadas.append(a), real(*a, **k))[1]
        self.addCleanup(lambda: setattr(S, "_git", real))
        self.assertIn("sin repo git", S.sincronizar(suelto))
        # rev-parse para descubrir la raíz sí se llama; add/commit/push no.
        self.assertFalse(any(a[1] in ("add", "commit", "push") for a in llamadas))


class TestDivergencia(CasoGit):
    def test_si_alguien_subio_antes_reordena_y_sube(self):
        # El remoto inserta DESPUÉS de la línea base y lo local ANTES: en
        # sitios distintos, así que el rebase se aplica solo (igual que el
        # original de midgaror con "línea base" en medio de dos añadidos).
        self._diverge('"otra cosa al final"\n')
        self.fichero.write_text('"un apunte arriba"\n{"linea base": true}\n', encoding="utf-8")
        self.assertEqual(S.sincronizar(self.fichero),
                          "escrito y subido a GitHub (tras reordenar sobre lo remoto)")
        self.assertIn("un apunte arriba", self._en_el_remoto())
        self.assertIn("otra cosa al final", self._en_el_remoto())

    def test_un_conflicto_no_deja_el_repo_a_medio_rebase(self):
        self._diverge('"linea base": true, "DESDE LA OTRA COPIA": true\n')
        self.fichero.write_text('"linea base": true, "APUNTE DE ALGUIEN": true\n', encoding="utf-8")
        respuesta = S.sincronizar(self.fichero)
        self.assertIn("conflicto", respuesta)
        self.assertEqual(self._rama(), "main")

    def test_tras_un_conflicto_sigue_funcionando(self):
        self._diverge('"linea base": true, "DESDE LA OTRA COPIA": true\n')
        self.fichero.write_text('"linea base": true, "APUNTE DE ALGUIEN": true\n', encoding="utf-8")
        S.sincronizar(self.fichero)
        self.assertEqual(self._rama(), "main")
        self.fichero.write_text(
            self.fichero.read_text(encoding="utf-8") + '"segundo": true\n', encoding="utf-8")
        segunda = S.sincronizar(self.fichero)
        self.assertNotIn("<remote>", segunda, "el aviso críptico de git no debe llegar al usuario")


class TestNuncaRevienta(CasoGit):
    def test_ni_un_camino_levanta_excepcion(self):
        for preparar, nombre in (
            (lambda: None, "camino normal"),
            (lambda: self.fichero.unlink(), "fichero borrado"),
        ):
            with self.subTest(nombre):
                preparar()
                self.assertIsInstance(S.sincronizar(self.fichero), str)


if __name__ == "__main__":
    unittest.main()
