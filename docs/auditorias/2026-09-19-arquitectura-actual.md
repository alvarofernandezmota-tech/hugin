---
tipo: auditoria
fecha: 2026-09-19
repo: hugin
estado: en-progreso
alcance: [nucleo, conectores, datos, rag, motores, pruebas]
relacionado:
  - docs/adr/027-hugin-nucleo-conectores.md
---

# Auditoría de arquitectura actual de Hugin

## Objetivo

Inventariar el código antes de moverlo a `src/` o renombrar directorios.

## Regla a verificar

```text
conectores → núcleo Hugin → dominio y persistencia
```

## Inventario inicial

| Ruta actual | Nombre arquitectónico | Destino previsto |
|---|---|---|
| `hugin/mente/` | Mente | `src/hugin/mente/` |
| `hugin/personal/` | Dominio personal | `src/hugin/personal/` |
| `hugin/negocio/` | Dominio negocio | `src/hugin/negocio/` |
| `hugin/guardado/` | Persistencia | `src/hugin/guardado/` |
| `hugin/inquilino.py` | Configuración de instalación | `src/hugin/inquilino.py` |
| `hugin/motores.py` | Motores LLM | `src/hugin/motores.py` |
| `hugin/apuntes.py` | Dominio estructurado | `src/hugin/apuntes.py` |
| `telegram/` | Conector Telegram | `conectores/telegram/` |
| `telefono/` | Conector teléfono | `conectores/telefono/` |
| `tests/` | Pruebas del núcleo | `tests/` |

## Auditoría por módulo

Para cada módulo se registrará:

- Responsabilidad.
- API pública.
- Imports.
- Quién lo llama.
- Lecturas de datos.
- Escrituras de datos.
- Pruebas.
- Dependencias indebidas.
- Destino tras migración.

## Hallazgos iniciales

- El núcleo está mayoritariamente concentrado bajo `hugin/`.
- Telegram y teléfono están físicamente separados, pero aún en la raíz.
- `inquilino.py` expresa capacidades y una base configurada.
- `guardado/postgres.py` persiste entidades estructuradas.
- Markdown conserva diario, tarifas y FAQ.
- `mente/rag.py` implementa recuperación local.
- Debe revisarse lógica de dominio aún situada en handlers de Telegram.

## Riesgos a verificar

- Imports desde núcleo hacia conectores.
- Lógica de dominio duplicada en handlers.
- SQL o JSON ejecutado directamente desde conectores.
- Aislamiento insuficiente entre instalaciones.
- Dependencia accidental de LLM para funciones deterministas.

## Resultados de la auditoría inicial

### Regla núcleo → conectores

La búsqueda de imports desde `hugin/` hacia `telegram` o `telefono` no produjo
coincidencias. El núcleo no parece depender directamente de esos conectores.

**Estado:** correcto.

### Regla conectores → núcleo

Los conectores importan Hugin. La búsqueda registró 142 imports desde
`telegram/` y `telefono/` hacia módulos `hugin.*`.

La dirección de dependencia es correcta, pero el teléfono importa muchas piezas
internas de `mente`, `negocio` y `guardado`. Antes de mover directorios se debe
definir una API pública de Hugin para que los conectores no dependan de detalles
internos.

**Estado:** correcto en dirección; requiere encapsulación.

### Persistencia en Telegram

La búsqueda de `open`, `json`, `psycopg`, SQL y llamadas `execute` dentro de
`telegram/handlers` y `telegram/utils` no produjo coincidencias.

Telegram no accede directamente a la persistencia. Delega en módulos de Hugin.

**Estado:** correcto.

### Postgres

`hugin/guardado/postgres.py` contiene tablas estructuradas para:

- `tareas`.
- `citas`.
- `habitos_registro`.
- `apuntes`.

El adaptador carga y guarda cada colección. En citas existe la migración
`sin_franja`, usada para conservar una hora ambigua que todavía debe ser
confirmada.

**Estado:** funcional; pendiente auditar semántica de `TRUNCATE` seguido de
reinserción completa para cada guardado.

### RAG

`hugin/mente/rag.py` implementa recuperación local léxica:

- Tokenización y normalización.
- Sinónimos desde `frases.toml`.
- Separación de documentos en pasajes.
- Puntuación por términos, títulos e IDF.
- Umbral mínimo de respuesta.
- Control de ambigüedad entre resultados.
- Invalidación del índice cuando cambia el conocimiento.

`hugin/mente/conocimiento.py` resuelve tarifas desde tablas Markdown y FAQ
desde ficheros editables.

**Estado:** no añadir embeddings ni base vectorial sin medir un fallo concreto
de recuperación que los sinónimos, los títulos y el ranking actual no resuelvan.

### Motores

`hugin/motores.py` centraliza la elección de proveedor. `hugin/mente/cerebro.py`
puede usar Claude, Ollama, Groq o Google mediante variables de entorno.

Los motores son opcionales y deben permanecer separados del dominio y de la
persistencia.

**Estado:** correcto; pendiente unificar nomenclatura histórica
`GJALLARHORN_LLM` / `MIDGAROR_LLM` en una futura decisión separada.

### Medición pendiente

El inventario bruto de Python bajo conectores contó 3.779 ficheros. La cifra
está contaminada por entorno virtual, cachés o dependencias locales. El próximo
inventario excluirá `venv`, `__pycache__` y directorios de dependencias para
medir únicamente código propio.

## Corrección: superficie real de telefono/

La cifra de 142 imports del hallazgo inicial mezclaba dos conectores
distintos con responsabilidades diferentes:

### `telefono/canal/` — el conector real (atiende llamadas)

Usa una superficie pequeña y ya pública:

```text
recepcion.conversacion_de, recepcion.Conversacion
negocios.cargar, negocios.listar, negocios.advertencias
datos.usar
conocimiento.tarifas, conocimiento.que_falta
_frases.problemas
memoria.ficha, memoria.Ficha, memoria.apuntar_cita,
memoria.apuntar_llamada, memoria.apuntar_anulacion
avisos.registrar
```

Ninguna de estas llamadas usa una función con guion bajo. `canal/` no
necesita una fachada nueva: ya se comporta como un conector correcto.

**Estado:** correcto, sin acción pendiente.

### `telefono/dueno/` — herramientas de operador, no un conector

Panel, diagnóstico, agentes, revisar, aprender y medir_voz acceden a
funciones marcadas como privadas en otros módulos:

```text
rag._tokens
rag._raiz
conocimiento._sin_tildes
_agenda._minutos
```

Esto es deuda real, pero de bajo riesgo: `dueno/` es código de
administración de un solo operador (tú), no una superficie ofrecida a
clientes ni a otro desarrollador. No bloquea clonar Hugin para un cliente.

**Decisión:** no crear una fachada pública general para `telefono/`. En su
lugar, cuando se toque `rag.py`, `conocimiento.py` o `agenda.py`, promover
esas funciones concretas a públicas (quitar el guion bajo) si de verdad
las necesita un script de operador, o dejarlas privadas y mover la lógica
que las usa dentro del propio módulo.

### Corrección del PR #20

La frase «teléfono depende de módulos internos y necesitará una API
pública» se matiza: aplica a `telefono/dueno/`, no a `telefono/canal/`.
