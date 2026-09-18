# Bifrost

Bot de Telegram para escribir y organizar entradas del diario personal.

**Nota de nombres.** El producto sigue llamándose Bifrost —así lo conoce
Álvaro, y así habla el bot en este documento—, pero desde el corte de
producción del 2026-09-18 el servicio de systemd que lo corre en Madre se
llama `hugin-telegram`, no `bifrost` (ver
[`systemd/hugin-telegram.service`](systemd/hugin-telegram.service), cuyos
propios comentarios explican el cambio). La unidad vieja, `bifrost.service`,
se dejó instalada y parada en Madre como vuelta atrás instantánea, pero no es
la que corre. Todos los comandos `systemctl`/`journalctl` y las rutas de
este documento usan el nombre de hoy.

## Estado

✅ **En producción** — corre como servicio de systemd en Madre y escribe
entradas reales del diario desde Telegram (la primera, el 2026-09-08).
✅ **Autorización por chat_id** — cerrada por defecto: sin un id válido en el
`.env` el bot no le responde a nadie y lo dice con ERROR en el journal.
✅ **Sobrevive a un arranque sin red** — reintenta en vez de morir, y la
unidad no tiene tope de reinicios.

Como está vivo y escribiendo en el diario de verdad, lo de aquí abajo no es
teoría: arrancar una segunda instancia a mano **rompe la que está corriendo**
(ver «Uso diario»).

## Estructura del repositorio

```text
telegram/
├─ bot.py                   # Punto de entrada del bot
├─ handlers/
│  ├─ __init__.py
│  ├─ diario.py             # /diario → hugin.personal.diario.organizar_texto
│  ├─ entrada.py            # /entrada → hugin.personal.diario.escribir_entrada
│  ├─ secciones.py          # /siento, /aprendo, /plan → hugin.personal.diario.organizar_texto
│  ├─ tarea.py              # /tarea, /tareas → hugin.personal.tareas (cerebro, ADR-024 fase 5)
│  ├─ cita.py               # /cita, /agenda → hugin.personal.citas (cerebro, ADR-024 fase 5)
│  ├─ habito.py             # /habito, /habitos → hugin.personal.habitos (cerebro, ADR-024 fase 5)
│  ├─ hoy.py                # /hoy → hugin.personal.diario.leer_entrada + citas/tareas/hábitos (cerebro)
│  ├─ apunte.py             # /apunte, /dia, /semana → hugin.apuntes (cerebro, ADR-024 fase 5)
│  ├─ menu.py               # /menu → botones que preguntan y enrutan al handler del comando
│  ├─ texto.py              # mensaje sin comando → hugin.personal.entender() y, si no, diario de hoy
│  ├─ voz.py                # nota de voz → Whisper → el mismo camino que el texto
│  └─ recordatorios.py      # avisa de una cita sin que nadie pregunte (ADR-020)
├─ utils/
│  ├─ auth.py               # autorización por chat_id
│  ├─ inquilino.py          # quién es el inquilino de esta copia (variable INQUILINO)
│  ├─ limites.py            # el tope de 4096 de Telegram, contado como lo cuenta Telegram
│  ├─ mensajes.py           # el texto tras el comando, con sus saltos de línea intactos
│  ├─ respuestas.py         # cómo se contesta: breve si va bien, entero si falla
│  └─ voz.py                # Whisper en local: audio → texto
├─ systemd/
│  └─ hugin-telegram.service # la unidad de producción (ver «Como servicio»)
├─ venv/ # Entorno virtual (NO commitear)
├─ .env # Token y chat_id (NO commitear)
├─ .env.example
├─ .gitignore
├─ AGENTS.md
├─ CONTEXT.md
├─ HANDLERS.md
├─ README.md
├─ SCRIPTS.md
└─ docs/
   └─ sesiones/
```

## Dónde tiene que vivir este repo

Nada de fuera hace falta ya: ni submódulo, ni una segunda ruta de código, ni
un `MIDGAROR_RAIZ` que apunte a otro repo.

