---
tipo: decision
fecha: 2026-09-12
repo: midgaror
etiquetas: [arquitectura, gjallarhorn, hugin, submodulos, ecosistema]
relacionado: [docs/adr/018-gjallarhorn-es-un-agente.md, docs/adr/017-entrada-por-voz-al-diario.md, docs/adr/011-mimir-repo-e-indices.md, docs/adr/008-regla-enganche-cuadruple.md, docs/estandares/frontmatter.md]
---

> **Portado el 2026-09-19** desde
> [midgaror](https://github.com/alvarofernandezmota-tech/midgaror/blob/main/docs/adr/019-cerebro-de-gjallarhorn-en-hugin.md),
> copia verbatim. Los ADR son inmutables allí; esta copia tampoco se edita —
> una nota de estado nueva va en `docs/adr/README.md` de hugin, no aquí
> dentro.

# ADR-019: El cerebro de gjallarhorn vive en hugin, y la dependencia va en un solo sentido

## Contexto

gjallarhorn empezó siendo un repo y acabó siendo dos cosas dentro de un repo.

Por un lado, **coger la llamada**: el webhook del proveedor, las firmas, los
dos puertos, el reconocimiento de voz, y lo que usa Álvaro para operarlo.
Por otro, **entender qué le han dicho y decidir qué contestar**: las reglas,
el buscador del conocimiento, la agenda, el LLM opcional, la memoria de quien
llama y dónde se escribe todo eso.

Lo segundo no tiene nada que ver con que haya un teléfono al otro lado. Una
llamada, un chat de Telegram y una ventana web son la misma conversación
vista por sitios distintos: entra texto, sale texto. El README de gjallarhorn
lo llevaba escrito desde el primer día —«`mente/` no sabe por dónde entró la
llamada»— y era verdad **de momento**, que es otra forma de decir que no
había nada que lo sujetara.

Ya se había empezado a deshacer sin que nadie lo decidiera: `mente/recepcion.py`
importaba `telefono/voz.py` para su `main()` de pruebas, y `mente/cerebro.py`
importaba `dueno/avisar.py` entero solo para preguntarle si había una clave de
LLM puesta. Dos líneas, las dos razonables por separado, y las dos en el
sentido contrario al que el README prometía.

El encargo de Álvaro el 2026-09-12, dicho tres veces, fue: **el cerebro va a
su propio repo y el bot de voz hereda de él**.

## Decisión

Tres repos, y la dirección importa más que el reparto:

| Repo | Qué es | Público |
|---|---|---|
| [gjallarhorn](https://github.com/alvarofernandezmota-tech/gjallarhorn) | la aplicación: por dónde entra la conversación (`telefono/`) y quién la opera (`dueno/`) | sí |
| [hugin](https://github.com/alvarofernandezmota-tech/hugin) | el cerebro: `mente/`, `negocio/`, `guardado/` | sí |

**gjallarhorn usa hugin; hugin no sabe que gjallarhorn existe.** hugin va
montado como submódulo en `gjallarhorn/hugin`, y los imports son
`from hugin.mente import recepcion`.

Se llama hugin por el cuervo de Odín que es el pensamiento (el otro, Munin,
es la memoria). **No se llama mimir**: ese nombre está cogido por el
[ADR-011](011-mimir-repo-e-indices.md) para otra cosa —los índices de
embeddings sobre el diario y el código—, y reusarlo habría dejado dos
sistemas distintos con el mismo nombre.

### La frontera no es una buena intención: son dos pruebas

- En hugin, `tests/test_libreria.py` lee el **árbol de sintaxis** de cada
  módulo y se cae si aparece un import de un canal (`telefono`, `dueno`,
  `twilio`, `telnyx`, `signalwire`, `flask`).
- En gjallarhorn, `tests/test_carpetas.py` se cae si el cerebro «vuelve a
  casa» en forma de copia, si alguien le habla por `from mente import ...` en
  vez de `from hugin.mente import ...`, o si `make pruebas` deja de entrar en
  el submódulo.

Se comprueba desde los dos lados a propósito: una frontera que solo se mira
desde uno se cruza por el otro.

## Qué relación tiene esto con midgaror

La pregunta de Álvaro fue «cada repo en su sitio y conectado con midgaror,
¿no?». La respuesta es que sí a lo primero y **no como submódulo** a lo
segundo, y eso ya estaba decidido: la nota de estado del
[ADR-018](018-gjallarhorn-es-un-agente.md) dice que gjallarhorn «no es
submódulo de midgaror ni va en `proyectos/`; es independiente y se clona
solo».

Esa decisión sigue en pie y se extiende a hugin. `proyectos/` es para lo que
midgaror **despliega y mantiene acoplado** —hoy, bifrost, que escribe el
diario ([ADR-009](009-bifrost-bridge-diario.md))—. Meter ahí gjallarhorn
haría que clonar midgaror arrastrara el recepcionista de una peluquería, y
recursivamente hugin, para poder leer un diario.

Lo que midgaror guarda de estos dos repos es **lo que midgaror es**: las
decisiones y su porqué. Este ADR, el 017 y el 018. El código vive en su repo,
con su propio `CONTEXT.md` y su propio `AGENTS.md`, y ahí es donde hay que
mirar para saber cómo funciona.

Consecuencia práctica: `python3 scripts/verificar.py` **no** corre las pruebas
de gjallarhorn ni las de hugin, igual que no las corría antes. Cada uno se
verifica en su casa con su `make pruebas`, que en gjallarhorn corre las dos
suites (458 + 350) y falla si el submódulo está vacío.

## Alternativas descartadas

- **Dejarlo en un repo y confiar en la disciplina.** Es lo que había, y ya se
  había roto dos veces sin que nadie se enterara. Una frontera sin prueba es
  una nota mental.
- **Publicar hugin como paquete en PyPI.** Para un repo de una persona,
  publicar y versionar a mano cada cambio del cerebro es fricción sin nada a
  cambio: el submódulo fija exactamente un commit y se actualiza con un `git
  add`.
- **Copiar el cerebro en cada aplicación**, que es lo que dice el ADR-018
  para el código que viene de fuera de la casa. Vale para treinta líneas de
  un parser de fechas; no vale para 5.000 líneas con 350 pruebas que van a
  seguir cambiando en los dos sitios a la vez.
- **Llamarlo mimir.** Nombre ocupado por el ADR-011.

## Consecuencias

**Lo que cuesta:**

- `git clone` de gjallarhorn ya no basta: hace falta
  `git submodule update --init`. Está en su README y en su `make pruebas`,
  que falla a propósito si el submódulo está vacío en vez de pasar en verde
  sin haber probado el cerebro.
- Tocar el cerebro es tocar **otro repositorio**: se commitea en hugin y
  luego se graba el enlace en gjallarhorn. Dos commits donde antes había uno.
- El servicio de actualización sola de Madre hacía `git pull --ff-only` y
  nada más. Eso habría traído el enlace al submódulo **sin descargarlo**:
  carpeta vacía, reinicio, y el teléfono mudo sin que nada lo dijera. La
  unidad ahora trae el submódulo antes de reiniciar, y si no puede, **no
  reinicia**: el proceso que está atendiendo sigue con el código que ya tiene
  cargado.

**El fallo que casi se cuela**, y que es la lección que vale para cualquier
otro corte de estos:

Tres funciones resolvían carpetas de datos con
`Path(__file__).parent.parent`. Eso apuntaba a la raíz del repo mientras
vivían dentro de la aplicación, y sacadas a librería apuntan a `hugin/`. La
agenda, el conocimiento y los negocios se habrían escrito **dentro del
submódulo**: datos de clientes en una carpeta que no es de nadie, con el bot
contestando tan tranquilo que no hay citas.

Una librería no puede resolver rutas desde donde está su código, porque su
código está dentro de la aplicación que la usa. Se resuelven desde el
directorio de trabajo —que las unidades de systemd fijan en la raíz— y hay
una prueba en hugin que lee el árbol de sintaxis y no deja que vuelva a
aparecer un `__file__`.

## Estado

Aceptado el 2026-09-12. El corte está hecho y verde en los dos repos: 458
pruebas en gjallarhorn y 350 en hugin, con el lint limpio.
