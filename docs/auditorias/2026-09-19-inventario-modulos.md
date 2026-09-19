---
tipo: auditoria
fecha: 2026-09-19
repo: hugin
estado: cerrada
alcance: [nucleo, telegram, telefono]
relacionado:
  - docs/arquitectura/07-hugin-bot-vivo.md
  - docs/auditorias/2026-09-19-arquitectura-actual.md
---

# Inventario de módulos: núcleo, Telegram y teléfono

Medido en disco el 2026-09-19, sobre `main` tras el PR #22 (layout
`src/hugin/`). Ningún fichero se mueve en esta auditoría — solo se registra
dónde está cada uno, qué hace, y si ya está en el sitio que le toca según
`docs/arquitectura/07-hugin-bot-vivo.md`.

## `src/hugin/` — el núcleo (31 ficheros)

| Módulo | Responsabilidad | Pruebas | Destino |
|---|---|---|---|
| `inquilino.py` | Quién es el inquilino, capacidades, ruta de datos | `tests/test_inquilino.py` | ya en su sitio |
| `motores.py` | Selector de motor LLM (Claude/Groq/Google/Ollama/auto) | `tests/test_motores.py` | ya en su sitio |
| `apuntes.py` | Notas sueltas estructuradas | `tests/test_apuntes.py` | ya en su sitio |
| `mente/cerebro.py` | Clasifica intención por teléfono, LLM opcional | `tests/test_cerebro.py` | ya en su sitio |
| `mente/rag.py` | Recuperación léxica local sobre el conocimiento | `tests/test_rag.py` | ya en su sitio |
| `mente/conocimiento.py` | Lee tarifas.md/faq.md, busca por término | `tests/test_conocimiento.py` | ya en su sitio |
| `mente/recepcion.py` | Máquina de estados de una llamada (`Conversacion`) | `tests/test_recepcion*.py` | ya en su sitio |
| `mente/memoria.py` | Ficha de quien llama (negocio) | `tests/test_memoria.py` | ya en su sitio |
| `mente/fechas.py` | Fechas/horas en español, lado negocio (`acotada`) | `tests/test_fechas.py` | ya en su sitio |
| `personal/citas.py` | Agenda personal, `sin_franja`/`confirmar_hora` | `tests/test_citas.py` | ya en su sitio |
| `personal/tareas.py` | Tareas, `sin_franja`/`confirmar_hora` | `tests/test_tareas.py` | ya en su sitio |
| `personal/habitos.py` | Registro de hábitos | `tests/test_habitos.py` | ya en su sitio |
| `personal/diario.py` | Prosa personal, lee/escribe entradas | `tests/test_diario_personal.py` | ya en su sitio |
| `personal/entender.py` | Clasifica mensaje suelto (tarea/hábito/cita/apunte/pregunta/diario) | `tests/test_entender_personal.py` | ya en su sitio |
| `personal/conversar.py` | Contesta preguntas sobre datos propios, solo lee | `tests/test_conversar_personal.py` | ya en su sitio |
| `personal/fechas.py` | Fechas/horas en español, lado personal | `tests/test_fechas_personal.py` | ya en su sitio |
| `personal/recordatorios.py` | Qué avisar, sin que nadie pregunte | `tests/test_recordatorios.py` | ya en su sitio |
| `negocio/agenda.py` | Huecos, horario, reservas de un negocio | `tests/test_agenda.py` | ya en su sitio |
| `negocio/negocio.py` | Identidad/configuración de un negocio | `tests/test_negocio.py` | ya en su sitio |
| `negocio/frases.py` | Sinónimos y lenguaje editable por negocio | `tests/test_frases.py` | ya en su sitio |
| `guardado/postgres.py` | Adaptador Postgres, una base por inquilino | `tests/test_postgres*.py` | ya en su sitio |
| `guardado/almacen.py` | JSON atómico con `schemaVersion` | `tests/test_almacen.py` | ya en su sitio |
| `guardado/datos.py` | Carpeta de datos de una instalación | `tests/test_datos.py` | ya en su sitio |
| `guardado/ajustes.py` | Lee el `.env`, última clave gana | `tests/test_ajustes.py` | ya en su sitio |
| `guardado/avisos.py` | Registro de avisos/fallos | `tests/test_avisos.py` | ya en su sitio |
| `guardado/copias.py` | Backups | `tests/test_copias.py` | ya en su sitio |
| `guardado/sincronizar.py` | `git commit`+`push` del repo de datos | `tests/test_sincronizar.py` | ya en su sitio |

