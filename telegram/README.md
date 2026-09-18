# Bifrost

Bot de Telegram para escribir y organizar entradas del diario personal.

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

bifrost/
├─ bot.py # Punto de entrada del bot
├─ handlers/
│ ├─ _init_.py
│ ├─ diario.py # /diario → organizar_texto()
│ ├─ entrada.py # /entrada → escribir_entrada()
│ ├─ secciones.py # /siento, /aprendo, /plan → secciones del diario
│ ├─ tarea.py # /tarea, /tareas → diario/tareas/tareas.py
│ ├─ cita.py # /cita, /agenda → diario/agenda/agenda.py
│ ├─ habito.py # /habito, /habitos → diario/habitos/habitos.py
│ ├─ hoy.py # /hoy → leer_entrada + citas + tareas + hábitos
│ ├─ apunte.py # /apunte, /dia, /semana → diario/registro/registro.py
│ ├─ menu.py # /menu → botones que preguntan y enrutan al handler del comando
│ ├─ texto.py # mensaje sin comando → entender() y, si no, diario de hoy
│ ├─ voz.py # nota de voz → Whisper → el mismo camino que el texto
│ └─ recordatorios.py # avisa de una cita sin que nadie pregunte (ADR-020)
├─ utils/
│ ├─ auth.py # autorización por chat_id
│ ├─ limites.py # el tope de 4096 de Telegram, contado como lo cuenta Telegram
│ ├─ midgaror.py # dónde está midgaror y cómo se importan sus módulos
│ ├─ respuestas.py # cómo se contesta: breve si va bien, entero si falla
│ └─ voz.py # Whisper en local: audio → texto
├─ venv/ # Entorno virtual (NO commitear)
├─ .env # Token y chat_id (NO commitear)
├─ .env.example # Plantilla
├─ .gitignore
├─ AGENTS.md
├─ CONTEXT.md
├─ HANDLERS.md
├─ README.md
├─ SCRIPTS.md
└─ docs/
└─ sesiones/

text

## Dónde tiene que vivir este repo

**Importante:** bifrost no funciona clonado por su cuenta.
[`utils/midgaror.py`](utils/midgaror.py) busca el diario cuatro niveles por
encima de `utils/`, así que el repo tiene que estar en
`midgaror/proyectos/bifrost`, que es donde lo pone el submódulo. Clonado en
otro sitio, los imports de `midgaror/diario/` fallan al arrancar. Ese fichero
es el único que lo sabe: si algún día bifrost se instala como paquete, es el
único que hay que tocar.

```bash
cd ~/GitHub/personal/midgaror     # o donde tengas midgaror
git submodule update --init --recursive
cd proyectos/bifrost
```

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

5. **Probar la escritura sin el bot**, para separar los fallos del diario de
   los de Telegram:

   ```bash
   cd ../..                      # raíz de midgaror
   python3 diario/organizar_diario.py --input "prueba desde terminal"
   python3 diario/bifrost_bridge.py escribir "prueba con fecha" --fecha 2026-09-04
   git diff diario/personal/     # mirar qué ha escrito
   ```

   Si esto falla, el problema está en midgaror, no en el bot.

6. **Arrancar el bot en primer plano.** Si el servicio está vivo en esta
   máquina, **párralo antes**: dos instancias con el mismo token se pelean por
   los mensajes y Telegram devuelve `409 Conflict` a las dos.

   ```bash
   sudo systemctl stop bifrost     # si el servicio está instalado aquí
   cd proyectos/bifrost
   source venv/bin/activate
   python3 bot.py
   ```

   Los mensajes de arranque salen por pantalla. Se para con `Ctrl+C`, y el
   servicio se vuelve a levantar con `sudo systemctl start bifrost`.

7. **Probar desde Telegram**, en este orden:

   | Mensaje | Qué debe pasar |
   |---------|----------------|
   | `/start` | Responde con la bienvenida |
   | `/help` | Responde con la ayuda |
   | `/diario probando hoy` | Escribe en la entrada de hoy y responde con la ruta |
   | `/entrada 2026-09-01 probando una fecha` | Escribe en la entrada de ese día |
   | `/entrada 01-09-2026 mal` | Responde que la fecha es inválida |
   | `/entrada 2026-09-01` | Responde con el uso correcto |

8. **Comprobar y guardar lo escrito**, desde la raíz de midgaror:

   ```bash
   git log -1 --stat
   ```

   El bot escribe, commitea y sube él solo (`diario/sincronizar.py`), así que
   lo que hay que mirar es el último commit, no el working tree: si el push
   falló, la respuesta del bot lo dice («⚠️ commiteado en local, sin subir»).

## Uso diario

El bot corre como servicio: no hay que arrancarlo a mano.

```bash
systemctl status bifrost           # ¿está vivo?
journalctl -u bifrost -f           # ver qué hace, en vivo
sudo systemctl restart bifrost     # tras cambiar código o .env
```

