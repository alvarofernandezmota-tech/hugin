"""Lo que hay que avisar sin que nadie pregunte: las citas que vienen.

Portado de `diario/recordatorios.py` de midgaror (ADR-020), a continuación
de la fase 4/5 del ADR-024: cierra el hueco que dejó
`hugin/personal/citas.py` al mudarse — una cita apuntada con `/cita` iba a
la carpeta del inquilino, pero `recordatorios` seguía mirando el
`agenda.json` de midgaror, así que no la veía nunca. Documentado y sujeto
con una prueba (`telegram/tests/test_recordatorios.py`,
`TestElHuecoConElCerebro`) antes de arreglarlo aquí.

Un bot solo habla cuando le hablas, hasta esto. Una agenda que solo
contesta a `/agenda` no te salva de olvidarte de una cita: te la enseña
justo cuando ya te habías acordado tú.

Aquí se decide **qué** avisar y **cuándo**, sin saber nada de Telegram: se
devuelven datos. Quien los manda es el canal (`handlers/recordatorios.py`).

## Por qué hay que guardar lo ya avisado

El bot mira cada pocos minutos. Sin memoria de lo dicho, una cita dentro de
la ventana se avisaría en cada vuelta, una y otra vez, hasta que pasara la
hora. `avisados.json` guarda la clave de cada aviso dado, en la carpeta del
inquilino — es un apéndice de sus citas, no un modelo nuevo, igual que en
midgaror.

La clave es **«fecha#id», no el id a secas**: los ids de `citas.json`
empiezan en 1 para cada fichero y una cita cancelada libera su hueco, así
que el id 3 de hoy y el 3 de la semana que viene pueden ser cosas
distintas. Guardar solo el número haría que la segunda no se avisara
nunca, y ese es el fallo que no se ve: no salta nada, simplemente no llega
el aviso.

La lista se limpia sola de lo anterior a hoy. Sin eso crece para siempre y
un día pesa más que la agenda.

## Lo que NO se avisa, a propósito

- **Las citas sin hora** (las de todo el día). No hay un momento del que
  avisar; hacerlo a medianoche sería ruido a una hora en la que no sirve.
- **Lo que ya pasó.** Si el bot ha estado parado tres horas, al arrancar no
  vomita los avisos de las citas que ya empezaron: eso no es un
  recordatorio, es una lista de cosas a las que ya llegas tarde.

Esto es siempre fichero, con Postgres o sin él: es una memoria pequeña de
lo ya dicho, no un registro del inquilino, y midgaror nunca la llevó a
tabla tampoco.
"""

from datetime import datetime, timedelta
from pathlib import Path

from hugin.guardado import almacen
from hugin.personal import citas, fechas

# Cuánto antes se avisa de una cita. Media hora es lo que suele hacer falta
# para salir de casa; se toca aquí y en un solo sitio.
VENTANA_MINUTOS = 30

VERSION = 1
FICHERO = "avisados.json"
MIGRACIONES = {}


def _ruta(inq) -> Path:
    if inq is None:
        raise ValueError("no sé de quién son estos avisos: falta el inquilino")
    return inq.ruta / FICHERO


def cargar_avisados(inq=None) -> list[str]:
    return almacen.cargar(_ruta(inq), VERSION, vacio=[], migraciones=MIGRACIONES)


def guardar_avisados(claves: list[str], inq=None) -> None:
    almacen.guardar(_ruta(inq), claves, VERSION)


def clave(cita: dict) -> str:
    """«2026-09-18#3». Ver el porqué de la fecha delante en la cabecera."""
    return f"{cita['fecha']}#{cita['id']}"


def _momento(cita: dict) -> datetime | None:
    """El instante exacto de la cita, en el reloj del diario. None si no tiene hora."""
    if not cita.get("hora"):
        return None
    return datetime.fromisoformat(f"{cita['fecha']}T{cita['hora']}").replace(
        tzinfo=fechas.ahora().tzinfo)


def pendientes(inq=None, ahora: datetime | None = None) -> list[dict]:
    """Las citas que toca avisar ahora mismo, sin avisar dos veces la misma.

    No escribe nada: decir que se ha avisado es cosa de `anotar()`, y va
    aparte a propósito — si el mensaje a Telegram falla, la cita sigue
    pendiente y se reintenta a la vuelta siguiente en vez de darse por
    avisada sin que nadie la haya visto.
    """
    ahora = ahora or fechas.ahora()
    ya = set(cargar_avisados(inq))
    limite = ahora + timedelta(minutes=VENTANA_MINUTOS)

    toca = []
    for cita in citas.activas(citas.cargar(inq)):
        momento = _momento(cita)
        if momento is None:               # todo el día: no hay de qué avisar
            continue
        if not ahora <= momento <= limite:  # ya pasó, o queda mucho
            continue
        if clave(cita) in ya:
            continue
        toca.append(cita)
    return sorted(toca, key=_momento)


def anotar(citas_avisadas: list[dict], inq=None, ahora: datetime | None = None) -> None:
    """Deja constancia de que estas citas ya se avisaron, y tira lo viejo."""
    ahora = ahora or fechas.ahora()
    hoy = ahora.date().isoformat()
    # Lo de antes de hoy ya no puede repetirse: su cita quedó atrás.
    vivos = [c for c in cargar_avisados(inq) if c.split("#")[0] >= hoy]
    guardar_avisados(sorted(set(vivos) | {clave(c) for c in citas_avisadas}), inq)
