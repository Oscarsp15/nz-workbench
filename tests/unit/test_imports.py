"""Smoke test: every public module imports without executing side effects."""

from __future__ import annotations

import importlib

import pytest

# Modules we expect to import cleanly at package load time.
_PUBLIC_MODULES = [
    "nz_workbench",
    "nz_workbench.cli",
    "nz_workbench.config",
    "nz_workbench.errors",
    "nz_workbench.kb",
    "nz_workbench.kb.chunker",
    "nz_workbench.kb.embedder",
    "nz_workbench.kb.chroma_store",
    "nz_workbench.kb.metadata_store",
    "nz_workbench.kb.indexer",
    "nz_workbench.kb.explainer",
    "nz_workbench.analyzer",
    "nz_workbench.analyzer.ren_parser",
    "nz_workbench.analyzer.clarification",
    "nz_workbench.analyzer.reference_finder",
    "nz_workbench.migrator",
    "nz_workbench.migrator.rules",
    "nz_workbench.migrator.manifest",
    "nz_workbench.migrator.side_effects",
    "nz_workbench.migrator.orchestrator",
    "nz_workbench.tester",
    "nz_workbench.tester.baseline",
    "nz_workbench.tester.comparison",
    "nz_workbench.tester.differ",
    "nz_workbench.docs_writer",
    "nz_workbench.docs_writer.procedure_doc",
    "nz_workbench.docs_writer.learning_log",
    "nz_workbench.docs_writer.ren_folder",
    "nz_workbench.nz_mcp_client",
    "nz_workbench.nz_mcp_client.client",
]


@pytest.mark.unit
@pytest.mark.parametrize("module_name", _PUBLIC_MODULES)
def test_module_imports(module_name: str) -> None:
    importlib.import_module(module_name)


@pytest.mark.unit
def test_version_is_a_string() -> None:
    from nz_workbench import __version__

    assert isinstance(__version__, str)
    assert __version__
