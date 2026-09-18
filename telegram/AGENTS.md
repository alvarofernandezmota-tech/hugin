# Instrucciones para Agentes AI

## Contexto del proyecto

Bifrost es un bot de Telegram para escribir y organizar entradas del diario personal.

## Estado actual

✅ **En produccion**: servicio de systemd en Madre, escribiendo entradas
reales del diario desde Telegram (la primera, el 2026-09-08)
✅ 18 comandos, 10 handlers, 179 pruebas, `ruff` limpio
✅ Autorizacion por chat_id cerrada por defecto, con pruebas que impiden que
abrirla pase en verde (2026-09-09)
✅ Arranque sin red, ediciones de mensajes y error handler resueltos
⚠️ Pendiente - usarlo 1-2 semanas y decidir con el uso (fase 2b)

**Antes de dar algo por bueno**: `python3 scripts/verificar.py` desde la raiz
de midgaror. La CI no arranca desde el 2026-09-05 (facturacion), asi que es la
unica verificacion real que hay. Un check en rojo en GitHub no dice nada del
codigo: mira `docs/infra/estado-ci.md` de midgaror.

## Estructura

```
bifrost/
├─ bot.py              # punto de entrada: registra los 18 comandos y arranca
├─ handlers/           # uno por familia de comandos (10)
│  ├─ diario.py        # /diario
│  ├─ entrada.py       # /entrada
│  ├─ secciones.py     # /siento, /aprendo, /plan
│  ├─ texto.py         # texto sin comando
│  ├─ tarea.py         # /tarea, /tareas
│  ├─ cita.py          # /cita, /agenda
│  ├─ habito.py        # /habito, /habitos
│  ├─ apunte.py        # /apunte, /dia, /semana  (ADR-012)
│  ├─ hoy.py           # /hoy
│  └─ menu.py          # /menu y los botones
├─ utils/
│  ├─ midgaror.py      # donde esta midgaror y como se importa. En un solo sitio
│  ├─ auth.py          # chats autorizados (TELEGRAM_CHAT_ID). Cerrado por defecto
│  ├─ respuestas.py    # todo lo que sale del bot pasa por aqui
│  ├─ mensajes.py      # el texto del usuario, sin comando y con sus saltos de linea
│  └─ limites.py       # el tope de 4096 de Telegram
├─ systemd/            # la unidad del servicio
├─ tests/              # 14 ficheros, 179 pruebas
├─ venv/               # (NO commitear)
└─ docs/sesiones/
```

## Scripts en midgaror/diario/

- `organizar_diario.py` → `organizar_texto(texto, fecha=None)`, unico camino de escritura
- `bifrost_bridge.py` → `escribir_entrada(texto, fecha=None)`, contrato con este bot (ADR-009)
- `diario.py` → rutas y plantilla del diario

## Problemas conocidos

- Los marcadores `=======` no son un fallo: son separadores propios del autor
  entre ratos del dia, y `organizar_texto` escribe dentro de la seccion sin
  tocarlos.
- Los objetivos de `/apunte` no se pueden fijar desde Telegram: hay que
  editar `diario/registro/datos/objetivos.json` a mano.
- Un comando mal escrito (`/diarrio`) no lo recoge ningun handler: el bot se
  queda mudo y no queda ni rastro en el log.
- La deuda con detalle y su orden esta en
  `midgaror/docs/auditorias/` (informe mas reciente).

## Reglas

- Nunca modificar `.env` (contiene secretos)
- **Verificar con `python3 scripts/verificar.py`** desde la raiz de midgaror,
  nunca con las auditorias sueltas: esas no corren ni una prueba
- **Contrastar contra el codigo, no contra esta documentacion**: si algo aqui
  no cuadra con lo que hace `bot.py`, manda `bot.py` y se corrige el
  documento en el mismo commit
- Documentar cambios en `docs/sesiones/`
- Un comando nuevo se engancha en **cinco** sitios en el mismo commit: el
  `CommandHandler` de `bot.py`, `MENU`, `ACCIONES`/`FILAS` de `handlers/menu.py`,
  la seccion de `/help`, y `HANDLERS.md`. Las pruebas vigilan los cuatro
  primeros; el quinto, de momento, no
