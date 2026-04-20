# Changelog

All notable changes to this project will be documented in this file. Each entry is in **español** y **english**.

El formato sigue [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) y el proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- ES: bootstrap inicial del proyecto — `AGENTS.md`, docs de arquitectura, standards, templates de RENs, skeleton de código, scripts CI.
- EN: initial project bootstrap — `AGENTS.md`, architecture docs, standards, REN templates, code skeleton, CI scripts.
- ES: knowledge base sprint 1 — chunker NZPLSQL, embedder BGE-M3 lazy, Chroma store, SQLite metadata store, indexer y wiring de CLI (`kb-bootstrap`, `kb-refresh`, `kb-refresh-cron`).
- EN: knowledge base sprint 1 — NZPLSQL chunker, lazy BGE-M3 embedder, Chroma store, SQLite metadata store, indexer and CLI wiring (`kb-bootstrap`, `kb-refresh`, `kb-refresh-cron`).

### Fixed
- ES: `NzMcpClient.call()` ahora desenvuelve el envelope MCP de `tools/call` (lee `structuredContent.result`) y mapea errores estructurados; incluye fallback a JSON en bloques `content`.
- EN: `NzMcpClient.call()` now unwraps the MCP `tools/call` envelope (reads `structuredContent.result`) and maps structured errors; includes fallback to JSON in `content` blocks.
- ES: `nz-workbench kb-bootstrap` ahora lista schemas via `nz_list_schemas` y luego procedures por schema (antes devolvía `0/0/0` en silencio porque `nz_list_procedures` requiere `schema` en nz-mcp). Errores de tools se propagan a `IndexReport.errors` en lugar de silenciarse.
- EN: `nz-workbench kb-bootstrap` now lists schemas via `nz_list_schemas` and then procedures per schema (previously returned `0/0/0` silently because `nz_list_procedures` requires `schema` in nz-mcp). Tool errors now surface in `IndexReport.errors` instead of being swallowed.
