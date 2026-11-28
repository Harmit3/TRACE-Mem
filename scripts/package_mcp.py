"""Build the optional source-only practice service from a fixed file inventory."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "requirements-mcp.txt",
    "docs/mcp/README.md", "docs/mcp/security.md", "docs/mcp/cross_agent_demo.md",
    "docs/mcp/client-example.json", "docs/mcp/codex.md", "docs/mcp/claude_desktop.md",
    "scripts/install_mcp.ps1", "scripts/serve_mcp.py", "scripts/test_mcp_integration.py",
    "scripts/package_mcp.py", "tests/test_mcp_store.py",
    "trace_mem/mcp_store.py", "trace_mem/mcp_server.py", "trace_mem/mcp_admin.py",
    "trace_mem/memory.py", "trace_mem/baselines.py", "trace_mem/claims.py",
    "trace_mem/controller.py", "trace_mem/data/memora.py", "trace_mem/hybrid_extraction.py",
    "trace_mem/llm_tasks.py", "trace_mem/providers.py", "trace_mem/semantic.py",
    "trace_mem/verification.py",
)


if __name__ == "__main__":
    destination = ROOT / "results/step45/TRACE-Mem-MCP-0.1.0-source.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "x") as archive:
        for name in sorted(FILES):
            info = ZipInfo(name)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (ROOT / name).read_bytes(), compress_type=ZIP_DEFLATED)
    print(destination)
