# Handlers de Bifrost

Un handler traduce el mensaje de Telegram a una llamada a midgaror y la
respuesta a texto. **Ninguna lógica vive aquí** (ADR-009): lo que decide qué
se guarda y cómo está en `midgaror/diario/`, con sus pruebas.

Todos siguen el mismo patrón: `AYUDA` con los usos, `try` alrededor de la
llamada, `ValueError` → `⚠️ <mensaje>` (error del usuario, se le dice qué
escribir), cualquier otra excepción → log completo y `❌ Error:` (fallo
nuestro). Lo que escribe sube con `sincronizar()`, y la confirmación se acorta
con `utils/respuestas.breve()`.

Esa subida va **siempre** por `await asyncio.to_thread(sincronizar, …)`, nunca
llamando a `sincronizar()` a pelo. `sincronizar()` hace `git commit` y
`git push`, que con mala red tarda hasta 90 segundos, y es código síncrono: si
se llama dentro de una corrutina bloquea el bucle de eventos entero, es decir,
el bot deja de responder **a todos los chats** mientras dura, no solo a quien
mandó el mensaje. `to_thread` lo saca a un hilo aparte y el bucle sigue
atendiendo lo demás. Un handler nuevo que escriba algo tiene que hacerlo igual.

## Cómo se importa midgaror

Por [`utils/midgaror.py`](utils/midgaror.py), y solo por ahí:

```python
from utils.midgaror import modulo
from utils.respuestas import breve, responder

tareas = modulo("tareas")
sincronizar = modulo("sincronizar").sincronizar
```

Bifrost es un submódulo dentro de midgaror y no se instala, así que el diario
se importa por ruta. Antes cada handler repetía el mismo preámbulo —subir
cuatro niveles con `Path(__file__).resolve()`, uno o dos `sys.path.insert`, y
los imports con `# noqa: E402` por quedar debajo de código—: ocho ficheros con
las mismas líneas y ningún sitio donde arreglarlo una vez. Ahora lo hace
`utils/midgaror.py` al importarse, y no queda ni un `# noqa: E402` en
`handlers/`.

Lo que sale de `modulo(...)` se asigna a un **nombre de módulo**, nunca dentro
de una función. Es lo que permite que `tests/dobles.py` sustituya `sincronizar`
handler por handler para que las pruebas no hagan `git push` de verdad; si se
importara dentro de la corrutina, ese doble dejaría de aplicarse y las pruebas
empezarían a escribir en el repo.

---

## `/menu` — los botones

**Módulo**: `handlers/menu.py` → los handlers de los demás comandos

| Botón | Qué hace |
|---|---|
| 📔 Diario · 💬 Me siento · 💡 Aprendo · 🌅 Mañana | pregunta, y lo que escribas va a su sección |
| 📋 Tarea · 📅 Cita · 🔁 Hábito | pregunta, y lo que escribas es lo que irías detrás del comando |
| 👁 Hoy · 📋 Tareas · 📅 Agenda · 🔁 Hábitos | se ejecutan al tocarlos |
| 📝 Apunte | pregunta, y lo que escribas es lo que iría detrás de `/apunte` |
| 📊 Día · 📆 Semana | se ejecutan al tocarlos |

Existe porque **tocar un comando en el menú «/» de Telegram lo envía tal
cual**, sin dejar escribir texto detrás: `/siento` llega vacío y el bot
contesta con la ayuda. No es un fallo nuestro y no tiene arreglo desde ese
menú.

Cómo va por dentro, en tres pasos:

1. `/menu` manda «¿Qué apuntamos?» con un `InlineKeyboardMarkup`. Cada botón
   lleva su clave (`siento`, `tarea`…) en el `callback_data`.
2. Tocar un botón llega como `callback_query`. Los de mirar ejecutan el
   handler del comando con `context.args = []`. Los de escribir contestan con
   la pregunta del botón y un `ForceReply`, que **abre la caja de escribir
   solo** y pone el ejemplo en gris.
3. Lo que se escriba llega como **respuesta** a esa pregunta
   (`reply_to_message`). `respuesta_al_menu` mira qué pregunta era, parte el
   texto en argumentos y llama al handler del comando. Si la respuesta era a
   cualquier otra cosa, es texto libre y va al diario.

**No hay estado por chat: la pregunta misma es la clave.** Si se contesta a
una pregunta de hace tres días, se apunta igual. Y como cada botón acaba en el
mismo handler que su comando, lo que entiende `/tarea` («comprar el pan
mañana») lo entiende el botón, sin dos caminos que mantener.