**Todo el cerebro (`hugin`) lo trae este mismo repo, diario en prosa
incluido.** `telegram/` es la carpeta `telegram/` de `hugin`, así que
`pip install -r requirements.txt` ya instala `hugin` en editable (ver
[`requirements.txt`](requirements.txt)) y tanto `from hugin.personal import
citas` como `from hugin.personal.diario import organizar_texto` funcionan
sin tocar el `sys.path`.

Hasta el 2026-09-18 la prosa del diario (`/diario`, `/entrada`,
`/siento`/`/aprendo`/`/plan`, y el texto suelto que no se reconoce como
tarea, cita, hábito o apunte) seguía siendo de midgaror, y `utils/midgaror.py`
la importaba en caliente contra la ruta que dijera `MIDGAROR_RAIZ`. Ese
fichero **se ha borrado**: la fase 5 del ADR-024 portó
`diario/organizar_diario.py` y `diario/bifrost_bridge.py` de midgaror a
`hugin/personal/diario.py` —fundidos en un único módulo, sin lógica
duplicada (mira su docstring)—, y ya no queda nada que importar desde otro
repo. `MIDGAROR_RAIZ` no existe en ningún sitio del código: no hace falta
ponerla, y ponerla no hace nada.

Lo único de fuera que sigue haciendo falta es **dónde viven los datos**, que
no es código, sino la carpeta del inquilino — dos variables de entorno que
no van en el `.env` (las pone quien arranca el proceso; en producción, la
unidad de systemd, ver «Como servicio»):

- `MIDGAROR_DATOS`: la raíz de la prosa del diario (la lee
  `hugin/personal/diario.py`).
- `INQUILINOS`: la carpeta que contiene a **todos** los inquilinos (la lee
  `hugin/inquilino.py`), de la que `INQUILINO` —esa sí, en el `.env`, ver el
  paso 4 de abajo— elige uno.

Hoy las dos apuntan al mismo sitio, el repo privado `midgaror-diario`
(ADR-025 de midgaror: *«midgaror-diario no se abandona: pasa a ser la
carpeta de inquilinos»*). Ninguna de las dos es obligatoria para que el bot
arranque —no son como `TELEGRAM_BOT_TOKEN`—, pero sin ponerlas el bot
escribe donde no toca: la prosa cae bajo el directorio desde el que
arrancaste el proceso, e `INQUILINOS` por defecto es `./inquilinos` ahí
mismo. En una máquina de verdad, se ponen siempre.

## Puesta en marcha, paso a paso

1. **Crear el bot en Telegram.** Habla con `@BotFather`, `/newbot`, y guarda
   el token que te da.

2. **Averiguar tu chat_id.** Escríbele algo a tu bot y luego:

   ```bash
   curl -s "https://api.telegram.org/bot<TU_TOKEN>/getUpdates" | grep -o '"id":[0-9-]*' | head -1
   ```

   Ese número va en `TELEGRAM_CHAT_ID` y es lo que hace que el bot te
   responda solo a ti. **Sin un id válido el bot no responde a nadie** y lo
   grita por el log al arrancar: cerrado por defecto.

3. **Entorno virtual y dependencias:**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

   Las versiones van fijadas en `requirements.txt` a propósito: el bot corre
   como servicio en Madre y se actualiza con un `git pull`, así que una
   versión nueva de `python-telegram-bot` que cambie la API lo dejaría sin
   arrancar sin haber tocado el código.

