"""云端/线上全量核对入口。

用法（项目根目录）:
  python scripts/cloud_suite.py --cloud
  python scripts/cloud_suite.py --web https://intern.openatom.club
  python scripts/cloud_suite.py --cloud --only security,smoke,browser
  SMOKE_WEB=http://127.0.0.1 python scripts/cloud_suite.py

默认套件: security → smoke → browser → e2e → extra
不含任何个人账号密码；仅用文档中的 Demo@123456 演示账号。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLOUD_WEB = "https://intern.openatom.club"

SUITES = (
    ("security", "scripts/verify_security.py", True),
    ("smoke", "scripts/cloud_smoke.py", False),
    ("browser", "scripts/cloud_browser.py", False),
    ("e2e", "scripts/cloud_e2e.py", False),
    ("extra", "scripts/cloud_extra_flows.py", False),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="云端全量测试套件")
    parser.add_argument("--cloud", action="store_true", help="打 https://intern.openatom.club")
    parser.add_argument("--web", default="", help="前端根地址，默认本地或 --cloud")
    parser.add_argument(
        "--only",
        default="",
        help="逗号分隔子集: security,smoke,browser,e2e,extra",
    )
    parser.add_argument("--skip-e2e", action="store_true", help="跳过会写数据的全链路 e2e")
    args = parser.parse_args()

    web = (args.web or os.environ.get("SMOKE_WEB") or "").rstrip("/")
    if args.cloud and not web:
        web = CLOUD_WEB
    if not web:
        web = "http://127.0.0.1"

    only = {x.strip() for x in args.only.split(",") if x.strip()}
    env = os.environ.copy()
    env["SMOKE_WEB"] = web
    env["SMOKE_API"] = f"{web}/api/v1"
    env["SECURITY_API_BASE"] = f"{web}/api/v1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    print()
    print("===== 云端/线上全量核对 =====")
    print(f"WEB: {web}")
    print(f"API: {env['SMOKE_API']}")
    print()

    results: list[tuple[str, int]] = []
    for name, rel, is_security in SUITES:
        if only and name not in only:
            continue
        if args.skip_e2e and name in {"e2e", "extra"}:
            print(f"[跳过] {name}")
            continue
        script = ROOT / rel
        if not script.is_file():
            print(f"[失败] 缺少脚本 {rel}")
            results.append((name, 1))
            continue
        cmd = [sys.executable, str(script)]
        if is_security:
            cmd.extend(["--base", env["SECURITY_API_BASE"]])
        print(f"----- {name}: {rel} -----")
        proc = subprocess.run(cmd, cwd=str(ROOT), env=env, check=False)
        results.append((name, proc.returncode))
        print(f"----- {name} exit={proc.returncode} -----")
        print()

    print("===== 套件汇总 =====")
    failed = 0
    for name, code in results:
        mark = "通过" if code == 0 else "失败"
        print(f"[{mark}] {name} (exit={code})")
        if code != 0:
            failed += 1
    print(f"合计 {len(results) - failed}/{len(results)} 套件通过")
    print()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
