"""MCP server for nz-workbench.

Exposes knowledge base tools to Claude CLI for intelligent SP maintenance.
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from nz_workbench.config import load_config
from nz_workbench.logging_config import configure_logging_for_stdio

# Constants
_MIN_DBS_FOR_COMPARE = 2  # Minimum databases needed for comparison
_MAX_DEPENDENCY_ROWS = 30  # Limit rows in dependency output

# Initialize MCP server
server = Server(
    name="nz-workbench",
    version="0.1.0",
    instructions="""
    Knowledge base tools for IBM Netezza stored procedure maintenance.
    Use these tools to understand SPs before editing, search for solutions,
    and save learnings for future reference.
    """,
)


def _get_db_path() -> Path:
    """Get the path to the metadata SQLite database."""
    cfg = load_config()
    return cfg.state_dir / "metadata.sqlite"


def _get_chroma_path() -> Path:
    """Get the path to the ChromaDB directory."""
    cfg = load_config()
    return cfg.state_dir / "chroma"


def _get_learnings_path() -> Path:
    """Get the path to the learnings SQLite database."""
    cfg = load_config()
    return cfg.state_dir / "learnings.sqlite"


def _ensure_learnings_db() -> None:
    """Create the learnings database if it doesn't exist."""
    path = _get_learnings_path()
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS learnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            database TEXT NOT NULL,
            schema TEXT NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_learnings_sp
        ON learnings(database, schema, name)
    """)
    conn.commit()
    conn.close()


@server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="kb_get_sp_context",
            description="""Get full context for a stored procedure before editing.
            Returns: code summary, known errors/solutions, business rules,
            dependencies, and human notes. ALWAYS call this before modifying an SP.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "database": {
                        "type": "string",
                        "description": "Database name (e.g., PROD_MODELOS)",
                    },
                    "schema": {
                        "type": "string",
                        "description": "Schema name (e.g., DBO)",
                    },
                    "name": {"type": "string", "description": "Procedure name"},
                },
                "required": ["database", "schema", "name"],
            },
        ),
        Tool(
            name="kb_search",
            description="""Semantic search across all indexed stored procedures.
            Use for conceptual queries like 'how are payments handled' or
            'error handling patterns'. Returns relevant code snippets.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 10)",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="kb_search_refs",
            description="""Search for SPs that reference a specific table.
            More precise than semantic search for structural queries like
            'which SPs INSERT into table X'. Returns exact matches.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name to search for"},
                    "operation": {
                        "type": "string",
                        "description": "Filter by operation: "
                        "INSERT, SELECT, UPDATE, DELETE, or ALL",
                        "default": "ALL",
                    },
                },
                "required": ["table"],
            },
        ),
        Tool(
            name="kb_save_learning",
            description="""Save a learning or note about a stored procedure.
            Use after solving a problem to help future debugging.
            Types: error_solution, business_rule, warning, dependency_note""",
            inputSchema={
                "type": "object",
                "properties": {
                    "database": {"type": "string", "description": "Database name"},
                    "schema": {"type": "string", "description": "Schema name"},
                    "name": {"type": "string", "description": "Procedure name"},
                    "type": {
                        "type": "string",
                        "enum": ["error_solution", "business_rule", "warning", "dependency_note"],
                        "description": "Type of learning",
                    },
                    "content": {"type": "string", "description": "The learning content"},
                },
                "required": ["database", "schema", "name", "type", "content"],
            },
        ),
        Tool(
            name="kb_compare_sps",
            description="""Compare a stored procedure across two databases.
            Useful to detect drift between environments (e.g., PROD_MODELOS vs PROD_ANALITICA).""",
            inputSchema={
                "type": "object",
                "properties": {
                    "schema": {"type": "string", "description": "Schema name"},
                    "name": {"type": "string", "description": "Procedure name"},
                    "database1": {"type": "string", "description": "First database"},
                    "database2": {"type": "string", "description": "Second database"},
                },
                "required": ["schema", "name", "database1", "database2"],
            },
        ),
        Tool(
            name="kb_get_table_dependencies",
            description="""Get all SPs that depend on a specific table.
            Useful before modifying a table to understand impact.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name"},
                },
                "required": ["table"],
            },
        ),
    ]


_TOOL_HANDLERS: dict[str, Any] = {
    "kb_get_sp_context": "_handle_get_sp_context",
    "kb_search": "_handle_search",
    "kb_search_refs": "_handle_search_refs",
    "kb_save_learning": "_handle_save_learning",
    "kb_compare_sps": "_handle_compare_sps",
    "kb_get_table_dependencies": "_handle_get_table_dependencies",
}


@server.call_tool()  # type: ignore[untyped-decorator]
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    handler_name = _TOOL_HANDLERS.get(name)
    if handler_name is None:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    handler = globals()[handler_name]
    result: list[TextContent] = await handler(arguments)
    return result


async def _handle_get_sp_context(args: dict[str, Any]) -> list[TextContent]:
    """Get full context for an SP."""
    db = args["database"]
    schema = args["schema"]
    name = args["name"]
    fqn = f"{db}.{schema}.{name}"

    result_parts: list[str] = [f"# Context for {fqn}\n"]

    # Get procedure metadata
    db_path = _get_db_path()
    if db_path.exists():
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get basic info
        cursor.execute(
            """SELECT body_sha256, indexed_at, chunker_version
               FROM procedure
               WHERE database=? AND schema=? AND name=?""",
            (db, schema, name),
        )
        row = cursor.fetchone()
        if row:
            result_parts.append("## Metadata")
            result_parts.append(f"- Hash: {row[0][:12]}...")
            result_parts.append(f"- Indexed: {row[1]}")
            result_parts.append("")

        # Get table references
        cursor.execute(
            """SELECT DISTINCT op, ref_object
               FROM sp_reference
               WHERE database=? AND schema=? AND name=?
               ORDER BY op, ref_object""",
            (db, schema, name),
        )
        refs = cursor.fetchall()
        if refs:
            result_parts.append("## Table Dependencies")
            for op, ref_obj in refs:
                result_parts.append(f"- [{op}] {ref_obj}")
            result_parts.append("")

        conn.close()

    # Get learnings
    learnings_path = _get_learnings_path()
    if learnings_path.exists():
        conn = sqlite3.connect(learnings_path)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT type, content, created_at
               FROM learnings
               WHERE database=? AND schema=? AND name=?
               ORDER BY created_at DESC""",
            (db, schema, name),
        )
        learnings = cursor.fetchall()
        if learnings:
            result_parts.append("## Known Issues & Learnings")
            for ltype, content, created in learnings:
                result_parts.append(f"### [{ltype}] ({created[:10]})")
                result_parts.append(content)
                result_parts.append("")
        conn.close()

    if len(result_parts) == 1:
        result_parts.append("No context found for this SP. It may not be indexed yet.")

    return [TextContent(type="text", text="\n".join(result_parts))]