4. **Configurar el `.env`:**

   ```bash
   cp .env.example .env
   ```

   Rellena `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`. El `.env` no se
   commitea nunca: ya está en `.gitignore`.

   Desde que los comandos personales viven en el cerebro (ADR-024, fase 5),
   hace falta decir para quién es esta copia: `INQUILINO=alvaro` en el
   `.env`, el nombre de su carpeta dentro de `INQUILINOS` (ver
   [`utils/inquilino.py`](utils/inquilino.py), variable `INQUILINO`). Sin
   ella, `/apunte`, `/dia`, `/semana`, `/tarea`, `/tareas`, `/cita`,
   `/agenda`, `/habito`, `/habitos`, `/hoy` y los recordatorios fallan con un
   aviso claro; solo `/diario`, `/entrada` y `/siento`/`/aprendo`/`/plan`
   —la prosa del diario, hoy en `hugin/personal/diario.py`— no la necesitan,
   porque ese módulo no distingue entre inquilinos (ver su docstring, «Por
   qué esto no lleva `inq=`»).

   `INQUILINOS` —en plural: dónde viven **todos** los inquilinos, no cuál es
   el tuyo— no va en el `.env`: la pone quien arranca el proceso, a mano con
   `export INQUILINOS=…` o, en producción, como `Environment=` de la unidad
   de systemd (ver «Como servicio»). Sin ella, por defecto es
   `./inquilinos` bajo el directorio desde el que arrancas, que casi nunca
   es lo que quieres fuera de una prueba.

5. **Probar la escritura sin el bot**, para separar los fallos del diario de
   los de Telegram. Con el venv activado (paso 3), desde `telegram/`:

   ```bash
   python3 -c "from hugin.personal.diario import organizar_texto; \
   print(organizar_texto('prueba desde terminal'))"
   python3 -c "from hugin.personal.diario import escribir_entrada; \
   print(escribir_entrada('prueba con fecha', fecha='2026-09-04'))"
   git -C "${MIDGAROR_DATOS:-.}" diff diario/personal/   # mirar qué ha escrito
   ```

   Ya no hay un script de línea de comandos aparte: `organizar_diario.py` y
   `bifrost_bridge.py` eran de midgaror, y `hugin/personal/diario.py` es una
   librería, no una CLI. `organizar_texto()` es lo que llama `/diario`, y
   `escribir_entrada()` —una capa fina sobre la misma función, con `fecha`—
   es lo que llama `/entrada`. Si esto falla, el problema está en
   `hugin/personal/diario.py`, no en el bot.

6. **Arrancar el bot en primer plano.** Si el servicio está instalado en
   esta máquina, **párralo antes**: dos instancias con el mismo token se
   pelean por los mensajes y Telegram devuelve `409 Conflict` a las dos.

   ```bash
   sudo systemctl stop hugin-telegram   # si el servicio está instalado aquí
   source venv/bin/activate
   python3 bot.py
   ```

   Los mensajes de arranque salen por pantalla. Se para con `Ctrl+C`, y el
   servicio se vuelve a levantar con `sudo systemctl start hugin-telegram`.

7. **Probar desde Telegram**, en este orden:

   | Mensaje | Qué debe pasar |
   |---------|----------------|
   | `/start` | Responde con la bienvenida |
   | `/help` | Responde con la ayuda |
   | `/diario probando hoy` | Escribe en la entrada de hoy y responde con la ruta |
   | `/entrada 2026-09-01 probando una fecha` | Escribe en la entrada de ese día |
   | `/entrada 01-09-2026 mal` | Responde que la fecha es inválida |
   | `/entrada 2026-09-01` | Responde con el uso correcto |

8. **Comprobar y guardar lo escrito**, desde la carpeta de datos
   (`$MIDGAROR_DATOS` si la pusiste; si no, el directorio desde el que
   arrancaste el bot — sin la variable, `hugin/personal/diario.py` cae a
   `Path.cwd()`):

   ```bash
   git log -1 --stat
   ```

   El bot escribe, commitea y sube él solo (`hugin.guardado.sincronizar`),
   así que lo que hay que mirar es el último commit, no el working tree: si
   el push falló, la respuesta del bot lo dice («⚠️ commiteado en local, sin
   subir»).

## Uso diario

El bot corre como servicio: no hay que arrancarlo a mano.

```bash
systemctl status hugin-telegram           # ¿está vivo?
journalctl -u hugin-telegram -f           # ver qué hace, en vivo
sudo systemctl restart hugin-telegram     # tras cambiar código o .env
```

