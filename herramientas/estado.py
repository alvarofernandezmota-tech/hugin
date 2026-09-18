"""Mide las pruebas del cerebro y escribe el badge del README.

    make estado

El badge es `estado-pruebas.json`, un fichero commiteado que shields.io lee
para pintar «399 pasando · local 2026-09-18» en el README.

Dice **local** a proposito. Hoy no hay CI: este repo no tiene workflow en la
raiz, y aunque lo tuviera, un cobro rechazado bloquea Actions en toda la
cuenta desde el 2026-09-04 y los jobs salen en rojo sin llegar a coger
runner. Un badge que insinuara «CI: passing» estaria vendiendo una
verificacion automatica que no existe. Lo que hay es alguien que corrio la
suite en su maquina, este dia, y lo que promete el badge es exactamente eso.

Y no se escribe en verde a ciegas: si la suite esta en rojo, esto se niega.
"""

import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ESTADO = RAIZ / "estado-pruebas.json"

# El fichero que comprueba este mismo badge. Sus fallos no cuentan para
# decidir si la suite esta en rojo, y si no fuera asi esto no podria
# arrancar nunca: el badge esta desfasado -> test_estado falla -> `make
# estado` se niega a arreglarlo -> el badge sigue desfasado.
PROPIO = "test_estado."

CUENTA = re.compile(r"^Ran (\d+) tests?", re.MULTILINE)
# unittest lo escribe asi: «FAIL: test_x (modulo.Clase.test_x)». El nombre
# suelto de delante no dice de que fichero viene; el de dentro del parentesis
# si, y es el unico que permite distinguir un fallo propio de uno ajeno.
FALLO = re.compile(r"^(?:FAIL|ERROR): \S+ \((\S+)\)", re.MULTILINE)


def correr() -> tuple[int, list[str]]:
    """Corre la suite del cerebro. Devuelve (cuantas, fallos ajenos)."""
    hecho = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        cwd=RAIZ, capture_output=True, text=True)
    # unittest escribe su resumen en stderr, no en stdout.
    salida = hecho.stderr
    casado = CUENTA.search(salida)
    if not casado:
        print(salida, file=sys.stderr)
        raise SystemExit("no he podido leer cuantas pruebas corrieron")
    ajenos = [n for n in FALLO.findall(salida) if not n.startswith(PROPIO)]
    return int(casado.group(1)), ajenos


def main() -> int:
    cuantas, ajenos = correr()
    if ajenos:
        print(f"❌ {len(ajenos)} prueba(s) en rojo. No escribo un badge verde:")
        for nombre in ajenos:
            print(f"   {nombre}")
        print("   Arreglalo y vuelve a correr `make estado`.")
        return 1

    hoy = date.today().isoformat()
    ESTADO.write_text(json.dumps({
        "schemaVersion": 1,
        "label": "pruebas del cerebro",
        "message": f"{cuantas} pasando · local {hoy}",
        "color": "brightgreen",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{ESTADO.name}: {cuantas} pruebas, {hoy}")
    print("   Commitealo: el badge del README lee este fichero.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
