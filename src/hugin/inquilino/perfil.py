"""Un inquilino: alguien a quien se atiende. Una persona o una empresa.

Hasta el ADR-024 esto se llamaba «negocio» y daba por supuesto que enfrente
había una peluquería: saludo, voz, tarifas y FAQ. Pero el mismo cerebro
atiende el diario de una persona, y una persona no tiene tarifas y sí tiene
hábitos. Seguir llamándolo negocio obligaba a que todos tuvieran los mismos
ficheros, o a llenar el código de «si es una persona…».

Un inquilino **es una carpeta**, igual que antes lo era un negocio: darlo de
alta sigue siendo copiarla. Lo que cambia es que la carpeta dice qué sabe
hacer ese inquilino en vez de que lo suponga el programa.

    inquilinos/
      alvaro/
        inquilino.toml     quien es, que tiene activado, y cual es su base
        diario/            su prosa, en Markdown
      peluqueria/
        inquilino.toml
        tarifas.md         los edita su dueña, sin llamar a nadie
        faq.md

## Las capacidades, y por que no un «tipo»

Se podria haber puesto `tipo = "persona"` o `"negocio"` y que cada tipo
trajera lo suyo. No sirve: un autonomo quiere agenda y tarifas **y** tareas,
y con dos tipos cerrados eso no cabe en ninguno. Con capacidades sueltas, lo
que cada uno tiene activado es una lista y no hay que inventar un tipo nuevo
por cada combinacion.

## De donde sale la base de datos

Del inquilino, no del `.env` del servicio. Hoy `DIARIO_DATABASE_URL` esta
clavada en el entorno del bot, y eso solo sirve mientras haya uno: el mismo
binario no puede atender a dos sin reiniciarse con otra variable.

Una base por inquilino, elegida por su fichero (ADR-024): leer lo de otro
pasa de «que nadie olvide un WHERE» a ser imposible.

Sin `base` en el TOML se usa la del entorno, que es lo que hay hoy. Por eso
esto no rompe nada: el bot actual sigue igual hasta que se le de su fichero.
"""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

VARIABLE = "INQUILINOS"
FICHERO = "inquilino.toml"

# Lo que un inquilino puede tener activado. La lista es cerrada a proposito:
# una capacidad mal escrita en el TOML es un fichero que alguien edito a mano,
# y es mejor decirlo que atender a medias sin que se note.
CAPACIDADES = frozenset({
    "diario",    # entradas en prosa, en Markdown
    "tareas",
    "habitos",
    "apuntes",
    "agenda",    # citas: las tuyas o las de tus clientes
    "tarifas",   # una tabla de precios que edita su dueño
    "faq",
})


def carpeta() -> Path:
    """Donde viven los inquilinos. Por defecto aqui dentro; se puede mover.

    Mismo motivo que en `negocio.carpeta_negocios()`: ahi dentro hay nombres,
    precios y el diario de alguien, y este repo es publico.

        export INQUILINOS=~/inquilinos

    Desde el directorio de trabajo y NUNCA desde `__file__`: esta libreria
    vive dentro de la aplicacion que la usa, y esta carpeta es de la
    aplicacion.
    """
    valor = os.environ.get(VARIABLE, "").strip()
    if valor:
        return Path(valor).expanduser().resolve()
    return Path.cwd() / "inquilinos"


@dataclass(frozen=True)
class Inquilino:
    """Quien es, que sabe hacer y donde estan sus datos."""

    nombre: str
    ruta: Path
    capacidades: frozenset[str]
    base: str | None

    def puede(self, capacidad: str) -> bool:
        """Si tiene esa capacidad activada.

        Preguntar por una que no existe es un error de programa, no un «no»:
        `inq.puede("tareaz")` devolviendo False callaria el fallo y la funcion
        que lo pregunta no se ejecutaria nunca sin que nadie se entere.
        """
        if capacidad not in CAPACIDADES:
            raise ValueError(
                f"capacidad desconocida: {capacidad!r} "
                f"(las que hay: {', '.join(sorted(CAPACIDADES))})")
        return capacidad in self.capacidades


def _leer(ruta: Path) -> dict:
    fichero = ruta / FICHERO
    if not fichero.exists():
        return {}
    try:
        return tomllib.loads(fichero.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        # Igual que con un JSON roto: se dice que fichero es y que le pasa,
        # porque lo ha escrito una persona a mano y va a tener que arreglarlo.
        raise ValueError(f"{fichero} no es un TOML valido: {error}") from error


def cargar(cual: str | Path) -> Inquilino:
    """El inquilino por su nombre de carpeta, o por una ruta.

    Sin `inquilino.toml` funciona igual: una carpeta con un `tarifas.md`
    dentro es un inquilino con la capacidad de tarifas y nada mas. Es lo
    mismo que hace `negocio.cargar()`, y por el mismo motivo: que dar de alta
    a alguien no exija escribir configuracion antes de tener nada.
    """
    ruta = Path(cual)
    if not ruta.is_absolute() and not ruta.exists():
        ruta = carpeta() / cual
    if not ruta.is_dir():
        disponibles = ", ".join(listar()) or "ninguno"
        raise ValueError(f"no encuentro al inquilino {cual!r} (hay: {disponibles})")

    config = _leer(ruta)
    declaradas = config.get("capacidades")
    if declaradas is None:
        capacidades = _deducidas(ruta)
    else:
        capacidades = frozenset(declaradas)
        desconocidas = capacidades - CAPACIDADES
        if desconocidas:
            raise ValueError(
                f"{ruta / FICHERO}: capacidad(es) que no existen: "
                f"{', '.join(sorted(desconocidas))}")

    return Inquilino(
        nombre=config.get("nombre") or ruta.name,
        ruta=ruta,
        capacidades=capacidades,
        base=(config.get("base") or "").strip() or None,
    )


def _deducidas(ruta: Path) -> frozenset[str]:
    """Que sabe hacer un inquilino sin `inquilino.toml`: lo que tenga escrito."""
    tiene = set()
    if (ruta / "tarifas.md").exists():
        tiene.add("tarifas")
    if (ruta / "faq.md").exists():
        tiene.add("faq")
    if (ruta / "diario").is_dir():
        tiene.add("diario")
    return frozenset(tiene)


def listar() -> list[str]:
    """Los inquilinos dados de alta, por nombre de carpeta."""
    base = carpeta()
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir() and not p.name.startswith("."))
