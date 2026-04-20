# nz-workbench

> Workbench asistido por IA para el mantenimiento de procedimientos de IBM Netezza. Framework para el flujo de trabajo REN: localizar, clonar a `DESA_*`, aplicar cambios quirúrgicos, comparar contra producción, documentar el cambio.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## Qué es este proyecto

Las empresas que usan IBM Netezza suelen acumular cientos de procedimientos almacenados con lógica de negocio que evoluciona durante años. Cuando llega un pedido para modificar esa lógica, el desarrollador típicamente:

1. Lee el pedido (acá lo llamamos **REN** — *Requerimiento de Negocio*).
2. Encuentra los procedimientos afectados.
3. Clona cada uno a una base de datos de desarrollo con un sufijo único.
4. Reescribe las referencias de escritura para que el clon toque `DESA_*` manteniendo las lecturas contra `PROD_*` para testing realista.
5. Aplica los cambios pedidos de forma quirúrgica.
6. Ejecuta el clon modificado y compara su salida contra producción.
7. Documenta lo que cambió.

`nz-workbench` es un framework Python + CLI + servidor MCP de Claude que automatiza los pasos 2–7 con garantías fuertes:

- **La IA nunca adivina.** Cualquier ambigüedad en el REN detiene el flujo y pregunta al humano.
- **Transparencia total.** Cada REN genera una carpeta con source, analysis, clarifications, manifest, diffs, reporte de test, decisiones y summary.
- **Memoria semántica.** Todos los procedimientos de producción se indexan localmente con BGE-M3 + Chroma, así RENs futuros pueden responder *"¿dónde está implementada esta regla de negocio?"* sin lectura bruta.
- **Cero fuga de datos.** Toda la lógica de negocio queda en la máquina del desarrollador. Este repo es el framework; tus datos de RENs están gitignored.

## Qué NO es

- **No** reemplaza la revisión humana. Es un copiloto. Toda decisión no trivial tiene un gate humano.
- **No** es un editor SQL general. Está acotado al flujo REN para Netezza.
- **No** es un driver directo de Netezza. Habla con `nz-mcp` que es el dueño del driver y la frontera de seguridad.

## Arquitectura en una mirada

```
Claude CLI  ─┐
Claude Desktop ─┤ (MCP stdio)
                │
                ▼
        nz-workbench (este proyecto)
             │
             ├─▶ Knowledge base (Chroma + BGE-M3, local)
             ├─▶ Analyzer (parsing del REN, clarificaciones)
             ├─▶ Migrator (reglas PROD→DESA, side effects)
             ├─▶ Tester (baseline + comparación)
             ├─▶ Docs writer (artifacts en docs/ y ren/)
             │
             ▼
        nz-mcp (https://github.com/Oscarsp15/nz-mcp)
             │
             ▼
        IBM Netezza
```

Ver [`docs/architecture/overview.md`](docs/architecture/overview.md) para la vista completa.

## Arranque rápido

### Requisitos previos