Para arrancarlo a mano (depurar), **para antes el servicio**: dos instancias
con el mismo token se pelean por los mensajes y Telegram devuelve `409
Conflict` a las dos.

```bash
sudo systemctl stop bifrost
cd ~/GitHub/personal/midgaror-bot/proyectos/bifrost
source venv/bin/activate
python3 bot.py
```

## Como servicio

Para que el bot no dependa de una terminal abierta. La unidad está en
[`systemd/bifrost.service`](systemd/bifrost.service).

La unidad apunta a **`~/GitHub/personal/midgaror-bot`**, una copia del repo
que es solo del bot y está siempre en `main`, no a la copia de trabajo. Un
`git checkout` mientras el servicio está vivo le cambiaría el diario, la rama
a la que commitea y el código que carga al reiniciar. Cómo montarla:
[`docs/infra/bifrost.md`](https://github.com/alvarofernandezmota-tech/midgaror/blob/main/docs/infra/bifrost.md),
sección «El bot tiene su propia copia del repo».

**Antes de instalarla**, comprueba que las rutas del fichero coinciden con
las tuyas. Llevan `varopc` y `~/GitHub/personal/midgaror-bot` escritos dentro:

```bash
grep -E "User=|WorkingDirectory=|ExecStart=|ReadWritePaths=" systemd/bifrost.service
```

Instalación:

```bash
sudo cp systemd/bifrost.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bifrost
```

Comprobación:

```bash
systemctl status bifrost
journalctl -u bifrost -n 30 --no-pager
```

En el arranque debe aparecer `Bot en marcha` y, si tienes puesto el chat_id,
`Autorizacion activa para 1 chat(s)`. Si en su lugar sale el aviso de que
no te responde a ti, mira el log: si dice «no tiene ni un id valido», el
`TELEGRAM_CHAT_ID` del `.env` falta o tiene una errata.

### Comandos del día a día

```bash
sudo systemctl restart bifrost     # tras cambiar código o .env
sudo systemctl stop bifrost        # pararlo
journalctl -u bifrost -f           # ver el log en vivo
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
  unidad.
- **Solo puede escribir dentro del repo midgaror.** El resto del disco lo ve
  de solo lectura. Tiene que ser el repo entero y no solo `diario/personal/`,
  porque al commitear git escribe en `.git/`, que está en la raíz.

### Dónde vive y qué toca

Todo lo del servicio vive en **`midgaror-bot`**, la copia que es solo del bot
y está siempre en `main`. La copia de trabajo (`midgaror/`) no corre el
servicio: es donde editas.

| Cosa | Dónde |
|------|-------|
| Código | `~/GitHub/personal/midgaror-bot/proyectos/bifrost/` |
| Entorno virtual | `proyectos/bifrost/venv/` |
| Token y chat_id | `proyectos/bifrost/.env` (nunca se commitea) |
| Unidad | `/etc/systemd/system/bifrost.service` |
| Lo que escribe | `~/GitHub/personal/midgaror-bot/diario/personal/AAAA/MM-mes/AAAA-MM-DD.md` |
| Logs | `journalctl -u bifrost` |
| Lógica del diario | `~/GitHub/personal/midgaror-bot/diario/` (no está en este repo) |

El bot **escribe, commitea y sube** él solo, con `diario/sincronizar.py`: una
entrada mandada desde Telegram está en GitHub en segundos. Por eso el permiso
de escritura tiene que cubrir el repo entero y no solo `diario/personal/` —
git escribe en `.git/`, que está en la raíz.

Cuando el push falla (sin red), la respuesta del bot lo dice en claro:
«⚠️ commiteado en local, sin subir». El commit está hecho; falta el push.

### Comprobar que no se muere

Instalarlo no demuestra nada. Estas cuatro pruebas sí, y son la fase 2b:

**1. Que resucita si lo matan**

Dos formas de morir, y tiene que volver de las dos:

```bash
sudo systemctl kill bifrost              # SIGTERM: el bot lo captura y sale limpio
sleep 15; systemctl is-active bifrost    # -> active

sudo systemctl kill -s SIGKILL bifrost   # muerte súbita, sin tiempo a nada
sleep 15; systemctl is-active bifrost    # -> active
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
systemctl is-enabled bifrost    # -> enabled
systemctl is-active bifrost     # -> active
```

Y lo que de verdad importa: escríbele por Telegram y comprueba que responde
sin que hayas tocado nada.

**3. Que aguanta un corte de red**

En una máquina a la que llegas por SSH, **no pares la red**: te quedas fuera.
La forma segura es esperar a que pase de verdad y mirarlo después:

```bash
systemctl show bifrost -p NRestarts
journalctl -u bifrost --since "1 day ago" | grep -iE "error|restart|network"
```

Si `NRestarts` sube solo, el bot se está muriendo por algo. Si sube y vuelve
solo, la unidad está cumpliendo.

**4. Que no se descuadra escribiendo**

Después de unos días de uso:

```bash
cd ~/GitHub/personal/midgaror
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
journalctl -u bifrost -n 20 --no-pager
```

Se arregla recreando el entorno y reiniciando el servicio.

## Comandos

| Comando | Descripción |
|---------|-------------|
Los ejemplos son literales: se escribe lo que se ve, **sin `<` ni `>`**. La
ayuda anterior los llevaba y se escribieron tal cual dos veces en el diario.

| Comando | Qué hace | Lógica en midgaror |
|---------|----------|--------------------|
| `/start` | Bienvenida con los comandos del día a día | — |
| `/help` | Ayuda completa | — |
| `/diario hoy he dormido fatal` | Añade el texto a la entrada de **hoy** | `diario/organizar_diario.py` |
| `/diario cené con mi hermana ayer` | Con «ayer» al final, a la entrada de **ayer**. Solo el pasado: «tengo examen mañana» se queda en hoy | idem |
| `/entrada ayer se me olvidó esto` · `/entrada 2026-09-03 …` | Lo mismo en **ese día**: ayer, antes de ayer, el lunes (el que pasó), hace 3 días o la fecha | `diario/bifrost_bridge.py` |
| `/siento contento, he dormido bien` | A **«Cómo me siento»**, con la hora | `diario/organizar_diario.py` |
| `/aprendo lo de filters.COMMAND` | A **«Avances / aprendizajes»**, como viñeta | idem |
| `/plan seguir con el portfolio` | A **«Para mañana»**, como viñeta | idem |
| `/tarea comprar el pan` | Apunta una tarea | `diario/tareas/tareas.py` |
| `/tarea médico mañana a las 10` | Con fecha: la saca del texto | idem + `diario/fechas.py` |
| `/tarea empezar 3` · `/tarea hecha 3` · `/tarea reabrir 3` | La mueve de estado | idem |
| `/tarea editar 3 …` · `/tarea aplazar 3 …` | Le cambia el texto o la fecha | idem |
| `/tarea borrar 3` | La retira | idem |
| `/tareas` | En proceso, pendientes por fecha y últimas hechas | idem |
| `/cita médico mañana a las 10` | Apunta una cita; avisa si choca con otra | `diario/agenda/agenda.py` |
| `/cita mover 3 …` · `/cita cancelar 3` | La cambia de hora o la retira | idem |
| `/agenda` · `/agenda semana` | Las citas del día o de los siete días | idem |
| `/habito deporte` · `/habito no meditar` | Apunta un hábito de hoy | `diario/habitos/habitos.py` |
| `/habito Leer Libro` | El nombre puede llevar espacios | idem |
| `/habito energia 7` | Un valor del 1 al 10 | idem |
| `/habito deporte ayer` · `/habito deporte 2026-09-03` | En otro día, dicho en español o con la fecha | idem |
| `/habito Beber agua 3 2026-09-03` | Nombre compuesto, valor y fecha | idem |
| `/habitos` · `/habitos semana` | El día, o la semana con totales y medias | idem |
| `/apunte deporte` · `/apunte tele 3h` · `/apunte agua 1,5l` | Apunta un evento del día, sin cantidad, con cantidad y unidad pegadas, o separadas | `diario/registro/registro.py` |
| `/apunte tele 1h ayer` | En otro día, dicho en español | idem |
| `/dia` · `/dia ayer` | Lo apuntado ese día, contra sus objetivos | idem |
| `/semana` · `/semana el lunes` | La semana natural de ese día, de lunes a domingo | idem |
| `/menu` | Botones: tocas uno, te pregunta, escribes. Para no teclear el comando | `handlers/menu.py` |
| `/hoy` · `/hoy ayer` · `/hoy 2026-09-03` | Diario, citas, tareas y hábitos juntos. **Solo lee** | `leer_entrada` + los tres módulos |
| *(cualquier texto sin comando)* | Se apunta en el diario de hoy, igual que `/diario` | `diario/organizar_diario.py` |

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
`diario/sincronizar.py`: el diario con su mensaje de siempre, las tareas, las
citas y los hábitos con el suyo. `/hoy` no escribe nada, así que no sube nada.

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
en midgaror, con sus pruebas (ADR-009 y la regla de arquitectura de
`plan-bot.md`). Por eso no hay base de datos en este repo.

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

Lo
avisa en el log al arrancar. Se dejó así para no romper una instalación al
actualizar, pero es un aviso, no una opción recomendable: este bot escribe en
tu diario.

## Problemas conocidos

- Corre en primer plano: aún no es servicio de systemd (fase 2b del plan).

## Documentación

- [HANDLERS.md](HANDLERS.md) - Documentación de cada handler
- [SCRIPTS.md](SCRIPTS.md) - Documentación de scripts
- [CONTEXT.md](CONTEXT.md) - Contexto y decisiones
- [AGENTS.md](AGENTS.md) - Instrucciones para agentes AI
- [docs/sesiones/](docs/sesiones/) - Registro de sesiones
