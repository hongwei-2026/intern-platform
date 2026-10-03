"""Build deploy zip with forward-slash paths; skip heavy/local-only dirs."""
from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "intern-platform-deploy-new.zip"
SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "backups",
    "coverage",
    ".cursor",
}
# Only skip repo-root runtime data/, never apps/web/src/data/
SKIP_ROOT_DIRS = {"data"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".db", ".db-wal", ".db-shm"}


def main() -> None:
    if OUT.exists():
        OUT.unlink()
    count = 0
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            if rel.parts and rel.parts[0] in SKIP_ROOT_DIRS:
                continue
            if any(part in SKIP_DIR_NAMES for part in rel.parts):
                continue
            if path.suffix.lower() in SKIP_SUFFIXES:
                continue
            if rel.name.startswith("intern-platform-deploy"):
                continue
            if rel.name.startswith("_tmp_"):
                continue
            arc = rel.as_posix()
            zf.write(path, arcname=arc)
            count += 1
    print("wrote", OUT, "files", count)
    guide = "apps/web/src/data/publishedGuide.ts"
    with zipfile.ZipFile(OUT) as check:
        names = set(check.namelist())
    if guide not in names:
        raise SystemExit(f"pack missing required file: {guide}")
    print("pack_ok includes", guide)


if __name__ == "__main__":
    main()
