"""Comprueba que el repo no se ha desconectado de si mismo.

    make auditar

No es un sustituto de las pruebas: las pruebas dicen si el codigo hace lo
que promete. Esto dice si los FICHEROS QUE DESCRIBEN EL PROYECTO —el
empaquetado, el CI— siguen de acuerdo con lo que hay en disco. Nacio el
2026-09-18 despues de encontrar, auditando a mano, dos casos reales de esto
mismo en un rato: `hugin/personal/` llevaba semanas sin estar en la lista
de paquetes de `pyproject.toml` (invisible con `pip install -e .`, que
expone el arbol entero da igual lo que diga la lista, pero una instalacion
NO editable se habria quedado sin el modulo mas usado del cerebro), y el
unico workflow de CI vivia en `telegram/.github/workflows/`, no en la raiz,
asi que GitHub nunca lo leyo — ni un dia, con o sin el bloqueo de cobro de
la cuenta.

Las dos son del mismo tipo: nada corre en rojo, nada avisa, y el fichero
que se supone que describe la verdad simplemente deja de decirla. Cada
comprobacion de aqui existe porque alguna vez fue verdad a medias.
"""

import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def paquetes_completos() -> list[str]:
    """Toda carpeta de hugin/ con __init__.py tiene que estar en pyproject.toml.

    `pip install -e .` no lo habria dicho nunca: el modo editable expone el
    arbol de codigo entero, siga o no la lista declarada. El problema solo
    se ve en una instalacion NO editable (una imagen de contenedor, un
    `pip install .` de verdad) — y para entonces ya esta en produccion.
    """
    config = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    find = config.get("tool", {}).get("setuptools", {}).get("packages", {}).get("find", {})
    where = find.get("where", ["."])
    include = find.get("include", ["*"])

    raiz_paquetes = RAIZ / where[0]
    base = raiz_paquetes / "hugin"

    reales = set()
    for init in base.rglob("__init__.py"):
        carpeta = init.parent
        punto = ".".join(carpeta.relative_to(raiz_paquetes).parts)
        reales.add(punto)

    from fnmatch import fnmatch
    no_cubiertos = sorted(
        p for p in reales if not any(fnmatch(p, patron) for patron in include)
    )
    if not no_cubiertos:
        return []
    return [
        f"pyproject.toml: [tool.setuptools.packages.find] no cubre: {', '.join(no_cubiertos)}",
        "  (tiene __init__.py en disco pero ningun patron de 'include' lo alcanza —",
        "   invisible con pip install -e ., reventaria en una instalacion normal)",
    ]


def workflows_en_su_sitio() -> list[str]:
    """GitHub SOLO lee .github/workflows/ en la raiz del repo.

    Un workflow en cualquier otra carpeta (por ejemplo telegram/.github/,
    herencia de cuando telegram/ era un repo aparte) no es que corra mal:
    no corre nunca, y no lo dice nadie. `find` no distingue eso de uno que
    si esta en la raiz; hay que mirar la ruta a mano.
    """
    huerfanos = sorted(
        p for p in RAIZ.rglob(".github/workflows/*.y*ml")
        if p.parent.parent.parent != RAIZ
    )
    if not huerfanos:
        return []
    listados = [str(p.relative_to(RAIZ)) for p in huerfanos]
    return [
        "workflow(s) de GitHub Actions fuera de la raiz del repo (GitHub no los lee, nunca):",
        *(f"  {p}" for p in listados),
    ]


COMPROBACIONES = (
    ("paquetes declarados", paquetes_completos),
    ("workflows en la raiz", workflows_en_su_sitio),
)


def main() -> int:
    fallos = 0
    for nombre, comprobar in COMPROBACIONES:
        problemas = comprobar()
        if problemas:
            fallos += 1
            print(f"❌ {nombre}")
            for linea in problemas:
                print(f"   {linea}")
        else:
            print(f"✅ {nombre}")
    print()
    if fallos:
        print(f"❌ {fallos} comprobacion(es) estructural(es) en rojo.")
        return 1
    print("✅ El repo esta de acuerdo consigo mismo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
