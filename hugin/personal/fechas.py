"""Interpreta fechas y horas escritas en español, en `Europe/Madrid`.

Reescritura de las reglas del parser de thea-ia, que se auditó el 2026-09-04
(`docs/ecosistema/auditoria-thea-ia.md`). De aquel se porta la idea, no el
código: acertaba lo relativo simple pero se comía el mes en «el 15 de
octubre», resolvía «pasado mañana» como si fuera «mañana», ignoraba las
franjas («por la tarde») y devolvía UTC pese a anunciar `Europe/Madrid`.

Solo biblioteca estándar. Nada de `dateutil` ni `pytz`: `zoneinfo` ya
resuelve la zona horaria y el resto son expresiones regulares.

Uso:

    >>> from datetime import datetime
    >>> ahora = datetime(2026, 9, 4, 20, 0)
    >>> interpretar("quedada mañana a las 10", ahora)
    ('2026-09-05', '10:00', 'quedada')
    >>> interpretar("comprar el pan", ahora) is None
    True

Este módulo **no** se enchufa todavía a `/tarea` ni a `/habito`: la regla del
repo es que la lógica se prueba en midgaror antes de exponerla en bifrost.
"""

import re
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ZONA = ZoneInfo("Europe/Madrid")

DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

# Hora canónica de cada franja. Son convenciones, no medidas: lo que importa
# es que «por la tarde» deje de perderse, que es lo que hacía thea-ia.
FRANJAS = {"madrugada": 3, "manana": 9, "mediodia": 14, "tarde": 16, "noche": 21}

_DIAS_RE = "|".join(DIAS)
_MESES_RE = "|".join(MESES)


def _plano(texto):
    """Minúsculas y sin tildes, **conservando la longitud** del original.

    Los índices del texto normalizado tienen que valer para recortar el texto
    de entrada, así que la equivalencia es carácter a carácter: `á` → `a`,
    `ñ` → `n`. Nada de `NFD`, que descompondría en dos caracteres y desplazaría
    todas las posiciones a partir de la primera tilde.
    """
    salida = []
    for c in texto.lower():
        base = unicodedata.normalize("NFD", c)
        letra = "".join(x for x in base if not unicodedata.combining(x))
        salida.append(letra if len(letra) == 1 else c)
    return "".join(salida)


def _solapa(inicio, fin, ocupados):
    return any(a < fin and inicio < b for a, b in ocupados)


def _buscar(patrones, plano, ocupados):
    """Primer patrón que casa sin pisar un trozo ya reclamado.

    El orden de `patrones` es el orden de prioridad, y por eso importa:
    `pasado manana` tiene que probarse antes que `manana`, o «pasado mañana»
    se resuelve como «mañana». Ese era literalmente el fallo de thea-ia.
    """
    for clave, patron in patrones:
        for m in re.finditer(patron, plano):
            if not _solapa(m.start(), m.end(), ocupados):
                return clave, m
    return None, None


def _proximo_dia_semana(base, objetivo):
    """Siguiente día de la semana, siempre en el futuro (nunca hoy)."""
    adelanto = (objetivo - base.weekday()) % 7
    return base + timedelta(days=adelanto or 7)


PATRONES_FRANJA = [
    ("hoy", r"\best[ae]\s+(madrugada|manana|tarde|noche)\b"),
    ("hoy", r"\bal\s+(mediodia)\b"),
    (None, r"\b(?:por|de)\s+la\s+(madrugada|manana|tarde|noche)\b"),
    (None, r"\ba\s+(?:el\s+)?(mediodia)\b"),
]