Dos cosas que no se ven y hay que saber:

- **El filtro de chat no llega a los botones.** `filters.Chat` mira mensajes y
  un `callback_query` no lo es, así que `boton()` comprueba la autorización a
  mano con la misma lista del `.env`. Sin eso, cualquiera con un menú viejo
  entraría.
- `respuesta_al_menu` se registra **antes** del texto libre y **después** de
  los comandos. Si fuera después del texto libre, el texto libre se comería las
  respuestas; si fuera antes de los comandos, un `/hoy` escrito como respuesta
  no se ejecutaría.

---

## `/diario <texto>`

**Módulo**: `handlers/diario.py` → `organizar_texto()` de
`midgaror/diario/organizar_diario.py`

Inserta el texto en «Qué ha pasado hoy» de la entrada de hoy, con la hora
delante, sin pisar lo que ya hubiera.

---

## `/entrada <día> <texto>`

**Módulo**: `handlers/entrada.py` → `escribir_entrada()` de
`midgaror/diario/bifrost_bridge.py`

Lo mismo, en el día que se diga. Crea la entrada si no existe.

---

## *(texto sin comando)*

**Módulo**: `handlers/texto.py` → primero `diario/entender.py`; si no dice
nada, lo mismo que `/diario`

Se registra **el último** en `bot.py`, con `filters.TEXT & ~filters.COMMAND`,
así que los comandos mandan. Escribir sin comando es lo normal: es como se usa
el bot el 90 % de las veces.

Pero `~filters.COMMAND` **no** quiere decir «no empieza por `/`»: quiere decir
«Telegram no lo marcó como `bot_command`». Un comando pegado con formato de
código llega marcado como `code` y cae aquí. Por eso el handler rechaza todo
lo que empiece por `/` con un aviso, y lo devuelve para poder reenviarlo. La
alternativa —escribirlo en el diario— es tragarse un comando en silencio, que
es lo que pasó el 2026-09-05 treinta veces seguidas.

Antes de ir al diario, se le pregunta a `entender()` si en realidad es una
tarea, un hábito, una cita o un apunte. Con alta confianza, va a la misma
función que su comando —`tareas.agregar`, `agenda.agregar`, `habitos.marcar`,
`registro.apuntar`— y contesta con la misma confirmación que daría ese
comando. Con cualquier duda, sin `ANTHROPIC_API_KEY` puesta, o si la propia
frase es un diario de verdad, cae aquí abajo exactamente como siempre: esto
no puede hacer que un mensaje se pierda, en el peor caso dejar de reconocer
algo que antes tampoco reconocía nadie.

---

## *(nota de voz)*

**Módulo**: `handlers/voz.py` → `utils/voz.py` (Whisper) → `texto.procesar()`

Se descarga la nota, se transcribe **en local** con `faster-whisper`, se dice
lo que se ha oído, y a partir de ahí es un mensaje suelto de toda la vida:
mismo `procesar()` que el texto, así que puede acabar en una tarea, un
hábito, una cita, un apunte o el diario.

Lo transcrito se dice **siempre, antes de actuar**. Whisper se come tildes y
palabras sueltas, y esto escribe en un diario que no se relee línea a línea:
si oye mal, tiene que verse, no colarse callado.

Transcribir es CPU y tarda, así que va por `asyncio.to_thread` por el mismo
motivo que `sincronizar()`: dentro de la corrutina congelaría el bot para
**todos** los chats. Una nota de más de `DURACION_MAXIMA` (180 s) se rechaza
sin transcribirla. Sin `faster-whisper` instalado el bot arranca igual: solo
falla la nota de voz, y el mensaje dice el `pip` exacto que hay que usar —
que no es el que contesta a `pip` cuando hay más de un Python.

---

## *(recordatorios: lo único que habla sin que le hablen)*

**Módulo**: `handlers/recordatorios.py` → `diario/recordatorios.py`

Un bucle de `asyncio` que cada minuto pregunta qué citas empiezan dentro de
los próximos 30 minutos y no se han avisado. Arranca en `post_init` y se
cancela en `post_shutdown`.

Tres cosas aquí no son estilo, son lo que separa esto de convertirse en spam
o en silencio:

- **Se anota después de mandar**, y solo lo que llegó a alguien. Al revés, un
  fallo de Telegram daría la cita por avisada sin que nadie la leyera.
