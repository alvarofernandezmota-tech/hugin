---
tipo: decision
fecha: 2026-09-18
repo: midgaror
etiquetas: [bifrost, gjallarhorn, hugin, arquitectura, multiinquilino, propuesta]
relacionado: [docs/adr/009-bifrost-bridge-diario.md, docs/adr/019-cerebro-de-gjallarhorn-en-hugin.md, docs/adr/023-diario-en-postgres.md]
---

> **Portado el 2026-09-19** desde
> [midgaror](https://github.com/alvarofernandezmota-tech/midgaror/blob/main/docs/adr/024-un-cerebro-dos-puertas.md),
> copia verbatim. El texto dice «de la fase 3 en adelante, sin empezar» y
> «hay que decidir cuál manda antes de mover nada» sobre el punto 4 (dos
> capas de entender) — en hugin ese trabajo ya está más avanzado de lo que
> este ADR registra: `personal/` existe con sus cuatro modelos portados, y
> `docs/adr/025-fusion-mente-personal.md` recoge la decisión sobre ese punto
> 4 con el estado real a 2026-09-19. Esta copia no se edita; la nota de
> estado va en `docs/adr/README.md` de hugin.

# ADR-024: Un cerebro y dos puertas — bifrost sobre hugin

**Estado: en marcha.** Las fases 1 y 2 están hechas y fusionadas
(`alvarofernandezmota-tech/hugin#1`, 2026-09-18): el producto ya vive en un
repo, con el cerebro en `hugin/` y las dos puertas dentro, empaquetado y con
una sola orden que corre las tres suites. **Nada de eso toca producción
todavía**: el bot sigue arrancando desde `midgaror-bot/proyectos/bifrost` y
sigue importando el diario de midgaror. De la fase 3 en adelante, sin
empezar.

## Contexto

La idea, dicha por Álvaro: que esto sirva igual para una persona sola que
para una empresa, y que sea **una sola cosa**, no dos productos parecidos.

Hoy hay dos bots que se parecen y no comparten casi nada:

| | bifrost | gjallarhorn |
|---|---|---|
| Canal | Telegram | teléfono (Whisper + Piper) |
| Cerebro | `diario/entender.py` y `diario/conversar.py`, en midgaror | `hugin` |
| Datos | los cuatro modelos del diario, ahora en Postgres (ADR-023) | `negocios/<cliente>/`, carpeta por cliente |
| Inquilinos | uno: Álvaro | varios, y dar de alta es copiar una carpeta |

Lo importante es que **la arquitectura que se quiere ya existe, y está en
gjallarhorn**: `telefono/` es solo el canal, `negocios/` son los datos de
cada cliente y `hugin` es el cerebro que no sabe por dónde le hablan
(ADR-019). El que va por libre es bifrost, que tiene su lógica dentro de
midgaror y no toca hugin.

## Decisión

**Un repo, y es el de hugin.** El producto entero vive donde hoy vive el
cerebro, y las dos puertas entran dentro como adaptadores:

```
hugin/                 el repo, que pasa a ser el producto
├── hugin/             el cerebro: sin un solo import de canal
├── telegram/          lo que hoy es bifrost
├── telefono/          lo que hoy es gjallarhorn
├── inquilinos/        una carpeta por persona o empresa
└── tests/
```

`bifrost` y `gjallarhorn` quedan archivados con un README que apunta aquí.
`midgaror` vuelve a ser lo que dice ser —documentación, infraestructura,
formación y lo que Álvaro escribe a mano— y deja de ser dependencia de
producción de nadie.

Y **un inquilino deja de ser «un negocio» para ser «alguien a quien se
atiende»**, que puede ser una empresa o una persona. Es el cambio que hace
verdad la frase «lo mismo sirve para los dos».

### Por qué un repo y no tres

La primera versión de este ADR decía lo contrario: que los repos se quedaban
separados, porque meter hugin dentro de un bot rompería su regla de no
importar canales. **Eso era un error de razonamiento.** Esa regla la sujeta
`tests/test_libreria.py`, que lee el árbol de sintaxis de cada módulo del
cerebro y se cae si aparece un canal. La prueba sigue valiendo igual dentro
de un repo común: el límite es el import, no la frontera del repositorio.

Lo que sí pesa, y no se estaba pesando: **todo lo que viene es cirugía entre
repos.** Llevar los modelos personales al cerebro, cambiar el cerebro y
adaptar el teléfono, quitar el submódulo — cada paso son commits coordinados
en tres sitios con un submódulo en medio. En un repo son refactors normales.
Para una persona sola haciendo justo este trabajo, tres repos son coste sin
contrapartida: nadie más reutiliza hugin.

Se elige el repo de hugin y no el de bifrost porque hugin es el núcleo y el
único que no cambia de papel: conserva su historial y sus 356 pruebas, y el
producto no acaba llamándose como una de sus puertas.

Lo que **no** cambia por esto: el cerebro sigue sin importar canales, y la
prueba que lo vigila pasa a ser más importante, no menos — es lo único que
queda sujetando el corte.

## Los cuatro problemas de verdad

No son detalles de implementación: si alguno se resuelve mal, esto no sale.

1. **A hugin le faltan los modelos personales.** Tiene agenda, memoria de
   quien llama, tarifas y FAQ. No tiene tareas, hábitos, apuntes ni entradas
   de diario, que es la mitad de lo que hace bifrost. Hay que llevarlos.

2. **Un inquilino persona no es un negocio.** `negocio.toml` habla de
   saludo, voz, tarifas y FAQ; una persona no tiene tarifas y sí tiene
   hábitos. El modelo tiene que pasar de «un negocio tiene estos ficheros» a
   «un inquilino tiene estas capacidades activadas», sin que dar de alta
   deje de ser copiar una carpeta.

3. **Separar los datos de cada inquilino.** Aquí hugin ya tiene la respuesta
   y es mejor que añadir una columna: `guardado/datos.py` guarda en
   `datos/<negocio>/…` y dice que **un proceso atiende a un bot**. La
   separación no es un filtro que haya que acordarse de poner, es una
   carpeta y un proceso.

   Llevado a Postgres, eso es **una base por inquilino, elegida por la URL
   de conexión** —como ya hace `DIARIO_DATABASE_URL`—, no una columna
   `inquilino` en cada tabla. Leer lo de otro pasa de «que nadie olvide un
   WHERE» a ser imposible, y el esquema del ADR-023 se queda como está. Si
   algún día hace falta servir a varios en el mismo proceso, lo que se toca
   es `datos.py`, que para eso está en un sitio solo.

4. **Hay dos capas de entender y una sobra.** `diario/entender.py` clasifica
   un mensaje suelto (tarea, hábito, cita o apunte) y `mente/recepcion.py`
   lleva la conversación de una llamada. Se parecen lo justo para estorbar.
   Hay que decidir cuál manda antes de mover nada.

## Dónde vive cada cosa: la raya entre tablas y ficheros

«Que todo apunte a Postgres» suena más simple de lo que sale. La raya que se
traza es **quién escribe cada cosa**:

| A Postgres, que son **registros** | En ficheros, que los **escribe o lee una persona** |
|---|---|
| tareas, citas, hábitos, apuntes | el diario en prosa |
| `mente/memoria.py` — la ficha de quien llama | `tarifas.md` y `faq.md` |
| `guardado/avisos.py` — el registro de llamadas | `negocio.toml`, las frases |

El motivo no es gusto: lo dice el propio `negocio/negocio.py` — *«quien lleva
el negocio tiene que poder cambiar un precio sin llamar a nadie»*. Con las
tarifas en una tabla, esa peluquera necesita que alguien le toque la base de
datos para subir un tinte dos euros. Y `mente/rag.py` busca justamente sobre
esos Markdown.

Es la misma regla que ya se aplicó al diario, dicha de una vez para todo: **lo
que escribe una persona va a ficheros; lo que registra el programa va a
tablas.** La memoria de quien llama es un registro y se va a Postgres; el
conocimiento del negocio es de su dueño y se queda en ficheros.

Lo que **sí** desaparece entero, sin matices, es la dependencia de midgaror.

## Lo que queda decidido de paso

- **El texto del diario se queda en Markdown**, no va a Postgres. Las tareas,
  citas, hábitos y apuntes son registros y van a tablas; una entrada de
  diario es prosa, y en ficheros se lee en Obsidian, se diffea en git y
  sobrevive a que la base no arranque. Postgres para lo estructurado,
  ficheros para lo que se lee.
- **El backend JSON no se quita hasta el final.** Es la vuelta atrás, y no
  es teórica: el 2026-09-18, con el cutover del ADR-023 recién hecho y
  `psycopg` faltando en el venv del bot, quitar dos líneas del `.env`
  devolvió el bot a funcionar. Se tira cuando Postgres lleve semanas
  corriendo, como paso propio y no de propina.
- **Quitar los conectores a midgaror** es, en concreto, que desaparezca
  `bifrost/utils/midgaror.py` —el módulo que busca midgaror y le importa los
  módulos— y con él las rutas y los `sys.path` que lo rodean.
- **midgaror vuelve a ser lo que dice ser**: documentación, infraestructura,
  formación y lo que Álvaro escribe a mano. Sin código que corra en
  producción.

## Por dónde se empieza (y qué no se toca todavía)

En fases, y la primera no toca producción:

1. ✅ **Juntar el repo, sin refactorizar nada.** `telefono/` entra desde
   gjallarhorn y `telegram/` desde bifrost, tal cual están, con sus pruebas
   pasando. Nada cambia de comportamiento y el bot en producción sigue
   corriendo desde donde corre hoy. Es aburrido a propósito: a partir de
   aquí, todo lo demás es un refactor dentro de casa en vez de commits
   coordinados en tres sitios.
2. ✅ **Paquetes de verdad.** Hoy el código se importa con
   `sys.path.insert(0, ...)` en cada módulo. `pyproject.toml`, instalación
   editable e imports normales. Arregla la mitad de lo que un revisor
   llamaría «prácticas de Python» y no cambia ni un comportamiento.
3. **Decidir la forma del inquilino antes de portar nada**: qué capacidades
   tiene (una peluquería: tarifas, FAQ, agenda; una persona: tareas,
   hábitos, apuntes, diario), y el paso de `negocio` a inquilino en
   `negocio.toml` y en `datos.py`. Portar los modelos antes de esto es
   portarlos dos veces.
4. **Llevar los modelos personales al cerebro**, ya con esa forma, con sus
   pruebas y sin que el canal de Telegram los use todavía.
5. **El canal de Telegram pasa al cerebro**, comando por comando, con el
   backend viejo como vuelta atrás igual que en el ADR-023.
6. **midgaror suelta el diario**, que para entonces ya no lo importa nadie,
   y se archivan `bifrost` y `gjallarhorn` apuntando al repo del producto.

## Consecuencias

- Es bastante más grande que el ADR-023, y toca el bot que escribe el diario
  todos los días. La vuelta atrás tiene que existir en cada fase, no al
  final.
- Parte de lo hecho en el ADR-023 se muda a hugin. No se tira: el esquema y
  los adaptadores valen, lo que cambia es dónde viven y que ganan inquilino.
- Mientras dure, hay dos sitios con lógica parecida. Es el precio de hacerlo
  por fases en vez de una reescritura de golpe, y es preferible.
- Si en algún momento esto deja de apetecer, se puede parar después de
  cualquier fase sin dejar el sistema a medias. Esa es la razón del orden.
- Juntar el repo toca cosas que no son código: el despliegue de Madre
  (ADR-013, la copia propia del bot), las unidades de systemd de los dos
  lados, el submódulo de gjallarhorn y las rutas del `.env`. Se hace en la
  fase 1, de una vez y con el bot corriendo desde donde corre hoy, en vez de
  ir arrastrándolo por todas las fases.
- El repo pasa a tener dentro el bot personal de Álvaro y el producto que se
  ofrece a terceros. Si algún día se abre el código o se vende, eso hay que
  separarlo entonces; hoy no hay motivo para pagar ese precio por
  adelantado.