Para arrancarlo a mano (depurar), **para antes el servicio**: dos instancias
con el mismo token se pelean por los mensajes y Telegram devuelve `409
Conflict` a las dos.

```bash
sudo systemctl stop hugin-telegram
cd ~/GitHub/personal/producto-bot/telegram
source venv/bin/activate
python3 bot.py
```

## Como servicio

Para que el bot no dependa de una terminal abierta. La unidad está en
[`systemd/hugin-telegram.service`](systemd/hugin-telegram.service), y sus
propios comentarios explican cada decisión de la configuración —léela entera
antes de tocarla, sobre todo el aviso sobre el endurecimiento, más abajo.

La unidad apunta a **`~/GitHub/personal/producto-bot/telegram`**, una copia
de este mismo repo (`hugin`) que es solo del bot y está siempre en `main`, no
a la copia de trabajo. Un `git checkout` mientras el servicio está vivo le
cambiaría el código que carga al reiniciar — mismo motivo que tenía
`midgaror-bot` con el bot viejo (ADR-013). Montarla es clonar `hugin` en esa
ruta y dejarla en `main`:

```bash
git clone https://github.com/alvarofernandezmota-tech/hugin.git ~/GitHub/personal/producto-bot
cd ~/GitHub/personal/producto-bot/telegram
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
cp ~/GitHub/personal/hugin/telegram/.env .   # o el que ya tuvieras
```

Actualizarla es un `git pull` en `producto-bot` (nunca en la copia de
trabajo) y `sudo systemctl restart hugin-telegram`.

**Antes de instalarla**, comprueba que las rutas del fichero coinciden con
las tuyas. Llevan `varopc` y `~/GitHub/personal/producto-bot/telegram`
escritos dentro:

```bash
grep -E "User=|WorkingDirectory=|ExecStart=|ReadWritePaths=" systemd/hugin-telegram.service
```

Instalación:

```bash
sudo cp systemd/hugin-telegram.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hugin-telegram
```

Comprobación:

```bash
systemctl status hugin-telegram
journalctl -u hugin-telegram -n 30 --no-pager
```

En el arranque debe aparecer `Bot en marcha` y, si tienes puesto el chat_id,
`Autorizacion activa para 1 chat(s)`. Si en su lugar sale el aviso de que
no te responde a ti, mira el log: si dice «no tiene ni un id valido», el
`TELEGRAM_CHAT_ID` del `.env` falta o tiene una errata.

### Comandos del día a día

```bash
sudo systemctl restart hugin-telegram     # tras cambiar código o .env
sudo systemctl stop hugin-telegram        # pararlo
journalctl -u hugin-telegram -f           # ver el log en vivo
```

### Qué hace la unidad

- **Se reinicia siempre** que el proceso termine, salga limpio o no. Solo
  `systemctl stop` lo deja parado. **Sin tope de reinicios**
  (`StartLimitIntervalSec=0`): el fallo probable al arrancar no es un bot roto
  sino que la red aún no está, y con el tope de antes cinco intentos se
  gastaban en ~50 s y la unidad quedaba en `failed` para siempre. Un error de
  configuración de verdad lo corta `bot.py` saliendo, no el tope.
- **El token no pasa por systemd.** Lo sigue leyendo `python-dotenv` del
  `.env`, así que no aparece en `systemctl show` ni en el volcado de la
  unidad. `MIDGAROR_DATOS` e `INQUILINOS` sí van como `Environment=` en la
  propia unidad (ADR-025): los lee código que corre antes de que exista el
  `inquilino.toml` de cada uno, y a diferencia del token no hay nada que
  ocultar en ellos.
