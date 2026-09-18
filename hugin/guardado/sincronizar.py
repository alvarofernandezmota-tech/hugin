"""Sube al remoto lo que el bot escribe en el fichero de un inquilino.

Sin esto, lo que llega por un canal vive solo en el disco de Madre hasta
que alguien se acuerda de hacer commit. Con esto, el dato está al día en
GitHub en cuanto se manda el mensaje.

Portado de `diario/sincronizar.py` de midgaror (ADR-016), con una
diferencia: aquí NO hay una raíz fija. midgaror tenía un único repo de
datos y una sola `ubicacion.raiz()`; un inquilino puede tener el suyo en
cualquier sitio, así que la raíz se **descubre** con
`git rev-parse --show-toplevel` a partir del propio fichero, en vez de
suponerla.

Reglas que se respetan a propósito, heredadas del original:

- Solo se prepara el fichero que se acaba de escribir. Nunca `git add -A`:
  el repo puede tener trabajo a medias y no es de este código commitearlo.
- Nunca lanza una excepción hacia arriba. El dato ya está escrito en disco
  antes de llamar aquí, así que un fallo de red no puede perder nada; solo
  hay que contarlo.
- Todo lleva timeout. Un `git push` colgado dejaría al bot sin responder.

Si el fichero no está dentro de un repo git (un inquilino sin repo de
datos propio, o en pruebas), se dice y no se hace nada más: sincronizar es
una mejora, no un requisito para que `guardar()` funcione.
"""

import subprocess
from pathlib import Path

TIEMPO_LOCAL = 15
TIEMPO_RED = 90


def _git(raiz: Path, *args: str, timeout: int = TIEMPO_LOCAL):
    """Ejecuta git en `raiz`. Devuelve (código, salida)."""
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=raiz,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, f"git {args[0]} agotó el tiempo de espera"
    except FileNotFoundError:
        return 127, "git no está instalado"


def _raiz_de(ruta: Path) -> Path | None:
    """La raíz del repo que contiene `ruta`, o None si no hay ninguno.

    `ruta` puede no existir todavía (se sincroniza tras escribirla) o
    haber sido borrada entre medias: se pregunta desde el padre, que sí
    tiene que existir para que el fichero se haya podido escribir ahí.
    """
    padre = ruta.parent
    if not padre.is_dir():
        return None
    codigo, salida = _git(padre, "rev-parse", "--show-toplevel")
    if codigo != 0:
        return None
    return Path(salida)


def sincronizar(ruta: Path, mensaje: str | None = None) -> str:
    """Prepara, commitea y sube ese fichero. Devuelve un texto para el usuario.

    Sin `mensaje`, el commit lleva el nombre del fichero. Quien llama
    conoce mejor el contexto (qué inquilino, qué modelo) y debería pasar
    el suyo.
    """
    ruta = Path(ruta)
    raiz = _raiz_de(ruta)
    if raiz is None:
        return "escrito (sin repo git: no hay nada que subir)"

    try:
        rel = ruta.resolve().relative_to(raiz.resolve())
    except ValueError:
        return f"⚠️ {ruta} está fuera de su propio repo, no se sube"

    codigo, salida = _git(raiz, "add", "--", str(rel))
    if codigo != 0:
        return f"⚠️ escrito, pero git add falló: {salida}"

    codigo, _ = _git(raiz, "diff", "--cached", "--quiet", "--", str(rel))
    if codigo == 0:
        return "escrito (sin cambios que subir)"

    mensaje = mensaje or f"datos: {rel.name}"
    codigo, salida = _git(raiz, "commit", "-m", mensaje, "--", str(rel))
    if codigo != 0:
        return f"⚠️ escrito, pero el commit falló: {salida}"

    codigo, salida = _git(raiz, "push", timeout=TIEMPO_RED)
    if codigo == 0:
        return "escrito y subido a GitHub"

    # Rechazo típico: alguien más commiteó desde otro sitio. Se reintenta
    # una vez, reordenando encima de lo remoto. Una sola vez: si vuelve a
    # fallar, es otra cosa y hay que mirarla a mano.
    codigo_pull, salida_pull = _git(raiz, "pull", "--rebase", "--autostash", timeout=TIEMPO_RED)
    if codigo_pull != 0:
        return _abortar_rebase(raiz, salida_pull)

    codigo, salida = _git(raiz, "push", timeout=TIEMPO_RED)
    if codigo == 0:
        return "escrito y subido a GitHub (tras reordenar sobre lo remoto)"

    ultima = salida.splitlines()[-1] if salida else "push falló"
    return f"⚠️ commiteado en local, sin subir: {ultima}"


def _abortar_rebase(raiz: Path, salida_pull: str) -> str:
    """Deshace un rebase a medias y devuelve el aviso para quien pregunta.

    Sin esto, un rebase con conflicto deja el repositorio en un estado del
    que no sale solo: HEAD desacoplado, marcadores <<<<<<< dentro del
    fichero, y cada escritura siguiente commiteando ahí sin poder subir
    nunca. Reproducido en midgaror el 2026-09-05 con dos copias
    escribiendo el mismo día. `git rebase --abort` devuelve la rama a su
    sitio y conserva el commit local: no se pierde nada, solo queda sin
    subir hasta la siguiente escritura o hasta que alguien lo resuelva.
    """
    primera = salida_pull.splitlines()[0] if salida_pull else "pull falló"
    codigo, _ = _git(raiz, "rebase", "--abort")
    if codigo != 0:
        return f"⚠️ commiteado en local, sin subir: {primera}"
    return ("⚠️ apuntado y commiteado, pero NO subido: hay un conflicto con "
            "lo que hay en el remoto. El dato está a salvo en el commit "
            "local. Resuélvelo a mano con: git pull --rebase")
