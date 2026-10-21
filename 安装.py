#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""接力包 · 一键安装

做四件事，一次做完，不用你手工改任何路径：
  1. 把本技能装到本机技能根（自动探测，~/.agents/skills 优先）
  2. 建状态目录（~/.relay，你自己的任务与画像放这）
  3. 往 AGENTS.md / CLAUDE.md 写一段"换 AI 接着干"的常驻指令
  4. 自检并打印结果

诚实说明：第 3 步写的是**文字指令**，不是系统钩子。
它能提高"AI 主动去读状态"的概率，但**不保证**——技能是"按需加载"的，
客户端不会因为装了技能就自动执行任何动作。

零依赖（Python 3.7+ 标准库）。不联网、不改系统设置、可重复运行、可卸载。

用法：
    python 安装.py                 # 装（默认：技能 + 注入块）
    python 安装.py --dry-run       # 只看看会做什么，不动手
    python 安装.py --list          # 看看探测到哪些技能根
    python 安装.py --no-agents     # 只装技能，不写注入块
    python 安装.py --agents-only   # 只写注入块，不装技能
    python 安装.py --root <目录>    # 指定技能根
    python 安装.py --uninstall     # 卸载（移除注入块；状态目录保留，需手动删）
"""
from __future__ import annotations

import argparse
import io
import os
import shutil
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
else:  # pragma: no cover
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SKILL_NAME = "接力包"
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
MARK_BEGIN = "<!-- BEGIN relay-kit -->"
MARK_END = "<!-- END relay-kit -->"

INJECT_BLOCK = f"""{MARK_BEGIN}
## 任务接力

### 一、用户给出**新任务**时：先问清真实需求，再动手

**不要拿到一句话就开工。** 先把原话拆成四要素，标「已知 / 未知」：

- **交付物**：要什么形态（文档 / 代码 / 表格 / 结论 / 系统）
- **领域**：哪个技术栈或业务域
- **关键动作**：生成 / 审查 / 迁移 / 排障 / 调研
- **验收标准**：怎么算做完了

**只对"不问就会做错方向"的项提问，最多 3 条**；能合理默认的，给默认值并说明"不接受就说不"。
提问用结构化工具（豆包 `interaction.ask`、Claude Code `AskUserQuestion`）；纯文本环境给编号选项 + 默认值。

**需求确认之后**才做这两件事：① 建卡落状态 ② 按「本地技能 → 本地知识/脚本 → 提示用户安装 → 自写并审计」选技能。

> **例外**：一句话能做完的小事（翻译一句、格式化一段）直接做，不追问、不建卡。

### 二、听到「继续」「接着做」「接着上次」「换个 AI 接着弄」「我们做到哪了」「上次那个做完没」

**第一件事就是跑下面这条，别先说话：**

`python "<技能目录>/scripts/relay.py" go`

- **有进行中的任务** → 直接接着干。**不要再问**已写在状态里的目标、已定决策、边界。
- **没有** → 按上面第一节走。

### 三、本机没装「接力包」技能时：**直接提示用户安装**

**不要静默跳过。** 用结构化提问工具问一次：

> 「要不要装一个『接力包』？它能让换 AI 接着干也不丢进度，并在动手前先问清你的需求。
>  装法：技能目录放进 `~/.agents/skills/`，跑一次 `python 安装.py`。
>  ① 装（帮我走一遍）　② 先不装，这次照常做」

