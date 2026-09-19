---
tipo: decision
fecha: 2026-09-19
repo: hugin
etiquetas: [arquitectura, producto, nucleo, conectores, datos, rag]
estado: propuesto
relacionado:
  - docs/adr/019-cerebro-de-gjallarhorn-en-hugin.md
  - docs/adr/024-un-cerebro-dos-puertas.md
  - docs/adr/025-fusion-mente-personal.md
  - docs/adr/026-postgres-estructurado.md
---

# ADR-027: Hugin es el núcleo; Telegram y teléfono son conectores

## Contexto

Hugin es el producto y el cerebro. No es un bot de Telegram ni un bot de
teléfono: ambos son conectores que permiten hablar con el mismo núcleo.

El núcleo recibe un mensaje y su contexto, interpreta la intención, consulta
conocimiento, aplica reglas, utiliza un motor LLM solo si está configurado y
lee o escribe datos de la instalación correspondiente.

Telegram, teléfono, web, WhatsApp y una API futura son puertas de entrada y
salida. No contienen el cerebro, el RAG, las reglas de citas ni el acceso
directo a las bases de datos.

## Decisión

- Hugin es un núcleo único reutilizable.
- `hugin/` contiene hoy el núcleo y se migrará gradualmente a `src/hugin/`.
- `telegram/` y `telefono/` son conectores; en la estructura destino vivirán
  bajo `conectores/`.
- Un conector adapta su protocolo a Hugin:
  recibe mensaje, identifica contexto, llama al núcleo y entrega respuesta.
- El núcleo no puede importar Telegram, teléfono ni ningún protocolo.
  Los conectores sí pueden importar Hugin.
- Una instalación se configura por capacidades, conocimiento y datos; no se
  reescribe el cerebro para una persona, un autónomo o una empresa.
- Una instalación puede tener capacidades como diario, citas, tareas, hábitos,
  apuntes, tarifas, FAQ y agenda comercial.
- Citas, tareas, hábitos y apuntes son datos estructurados: usan Postgres
  cuando la instalación tiene una `base` configurada.
- Diario, tarifas, FAQ y frases siguen en ficheros editables: Markdown y TOML.
- El RAG recupera tarifas, FAQ y conocimiento desde ficheros de la instalación.
  No se añade una base vectorial mientras la búsqueda léxica y los sinónimos
  configurables resuelvan el problema.
- Los motores LLM son opcionales. Las reglas y el dominio deben seguir
  funcionando sin red, clave ni proveedor externo.

## Arquitectura destino

```text
Hugin
├── src/
│   └── hugin/
│       ├── mente/           cerebro, conocimiento y RAG
│       ├── personal/        citas, tareas, hábitos, diario
│       ├── negocio/         agenda comercial, tarifas y FAQ
│       ├── guardado/        JSON, Postgres y sincronización
│       ├── inquilino.py     configuración y capacidades
│       └── motores.py       proveedores LLM opcionales
├── conectores/
│   ├── telegram/            adaptador Telegram
│   ├── telefono/            adaptador teléfono y voz
│   └── web/                 adaptador futuro
├── plantillas/
│   ├── persona/
│   ├── autonomo/
│   └── empresa/
└── docs/
```

## Regla de dependencias

```text
conectores → núcleo Hugin → dominio y persistencia
```

Nunca:

```text
núcleo Hugin → Telegram
núcleo Hugin → teléfono
mente → un conector concreto
RAG → un conector concreto
conector → SQL o JSON directamente
```

## Consecuencias

- Telegram, teléfono, web o WhatsApp pueden compartir cerebro, RAG, reglas y
  dominio sin duplicar código.
- Cada instalación usa únicamente su configuración, conocimiento y datos.
- El cliente de una empresa no accede al diario ni a los datos privados de la
  persona que administra la instalación.
- La migración a `src/` será un refactor posterior con pruebas verdes; no se
  mezcla con nuevas funciones ni con cambios de producción.
- Antes de mover código se realizará una auditoría completa de imports,
  responsabilidades, persistencia y pruebas.
