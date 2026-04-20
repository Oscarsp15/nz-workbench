# AGENTS.md — nz-workbench

**Audiencia**: agentes IA (Claude Code CLI, Claude Desktop) y cualquier colaborador futuro que trabaje en este repositorio. Este archivo es el **punto de entrada único**. Leelo completo antes de hacer cualquier cambio.

---

## 1. Misión

`nz-workbench` acelera el "flujo REN" para el mantenimiento de procedimientos de IBM Netezza. Un **REN** (Requerimiento de Negocio) es un pedido de negocio que solicita modificar la lógica de uno o varios procedimientos almacenados en producción. Por cada REN, el desarrollador:

1. Lee el REN, idealmente junto con el usuario de negocio.
2. Localiza el o los procedimientos de producción donde aplica el cambio.
3. Clona esos procedimientos a una base `DESA_*` bajo un nombre modificado, reescribiendo referencias de escritura para no tocar producción.
4. Aplica los cambios pedidos de forma quirúrgica a los clones.
5. Ejecuta los clones y compara su salida contra producción para confirmar que el comportamiento es el esperado.
6. Documenta el cambio para que RENs futuros puedan construir sobre él.

`nz-workbench` automatiza las partes mecánicas y mantiene al humano en control de toda decisión no trivial. También acumula conocimiento sobre cada procedimiento para que, con el tiempo, el entendimiento del equipo crezca junto con la herramienta.