**No hay nada que mover dentro de `src/hugin/`.** Los 31 ficheros ya viven
donde el mapa de destino los pone.

## `telegram/` — conector (20 ficheros + `bot.py`)

| Módulo | Responsabilidad | ¿Llama a `hugin.*` o reimplementa? | Destino |
|---|---|---|---|
| `bot.py` | Arranque, registra comandos y handlers | traduce (arranque PTB puro) | conector, ya en su sitio |
| `handlers/cita.py` | `/cita`, `/agenda` → `hugin.personal.citas` | llama al núcleo | conector; **candidato a Hugin.procesar()** |
| `handlers/tarea.py` | `/tarea`, `/tareas` → `hugin.personal.tareas` | llama al núcleo | conector; candidato |
| `handlers/habito.py` | `/habito`, `/habitos` → `hugin.personal.habitos` | llama al núcleo | conector; candidato |
| `handlers/apunte.py` | `/apunte`, `/dia`, `/semana` → `hugin.apuntes` | llama al núcleo | conector; candidato |
| `handlers/diario.py` | `/diario` → `hugin.personal.diario` | llama al núcleo | conector; candidato |
| `handlers/entrada.py` | `/entrada` → `hugin.personal.diario` | llama al núcleo | conector; candidato |
| `handlers/secciones.py` | `/siento`, `/aprendo`, `/plan` → diario | llama al núcleo | conector; candidato |
| `handlers/hoy.py` | `/hoy` → citas+tareas+hábitos+diario, **solo lectura** | llama al núcleo | conector; **primera extracción propuesta** |
| `handlers/texto.py` | Mensaje suelto → `hugin.personal.entender`/`conversar` | llama al núcleo | conector; candidato (ya toca `entender`/`conversar`, el más "cerebro" de los handlers) |
| `handlers/voz.py` | Nota de voz → Whisper → mismo camino que `texto.py` | transcribe (STT es del conector) + llama al núcleo | mixto: STT es conector, el resto ya delega |
| `handlers/recordatorios.py` | Avisa solo, sin que le hablen | llama al núcleo (`hugin.personal.recordatorios`) | conector; candidato |
| `handlers/menu.py` | Botones `/menu` | pinta UI de Telegram | **conector puro, no se mueve** — es exactamente lo que un conector debe hacer |
| `utils/auth.py` | Qué `chat_id` puede hablarle al bot | identidad de Telegram | conector puro |
| `utils/inquilino.py` | Qué inquilino atiende esta copia del bot | resuelve `hugin.inquilino` desde config del conector | conector, ya en su sitio |
| `utils/limites.py` | Recorta a 4096 caracteres (límite de Telegram) | formato del canal | conector puro |
| `utils/mensajes.py` | El texto tal cual lo escribió el usuario | formato del canal | conector puro |
| `utils/respuestas.py` | Cómo se contesta (con qué botones, cuándo se corta) | formato del canal | conector puro |
| `utils/voz.py` | Nota de voz de Telegram → texto (Whisper) | STT es del conector a propósito (motor concreto) | conector puro |

**Todos los handlers ya llaman al núcleo — ninguno reimplementa lógica de
dominio.** Lo que falta no es sacar código de aquí: es que, en vez de que
cada handler construya su propia llamada (`citas.agregar(" ".join(args),
inq)`), exista una forma neutral de pasar por el mismo camino sin ser un
`Update` de Telegram.

