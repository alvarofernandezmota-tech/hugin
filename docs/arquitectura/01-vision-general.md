# Visión general de Hugin

Hugin es el núcleo del producto. Recibe texto y contexto, entiende la
intención, consulta conocimiento, aplica reglas del dominio y responde o
ejecuta una acción permitida.

Los conectores no son cerebros separados. Traducen mensajes entre su canal y
Hugin.

```text
Telegram ─┐
Teléfono ─┼──→ Hugin ──→ mente / dominio / guardado
Web/API ──┘
```

## Capas

```text
Conectores
    ↓
Núcleo Hugin
    ↓
Mente, dominio y conocimiento
    ↓
Persistencia y ficheros editables
```

## Regla

El núcleo no conoce `Update` de Telegram, llamadas telefónicas ni HTTP.
Un conector sí conoce su protocolo y llama al núcleo.