- **Solo puede escribir dentro del repo de datos** (`midgaror-diario`,
  `ReadWritePaths=`). El resto del disco lo ve de solo lectura —
  `producto-bot` incluido: el código se lee, los datos se escriben, y son
  dos repos distintos (ADR-025). Tiene que ser el repo entero y no solo
  `diario/personal/`, porque al commitear git escribe en `.git/`, que está
  en la raíz.

  **Ojo, a fecha de hoy:** el endurecimiento de arriba y el resto
  (`NoNewPrivileges`, `PrivateTmp`, `ProtectSystem`, `ProtectHome`,
  `ProtectKernelTunables`, `ProtectKernelModules`, `ProtectControlGroups`,
  `RestrictSUIDSGID`, `LockPersonality`) está **descrito en el fichero pero
  no aplicado de verdad en Madre**: se quitó a mano el 2026-09-18 para
  depurar un fallo que no tenía que ver con esto, y todavía no se ha vuelto
  a poner (lo dicen los comentarios de
  [`systemd/hugin-telegram.service`](systemd/hugin-telegram.service)).
  Antes de dar el aislamiento por hecho, comprobar con
  `systemctl cat hugin-telegram` qué hay instalado de verdad, no lo que dice
  este repo.

### Dónde vive y qué toca

Todo el código del servicio vive en **`producto-bot`**, la copia que es solo
del bot y está siempre en `main`. La copia de trabajo (este repo, `hugin/`)
no corre el servicio: es donde editas.

| Cosa | Dónde |
|------|-------|
| Código | `~/GitHub/personal/producto-bot/telegram/` |
| Entorno virtual | `producto-bot/telegram/venv/` |
| Token y chat_id | `producto-bot/telegram/.env` (nunca se commitea) |
| Unidad | `/etc/systemd/system/hugin-telegram.service` |
| Datos (diario, tareas, citas, hábitos, apuntes) | `MIDGAROR_DATOS` / `INQUILINOS`, hoy las dos `~/GitHub/personal/midgaror-diario` (ADR-025 de midgaror) |
| Logs | `journalctl -u hugin-telegram` |
| Lógica del diario y de los cuatro modelos | `hugin/personal/` y `hugin/apuntes.py` — **en este mismo repo** (ADR-024 fase 5), no en un repo aparte |

Dentro de `midgaror-diario`, la prosa cae en
`diario/personal/AAAA/MM-mes/AAAA-MM-DD.md` (bajo `MIDGAROR_DATOS`, ver
`hugin/personal/diario.py`), y las tareas, citas, hábitos y apuntes en
`<inquilino>/tareas.json`, `citas.json`, `habitos.json` y `apuntes.json`
(bajo `INQUILINOS`, una carpeta por inquilino — hoy solo `alvaro`, ver
`hugin/inquilino.py`).

El bot **escribe, commitea y sube** él solo, con `hugin.guardado.sincronizar`:
una entrada mandada desde Telegram está en GitHub en segundos.
`sincronizar()` no asume una raíz fija — descubre el repo git a partir del
propio fichero que acaba de escribirse (`git rev-parse --show-toplevel`), así
que hoy sube a `midgaror-diario`, el repo de datos, no al de código. Por eso
el permiso de escritura de la unidad cubre `midgaror-diario` entero —ahí
también está el `.git/` del commit— y no `producto-bot`.

Cuando el push falla (sin red), la respuesta del bot lo dice en claro:
«⚠️ commiteado en local, sin subir». El commit está hecho; falta el push.

### Comprobar que no se muere

Instalarlo no demuestra nada. Estas cuatro pruebas sí, y son la fase 2b:

**1. Que resucita si lo matan**

Dos formas de morir, y tiene que volver de las dos:

```bash
sudo systemctl kill hugin-telegram              # SIGTERM: el bot lo captura y sale limpio
sleep 15; systemctl is-active hugin-telegram    # -> active

sudo systemctl kill -s SIGKILL hugin-telegram   # muerte súbita, sin tiempo a nada
sleep 15; systemctl is-active hugin-telegram    # -> active
```

La primera es la trampa: python-telegram-bot captura SIGTERM y sale con
código 0, y systemd no cuenta una salida limpia como fallo. Con
`Restart=on-failure` el bot **no volvía**; se vio en Madre el 2026-09-04,
`inactive` tras el kill. Por eso la unidad lleva `Restart=always`: vuelve
salga como salga, salvo que alguien haga `systemctl stop` a propósito.

