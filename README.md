# hugin

[![pruebas](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Falvarofernandezmota-tech%2Fhugin%2Fmain%2Festado-pruebas.json)](#comprobarlo)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![sin dependencias](https://img.shields.io/badge/dependencias-biblioteca%20est%C3%A1ndar-brightgreen)](pyproject.toml)

**Un cerebro que atiende a gente, y dos puertas por las que le hablan.**
Entiende lo que le dicen, decide que contestar y guarda lo que hay que
guardar. El cerebro **no sabe por donde le hablan**: da igual que sea una
llamada de telefono o un chat de Telegram.

De los dos cuervos de Odin —Hugin, el pensamiento; Munin, la memoria— este es
el que piensa.

## Que hay aqui

```
hugin/          el cerebro. Ni un import de un canal
├── mente/      entender y decidir: reglas, buscador, LLM opcional, memoria
├── negocio/    de quien se habla: sus datos, sus frases, su agenda
├── guardado/   donde se escribe y como: ajustes, almacen, Postgres, avisos
├── inquilino.py  quien es el inquilino y que sabe hacer
└── apuntes.py    las notas sueltas de una persona

telegram/       una puerta: el bot de Telegram (en produccion)
telefono/       la otra: Whisper + Piper, una llamada de verdad
tests/          las pruebas del cerebro
```

Es **un solo producto** y sirve igual para una persona sola que para una
empresa: quien esta al otro lado es un *inquilino*, y un inquilino es una
carpeta con un `inquilino.toml` que dice que sabe hacer.

```toml
# inquilinos/peluqueria/inquilino.toml
nombre = "Peluqueria Carmen"
capacidades = ["agenda", "tarifas", "faq"]

# inquilinos/alvaro/inquilino.toml
nombre = "Alvaro"
capacidades = ["diario", "tareas", "habitos", "apuntes", "agenda"]
```

Darlo de alta es copiar la carpeta. No hay un `tipo = "persona" | "negocio"`
con dos moldes cerrados: un autonomo quiere agenda y tarifas **y** tareas, y
eso no cabe en ninguno de los dos moldes.

## Las decisiones que sujetan esto

Lo que no es negociable, y por que. Cada una tiene una prueba detras.

- **Aqui no entra ni un import de un canal.** Una llamada, un chat y una
  ventana web son la misma conversacion vista por sitios distintos: entra
  texto, sale texto. `tests/test_libreria.py` lee el **arbol de sintaxis** de
  cada modulo del cerebro y se cae si aparece uno. Desde que las dos puertas
  viven en este mismo repo, esa prueba es lo *unico* que sujeta el corte:
  antes tambien lo sujetaba la frontera entre repositorios.
- **Un precio sale de la tabla o no sale.** Un LLM puede redactar mejor la
  frase; el numero no lo pone el. Si el servicio no esta, se dice que no se
  sabe.
- **Una hora sin franja no se supone.** «a las cinco» devuelve `05:00` y la
  marca de que venia sin franja, y quien la confirma es el cliente. Es la
  regla que evito citar a alguien de madrugada.
- **Lo que escribe una persona va a ficheros; lo que registra el programa va
  a tablas.** Las tarifas y el diario en prosa son Markdown, porque su dueño
  tiene que poder cambiarlos sin llamar a nadie. Las tareas, las citas y los
  apuntes son registros y van a Postgres.
- **Una base de datos por inquilino, elegida por la URL de conexion**, no una
  columna `inquilino` en cada tabla. Leer lo de otro pasa de «que nadie
  olvide un WHERE» a ser imposible.
- **Nada de `__file__` para rutas de datos.** Esta libreria vive *dentro* de
  la aplicacion que la usa, asi que `__file__` apunta aqui y no a la raiz de
  quien despliega. Tambien lo sujeta una prueba sobre el arbol de sintaxis.

## Comprobarlo

```bash
make instalar      # venv + el paquete en editable
make pruebas       # las tres suites y el lint, de una vez
```

`make pruebas` corre las pruebas del cerebro, las de las dos puertas y
`ruff`, y **sigue hasta el final** en vez de parar en el primer fallo. Lo que
se salta lo dice con un aviso: una comprobacion saltada no es una
comprobacion pasada.

### No hay CI, y el badge no finge que lo haya

Un cobro rechazado bloquea GitHub Actions en toda la cuenta desde el
2026-09-04: los jobs salen en rojo sin llegar a coger runner, asi que un
check en rojo ahi no dice nada del codigo.

Mientras siga asi, **`make pruebas` en local es la unica verificacion real**,
y el badge de arriba dice literalmente «local» con la fecha de la medida, en
vez de un «CI: passing» que seria mentira. Lo escribe `make estado`, que se
niega a pintarlo verde si la suite esta en rojo.

Y no puede envejecer en silencio: `tests/test_estado.py` cuenta las pruebas
que hay de verdad y se cae si ya no son las que promete el badge.

Para que no se suba nada sin verificar, hay un gancho de `pre-push`. **No se
activa solo**, hay que decirselo a git en cada clon:

```bash
git config core.hooksPath .githooks
```

Es a proposito que no viaje activado: la copia del bot hace `git push` en
cada mensaje de Telegram, y ahi el gancho añadiria segundos a cada apunte y
bloquearia la subida del diario por una prueba en rojo sin relacion.

## Configuracion

Se lee del entorno, y `guardado/ajustes.py` carga el `.env` del **directorio
de trabajo** —el de la aplicacion que despliega, no el de esta libreria—. Se
puede decir a mano con `GJALLARHORN_ENV`.

| Variable | Para que |
|---|---|
| `INQUILINOS` | carpeta con los inquilinos dados de alta |
| `GJALLARHORN_NEGOCIOS` | igual, con el nombre de antes del ADR-024 |
| `GJALLARHORN_DATOS` | donde se escriben agenda, avisos y memoria |
| `GJALLARHORN_CONOCIMIENTO` | carpeta del conocimiento del inquilino |
| `DIARIO_DATABASE_URL` | Postgres, cuando el inquilino no trae la suya |
| `GJALLARHORN_LLM` / `GJALLARHORN_LLM_MODELO` | que modelo se usa, si se usa |
| `ANTHROPIC_API_KEY` | clave del LLM; sin ella se va con reglas |

El prefijo `GJALLARHORN_` es herencia de la primera aplicacion que uso esto.
Se queda mientras haya un bot en produccion leyendolo: renombrarlo obliga a
tocar su `.env` y sus unidades de systemd, y eso se hace como paso propio y
no de propina.

`anthropic` y `psycopg` son opcionales. Sin la libreria del LLM y sin clave,
el cerebro tira de reglas **y lo dice**; sin `psycopg`, guarda en ficheros.

## De donde sale

El cerebro vivia dentro de
[gjallarhorn](https://github.com/alvarofernandezmota-tech/gjallarhorn) y se
saco de ahi en el commit `cf000df`. Las dos puertas entraron aqui con su
historia entera —`telegram/` desde
[bifrost](https://github.com/alvarofernandezmota-tech/bifrost) y `telefono/`
desde gjallarhorn— al juntar el producto en un repo.

El porque de cada paso esta escrito: los ADR viven en el repo de
documentacion, y el que manda aqui es el **ADR-024, «un cerebro y dos
puertas»**.