- **`avisar_una_vez()` no lanza nunca.** Quien la llama es un bucle infinito:
  una excepción ahí deja el bot mudo para siempre sin que nada lo diga.
- **La tarea se guarda en el módulo.** `asyncio.create_task` no guarda una
  referencia fuerte; sin guardarla, el recolector de basura puede llevarse el
  bucle a media ejecución.

---

## `/siento`, `/aprendo` y `/plan`

**Módulo**: `handlers/secciones.py` → `organizar_texto(..., seccion=...)` de
`midgaror/diario/organizar_diario.py`

| Mensaje | Va a | Cómo se ve |
|---|---|---|
| `/siento contento, he dormido bien` | `## Cómo me siento` | con la hora delante |
| `/aprendo lo de filters.COMMAND` | `## Avances / aprendizajes` | como viñeta |
| `/plan seguir con el portfolio` | `## Para mañana` | como viñeta |

**Por qué existen.** De las cuatro secciones de la plantilla, «Qué ha pasado
hoy» está rellena el 100 % de los días y las otras tres entre el 30 y el
40 %. La diferencia no es la disciplina: es que en la primera escribe el bot
y en las otras hay que abrir un editor (ADR-012, apartado 5).

**Por qué `/plan` y no `/mañana`.** Los comandos de Telegram solo admiten
`a-z`, `0-9` y `_`: con eñe no llegan marcados como comando.

La hora o la viñeta no las decide este handler: están en
`organizar_diario.SECCIONES`, con el resto de la lógica.

---

## `/tarea` y `/tareas`

**Módulo**: `handlers/tarea.py` → `midgaror/diario/tareas/tareas.py`

| Mensaje | Qué hace |
|---|---|
| `/tarea comprar el pan` | apunta una tarea sin fecha |
| `/tarea médico mañana a las 10` | apunta con fecha: la saca del texto con `fechas.py` |
| `/tarea empezar 3` | la pone en proceso (`◐`) |
| `/tarea hecha 3` · `/tarea reabrir 3` | la cierra o la devuelve a pendiente |
| `/tarea editar 3 comprar pan y leche` | le cambia el texto (y la fecha, si el texto nuevo la trae) |
| `/tarea aplazar 3 el lunes por la tarde` | le cambia solo la fecha |
| `/tarea borrar 3` | la retira; no se elimina, los ids no se reutilizan |
| `/tareas` | en proceso, pendientes por fecha (`⚠️ vencida` las pasadas) y últimas hechas |

Las acciones están en dos diccionarios, `SOLO_ID` y `CON_TEXTO`: añadir una
es añadir una línea, no otro `if`.

---

## `/cita` y `/agenda`

**Módulo**: `handlers/cita.py` → `midgaror/diario/agenda/agenda.py`

| Mensaje | Qué hace |
|---|---|
| `/cita médico mañana a las 10` | apunta una cita |
| `/cita mover 3 el lunes a las 17` | la cambia de día u hora |
| `/cita cancelar 3` | la retira |
| `/agenda` · `/agenda 2026-09-06` | las citas de un día |
| `/agenda semana` | los siete días desde hoy, agrupados por día |

**Una cita siempre lleva cuándo**; eso es lo que la separa de una tarea. Si el
texto no lo dice, se avisa y no se guarda nada. Sin hora, la cita es de todo
el día. Si el horario se pisa con otra, **se guarda igual y se avisa debajo**:
dos cosas a la misma hora pasan, y quien decide es Álvaro.

---

## `/habito` y `/habitos`

**Módulo**: `handlers/habito.py` → `midgaror/diario/habitos/habitos.py`

| Mensaje | Qué hace |
|---|---|
| `/habito deporte` · `/habito no meditar` | hecho o no hecho hoy |
| `/habito Leer Libro` | el nombre puede llevar espacios |
| `/habito energia 7` | un valor del 1 al 10 en vez del sí o no |
| `/habito deporte 2026-09-03` | en otro día |
| `/habito Beber agua 3 2026-09-03` | nombre compuesto, valor y fecha a la vez |
| `/habitos` · `/habitos semana` | el día, o la semana con totales y medias |