## `telefono/` — conector (16 ficheros)

| Módulo | Responsabilidad | Destino |
|---|---|---|
| `canal/telefonia.py` | Webhook de un proveedor de telefonía real | conector puro |
| `canal/firmas.py` | Comprobar firma Ed25519 del webhook | conector puro |
| `canal/servidor.py` | Servidor HTTP del MVP (sin teléfono, navegador) | conector puro |
| `canal/urlpublica.py` | Resuelve la URL pública de la máquina | conector puro (detalle de despliegue) |
| `canal/voz.py` | STT+TTS en local (Whisper+Piper) | conector puro — motor concreto, a propósito |
| `canal/demo.py` | Demo por teclado/audio contra `mente.recepcion` | conector puro (ya llama al núcleo) |
| `dueno/panel.py` | Panel del dueño en el móvil | herramienta de operador, no de producto |
| `dueno/diagnostico.py` | Estado de la máquina | herramienta de operador |
| `dueno/revisar.py` | «¿está listo para coger llamadas?» | herramienta de operador |
| `dueno/lanzar.py` | `make lanzar`: arranque guiado | herramienta de operador |
| `dueno/avisar.py` | Avisos al móvil del dueño (citas/recados) | herramienta de operador, ya llama a `guardado.avisos`/LLM |
| `dueno/agentes.py` | Trabajo en background sin llamada activa | **el único con forma de "capacidad de producto"** — a revisar si pasa a `mente/` cuando tenga caso de uso fuera del teléfono |
| `dueno/aprender.py` | Agrupa lo que el agente no supo contestar | herramienta de operador (alimenta al dueño, no al cliente) |
| `dueno/medir_voz.py` | Cuánto tarda el agente en contestar | herramienta de operador |

Confirma lo que ya encontró la auditoría del PR #21: `telefono/canal/` es
un conector limpio (superficie pública de 9 funciones); `telefono/dueno/`
es deuda de **operador** (accede a alguna función privada con guion bajo),
no deuda de arquitectura núcleo/conector — nadie de fuera lo usa como
producto.

## Conclusión del inventario

- **0 ficheros de `telegram/` o `telefono/` contienen lógica de dominio
  que deba moverse a `src/hugin/`.** La separación núcleo/conector, en el
  sentido de "dónde vive la lógica", ya está hecha.
- Lo que falta es aditivo, no una migración: un contrato neutral
  (`Mensaje`/`Sesion`/`Respuesta`), una fachada (`Hugin.procesar()`) y una
  CLI que hablen con el mismo `src/hugin/personal/*` que ya usan los
  handlers — sin tocar ni un fichero de `telegram/` ni `telefono/`.

## Primera extracción propuesta: `/hoy`

`telegram/handlers/hoy.py` es el candidato de menor riesgo:

- **Solo lee.** `tests/test_hoy.py::test_no_escribe_nada` lo comprueba
  explícitamente: ni toca el diario, ni crea ficheros.
- Ya delega el 100% de la lógica a `hugin.personal.{citas,tareas,habitos}`
  y `hugin.personal.diario.leer_entrada` — no hay nada que "portar", solo
  que envolver en el contrato neutral.
- 6 pruebas existentes (`telegram/tests/test_hoy.py`) documentan el
  comportamiento esperado byte a byte.
- **Plan de rollback**: la extracción es pura adición — un módulo nuevo
  (`src/hugin/bot/` con `Mensaje`/`Sesion`/`Respuesta`/`Hugin.procesar()`)
  y un punto de entrada nuevo (`python -m hugin`). No se toca ni una línea
  de `telegram/handlers/hoy.py` ni de `tests/test_hoy.py`. Si algo falla,
  revertir el PR no tiene ningún efecto sobre Telegram, que sigue llamando
  a `hugin.personal.*` exactamente como hoy.