async def _handle_search(args: dict[str, Any]) -> list[TextContent]:
    """Semantic search in the KB."""
    query = args["query"]
    limit = args.get("limit", 10)

    try:
        import chromadb  # noqa: PLC0415
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        model = SentenceTransformer("BAAI/bge-m3")
        client = chromadb.PersistentClient(path=str(_get_chroma_path()))
        collection = client.get_collection("procedure_chunks")

        query_embedding = model.encode([query], normalize_embeddings=True).tolist()
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=limit,
            include=["metadatas", "documents"],
        )

        output_parts = [f"# Search Results for: {query}\n"]
        seen: set[str] = set()

        metadatas_list = results.get("metadatas")
        documents_list = results.get("documents")
        if not metadatas_list or not documents_list:
            return [TextContent(type="text", text="No results found.")]

        metadatas = metadatas_list[0]
        documents = documents_list[0]
        for meta, doc in zip(metadatas, documents, strict=True):
            db_name = meta.get("database", "?")
            schema_name = meta.get("schema", "?")
            proc_name = meta.get("procedure", "?")
            sp = f"{db_name}.{schema_name}.{proc_name}"
            if sp not in seen:
                seen.add(sp)
                snippet = doc[:300].replace("\n", " ").strip()
                output_parts.append(f"## {sp}")
                output_parts.append(f"```sql\n{snippet}...\n```\n")

        return [TextContent(type="text", text="\n".join(output_parts))]

    except Exception as e:
        return [TextContent(type="text", text=f"Search error: {e}")]


