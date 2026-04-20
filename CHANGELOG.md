# Changelog

All notable changes to this project will be documented in this file. Each entry is in **español** y **english**.

El formato sigue [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) y el proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- ES: bootstrap inicial del proyecto — `AGENTS.md`, docs de arquitectura, standards, templates de RENs, skeleton de código, scripts CI.
- EN: initial project bootstrap — `AGENTS.md`, architecture docs, standards, REN templates, code skeleton, CI scripts.
- ES: knowledge base sprint 1 — chunker NZPLSQL, embedder BGE-M3 lazy, Chroma store, SQLite metadata store, indexer y wiring de CLI (`kb-bootstrap`, `kb-refresh`, `kb-refresh-cron`).
- EN: knowledge base sprint 1 — NZPLSQL chunker, lazy BGE-M3 embedder, Chroma store, SQLite metadata store, indexer and CLI wiring (`kb-bootstrap`, `kb-refresh`, `kb-refresh-cron`).
- ES: barra de progreso Rich en `kb-bootstrap` / `kb-refresh` / `kb-refresh-cron` con descripción por procedimiento, contador M/N, tiempo transcurrido y ETA; durante la barra el logging INFO se silencia para no romper el render. El indexer expone un callback `on_progress` agnóstico de UI (`ProgressCallback`/`ProgressEvent`).
- EN: Rich progress bar on `kb-bootstrap` / `kb-refresh` / `kb-refresh-cron` showing per-procedure description, M/N counter, elapsed time, and ETA; INFO logs are silenced while the bar is active to keep the render clean. The indexer exposes a UI-agnostic `on_progress` callback (`ProgressCallback`/`ProgressEvent`).

### Fixed
- ES: `_progress_context` ahora silencia también los eventos INFO de structlog mediante un procesador controlado por `set_suppress_info_events`. Antes solo bajaba el root logger, que no afectaba a structlog por usar `PrintLoggerFactory` directo — los eventos `kb_index_proc_start/done` seguían rompiendo la animación de la barra Rich.
- EN: `_progress_context` now silences structlog INFO events too via a processor driven by `set_suppress_info_events`. Previously only the root stdlib logger was lowered, which had no effect on structlog (goes through `PrintLoggerFactory` directly) — events like `kb_index_proc_start/done` kept shredding the Rich bar animation.
- ES: `chunker.chunk` garantiza que todos los chunks tienen ≤ `MAX_TOKENS` (2000) mediante un corte duro post-stitch. Antes, procedures con bloques monolíticos sin semicolons top-level podían generar chunks > 8192 tokens, que BGE-M3 truncaba silenciosamente y dejaba la cola de la SP sin representación en el embedding (recall cero para búsquedas en esa zona).
- EN: `chunker.chunk` now guarantees every chunk is ≤ `MAX_TOKENS` (2000) via a post-stitch hard ceiling. Before, procedures with monolithic blocks and no top-level semicolons could yield chunks > 8192 tokens, which BGE-M3 silently truncates — tail content had zero embedding representation and was invisible to semantic search.

### Added
- ES: `CHUNKER_VERSION` persistido en `procedure.chunker_version` (migración automática para DBs legacy). El indexer re-chunka/re-embedda cuando la versión almacenada no coincide con la actual, aunque `body_sha256` sea el mismo. Así un bump del chunker dispara re-index sin requerir `--force` manual.
- EN: `CHUNKER_VERSION` persisted in `procedure.chunker_version` (auto-migrates legacy DBs). The indexer re-chunks/re-embeds when the stored version doesn't match the current one, even if `body_sha256` is unchanged — a chunker bump triggers re-index without requiring manual `--force`.

### Changed
- ES: indexer deja de llamar `nz_analyze_procedure_references` (tool inexistente en nz-mcp). La extracción de referencias estructurales ahora va 100% por regex sobre el DDL. Esto elimina los ~4 WARNINGs `Tool '…' not listed, no validation will be performed` por procedure que rompían la barra Rich. Si nz-mcp expone la tool en el futuro, se re-enchufa en `_index_one`.
- EN: the indexer no longer calls `nz_analyze_procedure_references` (tool doesn't exist in nz-mcp). Structural reference extraction is now 100% regex over the DDL. Removes the ~4 `Tool '…' not listed, no validation will be performed` WARNINGs per procedure that shredded the Rich bar. If nz-mcp exposes the tool later, wire it back in `_index_one`.

### Fixed
- ES: `NzMcpClient.call()` ahora desenvuelve el envelope MCP de `tools/call` (lee `structuredContent.result`) y mapea errores estructurados; incluye fallback a JSON en bloques `content`.
- EN: `NzMcpClient.call()` now unwraps the MCP `tools/call` envelope (reads `structuredContent.result`) and maps structured errors; includes fallback to JSON in `content` blocks.
- ES: `nz-workbench kb-bootstrap` ahora lista schemas via `nz_list_schemas` y luego procedures por schema (antes devolvía `0/0/0` en silencio porque `nz_list_procedures` requiere `schema` en nz-mcp). Errores de tools se propagan a `IndexReport.errors` en lugar de silenciarse.
- EN: `nz-workbench kb-bootstrap` now lists schemas via `nz_list_schemas` and then procedures per schema (previously returned `0/0/0` silently because `nz_list_procedures` requires `schema` in nz-mcp). Tool errors now surface in `IndexReport.errors` instead of being swallowed.