- Python 3.11 o más reciente.
- `nz-mcp` instalado y configurado contra tu entorno Netezza. Ver su [quickstart](https://github.com/Oscarsp15/nz-mcp#readme).
- Claude Code CLI o Claude Desktop (para manejar el servidor MCP interactivamente).

### Instalación

```bash
pipx install git+https://github.com/Oscarsp15/nz-workbench.git
# o para desarrollo:
git clone https://github.com/Oscarsp15/nz-workbench.git
cd nz-workbench
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate    # Linux/macOS
pip install -e ".[dev]"
```

### Crear tus archivos de arranque

El framework trae plantillas; tus datos reales se crean localmente y nunca se commitean:

```bash
cp docs/learning-log.md.template         docs/learning-log.md
cp docs/technical-decisions.md.template  docs/technical-decisions.md
cp docs/side-effects-catalog.md.template docs/side-effects-catalog.md
```

### Indexá tus procedimientos de producción

Bootstrap de día 1. Corre BGE-M3 en tu CPU local. Cero tokens de Claude, cero llamadas a APIs externas.

```bash
nz-workbench kb-bootstrap --databases PROD_MAESTROBI,PROD_COMERCIAL,PROD_MODELOS
```

Esperá ~2 horas para ~6.000 procedimientos en una laptop. ~1–2 GB en disco bajo `.nz-workbench/`.

### Configurar Claude Code para usar el servidor MCP

Agregá en tu `.claude.json` o `.mcp.json`:

```json
{
  "mcpServers": {
    "nz-workbench": {
      "command": "nz-workbench",
      "args": ["serve"]
    }
  }
}
```

Abrí Claude Code en el repo y preguntá:

> "Acabo de recibir el REN 35145. Empezamos con el análisis."

## Sesión típica de un REN

1. Pegá el documento del REN en la sesión de Claude (o guardalo como `ren/REN_35145/source.md`).
2. Pedile a Claude que analice — corre el analyzer, pregunta clarificaciones si hay ambigüedad.
3. Vos resolvés las clarificaciones (con el usuario de negocio si hace falta).
4. Claude genera el manifest, clona los procedimientos, corre el baseline test.
5. Claude aplica cada change point, te pide aprobación en los diffs, re-testea.
6. Vos revisás la comparación PROD vs DESA.
7. Claude escribe la documentación. Commiteás la carpeta del REN localmente (o la pusheás a un fork privado).

Flujo fase por fase: [`docs/architecture/ren-lifecycle.md`](docs/architecture/ren-lifecycle.md).

## Framework público vs datos privados

Este repo es **público** bajo MIT. Contiene:

- Código del framework (`src/nz_workbench/`).
- Plantillas (`docs/procedures/_TEMPLATE.md`, `ren/_TEMPLATE/`, `docs/*.md.template`).
- Standards, workflows y docs de arquitectura.
- Scripts de CI y regex de validación.

**Los datos privados de cada usuario están gitignored**:

- `ren/REN_*` — tus carpetas REN reales con contenido específico de tu empresa.
- `docs/procedures/*.md` (excepto `_TEMPLATE.md`) — nombres de procedimientos reales y su mapeo.
- `docs/learning-log.md`, `docs/technical-decisions.md`, `docs/side-effects-catalog.md` — tus notas acumuladas. Usá las versiones `.template` como punto de partida.
- `.nz-workbench/` — tus stores locales de Chroma y SQLite.

Para compartir tus datos con compañeros, hacé fork privado o usá un mecanismo aparte de sincronización (rsync a un drive compartido, repo git privado).

## Índice de documentación

- [`AGENTS.md`](AGENTS.md) — punto de entrada único para agentes IA y humanos que trabajen en este repo.
- [`docs/architecture/overview.md`](docs/architecture/overview.md) — diagrama del sistema y responsabilidades por módulo.
- [`docs/architecture/ren-lifecycle.md`](docs/architecture/ren-lifecycle.md) — flujo del REN, fase por fase.
- [`docs/architecture/prod-desa-rules.md`](docs/architecture/prod-desa-rules.md) — reglas exactas de reescritura al clonar.
- [`docs/architecture/knowledge-base.md`](docs/architecture/knowledge-base.md) — Chroma + BGE-M3 + estrategia de chunking.
- [`docs/standards/`](docs/standards/) — git workflow, auditoría de PR, testing, secretos, mantenibilidad.
- [`docs/adr/`](docs/adr/) — architecture decision records.

## Contribuciones

Se aceptan contribuciones públicas. Leé `AGENTS.md` primero. Todo PR pasa por la auditoría de siete dimensiones descripta en [`docs/standards/pr-audit.md`](docs/standards/pr-audit.md).

Abrí un issue antes de cambios grandes.

## Licencia

MIT — ver [LICENSE](LICENSE).

## Reconocimientos

- [`nz-mcp`](https://github.com/Oscarsp15/nz-mcp) — el servidor MCP con el que hablamos para todo acceso a Netezza.
- [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) — embedder multilingüe.
- [Chroma](https://www.trychroma.com/) — vector store embebido.
- [Model Context Protocol](https://modelcontextprotocol.io/) — el protocolo que hace natural la integración con Claude.