Este proyecto es **público** bajo MIT. Cualquier equipo Netezza puede forkearlo y adaptarlo. Depende del proyecto hermano `nz-mcp` ([Oscarsp15/nz-mcp](https://github.com/Oscarsp15/nz-mcp)) como cliente MCP para hablar con Netezza. Las capacidades genéricas de Netezza siempre van en `nz-mcp`; lo que sea específico del flujo REN, de plantillas de workflow, o de convenciones de equipos que usan este framework va acá. Los **datos reales de cada usuario** (carpetas REN, mapeos de procedimientos, notas) quedan **gitignored** — nunca se suben al repo público.

---

## 2. Principios no negociables

Tres reglas están por encima de todo lo demás en este archivo. Si alguna guía en otro lugar parece contradecir estos principios, ganan los principios.

### 2.1. Separación estricta

El proyecto es público, pero los datos de cada usuario no. Nada específico de una empresa, de sus RENs, de sus convenciones internas, o de sus procedimientos reales se commitea al repo. Lo que sí va en el repo:

- Código del framework.
- Plantillas (`ren/_TEMPLATE/`, `docs/procedures/_TEMPLATE.md`, `docs/*.md.template`).
- Standards, docs de arquitectura, ADRs.
- Scripts de CI y regex de validación.

Todo lo que acumule un usuario al operar la herramienta (carpetas `ren/REN_*`, archivos `docs/procedures/<SP>.md`, logs de aprendizaje, catálogos de side effects, estado local bajo `.nz-workbench/`) está en `.gitignore` y nunca se publica.

Antes de proponer un cambio a este repo, preguntate: *"¿Sería útil para un usuario de Netezza de una empresa distinta?"* Si la respuesta es no, no va.

Antes de proponer un cambio a `nz-mcp` (el proyecto hermano), preguntate lo mismo. Si la funcionalidad es específica del flujo REN, quedate en este repo.

### 2.2. La IA nunca adivina

Cuando la IA encuentra ambigüedad — una definición faltante en el REN, una referencia poco clara a una tabla, un match semántico débil, una regla de negocio que no está explícita — **se detiene y pregunta**. Nunca completa con un default silencioso. Una clarificación con el humano es más barata que un clon equivocado.

Patrones concretos que la IA debe tratar como ambigüedad:

- Un REN menciona "la tabla X" sin calificar base/schema.
- Un REN se refiere a una regla o columna cuyo texto literal no aparece en el procedimiento candidato.
- Varios `CASE`, `JOIN` o `FROM` en el procedimiento podrían ser el target esperado.
- Un umbral numérico o rango de fechas se da sin fórmula clara ni parametrización.
- Un procedimiento side-effect (emails, logs, llamadas externas) cuyo comportamiento en `DESA_*` no está aún catalogado.

Ver `docs/standards/pr-audit.md` § "Zero-guess enforcement" para cómo esto se revisa al momento del PR.

### 2.3. Transparencia total

Toda decisión no trivial que tome la IA se escribe. Toda asunción se confirma con un humano o queda como pregunta pendiente. Cada REN produce una carpeta bajo `ren/REN_<N>/` con la cadena completa de evidencia — el REN original, las clarificaciones, el manifest, los diffs, el baseline test, el reporte final, el log de decisiones y la transcripción de la conversación.

La prueba: un miembro nuevo del equipo que se una en seis meses debería poder reconstruir cualquier REN leyendo solo su carpeta.

---

## 3. Estructura del repositorio

```
nz-workbench/
├── AGENTS.md                         # este archivo — punto de entrada único
├── README.md                         # quickstart para humanos
├── CHANGELOG.md                      # changelog bilingüe (ES/EN)
├── pyproject.toml
├── docs/
│   ├── architecture/                 # cómo está armado el sistema
│   ├── standards/                    # git, PR, testing, secretos, estilo
│   ├── adr/                          # architecture decision records
│   ├── guides/                       # onboarding, operación
│   ├── procedures/                   # un markdown por SP aprendido (acumula — gitignored)
│   ├── technical-decisions.md        # lecciones reutilizables entre RENs (gitignored)
│   ├── side-effects-catalog.md       # patrones para comentar / redirigir / mantener (gitignored)
│   └── learning-log.md               # tu traza personal de aprendizaje (gitignored)
├── ren/
│   └── _TEMPLATE/                    # estructura canónica de una carpeta REN
│   # ren/REN_* — carpetas reales, gitignored
├── src/nz_workbench/
│   ├── cli.py                        # CLI con typer
│   ├── mcp_server.py                 # expone tools del workbench a Claude CLI
│   ├── config.py
│   ├── kb/                           # knowledge base (Chroma + SQLite)
│   ├── analyzer/                     # parsing del REN + clarificaciones
│   ├── migrator/                     # reglas PROD→DESA + suffix + side effects
│   ├── tester/                       # baseline + comparación PROD vs DESA
│   ├── docs_writer/                  # genera artifacts de docs/ y ren/
│   └── nz_mcp_client/                # cliente MCP a nz-mcp
├── tests/
│   ├── unit/
│   └── integration/
└── scripts/                          # scripts de validación de CI
```

El estado local que no se commitea vive bajo `.nz-workbench/` (vector DB, SQLite metadata, cache). Es portable: copiando esa carpeta a otra máquina se transfiere todo el conocimiento acumulado.

---

## 4. Roles

Hoy existe un único rol humano en este repo: **mantenedor** (quien forkee y opere el workbench). El mantenedor valida clarificaciones, confirma diffs, aprueba PRs, y edita a mano la sección "notas humanas" de los archivos `docs/procedures/<SP>.md`.

Existen dos roles IA, siempre desempeñados por agentes distintos para evitar conflictos de interés:

- **Author IA**: abre PRs con trabajo de feature o fix. Típicamente manejada desde Cursor, Claude Desktop, o una sesión scripteada de Claude Code. Sigue las convenciones en `docs/standards/`.
- **Auditor IA**: revisa cada PR antes del merge contra siete dimensiones (ver `docs/standards/pr-audit.md`). Solo el auditor mergea. Se maneja desde Claude Code en la máquina del mantenedor con permisos de merge.

Este es el mismo patrón dual-IA validado en el proyecto hermano `nz-mcp`.

---

## 5. Flujo de trabajo

### 5.1. Ciclo de vida de features / fixes

1. Se abre un issue en GitHub usando una de las labels en `docs/standards/git-workflow.md`.
2. La Author IA crea una branch que cumpla el regex (`^(feat|fix|chore|refactor|docs|test|security|perf|build|ci|ren)/\d+-[a-z0-9-]+$`).
3. Los commits siguen conventional-commits con scope en `[a-z0-9-]+` (sin underscores, sin comas, sin elipsis — ver `docs/standards/git-workflow.md` § 2).
4. El body del PR usa el template en `.github/PULL_REQUEST_TEMPLATE.md`. Los cinco headings obligatorios deben estar presentes textualmente.
5. CI corre `ruff`, `mypy --strict`, `pytest` sobre Ubuntu, Windows y macOS en Python 3.11 y 3.12.
6. La Auditor IA revisa contra siete dimensiones. Aprueba y mergea, o postea un block comment con fixes concretos.
7. Tras el merge, si el PR cambió comportamiento, `CHANGELOG.md` ya contiene la entrada bilingüe.

### 5.2. Ciclo de vida de un REN (caso de uso principal)

El flujo end-to-end de un REN está detallado en `docs/architecture/ren-lifecycle.md`. Resumen:

1. **Ingesta**: el usuario pega el REN en una conversación o en `ren/REN_<N>/source.md`.
2. **Análisis**: la IA extrae entidades, consulta la knowledge base, produce `analysis.yaml` y una lista de clarificaciones si hay ambigüedad.
3. **Gate 1 — clarificaciones**: el humano resuelve toda clarificación con el usuario de negocio si hace falta. No puede quedar ambigüedad antes de avanzar.
4. **Manifest**: la IA genera `manifest.yaml` — la lista de procedimientos y tablas a clonar, con su sufijo y reglas de reescritura.
5. **Clone**: la IA crea los clones en `DESA_*` usando el manifest. No aplica change points todavía.
6. **Baseline**: la IA ejecuta el SP original de PROD y el clon sin modificar, compara sus tablas de output, y bloquea si difieren. Paridad de entorno antes de editar.
7. **Ediciones**: la IA aplica los change points del REN uno por uno a cada clon, produciendo diffs bajo `ren/REN_<N>/diffs/`.
8. **Comparación**: la IA ejecuta los clones modificados y compara su output con PROD, produciendo `test_report.md`.
9. **Gate 2 — revisión final**: el humano revisa la comparación y los diffs. Aprueba o pide iterar.
10. **Documentación**: la IA actualiza `docs/procedures/<SP>.md` por cada SP tocado, el `learning-log.md`, y `ren/REN_<N>/summary.md`. Los commits son por fase.

---

## 6. Knowledge base

La knowledge base (KB) es la memoria del proyecto. Vive bajo `.nz-workbench/` (no commiteada) más `docs/procedures/` (gitignored en el repo público; cada usuario la mantiene localmente).

### 6.1. Qué se indexa

- El body de cada procedimiento en las bases de datos de producción (prefijo `PROD_*`). El bootstrap de día 1 cubre todos los procedimientos — del orden de 6.300 entre 18 bases de datos en casos típicos — usando el embedder BGE-M3 local. **No se consumen tokens de Claude** para indexar.
- Notas humanas en `docs/procedures/<SP>.md` (§ "Notas humanas").
- Mapeos pedagógicos generados por la IA cuando existan.
- Decisiones técnicas acumuladas a través de RENs.

Las bases `DESA_*` **no** se indexan. Contienen trabajo en progreso y borradores; su contenido contamina los resultados de búsqueda.

### 6.2. Cuándo se refresca el índice

- Manualmente: `nz-workbench kb-refresh <sp>` re-indexa un único procedimiento. Se usa cuando sabés que un SP específico cambió.
- Cron opt-in: `nz-workbench kb-refresh-cron` (opcional, deshabilitado por default) escanea `_V_PROCEDURE` nocturnamente y re-indexa procedimientos cuyo `LASTALTERTIME` cambió.

### 6.3. Portabilidad

La knowledge base es un conjunto de archivos bajo `.nz-workbench/`. Para moverla a otra máquina:

```bash
nz-workbench kb-export out.tar.zst
# en la otra máquina:
nz-workbench kb-import out.tar.zst
```

Sin servidor, sin estado centralizado. Copiar archivos alcanza.

---

## 7. Contrato de `docs/procedures/<SP>.md`

Cada procedimiento aprendido vive en un archivo bajo `docs/procedures/`. El archivo tiene cuatro secciones fijas con reglas estrictas de dueño:

```markdown
# <nombre del procedimiento>

## Metadata (auto)
<Mantiene la IA — schema, BD, fecha indexada, último REN que lo tocó>

## IA mapping (auto)
<Mantiene la IA — mapeo pedagógico bloque por bloque>

## Notas humanas (manual)
<Solo edita el mantenedor — la IA nunca toca>

## Change log (auto)
<La IA agrega al final una entrada por REN que toque el SP>
```

La IA lee la sección "Notas humanas" para enriquecer su mapeo, pero nunca escribe ahí. Los conflictos son imposibles por construcción.

Ver `docs/procedures/_TEMPLATE.md` para el layout canónico.

---

## 8. Side effects

El catálogo en `docs/side-effects-catalog.md` lista patrones de procedimientos o tablas que deben tratarse de forma especial al clonarse a `DESA_*`. Acciones soportadas:

- `comment_out` — el call o insert queda comentado en el body clonado.
- `redirect_to(<email>)` — para side effects de envío de email, redirige el destinatario a una dirección dada.
- `keep` — el side effect se preserva tal cual (tablas de auditoría, logs inocuos).

El catálogo arranca vacío. La IA agrega patrones a medida que los descubre, siempre preguntando al humano antes de asignar una acción default a un patrón nuevo. Una vez catalogado, matches subsiguientes aplican la default sin preguntar.

---

## 9. Stack

- Python 3.11+, typer para la CLI, pydantic v2 para los data models.
- Knowledge base: Chroma (archivo SQLite embebido, sin Docker) + BGE-M3 vía sentence-transformers, inferencia local.
- Metadata index: SQLite plano.
- Acceso a Netezza: cliente MCP a `nz-mcp`. Ningún uso directo de nzpy o drivers SQL — todo enrutado a través de tools de `nz-mcp`.
- Tests: pytest, pytest-cov, hypothesis para property-based tests.
- Linter / formatter: ruff.
- Type checker: mypy --strict.

Ver `docs/adr/` para el fundamento de cada decisión.

---

## 10. Glosario

- **REN**: Requerimiento de Negocio. Documento tipo ticket que describe un cambio pedido a uno o varios procedimientos. Identificado por un número, p. ej. REN 35145.
- **SP**: stored procedure. Escrito en NZPLSQL.
- **Clone**: copia de un procedimiento PROD ubicada en `DESA_*` con referencias de escritura modificadas y el sufijo del REN, usada para desarrollar y testear un cambio sin impactar producción.
- **Manifest**: `ren/REN_<N>/manifest.yaml`. El contrato de qué se clona bajo qué nombres para un REN dado.
- **Change point**: unidad atómica de trabajo listada en `analysis.yaml`. Un REN tiene muchos change points.
- **Baseline test**: correr el clon sin modificar contra PROD para verificar paridad de entorno.
- **Side effect**: cualquier procedimiento o statement cuya ejecución cambia estado fuera de la tabla output esperada (emails, logs externos, triggers que arrancan jobs downstream).