Si sale `inactive` o `failed`, la unidad no está haciendo su trabajo.

**2. Que arranca solo al encender la máquina**

```bash
sudo reboot
# cuando vuelva:
systemctl is-enabled hugin-telegram    # -> enabled
systemctl is-active hugin-telegram     # -> active
```

Y lo que de verdad importa: escríbele por Telegram y comprueba que responde
sin que hayas tocado nada.

**3. Que aguanta un corte de red**

En una máquina a la que llegas por SSH, **no pares la red**: te quedas fuera.
La forma segura es esperar a que pase de verdad y mirarlo después:

```bash
systemctl show hugin-telegram -p NRestarts
journalctl -u hugin-telegram --since "1 day ago" | grep -iE "error|restart|network"
```

Si `NRestarts` sube solo, el bot se está muriendo por algo. Si sube y vuelve
solo, la unidad está cumpliendo.

**4. Que no se descuadra escribiendo**

Después de unos días de uso:

```bash
cd ~/GitHub/personal/midgaror-diario   # o $MIDGAROR_DATOS, si lo moviste
git status diario/personal/
git diff diario/personal/
```

Las entradas deben tener la hora delante y estar dentro de "Qué ha pasado
hoy", sin duplicados ni texto pegado al final del fichero.

### Qué anotar durante las dos semanas

La fase 2b pide uso real, y de eso salen datos. Vale con apuntar en la sesión
de trabajo, al final de cada semana:

- Cuántas veces se reinició (`NRestarts`) y por qué.
- Si alguna vez no respondió, y qué decía el log en ese momento.
- Si el formato de alguna entrada quedó raro.
- Cuántas veces lo usaste de verdad. Si la respuesta es "casi ninguna", eso
  también es un resultado, y más útil que cualquier mejora técnica.

### Cuidado al actualizar

Systemd arranca el bot con el Python del entorno virtual. Si rehaces el
`venv`, o si Arch sube de versión menor de Python y el entorno se queda
huérfano, el servicio deja de arrancar. Se ve claro en el log:

```bash
journalctl -u hugin-telegram -n 20 --no-pager
```

Se arregla recreando el entorno y reiniciando el servicio.

## Comandos

Los ejemplos son literales: se escribe lo que se ve, **sin `<` ni `>`**. La
ayuda anterior los llevaba y se escribieron tal cual dos veces en el diario.