**规矩**：同一会话最多提示一次；用户选②就不要再提；**绝不替用户下载或写技能目录**——安装必须用户本人确认。
（技能目录通常是 `~/.agents/skills/{SKILL_NAME}`。）
{MARK_END}"""


def home():
    return os.path.expanduser("~")


def state_root():
    env = (os.environ.get("RELAY_HOME") or "").strip()
    if env:
        return os.path.abspath(os.path.expanduser(env))
    return os.path.join(home(), ".relay")


def discover_roots():
    """探测技能根。~/.agents/skills 在首位（Agent Skills 生态的跨工具共享目录）。"""
    h = home()
    cands = [
        os.path.join(h, ".agents", "skills"),
        os.path.join(h, ".claude", "skills"),
        os.path.join(h, ".codex", "skills"),
        os.path.join(h, ".cursor", "skills"),
        os.path.join(h, ".gemini", "skills"),
        os.path.join(h, ".copilot", "skills"),
        os.path.join(h, ".workbuddy", "skills"),
    ]
    existing, missing = [], []
    seen = set()
    for p in cands:
        p = os.path.abspath(p)
        k = p.casefold()
        if k in seen:
            continue
        seen.add(k)
        (existing if os.path.isdir(p) else missing).append(p)
    return existing, missing


def rule_files():
    """要写注入块的规则文件。AGENTS.md 是生态通用名，CLAUDE.md 给 Claude Code。"""
    h = home()
    return [
        os.path.join(h, ".agents", "AGENTS.md"),
        os.path.join(h, ".claude", "CLAUDE.md"),
        os.path.join(h, ".codex", "AGENTS.md"),
    ]


# ---------------------------------------------------------------- 步骤

def step_install_skill(root, dry):
    target = os.path.join(root, SKILL_NAME)
    print("\n[1/4] 安装技能")
    print("      源：%s" % SRC_DIR)
    print("      到：%s" % target)
    if dry:
        print("      (dry-run，不动手)")
        return target, True
    try:
        os.makedirs(root, exist_ok=True)
        if os.path.abspath(target).casefold() == SRC_DIR.casefold():
            print("      ✓ 已经在目标位置，无需复制")
            return target, True
        if os.path.isdir(target):
            shutil.rmtree(target)
        shutil.copytree(SRC_DIR, target, ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", "config.local.json"))
        print("      ✓ 已安装")
        return target, True
    except Exception as exc:
        print("      ✗ 失败：%s" % exc)
        return target, False


def step_state(dry):
    root = state_root()
    print("\n[2/4] 建状态目录")
    print("      %s" % root)
    if dry:
        print("      (dry-run，不动手)")
        return root, True
    try:
        os.makedirs(os.path.join(root, "tasks"), exist_ok=True)
        prof = os.path.join(root, "用户画像.md")
        if not os.path.isfile(prof):
            _write_text(prof,
                        "# 用户画像\n\n"
                        "> 由「接力包」维护。只存**稳定、可跨任务复用**的偏好。\n"
                        "> 仅存在于本地，不上传任何服务。\n\n"
                        "（空）\n")
        print("      ✓ 已就绪（你的任务与画像都在这，换机器需自己搬）")
        return root, True
    except Exception as exc:
        print("      ✗ 失败：%s" % exc)
        return root, False


def _read_text(path):
    """原样读取（newline="" 不做行尾归一化，保住 CRLF / LF 原貌）。"""
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def _write_text(path, text):
    """原样写入。

    newline="" 是关键：Windows 上 open(..., "w") 默认会把 "\\n" 翻译成 "\\r\\n"，
    那会把用户整个文件的行尾符换掉（git diff 全红）。必须显式关掉这个翻译。
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def _match_eol(old, block):
    """让注入块跟随目标文件的行尾风格；空文件或 LF 文件保持 LF。"""
    if old.count("\r\n") > 0 and old.count("\r\n") >= old.count("\n") - old.count("\r\n"):
        return block.replace("\n", "\r\n")
    return block


def _write_block(path, dry):
    """把注入块写进规则文件；已有同名块则替换，其余内容原样保留。"""
    old = ""
    if os.path.isfile(path):
        try:
            old = _read_text(path)
        except Exception:
            old = ""

    block = _match_eol(old, INJECT_BLOCK or "")

    if MARK_BEGIN in old and MARK_END in old:
        start = old.index(MARK_BEGIN)
        end = old.index(MARK_END) + len(MARK_END)
        new = old[:start] + block + old[end:]
        action = "替换旧块"
    elif old.strip():
        nl = "\r\n" if old.count("\r\n") > 0 else "\n"
        new = old.rstrip("\r\n") + nl + nl + block + nl
        action = "追加"
    else:
        new = INJECT_BLOCK + "\n"
        action = "新建"

    if dry:
        return action, True
    try:
        _write_text(path, new)
        return action, True
    except Exception as exc:
        return "失败：%s" % exc, False


def step_agents(dry):
    print("\n[3/4] 写注入块（让 AI 在你说「继续」时先读状态）")
    print("      说明：这是**文字指令**，不是系统钩子——能提高触发率，不保证 100%")
    ok = True
    for path in rule_files():
        action, good = _write_block(path, dry)
        flag = "✓" if good else "✗"
        print("      %s %s（%s）" % (flag, path, action))
        ok = ok and good
    return ok