PATRONES_FECHA = [
    ("iso", r"\b(\d{4})-(\d{2})-(\d{2})\b"),
    ("dias", r"\bpasado\s+manana\b"),
    ("dias", r"\banteayer\b|\bantes\s+de\s+ayer\b"),
    ("dias", r"\bayer\b"),
    ("dias", r"\bhoy\b"),
    ("dias", r"\bmanana\b"),
    ("en", r"\ben\s+(\d{1,3})\s+(dias?|semanas?|meses|mes)\b"),
    ("hace", r"\bhace\s+(\d{1,3})\s+(dias?|semanas?)\b"),
    ("semana", rf"\b(?:el\s+)?(?:proximo|proxima|siguiente)\s+({_DIAS_RE})\b"),
    ("semana", rf"\b(?:el\s+)?({_DIAS_RE})\s+(?:que\s+viene|proximo)\b"),
    ("semana", rf"\b(?:el\s+)?({_DIAS_RE})\b"),
    ("mes", rf"\b(?:el\s+)?(\d{{1,2}})\s+de\s+({_MESES_RE})(?:\s+de\s+(\d{{4}}))?\b"),
    ("barras", r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b"),
]

DESPLAZAMIENTO = {"pasado manana": 2, "manana": 1, "hoy": 0,
                  "ayer": -1, "anteayer": -2, "antes de ayer": -2}

PATRONES_HORA = [
    ("exacta", r"\ba\s+las?\s+(\d{1,2})[:.](\d{2})\b"),
    ("exacta", r"\b(\d{1,2}):(\d{2})\b"),
    ("suelta", r"\ba\s+las?\s+(\d{1,2})\s*(?:h|horas)?\b"),
    ("suelta", r"\b(\d{1,2})\s*(?:h|horas)\b"),
]

# «a las 5 de la tarde» son las 17:00; «a las 5 de la mañana», las 5:00.
SUFIJO_HORA = re.compile(r"\s*(?:de|por)\s+la\s+(madrugada|manana|tarde|noche)\b")


def _anterior_dia_semana(base, objetivo):
    """Último día de la semana que ya pasó (nunca hoy)."""
    retroceso = (base.weekday() - objetivo) % 7
    return base - timedelta(days=retroceso or 7)


def _fecha_desde(clave, m, base, hacia_atras=False):
    """Traduce un patrón de fecha ya casado a un `date`. `None` si no cuadra.

    Lo ambiguo —«el lunes», «el 4 de septiembre»— se resuelve hacia delante
    por defecto, que es lo que quiere una cita, y hacia atrás con
    `hacia_atras`, que es lo que quiere el diario: cuando se escribe «fui al
    médico el lunes», el lunes ya pasó.
    """
    if clave == "dias":
        return base + timedelta(days=DESPLAZAMIENTO[re.sub(r"\s+", " ", m.group(0))])

    if clave in ("en", "hace"):
        cantidad, unidad = int(m.group(1)), m.group(2)
        signo = -1 if clave == "hace" else 1
        if unidad.startswith("semana"):
            return base + signo * timedelta(weeks=cantidad)
        if unidad.startswith("mes"):
            return base + signo * timedelta(days=30 * cantidad)
        return base + signo * timedelta(days=cantidad)

    if clave == "semana":
        indice = DIAS.index(m.group(1))
        return (_anterior_dia_semana if hacia_atras else _proximo_dia_semana)(base, indice)

    if clave == "iso":
        return _fecha_valida(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    if clave == "mes":
        dia, mes = int(m.group(1)), MESES.index(m.group(2)) + 1
        if m.group(3):
            return _fecha_valida(int(m.group(3)), mes, dia)
        return _sin_ano(base, mes, dia, hacia_atras)

    dia, mes = int(m.group(1)), int(m.group(2))
    if m.group(3):
        ano = int(m.group(3))
        return _fecha_valida(ano + 2000 if ano < 100 else ano, mes, dia)
    return _sin_ano(base, mes, dia, hacia_atras)


def _sin_ano(base, mes, dia, hacia_atras=False):
    """Sin año escrito: la próxima vez que ocurre ese día y mes, o la última."""
    fecha = _fecha_valida(base.year, mes, dia)
    if fecha is None:
        return None
    if hacia_atras:
        return fecha if fecha <= base else _fecha_valida(base.year - 1, mes, dia)
    return fecha if fecha >= base else _fecha_valida(base.year + 1, mes, dia)


def _fecha_valida(ano, mes, dia):
    try:
        return datetime(ano, mes, dia).date()
    except ValueError:
        return None


def _limpiar(texto, ocupados):
    """Devuelve el texto sin los trozos reclamados, con los espacios cuadrados."""
    resto = texto
    for inicio, fin in sorted(ocupados, reverse=True):
        resto = resto[:inicio] + " " + resto[fin:]
    resto = re.sub(r"\s+", " ", resto).strip()
    return re.sub(r"^[,;:.\-–—]+\s*|\s*[,;:.\-–—]+$", "", resto).strip()


def ahora():
    """El momento actual en `Europe/Madrid`, que es la zona del diario.

    Existe para que el resto del diario no tenga que saber de zonas horarias
    ni repetir `datetime.now(ZONA)`. Antes cada modelo resolvia su «hoy» con
    `date.today()`, o sea con la zona del sistema, mientras las palabras
    («ayer», «el lunes») se resolvian aqui en Madrid. En Madre las dos
    coinciden y no se notaba; en cualquier maquina que no este en Madrid, no.
    """
    return datetime.now(ZONA)


def hoy():
    """La fecha de hoy en Madrid, `'AAAA-MM-DD'`.

    Un solo «hoy» para todo el diario. Lo comprobo una prueba de bifrost que
    empezo a fallar el 2026-09-10 a las 22:00 UTC: «ayer» caia en el mismo dia
    que el «hoy» del sistema, porque eran dos relojes distintos.
    """
    return ahora().date().isoformat()


def interpretar(texto, ahora=None, hacia_atras=False):
    """Extrae fecha y hora de un texto en español.

    Devuelve `(fecha_iso, hora, resto)` donde `fecha_iso` es `'AAAA-MM-DD'`,
    `hora` es `'HH:MM'` o `None` si el texto no dice ninguna, y `resto` es lo
    que queda del texto al quitarle la expresión temporal. Devuelve `None`
    —no una fecha inventada— si el texto no menciona ni fecha ni hora.

    `ahora` es la referencia desde la que se resuelve lo relativo; por defecto,
    el momento actual en `Europe/Madrid`. Se acepta un `datetime` sin zona
    para poder fijarlo en las pruebas.

    `hacia_atras` resuelve lo ambiguo («el lunes», «el 4 de septiembre») al
    último que pasó en vez de al próximo. Lo explícito («mañana», «en 3 días»)
    no cambia.
    """
    if not texto or not texto.strip():
        return None

    ahora = ahora or datetime.now(ZONA)
    base = ahora.date()
    plano = _plano(texto)
    ocupados = []

    fecha = hora = None

    clave_hora, m_hora = _buscar(PATRONES_HORA, plano, ocupados)
    if m_hora:
        h = int(m_hora.group(1))
        minutos = int(m_hora.group(2)) if clave_hora == "exacta" else 0
        fin = m_hora.end()
        sufijo = SUFIJO_HORA.match(plano, fin)
        if sufijo:
            franja = sufijo.group(1)
            if h < 12 and franja in ("tarde", "noche"):
                h += 12
            elif h == 12 and franja in ("noche", "madrugada"):
                # «las 12 de la noche» es medianoche; «las 12 de la mañana»,
                # mediodía. Son los dos únicos casos donde el 12 no es 12.
                h = 0
            fin = sufijo.end()
        if h < 24 and minutos < 60:
            hora = f"{h:02d}:{minutos:02d}"
            ocupados.append((m_hora.start(), fin))

    clave_franja, m_franja = _buscar(PATRONES_FRANJA, plano, ocupados)
    if m_franja:
        ocupados.append((m_franja.start(), m_franja.end()))
        if hora is None:
            hora = f"{FRANJAS[m_franja.group(1)]:02d}:00"
        if clave_franja == "hoy":
            fecha = base

    clave_fecha, m_fecha = _buscar(PATRONES_FECHA, plano, ocupados)
    if m_fecha:
        candidata = _fecha_desde(clave_fecha, m_fecha, base, hacia_atras)
        if candidata is not None:
            fecha = candidata
            ocupados.append((m_fecha.start(), m_fecha.end()))

    if fecha is None and hora is None:
        return None

    return (fecha or base).isoformat(), hora, _limpiar(texto, ocupados)



# ---- para los comandos: una fecha suelta, delante o detrás ---------------

MAX_PALABRAS = 6  # «el 15 de octubre de 2026» son seis palabras; nada de fecha pasa de ahí


def como_fecha(texto, ahora=None, hacia_atras=False):
    """`texto` en ISO si es **solo** una fecha («ayer», «el lunes», «2026-09-05»).

    Si sobra algo, o si lo que hay es una hora, devuelve `None`: «deporte» no
    es una fecha, y «a las 10» tampoco. Es lo que distingue el argumento de
    fecha de un comando del nombre de un hábito o del texto de un diario.
    """
    resultado = interpretar(texto, ahora, hacia_atras)
    if resultado is None:
        return None
    fecha, hora, resto = resultado
    return fecha if not resto and hora is None else None


def normalizar(fecha, ahora=None, hacia_atras=False):
    """ISO de una fecha escrita como sea; hoy si es `None`. `ValueError` si no lo es.

    Es lo que usan `agenda`, `habitos` y los handlers del bot para aceptar
    «ayer» donde antes solo entraba `AAAA-MM-DD`.
    """
    if fecha is None or not str(fecha).strip():
        return (ahora or datetime.now(ZONA)).date().isoformat()
    iso = como_fecha(str(fecha), ahora, hacia_atras)
    if iso is None:
        raise ValueError(f"fecha no válida: {fecha!r} (ayer, mañana, el lunes, 2026-09-05…)")
    return iso


def _partes(texto):
    return texto.split()


def fecha_delante(texto, ahora=None):
    """(fecha, resto) si el texto **empieza** por una fecha; (None, texto) si no.

    Para `/entrada ayer se me olvidó esto`. Se prueba primero el trozo más
    largo, para que «antes de ayer cené fuera» dé «antes de ayer» y no «antes».
    Hacia atrás: lo que se apunta con fecha delante ya pasó.
    """
    palabras = _partes(texto)
    for n in range(min(MAX_PALABRAS, len(palabras) - 1), 0, -1):
        fecha = como_fecha(" ".join(palabras[:n]), ahora, hacia_atras=True)
        if fecha:
            # El resto se corta del texto original, no se recompone con
            # `join`: si se recompone, «/entrada ayer linea una\nlinea dos»
            # llega al diario en una sola linea y ya no hay como recuperarlo.
            # `split(maxsplit=n)` parte por los n primeros huecos y deja lo
            # demas tal cual, saltos de linea incluidos.
            return fecha, texto.split(maxsplit=n)[n].strip()
    return None, texto.strip()


def fecha_detras(texto, ahora=None):
    """(resto, fecha) si el texto **acaba** en una fecha pasada; (texto, None) si no.

    Para el diario: «cené con Ana ayer» va al día de ayer, sin el «ayer».

    Solo pasado, y solo pasado **sin ambigüedad**: «ayer», «antes de ayer»,
    «hace 3 días», una fecha completa. Lo ambiguo se resuelve hacia delante a
    propósito, para que NO cuente: «quedo con Ana el lunes» y «vuelvo el 15
    de octubre» son frases de hoy sobre el futuro, y con «el lunes» leído
    hacia atrás se irían a la semana pasada. «Tengo examen mañana» y «he
    dormido fatal hoy» se quedan enteras y en hoy, por lo mismo: en el diario
    el futuro no es una fecha, es parte de lo que se cuenta.

    Lo que se corta es la fecha a secas: «ayer por la tarde» no se toca,
    porque la franja horaria es parte de la frase. Para un día ambiguo hay
    `/entrada el lunes …`, donde la fecha va delante y a propósito.
    """
    palabras = _partes(texto)
    hoy = (ahora or datetime.now(ZONA)).date().isoformat()
    for n in range(min(MAX_PALABRAS, len(palabras) - 1), 0, -1):
        fecha = como_fecha(" ".join(palabras[-n:]), ahora)
        if fecha and fecha < hoy:
            # Igual que en fecha_delante, pero cortando por el final: `rsplit`
            # se come los n ultimos huecos y devuelve la cabeza intacta.
            return texto.rsplit(maxsplit=n)[0].strip(), fecha
    return texto.strip(), None
