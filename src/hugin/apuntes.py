"""Lo que pasa en el dia de un inquilino: `tele 3h`, `deporte`, `agua 1.5l`.

Viene del ADR-012 de midgaror, y se muda aqui entero con sus reglas (ADR-024).
Da igual la clase de cosa que se apunte; lo que cambia es su valor y su unidad.

    {"fecha": "2026-09-08", "que": "tele", "valor": 3, "unidad": "h", "hora": "22:10"}

Tres reglas que no son detalle:

- **Valor ausente = «hecho»** (el si/no de siempre); `valor: 0`, no hecho.
- **Varios apuntes del mismo dia se suman.** Dos ratos de tele son dos apuntes,
  no uno que corregir. Se guarda una lista que solo crece por el final: nunca
  se reescribe un dia entero. La suma se hace al leer.
- **La direccion la pone el objetivo, no una etiqueta.** `ejercicio` es «al
  menos 3 h/semana», `tele` es «como mucho 7 h/semana». Aqui no se clasifica
  nada como bueno o malo: se compara con el objetivo que puso su dueno.

Los totales, las medias y el «llevas 5 de 7 h» **no se guardan**: son informes,
se calculan al leer. En disco (o en la tabla) solo hay apuntes.

## Por que este modulo se puede mudar y los otros tres todavia no

`tareas`, `agenda` y `habitos` sacan la fecha del propio texto
(«medico manana a las 10») con el parser del diario, que resuelve **hacia
atras** cuando se le pide: «el lunes» es el lunes que paso, porque un habito se
apunta despues de hacerlo. Y `hugin/mente/fechas.py` resuelve **solo hacia
delante** a proposito, porque nadie reserva cita para el martes pasado. Fundir
los dos es una decision pendiente.

Los apuntes no tienen ese problema: solo preguntan que dia es hoy.

## Donde se guarda

Lo dice el inquilino. Con `base` en su `inquilino.toml`, en su tabla; sin ella,
en ficheros dentro de su carpeta. La separacion entre inquilinos no es un
filtro que se pueda olvidar: son carpetas y bases distintas.
"""

import os
import re
from datetime import date, datetime, timedelta

from hugin.guardado import almacen
from hugin.mente import fechas

VERSION = 1
FICHERO = "apuntes.json"
FICHERO_OBJETIVOS = "objetivos.json"

# Con acentos y ñ: `normalizar_que` ya ha pasado a minusculas antes de llegar
# aqui. Sin esto, «café», «meditación» o «entrenamiento físico» se rechazaban,
# y son justo la clase de cosa que se apunta a diario escribiendo en espanol.
NOMBRE_RE = re.compile(r"^[a-z0-9áéíóúüñ][a-z0-9áéíóúüñ _-]{0,40}$")
TIPOS_OBJETIVO = ("al_menos", "como_mucho")
PERIODOS = ("dia", "semana")


def _en_postgres(inq) -> bool:
    """Si los apuntes de este inquilino viven en una tabla o en un fichero.

    Manda su `base`; si no la tiene, vale la variable de entorno, que es como
    corre el bot hoy mientras nadie tenga todavia su `inquilino.toml`.
    """
    from hugin.guardado import postgres as _p
    return bool(getattr(inq, "base", None)) or bool(os.environ.get(_p.VARIABLE, "").strip())


def _ruta(inq, nombre: str):
    if inq is None:
        raise ValueError("no se de quien son estos apuntes: falta el inquilino")
    return inq.ruta / nombre


def normalizar_que(que: str) -> str:
    """Minusculas y sin espacios de sobra. «Ver la Tele» y «ver la tele» son lo mismo."""
    limpio = " ".join(que.strip().lower().split())
    if not NOMBRE_RE.match(limpio):
        raise ValueError(f"nombre no válido: {que!r} (letras, números, espacio, - o _)")
    return limpio