def step_doctor(target):
    print("\n[4/4] 自检")
    relay = os.path.join(target, "scripts", "relay.py")
    if not os.path.isfile(relay):
        print("      ✗ 找不到 relay.py，安装可能不完整")
        return False
    print("      ✓ 脚本就位：%s" % relay)
    print("      ✓ Python %s" % sys.version.split()[0])
    print("\n      下一步：跑一次初始化看看")
    print("        python \"%s\" init" % relay)
    return True


# ---------------------------------------------------------------- 卸载

def uninstall(dry):
    print("=" * 62)
    print("接力包 · 卸载")
    print("=" * 62)
    for path in rule_files():
        if not os.path.isfile(path):
            continue
        try:
            txt = _read_text(path)
        except Exception:
            continue
        if MARK_BEGIN not in txt:
            continue
        nl = "\r\n" if txt.count("\r\n") > 0 else "\n"
        new = txt[:txt.index(MARK_BEGIN)].rstrip("\r\n")
        new = (new + nl) if new.strip() else ""
        if dry:
            print("\n  (dry-run) 会从 %s 移除注入块" % path)
            continue
        try:
            _write_text(path, new)
        except Exception as exc:
            print("\n  ✗ 写入失败：%s（%s）" % (path, exc))
            continue
        print("\n  ✓ 已移除注入块：%s" % path)

    print("\n  技能目录请手动删（在技能根下的 %s）。" % SKILL_NAME)
    print("  状态目录 %s 保留着——要清干净就手动删。" % state_root())
    print("\n  注意：客户端不会热重载技能，删完记得新开一个会话。")
    return 0


# ---------------------------------------------------------------- 主流程

def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="安装.py",
        description="接力包 · 一键安装（零依赖、可重复运行、可卸载）",
    )
    ap.add_argument("--root", help="指定技能根（默认自动探测，~/.agents/skills 优先）")
    ap.add_argument("--dry-run", action="store_true", help="只看看会做什么")
    ap.add_argument("--list", action="store_true", help="列出探测到的技能根")
    ap.add_argument("--no-agents", action="store_true", help="只装技能，不写注入块")
    ap.add_argument("--agents-only", action="store_true", help="只写注入块，不装技能")
    ap.add_argument("--uninstall", action="store_true", help="卸载")
    args = ap.parse_args(argv)

    print("=" * 62)
    print("接力包 · 一键安装")
    print("=" * 62)

    if args.uninstall:
        return uninstall(args.dry_run)

    existing, missing = discover_roots()

    if args.list:
        print("\n已有的技能根（会装到第一个）：")
        for p in existing:
            print("  [有] %s" % p)
        if not existing:
            print("  （一个都没有）")
        print("\n尚未创建的技能根：")
        for p in missing:
            print("  [无] %s" % p)
        print("\n提示：什么都不用做，直接跑 python 安装.py 即可，它会自动建。")
        return 0

    # 定目标技能根
    if args.root:
        target_root = os.path.abspath(os.path.expanduser(args.root))
    elif existing:
        target_root = existing[0]
    else:
        target_root = missing[0] if missing else os.path.join(home(), ".agents", "skills")
    print("\n目标技能根：%s" % target_root)
    if len(existing) > 1:
        print("（另外还探测到 %d 个技能根；要让所有客户端都看见，可再对它们跑一次 --root）"
              % (len(existing) - 1))

    ok = True
    if args.agents_only:
        print("\n[1/4] 跳过（--agents-only）")
        target = os.path.join(target_root, SKILL_NAME)
        print("[2/4] 跳过（--agents-only）")
    else:
        target, good = step_install_skill(target_root, args.dry_run)
        ok = ok and good
        _, good = step_state(args.dry_run)
        ok = ok and good

    if args.no_agents:
        print("\n[3/4] 跳过（--no-agents）")
    else:
        ok = step_agents(args.dry_run) and ok

    if args.dry_run:
        print("\n[4/4] 跳过（dry-run）")
    else:
        ok = step_doctor(target) and ok

    print("\n" + "=" * 62)
    if args.dry_run:
        print("以上是预演。真正执行请去掉 --dry-run。")
    elif ok:
        print("装好了。三个要点：")
        print("  1. 客户端不热重载技能 —— 请**新开一个会话**")
        print("  2. 日常你不用说任何命令，直接说「接着上次做」")
        print("  3. 自检：python \"%s\" doctor" % os.path.join(target, "scripts", "relay.py"))
    else:
        print("有步骤失败，看上面的 ✗ 行。可以重复运行本脚本，它是幂等的。")
    print("=" * 62)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
