import os
import sys
import click
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.indexer import CodeIndexer


def scan_project(root_path: str) -> list[str]:
    """Scan a directory for source files."""
    extensions = {".py", ".js", ".ts", ".go", ".rs", ".java", ".cpp", ".c"}
    files = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in
                       {"node_modules", "venv", "__pycache__", ".git", "dist", "build"}]
        for filename in filenames:
            if Path(filename).suffix in extensions:
                files.append(os.path.join(dirpath, filename))
    return files


def import_file(filepath: str, root_path: str, neo4j, chroma) -> dict:
    """Import a single file into the knowledge graph."""
    indexer = CodeIndexer()
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    ext = Path(filepath).suffix
    lang_map = {".py": "python", ".js": "javascript", ".ts": "typescript", ".go": "go"}
    language = lang_map.get(ext, "unknown")
    rel_path = os.path.relpath(filepath, root_path)
    result = indexer.index_file(rel_path, content, language)
    neo4j.upsert_index_result(result)
    for func in result.functions:
        uid = f"{func.file_path}:{func.name}"
        chroma.add_function_embedding(uid=uid, body=func.body,
            metadata={"name": func.name, "file": func.file_path, "docstring": func.docstring})
    for cls in result.classes:
        uid = f"{cls.file_path}:{cls.name}"
        chroma.add_class_embedding(uid=uid, body=cls.body,
            metadata={"name": cls.name, "file": cls.file_path, "docstring": cls.docstring})
    return {"file": rel_path, "functions": len(result.functions), "classes": len(result.classes), "calls": len(result.calls)}


@click.command()
@click.argument("project_path", type=click.Path(exists=True))
def preimport(project_path: str):
    """Bulk import a codebase into the Sea Qwens knowledge graph."""
    project_path = os.path.abspath(project_path)
    click.echo(f"Scanning project: {project_path}")
    from services.librarian.neo4j_store import Neo4jStore
    from services.librarian.chroma_store import ChromaStore
    neo4j = Neo4jStore()
    chroma = ChromaStore()
    files = scan_project(project_path)
    click.echo(f"Found {len(files)} source files")
    total_funcs = 0
    total_classes = 0
    total_calls = 0
    errors = 0
    for i, filepath in enumerate(files):
        try:
            result = import_file(filepath, project_path, neo4j, chroma)
            total_funcs += result.get("functions", 0)
            total_classes += result.get("classes", 0)
            total_calls += result.get("calls", 0)
            if (i + 1) % 10 == 0:
                click.echo(f"  Processed {i + 1}/{len(files)} files...")
        except Exception as e:
            click.echo(f"  ERROR: {filepath}: {e}")
            errors += 1
    click.echo("")
    click.echo("=" * 50)
    click.echo("Import complete!")
    click.echo(f"  Files:     {len(files) - errors}")
    click.echo(f"  Classes:   {total_classes}")
    click.echo(f"  Functions: {total_funcs}")
    click.echo(f"  Calls:     {total_calls}")
    if errors:
        click.echo(f"  Errors:    {errors}")
    click.echo("=" * 50)


if __name__ == "__main__":
    preimport()