| Comando | Qué hace | Módulo |
|---------|----------|--------|
| `/start` | Bienvenida con los comandos del día a día | — |
| `/help` | Ayuda completa | — |
| `/diario hoy he dormido fatal` | Añade el texto a la entrada de **hoy** | `hugin.personal.diario.organizar_texto` |
| `/diario cené con mi hermana ayer` | Con «ayer» al final, a la entrada de **ayer**. Solo el pasado: «tengo examen mañana» se queda en hoy | idem |
| `/entrada ayer se me olvidó esto` · `/entrada 2026-09-03 …` | Lo mismo en **ese día**: ayer, antes de ayer, el lunes (el que pasó), hace 3 días o la fecha | `hugin.personal.diario.escribir_entrada` |
| `/siento contento, he dormido bien` | A **«Cómo me siento»**, con la hora | `hugin.personal.diario.organizar_texto` (`seccion="siento"`) |
| `/aprendo lo de filters.COMMAND` | A **«Avances / aprendizajes»**, como viñeta | idem (`seccion="aprendo"`) |
| `/plan seguir con el portfolio` | A **«Para mañana»**, como viñeta | idem (`seccion="plan"`) |
| `/tarea comprar el pan` | Apunta una tarea | `hugin.personal.tareas` |
| `/tarea médico mañana a las 10` | Con fecha: la saca del texto | idem + `hugin.personal.fechas` |
| `/tarea empezar 3` · `/tarea hecha 3` · `/tarea reabrir 3` | La mueve de estado | idem |
| `/tarea editar 3 …` · `/tarea aplazar 3 …` | Le cambia el texto o la fecha | idem |
| `/tarea borrar 3` | La retira | idem |
| `/tareas` | En proceso, pendientes por fecha y últimas hechas | idem |
| `/cita médico mañana a las 10` | Apunta una cita; avisa si choca con otra | `hugin.personal.citas` |
| `/cita mover 3 …` · `/cita cancelar 3` | La cambia de hora o la retira | idem |
| `/agenda` · `/agenda semana` | Las citas del día o de los siete días | idem |
| `/habito deporte` · `/habito no meditar` | Apunta un hábito de hoy | `hugin.personal.habitos` |
| `/habito Leer Libro` | El nombre puede llevar espacios | idem |
| `/habito energia 7` | Un valor del 1 al 10 | idem |
| `/habito deporte ayer` · `/habito deporte 2026-09-03` | En otro día, dicho en español o con la fecha | idem |
| `/habito Beber agua 3 2026-09-03` | Nombre compuesto, valor y fecha | idem |
| `/habitos` · `/habitos semana` | El día, o la semana con totales y medias | idem |
| `/apunte deporte` · `/apunte tele 3h` · `/apunte agua 1,5l` | Apunta un evento del día, sin cantidad, con cantidad y unidad pegadas, o separadas | `hugin.apuntes` |
| `/apunte tele 1h ayer` | En otro día, dicho en español | idem |
| `/dia` · `/dia ayer` | Lo apuntado ese día, contra sus objetivos | idem |
| `/semana` · `/semana el lunes` | La semana natural de ese día, de lunes a domingo | idem |
| `/menu` | Botones: tocas uno, te pregunta, escribes. Para no teclear el comando | `handlers/menu.py` |
| `/hoy` · `/hoy ayer` · `/hoy 2026-09-03` | Diario, citas, tareas y hábitos juntos. **Solo lee** | `hugin.personal.diario.leer_entrada` + `hugin.personal.{citas,tareas,habitos}` |
| *(cualquier texto sin comando)* | Se le pregunta primero a `hugin.personal.entender`; si no reconoce nada con seguridad, se apunta en el diario de hoy, igual que `/diario` | `hugin.personal.entender` + `hugin.personal.diario.organizar_texto` |

Los dos primeros, y el texto suelto, escriben dentro de la sección "Qué ha
pasado hoy", con la hora delante, sin pisar lo que ya hubiera. Lo único que
cambia es el día.

**`/siento`, `/aprendo` y `/plan` escriben en las otras tres secciones.** De
las cuatro de la plantilla, «Qué ha pasado hoy» está rellena el 100 % de los
días y las otras entre el 30 y el 40 %: la diferencia es que en la primera
escribe el bot y en las otras había que abrir un editor. Con esto la entrada
del día se relee entera —qué hiciste, cómo estabas, qué aprendiste y qué
queda— en vez de todo amontonado en un solo apartado.

**Escribir sin comando es lo normal.** El handler de texto libre se registra
el último, así que los comandos mandan. Sin él, mandar «hoy he dormido fatal»
dejaba al bot callado y el texto se perdía.

**Y no se traga comandos.** «Lo que Telegram marca como comando» no es lo
mismo que «lo que empieza por `/`»: un comando **pegado con formato de
código** llega sin la marca `bot_command` y caía aquí. El 2026-09-05 se
fueron treinta comandos seguidos al diario en vez de ejecutarse, sin un solo
aviso. Ahora, cualquier texto que empiece por `/` se rechaza con un aviso que
además lo devuelve, para reenviarlo sin reescribirlo.

Las respuestas son cortas a propósito: `📔 Apuntado en el diario de hoy ·
subido`. Antes cada escritura devolvía la ruta completa del fichero en el
disco de Madre, que servía para depurar y en el móvil solo estorba. Los
avisos sí salen enteros: si el push falla, hay que leerlo.