El final del mensaje se lee **por descarte**, y en este orden: del final se
quita la fecha si lo es —«ayer», «antes de ayer», «el lunes», `AAAA-MM-DD`;
se prueba primero el trozo más largo, y siempre dejando algo para el nombre—;
el siguiente por la cola es el valor solo si es un entero **y queda algo
detrás para el nombre**; todo lo que sobra es el nombre, unido con espacios.
Una fecha escrita con números que `fechas.py` no entienda («2026-13-45») da
aviso en vez de convertirse en un hábito llamado así.

Tiene que ser por descarte porque el nombre puede llevar espacios y Telegram
entrega los argumentos ya partidos: no hay manera de saber dónde acaba el
nombre si no es mirando qué forma tiene lo que viene después. Leer siempre el
último argumento como fecha es lo que hacía que `/habito Leer Libro` muriera
con «fecha no válida: 'Libro'».

El efecto secundario, a propósito: una fecha mal escrita que no tenga forma de
fecha (`/habito deporte ayer`) ya no da error, se convierte en parte del
nombre (`deporte-ayer`). Es el precio de admitir nombres de varias palabras, y
sale barato: el hábito raro se ve en `/habitos` del mismo día.

---

## `/apunte`, `/dia` y `/semana`

**Módulo**: `handlers/apunte.py` → `midgaror/diario/registro/registro.py`

