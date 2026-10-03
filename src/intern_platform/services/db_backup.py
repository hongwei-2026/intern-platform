"""SQLite 数据库快照：启动时拍一份，之后有改动就跟着拍，方便整库回退。"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from intern_platform.config import PROJECT_ROOT, get_settings

_lock = threading.Lock()
_stop = threading.Event()
_thread: threading.Thread | None = None
_last_signature: tuple[int, int] | None = None


def backup_dir() -> Path:
    path = PROJECT_ROOT / "data" / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sqlite_path() -> Path | None:
    settings = get_settings()
    if settings.db_driver != "sqlite":
        return None
    url = settings.resolve_database_url()
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return None
    return Path(url.removeprefix(prefix))


def _signature(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size


def snapshot(*, force: bool = False) -> Path | None:
    """拷贝一份一致的数据库。没有变化时不重复拍，除非 force。"""
    source = sqlite_path()
    if source is None or not source.exists():
        return None
    signature = _signature(source)
    global _last_signature
    with _lock:
        if not force and signature == _last_signature:
            return None
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = backup_dir() / f"intern-{stamp}.db"
        if target.exists():
            target = backup_dir() / f"intern-{stamp}-{signature[0]}.db"
        src = sqlite3.connect(source)
        dst = sqlite3.connect(target)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        _last_signature = signature
        _prune(keep=3)
        return target


def list_backups() -> list[Path]:
    return sorted(backup_dir().glob("intern-*.db"), reverse=True)


def restore(backup: Path) -> Path:
    """用某份快照替换当前库。调用前应先停掉正在访问数据库的进程。"""
    source = sqlite_path()
    if source is None:
        raise RuntimeError("当前不是 SQLite，不能按文件恢复")
    if not backup.exists():
        raise FileNotFoundError(backup)
    safety = snapshot(force=True)
    src = sqlite3.connect(backup)
    dst = sqlite3.connect(source)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    if safety is None:
        raise RuntimeError("恢复前的快照没有生成")
    return safety


def _prune(keep: int) -> None:
    files = sorted(backup_dir().glob("intern-*.db"))
    for old in files[:-keep]:
        old.unlink(missing_ok=True)


def _loop() -> None:
    while not _stop.wait(60):
        try:
            snapshot()
        except Exception:
            continue


def start_backup_loop() -> None:
    global _thread
    if sqlite_path() is None or _thread is not None:
        return
    try:
        snapshot(force=True)
    except Exception:
        pass
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="db-backup", daemon=True)
    _thread.start()
