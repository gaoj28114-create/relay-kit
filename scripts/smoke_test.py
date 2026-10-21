#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""接力包 · Smoke Test

建卡 → set → ask-style → preflight → done，一条龙验证没崩。
任何一步非零退出，立即报错。
"""
import subprocess
import sys
import os

PYTHON = sys.executable
RELAY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "relay.py")


def run(args, expect=0):
    print("\n$ python relay.py %s" % " ".join(args))
    r = subprocess.run([PYTHON, RELAY] + args, capture_output=True, text=True, encoding="utf-8")
    print(r.stdout)
    if r.returncode != expect:
        print("✗ FAIL: 退出码 %d，期望 %d" % (r.returncode, expect))
        print(r.stderr)
        sys.exit(1)
    return r


def main():
    print("=" * 62)
    print("接力包 · Smoke Test")
    print("=" * 62)

    # 1. doctor
    run(["doctor"])

    # 2. 建测试卡
    r = run(["new", "smoke test", "--goal", "一条龙验证", "--deliverable", "报告"])
    tid = r.stdout.strip().split("\n")[0].strip()
    print("测试卡: %s" % tid)

    # 3. ask-style（没选过，应该给建议）
    run(["ask-style", tid])

    # 4. 选风格档
    run(["set", tid, "--style", "自适应档"])

    # 5. ask-style（选过了，应该显示已定）
    run(["ask-style", tid])

    # 6. 加 decision（preflight 阻断项）
    run(["set", tid, "--decision", "已定：输出用中文"])

    # 7. preflight（应该过）
    run(["preflight", tid])

    # 8. preflight --json
    run(["preflight", tid, "--json"])

    # 9. go --json
    run(["go", "--json"])

    # 10. done 收尾
    run(["done", tid, "--note", "smoke test 通过"])

    print("\n" + "=" * 62)
    print("✓ Smoke Test 全部通过")
    print("=" * 62)


if __name__ == "__main__":
    main()