El modelo del [ADR-012](https://github.com/alvarofernandezmota-tech/midgaror/blob/main/docs/adr/012-modelo-de-registro-diario.md).
Un **apunte** es un evento, no una casilla: `tele 3h`, `deporte`, `agua 1,5l`.

| Mensaje | Qué hace |
|---|---|
| `/apunte deporte` | hecho, sin cantidad |
| `/apunte tele 3h` | cantidad y unidad pegadas |
| `/apunte agua 1,5 l` | o separadas |
| `/apunte ver la tele 2h` | el nombre puede llevar espacios |
| `/apunte tele 1h ayer` | en otro día, dicho en español |
| `/dia` · `/dia ayer` | lo apuntado ese día, contra sus objetivos |
| `/semana` · `/semana el lunes` | la semana natural de ese día, de lunes a domingo |

Tres reglas que vienen del ADR y que conviene no perder de vista:

- **Varios apuntes del mismo día se suman al leer**, no se pisan. Dos ratos de
  tele son dos apuntes; el total lo calcula `/dia`.
- **Los totales no se guardan.** En disco solo hay apuntes; `/dia` y `/semana`
  son informes que se calculan al mostrar (apartado 6).
- **La dirección la pone el objetivo, no el nombre.** `ejercicio` es «al menos
  3 h/semana» y `tele` es «como mucho 7 h/semana». El programa no clasifica
  nada como bueno o malo.

Eso último se ve en cómo se pinta: el icono sale del **objetivo**, no de la
cosa. Un `al_menos` sin cumplir es ⏳ («te falta»), no ❌; un `como_mucho`
pasado sí es ❌; cumplido es ✅ en los dos casos. Sin objetivo no hay icono de
juicio, solo el dato: `· tele 5 h`.

El mensaje se lee **por descarte**, igual que `/habito` y por el mismo motivo
—el nombre puede llevar espacios y Telegram entrega los argumentos ya
partidos—: primero la fecha desde el final, luego la cantidad (`3h`, `1,5l`,
`30min`, o el número y la unidad sueltos), y lo que sobra es el nombre.
Siempre queda al menos una palabra de nombre, así que `/apunte 7` apunta una
cosa llamada «7» y no un valor suelto sin nada a lo que pegarse.

La semana es la **natural**, de lunes a domingo, y no los siete días
anteriores a hoy: un objetivo de «3 h/semana» se cuenta sobre una semana del
calendario, que es la que uno tiene en la cabeza al mirarlo un miércoles.

Lo que **no** hay todavía: fijar objetivos desde Telegram. `fijar_objetivo()`
existe en el módulo pero no tiene comando, así que hoy los objetivos se ponen
a mano en `diario/registro/datos/objetivos.json`.

---

## Las fechas, en español

Desde el 2026-09-06 ningún comando exige `AAAA-MM-DD`: donde iba una fecha
vale «ayer», «antes de ayer», «hace 3 días», «el lunes», «el 15 de octubre»,
«04/09/2026» o la fecha entera. Lo resuelve `diario/fechas.py` de midgaror;
los handlers solo le pasan el trozo que toca. Tres reglas:

| Dónde | Qué se lee | Sentido |
|---|---|---|
| `/hoy`, `/habito`, `/habitos`, `/entrada` | el argumento de fecha | **hacia atrás**: «el lunes» es el que ya pasó, porque un día se revisa y un hábito se apunta después |
| `/agenda`, `/tarea`, `/cita` | el argumento o la fecha dentro del texto | **hacia delante**: la agenda se mira para lo que viene |
| `/diario`, `/siento`, `/aprendo`, `/plan`, texto suelto | **solo una fecha pasada al final** | «cené con Ana ayer» va a ayer, sin el «ayer» |

La tercera es la que hay que tener clara. En el diario **el futuro no es una
fecha, es parte de lo que se cuenta**: «tengo examen mañana» es una frase de
hoy y se queda entera en hoy. Y lo ambiguo tampoco cuenta: «quedo con Ana el
lunes» se queda en hoy, porque leído hacia atrás se iría a la semana pasada.
Solo cortan «ayer», «antes de ayer», «hace N días» y una fecha completa; la
hora se queda en la frase («cené a las 10 ayer» corta «ayer» y deja «a las
10»). Para un día ambiguo está `/entrada el lunes fui al médico`, con la
fecha delante y a posta.

Cuando lo escrito fue a otro día, la confirmación lo dice: «📔 Apuntado en el
diario **del 2026-09-05**» en vez de «de hoy».

---

## `/hoy`

**Módulo**: `handlers/hoy.py` → `leer_entrada` + `agenda` + `tareas` + `habitos`

`/hoy [ayer | el lunes | AAAA-MM-DD]` junta en un mensaje el diario del día, las citas, las
tareas y los hábitos. **Solo lee**: si no hay entrada, lo dice en vez de
crearla, y no sube nada. Si el mensaje entero no cabe, lo recorta
`utils/limites.py`, como cualquier otra respuesta del bot.

---

## `/start` y `/help`

**Módulo**: `bot.py` — son los dos únicos comandos que no tienen handler
propio, porque no tocan el diario ni ningún modelo: solo contestan texto.

| Mensaje | Qué hace |
|---|---|
| `/start` | el saludo de bienvenida, lo que Telegram manda al abrir el chat |
| `/help` | la ayuda entera, comando por comando, con ejemplos literales |

`/start` **no va en `MENU`** a propósito: Telegram ya lo ofrece solo al abrir
la conversación, y repetirlo en la lista de «/» solo gasta un hueco. Es la
única excepción, y `tests/test_menu.py` la tiene escrita como tal
(`FUERA_DEL_MENU`), para que la prueba que exige que todo lo de `MENU` tenga
handler no la cuente como un olvido.

`/help` sí está en `MENU`, y hay una prueba que exige que **cada botón del
menú tenga su comando explicado ahí** (`test_botones.py`). Es la que cazó que
faltaba `/apunte` cuando se añadió.

Los dos van con `filters=autorizado`, como el resto: la ayuda no se le enseña
a quien no puede usar el bot.

---

## El menú de comandos

`bot.py` publica la lista `MENU` con `setMyCommands` al arrancar
(`post_init=registrar_menu`): es lo que sale al pulsar «/» en el chat. Un
comando nuevo se añade ahí y aparece solo. Si Telegram no contesta, se
registra el fallo y **el bot arranca igual**: quedarse sin bot por no poder
pintar una lista sería peor.

---

## El límite de Telegram

**Todo lo que sale del bot pasa por `responder(update, texto)`**
(`utils/respuestas.py`). Es un punto único a propósito: había 47 llamadas
sueltas a `reply_text`, cualquiera podía pasarse de los 4096 de Telegram, y
algunas ni siquiera estaban dentro de un `try` — así que el error no llegaba
al usuario, se quedaba en el log.

`utils/limites.py` mide en **unidades UTF-16, como hace Telegram**, no con
`len()`: `📅` mide 1 para Python y 2 para Telegram, y hay una banda real
donde `len()` dice que cabe y Telegram lo rechaza. Recorta por **líneas
enteras** y dice cuántas faltan (`… y 92 líneas más`), porque una tarea
cortada por la mitad pierde su id, que es el asa para actuar sobre ella. Y
conserva las primeras, que el dominio ya ordena por urgencia.

Medido el 2026-09-05, antes del arreglo: `/hoy` reventaba con **29 tareas
pendientes**, `/tareas` con 81, `/agenda semana` con 126 citas y
`/habitos semana` con 68 hábitos. Cuando pasaba, el bot contestaba
`❌ Error: Message is too long` y ese comando quedaba inservible hasta
limpiar la lista.