async def _handle_search_refs(args: dict[str, Any]) -> list[TextContent]:
    """Search for SPs by table reference."""
    table = args["table"].lower()
    operation = args.get("operation", "ALL").upper()

    db_path = _get_db_path()
    if not db_path.exists():
        return [TextContent(type="text", text="KB not initialized. Run kb-bootstrap first.")]

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if operation == "ALL":
        cursor.execute(
            """SELECT DISTINCT database, schema, name, op
               FROM sp_reference
               WHERE LOWER(ref_object) LIKE ?
               ORDER BY op, database, schema, name""",
            (f"%{table}%",),
        )
    else:
        cursor.execute(
            """SELECT DISTINCT database, schema, name, op
               FROM sp_reference
               WHERE LOWER(ref_object) LIKE ? AND UPPER(op) = ?
               ORDER BY database, schema, name""",
            (f"%{table}%", operation),
        )

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return [TextContent(type="text", text=f"No SPs found referencing '{table}'")]

    output_parts = [f"# SPs referencing '{table}'\n"]
    current_op = None

    for db, schema, name, op in rows:
        if op != current_op:
            current_op = op
            output_parts.append(f"\n## {op}")
        output_parts.append(f"- {db}.{schema}.{name}")

    return [TextContent(type="text", text="\n".join(output_parts))]


async def _handle_save_learning(args: dict[str, Any]) -> list[TextContent]:
    """Save a learning about an SP."""
    _ensure_learnings_db()

    conn = sqlite3.connect(_get_learnings_path())
    conn.execute(
        """INSERT INTO learnings (database, schema, name, type, content)
           VALUES (?, ?, ?, ?, ?)""",
        (args["database"], args["schema"], args["name"], args["type"], args["content"]),
    )
    conn.commit()
    conn.close()

    fqn = f"{args['database']}.{args['schema']}.{args['name']}"
    return [TextContent(type="text", text=f"✓ Learning saved for {fqn}")]


async def _handle_compare_sps(args: dict[str, Any]) -> list[TextContent]:
    """Compare an SP across two databases."""
    schema = args["schema"]
    name = args["name"]
    db1 = args["database1"]
    db2 = args["database2"]

    db_path = _get_db_path()
    if not db_path.exists():
        return [TextContent(type="text", text="KB not initialized. Run kb-bootstrap first.")]

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """SELECT database, body_sha256, indexed_at
           FROM procedure
           WHERE schema=? AND name=? AND database IN (?, ?)""",
        (schema, name, db1, db2),
    )
    rows = cursor.fetchall()
    conn.close()

    if len(rows) < _MIN_DBS_FOR_COMPARE:
        found = [r[0] for r in rows]
        missing = [d for d in [db1, db2] if d not in found]
        return [TextContent(type="text", text=f"SP not found in: {', '.join(missing)}")]

    info = {r[0]: {"hash": r[1], "indexed": r[2]} for r in rows}

    output_parts = [f"# Comparison: {schema}.{name}\n"]
    output_parts.append("| Database | Hash | Indexed |")
    output_parts.append("|----------|------|---------|")

    for db in [db1, db2]:
        h = info[db]["hash"][:12]
        idx = info[db]["indexed"][:10]
        output_parts.append(f"| {db} | {h}... | {idx} |")

    if info[db1]["hash"] == info[db2]["hash"]:
        output_parts.append("\n✅ **IDENTICAL** - Same code in both databases")
    else:
        output_parts.append("\n⚠️ **DIFFERENT** - Code differs between databases")

    return [TextContent(type="text", text="\n".join(output_parts))]


async def _handle_get_table_dependencies(args: dict[str, Any]) -> list[TextContent]:
    """Get all SPs that depend on a table."""
    table = args["table"].lower()

    db_path = _get_db_path()
    if not db_path.exists():
        return [TextContent(type="text", text="KB not initialized. Run kb-bootstrap first.")]

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """SELECT database, schema, name, op, COUNT(*) as refs
           FROM sp_reference
           WHERE LOWER(ref_object) LIKE ?
           GROUP BY database, schema, name, op
           ORDER BY refs DESC, database, schema, name""",
        (f"%{table}%",),
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return [TextContent(type="text", text=f"No SPs depend on '{table}'")]

    output_parts = [f"# SPs depending on '{table}'\n"]
    output_parts.append("| SP | Operation | References |")
    output_parts.append("|-----|-----------|------------|")

    for db, schema, name, op, refs in rows[:_MAX_DEPENDENCY_ROWS]:
        output_parts.append(f"| {db}.{schema}.{name} | {op} | {refs} |")

    if len(rows) > _MAX_DEPENDENCY_ROWS:
        output_parts.append(f"\n... and {len(rows) - _MAX_DEPENDENCY_ROWS} more")

    return [TextContent(type="text", text="\n".join(output_parts))]


def run_stdio_server() -> None:
    """Run the MCP server over stdio."""
    configure_logging_for_stdio()
    asyncio.run(_run_server())


async def _run_server() -> None:
    """Async server runner."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


__all__ = ["run_stdio_server"]
