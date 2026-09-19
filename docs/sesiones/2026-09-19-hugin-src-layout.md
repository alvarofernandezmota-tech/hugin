---
tipo: sesion
fecha: 2026-09-19
repo: hugin
etiquetas: [arquitectura, refactor, src-layout, auditoria, telefono, telegram]
estado: en-progreso
relacionado:
  - docs/adr/027-hugin-nucleo-conectores.md
  - docs/auditorias/2026-09-19-arquitectura-actual.md
---

# Sesión 2026-09-19: de "un cerebro y dos puertas" a "núcleo en src/"

## Punto de partida

Hugin ya tenía la decisión correcta tomada desde el ADR-024: el cerebro
(`hugin/`) es una librería; `telegram/` y `telefono/` son aplicaciones
hermanas, cada una con su venv, que instalan el cerebro en modo editable.
Lo que faltaba era: documentarlo con datos reales, no con intuición, y dar
el primer paso de un layout `src/` sin romper Madre.

## Qué se cerró hoy (fusionado en `main`)

- **PR #20** — ADR-027: Hugin como núcleo, Telegram y teléfono como
  conectores. Primera auditoría de imports: el núcleo no importa
  conectores; Telegram no toca persistencia directamente.
- **PR #21** — Corrección de esa auditoría: la cifra de 142 imports de
  `telefono/` mezclaba `telefono/canal/` (el conector real, con una API
  pública limpia de 9 funciones) con `telefono/dueno/` (herramientas de
  operador, con acceso legítimo pero informal a funciones privadas como
  `rag._tokens` o `_agenda._minutos`). Decisión: no se crea una fachada
  nueva; la deuda de `dueno/` queda documentada y es de bajo riesgo.

## Qué queda en curso (rama local, sin commit, sin tocar `main` ni Madre)

Rama: `refactor/hugin-src-layout`.

Objetivo: mover `hugin/` → `src/hugin/`, siguiendo el layout `src/`
estándar de Python, sin tocar `telegram/` ni `telefono/` como aplicaciones
(ver ADR-027: sus venvs y su arranque independiente son correctos, no una
carencia).

### Hecho

1. `git mv hugin src/hugin` (conserva historial).
2. `pyproject.toml`: de `packages = [...]` explícito a
   `package-dir = {"" = "src"}` + `[tool.setuptools.packages.find]`.
3. `herramientas/auditoria.py::paquetes_completos()`: adaptado para leer
   `packages.find` (`where`/`include`) en vez de una lista plana, y para
   calcular el nombre de paquete relativo a `src/`, no a la raíz.
4. `telefono/tests/test_carpetas.py`: dos aserciones que asumían
   `RAIZ.parent / "hugin"` corregidas a `RAIZ.parent / "src" / "hugin"`.
   Resultado: la suite de teléfono pasa entera (429/429).
5. Confirmado que `telefono/requirements.txt` **no** instala `hugin` en
   modo editable (a diferencia de `telegram/requirements.txt`, que sí
   tiene `-e ..`): `telefono/` depende de `sys.path.insert(0, str(RAIZ))`
   repartido en ~20 ficheros (`telefono/dueno/diagnostico.py` y la mayoría
   de `telefono/tests/test_*.py`). `make pruebas` no lo nota porque llama
   siempre al intérprete de la raíz (`$(CURDIR)/$(PY)`, ver `Makefile`),
   no al `venv` propio de `telefono/`. Un `telefono/venv` aislado sí falla
   con `ModuleNotFoundError: No module named 'hugin'`. Deuda real,
   documentada, para PR aparte.

### Pendiente al cerrar la sesión

`make pruebas` termina con la suite del cerebro (`tests/`) en rojo por dos
motivos, ambos del mismo tipo — ficheros de test con una ruta a `hugin/`
hardcodeada a la raíz, sin pasar por `src/`:

1. `tests/test_libreria.py`: `CEREBRO = RAIZ / "hugin"` (o equivalente,
   pendiente de confirmar la línea exacta) — provoca
   `FileNotFoundError` en `guardado/ajustes.py` y el fallo
   `falta el paquete hugin/`.
2. `tests/test_auditoria.py` → `herramientas/auditoria.py:37`:
   `AttributeError: 'list' object has no attribute 'get'` al leer
   `config["tool"]["setuptools"]["packages"]`. Indica una inconsistencia
   real en el `pyproject.toml` en disco frente a lo esperado por el
   parche de `auditoria.py` — pendiente de revisar el fichero completo
   tal cual quedó, no de memoria.

Ningún cambio de esta rama ha llegado a `main` ni a Madre. El servicio
`hugin-telegram` sigue sirviendo el código de siempre.

## Próxima sesión — orden de trabajo

1. `cat pyproject.toml` completo: confirmar el estado real de
   `[tool.setuptools]` / `[tool.setuptools.packages.find]`.
2. `sed -n '1,40p' tests/test_libreria.py`: localizar `CEREBRO` y
   corregirlo a `RAIZ / "src" / "hugin"`.
3. Repetir `make pruebas` hasta `✅ Todo en verde.`
4. `git add`, revisar `git diff --stat` completo, commit, PR.
5. Después de fusionar: PR aparte para migrar `telefono/` de
   `sys.path.insert` a instalación editable (`-e ..` en
   `telefono/requirements.txt`), quitando el hack de los ~20 ficheros.
6. Solo entonces: handler de Telegram que pregunte «¿mañana o tarde?»
   para citas con `sin_franja` — pendiente desde el PR #19, aún sin
   tocar.