Todo lo que escribe cualquier comando se commitea y se sube con
`hugin.guardado.sincronizar`: el diario con su mensaje de siempre, las
tareas, las citas y los hábitos con el suyo. `/hoy` no escribe nada, así que
no sube nada.

**El menú de «/»** sale de la lista `MENU` de `bot.py`, publicada con
`setMyCommands` al arrancar. Un comando nuevo se añade ahí y aparece solo; si
Telegram no contesta, se registra el fallo y el bot arranca igual.

## Pruebas

```bash
python3 -m unittest discover -s tests
```

179 pruebas de los handlers, en menos de tres segundos, sin red y sin
Telegram instalado: `tests/dobles.py` pone un `telegram` de mentira y un
diario en un temporal. Detalle en [`tests/README.md`](tests/README.md).

Entre ellas está la que impide que vuelva el bug del 2026-09-05: un texto que
empieza por `/` **nunca** se escribe en el diario. Y `test_menu.py` comprueba
que el menú de «/» y los comandos registrados no se separen.

Lo que las pruebas no pueden decir —que Telegram marque un mensaje como
comando, que lo desplegado sea este código, que el push llegue— sigue
necesitando probarlo a mano.

**Ninguna lógica vive aquí.** Los handlers traducen el mensaje de Telegram a
una llamada y la respuesta a texto; lo que decide qué se guarda y cómo está
en `hugin/personal/` y `hugin/apuntes.py` —el cerebro, en este mismo repo—,
con sus propias pruebas (ADR-009, ADR-024 fase 5, y la regla de arquitectura
de `plan-bot.md` en midgaror). Por eso no hay base de datos en este repo: los
ficheros de verdad viven en el repo de datos del inquilino (`MIDGAROR_DATOS`
/ `INQUILINOS`, hoy `midgaror-diario`, ADR-025), no aquí.

## Seguridad

- **El token no se pega en ningún sitio.** Vive solo en el `.env`, que está en
  `.gitignore`. Si se filtra (un log pegado en un chat, una captura), se revoca
  desde `@BotFather` con `/revoke` y se pone el nuevo en el `.env`.
- Desde el 2026-09-04 el bot silencia el log de `httpx`, que imprimía la URL
  completa de cada petición, token incluido, unas seis veces por minuto.

## Autorización

`TELEGRAM_CHAT_ID` decide quién puede darle órdenes al bot. Acepta varios
separados por comas:

```
TELEGRAM_CHAT_ID=123456789
TELEGRAM_CHAT_ID=123456789,987654321
```

Los no autorizados **no reciben respuesta**. Es a propósito: contestarles
confirma que el bot existe.

**Cerrado por defecto.** Si la variable falta, está vacía o no tiene ni un id
válido, el bot **no responde a nadie** y lo dice con un `ERROR` en el log al
arrancar. Antes hacía lo contrario —respondía a todo el mundo, para no romper
una instalación al actualizar— y ese es el modo de fallo al revés: una errata
al copiar el id (una letra `O` donde va un cero) dejaba el bot **abierto**.
Un bot mudo se nota en un minuto; uno abierto puede tardar semanas, y para
entonces alguien ha escrito en el diario.

## Problemas conocidos

- El endurecimiento de la unidad de systemd (`ProtectSystem`, `ProtectHome`,
  `NoNewPrivileges`, `PrivateTmp` y el resto de `Protect*`/`Restrict*`) está
  descrito en `systemd/hugin-telegram.service` pero **no aplicado de verdad
  en Madre** desde el 2026-09-18: se quitó a mano para depurar un fallo que
  no tenía que ver con ellos y todavía no se ha vuelto a poner. Ver «Como
  servicio», sección «Qué hace la unidad».

## Documentación

- [HANDLERS.md](HANDLERS.md) - Documentación de cada handler
- [SCRIPTS.md](SCRIPTS.md) - Documentación de scripts
- [CONTEXT.md](CONTEXT.md) - Contexto y decisiones
- [AGENTS.md](AGENTS.md) - Instrucciones para agentes AI
- [docs/sesiones/](docs/sesiones/) - Registro de sesiones