def normalizar_fecha(fecha) -> str:
    """Una fecha en AAAA-MM-DD, o hoy.

    Aqui NO se interpreta lenguaje natural a proposito: "el lunes" significa
    cosas distintas para un apunte y para una cita, y esa decision es del
    parser que corresponda, no de este modulo.
    """
    if fecha is None:
        return fechas.hoy()
    try:
        return datetime.strptime(str(fecha), "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise ValueError(f"fecha no válida: {fecha!r} (AAAA-MM-DD)") from None


def _numero(valor):
    """Un valor es un numero: entero si puede, si no float."""
    try:
        n = float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError(f"valor no válido: {valor!r} (un número)") from None
    return int(n) if n == int(n) else n


def _entero_si_puede(n):
    """5.0 se ensena como 5, 1.5 como 1.5. Solo afecta a como se ve."""
    return int(n) if n == int(n) else n


# ---- apuntes ---------------------------------------------------------------


def cargar(inq=None) -> list[dict]:
    if _en_postgres(inq):
        from hugin.guardado import postgres
        return postgres.cargar_apuntes(inq)
    return almacen.cargar(_ruta(inq, FICHERO), VERSION, [])


def guardar(apuntes: list[dict], inq=None) -> None:
    if _en_postgres(inq):
        from hugin.guardado import postgres
        postgres.guardar_apuntes(apuntes, inq)
        return
    almacen.guardar(_ruta(inq, FICHERO), apuntes, VERSION)


def apuntar(que: str, valor=None, unidad: str | None = None,
            fecha: str | None = None, hora: str | None = None, inq=None) -> dict:
    """Anade un apunte y lo devuelve. No suma ni pisa: solo anade al final.

    `valor` None se guarda como «hecho» (no aparece la clave). Un numero, tal
    cual. La suma con lo que ya haya del dia se hace al leer, no aqui.
    """
    que = normalizar_que(que)
    fecha = normalizar_fecha(fecha)
    apunte = {"fecha": fecha, "que": que}
    if valor is not None:
        apunte["valor"] = _numero(valor)
    if unidad:
        apunte["unidad"] = unidad.strip()
    if hora:
        apunte["hora"] = hora
    apuntes = cargar(inq)
    apuntes.append(apunte)
    guardar(apuntes, inq)
    return apunte


def del_dia(fecha: str | None = None, inq=None) -> list[dict]:
    fecha = normalizar_fecha(fecha)
    return [a for a in cargar(inq) if a["fecha"] == fecha]


def total(que: str, fecha: str | None = None, inq=None):
    """Cuanto suma un `que` en un dia. Cuenta los «hechos» como 1 cada uno."""
    que = normalizar_que(que)
    suma = 0
    for a in del_dia(fecha, inq):
        if a["que"] == que:
            suma += a.get("valor", 1)
    return _entero_si_puede(suma)


# ---- objetivos -------------------------------------------------------------


def cargar_objetivos(inq=None) -> list[dict]:
    # Los objetivos se quedan SIEMPRE en fichero, tambien con Postgres: son
    # cuatro lineas que escribe y relee su dueno, no un registro que crezca
    # (ADR-024, la raya entre tablas y ficheros).
    return almacen.cargar(_ruta(inq, FICHERO_OBJETIVOS), VERSION, [])


def guardar_objetivos(objetivos: list[dict], inq=None) -> None:
    almacen.guardar(_ruta(inq, FICHERO_OBJETIVOS), objetivos, VERSION)


def fijar_objetivo(que: str, tipo: str, valor, periodo: str = "semana",
                   unidad: str | None = None, inq=None) -> dict:
    """«al_menos 3 h/semana» o «como_mucho 7 h/semana». Uno por `que`: se pisa."""
    que = normalizar_que(que)
    if tipo not in TIPOS_OBJETIVO:
        raise ValueError(f"tipo de objetivo no válido: {tipo!r} ({' o '.join(TIPOS_OBJETIVO)})")
    if periodo not in PERIODOS:
        raise ValueError(f"periodo no válido: {periodo!r} ({' o '.join(PERIODOS)})")
    objetivo = {"que": que, "tipo": tipo, "valor": _numero(valor), "periodo": periodo}
    if unidad:
        objetivo["unidad"] = unidad.strip()
    objetivos = [o for o in cargar_objetivos(inq) if o["que"] != que]
    objetivos.append(objetivo)
    guardar_objetivos(objetivos, inq)
    return objetivo


def objetivo_de(que: str, inq=None) -> dict | None:
    que = normalizar_que(que)
    return next((o for o in cargar_objetivos(inq) if o["que"] == que), None)


def cumple(objetivo: dict, acumulado) -> bool:
    """Si un acumulado cumple el objetivo. `al_menos` >=, `como_mucho` <=."""
    if objetivo["tipo"] == "al_menos":
        return acumulado >= objetivo["valor"]
    return acumulado <= objetivo["valor"]


# ---- informes --------------------------------------------------------------
#
# Nada de esto se guarda (ADR-012, apartado 6): se calcula al leer. Devuelven
# datos, no texto: el que los pinta es la puerta, no este modulo.


def _entre(desde: str, hasta: str, inq=None) -> list[dict]:
    """Los apuntes de un tramo de fechas, extremos incluidos."""
    return [a for a in cargar(inq) if desde <= a["fecha"] <= hasta]


def _lineas(apuntes: list[dict], periodo: str, inq=None) -> list[dict]:
    """Una linea por `que`: total del tramo y, si lo hay, su objetivo.

    Un objetivo del periodo sin ningun apunte tambien sale, con total 0: el
    «llevas 0 de 3 h» es justo lo que hay que ver, no un hueco en la lista.
    """
    totales = {}
    unidades = {}
    for a in apuntes:
        que = a["que"]
        totales[que] = totales.get(que, 0) + a.get("valor", 1)
        if "unidad" in a and que not in unidades:
            unidades[que] = a["unidad"]

    objetivos = {o["que"]: o for o in cargar_objetivos(inq) if o["periodo"] == periodo}
    for que in objetivos:
        totales.setdefault(que, 0)

    lineas = []
    for que in sorted(totales):
        suma = _entero_si_puede(totales[que])
        linea = {"que": que, "total": suma}
        unidad = unidades.get(que) or objetivos.get(que, {}).get("unidad")
        if unidad:
            linea["unidad"] = unidad
        objetivo = objetivos.get(que)
        if objetivo is not None:
            linea["objetivo"] = objetivo
            linea["cumple"] = cumple(objetivo, suma)
        lineas.append(linea)
    return lineas


def resumen_dia(fecha: str | None = None, inq=None) -> dict:
    """Lo apuntado en un dia, agrupado por `que` y contra los objetivos diarios."""
    fecha = normalizar_fecha(fecha)
    return {"fecha": fecha, "lineas": _lineas(_entre(fecha, fecha, inq), "dia", inq)}


def semana_de(fecha: str | None = None) -> tuple[str, str]:
    """(lunes, domingo) de la semana en la que cae `fecha`.

    La semana es la natural, de lunes a domingo, y no los siete dias anteriores
    a hoy: un objetivo de «3 h/semana» se cuenta sobre una semana del
    calendario, que es la que uno tiene en la cabeza al mirarlo un miercoles.
    """
    dia = date.fromisoformat(normalizar_fecha(fecha))
    lunes = dia - timedelta(days=dia.weekday())
    return lunes.isoformat(), (lunes + timedelta(days=6)).isoformat()


def resumen_semana(fecha: str | None = None, inq=None) -> dict:
    """Lo mismo que `resumen_dia` sobre la semana natural de `fecha`."""
    desde, hasta = semana_de(fecha)
    return {"desde": desde, "hasta": hasta,
            "lineas": _lineas(_entre(desde, hasta, inq), "semana", inq)}
