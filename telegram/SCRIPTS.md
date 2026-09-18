# Scripts de Bifrost

## estado.sh

¿Cómo está el bot? Todo lo que hace falta saber, en una palabra:

```bash
./estado.sh
```

Dice: si el servicio vive (y si no, las últimas líneas del log), en qué commit
corre, qué variables hay en el `.env`, si cada paquete **importa de verdad**, y
si el cerebro (`entender()`) y la voz están encendidos o dormidos.

Tres decisiones que no son estilo:

- **Imprime nombres de variables, nunca valores.** Un diagnóstico que hay que
  censurar antes de enseñarlo no se enseña, y entonces no sirve de nada. Este
  se puede pegar entero en un chat.
- **Avisa de las líneas que `dotenv` no va a entender.** El 2026-09-18 el bot
  se cayó porque una `x` y unos espacios se colaron delante de
  `TELEGRAM_BOT_TOKEN` al pasar por un editor, y el error solo decía «no
  encontrado».
- **Prueba a importar, y cada uno en su propio proceso.** `pip` decía
  «Successfully installed faster-whisper» mientras el import moría por una
  dependencia sin declarar; y un paquete compilado que no cuadra con el Python
  de la máquina no lanza una excepción, **mata al intérprete** — con los cuatro
  en el mismo proceso, el primero que revienta deja la comprobación muda justo
  cuando más falta hace.

## bot.py

Punto de entrada del bot. Inicia la aplicación de Telegram y registra handlers.

**Dependencias**:
- `python-telegram-bot`
- `python-dotenv`

## handlers/

Uno por familia de comandos. Cada uno es la cara en Telegram de un módulo de
`midgaror/diario/`: recibe datos, devuelve texto, y **no decide nada** que no
sea de presentación. La lógica vive en midgaror y se prueba allí.

| Fichero | Comandos | Módulo de midgaror |
|---|---|---|
| `diario.py` | `/diario` | `organizar_diario.organizar_texto()` |
| `entrada.py` | `/entrada` | `bifrost_bridge.escribir_entrada()` |
| `secciones.py` | `/siento`, `/aprendo`, `/plan` | `organizar_diario.organizar_texto(seccion=…)` |
| `texto.py` | *(texto sin comando)* | `organizar_diario.organizar_texto()` |
| `tarea.py` | `/tarea`, `/tareas` | `tareas.py` |
| `cita.py` | `/cita`, `/agenda` | `agenda.py` |
| `habito.py` | `/habito`, `/habitos` | `habitos.py` |
| `apunte.py` | `/apunte`, `/dia`, `/semana` | `registro/registro.py` (ADR-012) |
| `hoy.py` | `/hoy` | los cuatro anteriores, juntos |
| `menu.py` | `/menu` y los botones | enruta al handler del comando |

Detalle de cada uno, con la sintaxis que entiende: [`HANDLERS.md`](HANDLERS.md).

## utils/

| Fichero | Qué es |
|---|---|
| `midgaror.py` | el único sitio que sabe dónde está midgaror y cómo se importan sus módulos |
| `auth.py` | quién puede darle órdenes al bot. Cerrado por defecto |
| `respuestas.py` | todo lo que sale del bot pasa por aquí (`responder`, `responder_si_puedo`) |
| `mensajes.py` | el texto que escribió el usuario, sin el comando y **con sus saltos de línea** |
| `limites.py` | el tope de 4096 de Telegram, medido en unidades UTF-16 como lo mide Telegram |

## Scripts en midgaror/diario/

- `organizar_diario.py` → `organizar_texto(texto, fecha=None, seccion=None)`, único camino de escritura del diario
- `bifrost_bridge.py` → `escribir_entrada(texto, fecha=None)`, contrato con este bot (ADR-009)
- `diario.py` → rutas y plantilla del diario
- `fechas.py` → «ayer», «el lunes», «hace 3 días»… en español
- `tareas.py`, `agenda.py`, `habitos.py`, `registro/registro.py` → los cuatro modelos
- `almacen.py` → el único que lee y escribe JSON, con `schemaVersion`
- `atomico.py` → escritura atómica: un fallo a mitad no deja el fichero a medias
- `sincronizar.py` → `git commit` y `git push` de lo escrito

## Ruta de import

Ningún handler calcula la ruta: la calcula **`utils/midgaror.py`**, una sola
vez, cuatro niveles por encima de `utils/`. Antes lo repetía cada handler con
su propio `sys.path.insert`, ocho ficheros con el mismo preámbulo y ningún
sitio donde arreglarlo una vez.

Eso obliga a que este repo viva en `midgaror/proyectos/bifrost`. Clonado en
otro sitio, el bot no arranca. Si algún día bifrost se instala como paquete,
`utils/midgaror.py` es el único fichero que hay que tocar.
