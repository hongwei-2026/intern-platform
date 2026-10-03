"""列出或恢复 SQLite 快照。恢复前先停掉 8001 上的 API。"""

from __future__ import annotations

import argparse
from pathlib import Path

from intern_platform.services.db_backup import list_backups, restore


def main() -> None:
    parser = argparse.ArgumentParser(description="列出或恢复数据库快照")
    parser.add_argument("--list", action="store_true", help="列出快照")
    parser.add_argument("--file", help="要恢复的快照文件名或路径")
    args = parser.parse_args()
    if args.list or not args.file:
        for path in list_backups():
            print(path)
        return
    safety = restore(Path(args.file))
    print(f"已恢复。恢复前的库另存为 {safety}")


if __name__ == "__main__":
    main()
