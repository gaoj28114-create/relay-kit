#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""接力包 · 任务状态的本地读写（零配置 · 跨客户端）

三条设计原则：
  1. 零配置——不要求你有知识库、不改任何配置文件就能用
  2. 状态自举——状态落在用户主目录，任何机器都算得出来，不依赖谁的本地库
  3. 只写本地——不联网、不上传、无第三方依赖（Python 3.7+ 标准库即可）

状态位置按顺序解析：
  环境变量 RELAY_HOME  >  config.json 的 state_root  >  ~/.relay

用法示例：
    python relay.py init                  # 首次使用，建目录
    python relay.py go                    # ★ 单入口：看状态 / 提示下一步
    python relay.py go "用户的原话需求"     # 建卡 + 告诉你还缺什么
    python relay.py doctor                # 自检：能不能用、缺什么、状态在哪
    python relay.py set <id> --decision "已定：用中文"
    python relay.py done <id>
    python relay.py profile set "回复始终用简体中文"
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
else:  # pragma: no cover - 老版本 Python 兜底
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(SKILL_DIR, "config.json")

ACTIVE_STATES = ("active", "paused")
# (argparse 参数名, JSON 字段名) —— 两者不同名，别混用
LIST_FIELDS = (
    ("decision", "decisions"),
    ("todo", "todos"),
    ("artifact", "artifacts"),
    ("blocker", "blockers"),
    ("log", "log"),
)


# ---------------------------------------------------------------- 状态位置

def default_state_root():
    """状态根：任何机器都能算出来，不依赖某个人的知识库。

    这里放的是**你自己的**任务状态与画像，不随技能分发——
    所以别人拿走技能目录，用的是他自己的状态，不会串味。
    """
    env = (os.environ.get("RELAY_HOME") or "").strip()
    if env:
        return os.path.abspath(os.path.expanduser(env))
    return os.path.join(os.path.expanduser("~"), ".relay")


def load_config():
    cfg = {}
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                cfg = {k: v for k, v in data.items() if v not in ("", [], None)}
        except Exception as exc:
            print("[warn] config.json 解析失败，用默认值：%s" % exc, file=sys.stderr)
    cfg.setdefault("profile_file", "用户画像.md")
    cfg.setdefault("cap_index_file", "cap_index.json")
    if not cfg.get("state_root"):
        cfg["state_root"] = default_state_root()
    return cfg


# ---------------------------------------------------------------- 基础工具

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def tasks_dir(cfg):
    return os.path.join(cfg["state_root"], "tasks")


def task_path(cfg, tid):
    return os.path.join(tasks_dir(cfg), "%s.json" % tid)


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    # newline="" 关掉 Windows 上的 "\n"→"\r\n" 自动翻译，保证行尾可预期
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_task(cfg, tid):
    path = task_path(cfg, tid)
    if not os.path.isfile(path):
        die("找不到任务 %s（%s）" % (tid, path))
    return read_json(path)


def save_task(cfg, task):
    task["updated_at"] = now_str()
    write_json(task_path(cfg, task["id"]), task)


def all_tasks(cfg):
    d = tasks_dir(cfg)
    if not os.path.isdir(d):
        return []
    out = []
    for name in sorted(os.listdir(d), reverse=True):
        if not name.endswith(".json"):
            continue
        try:
            out.append(read_json(os.path.join(d, name)))
        except Exception:
            continue
    out.sort(key=lambda t: t.get("updated_at", ""), reverse=True)
    return out


def active_tasks(cfg):
    return [t for t in all_tasks(cfg) if t.get("status") in ACTIVE_STATES]


def die(msg, code=1):
    print("[error] %s" % msg, file=sys.stderr)
    sys.exit(code)


def short(text, limit):
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def append_item(task, field, text):
    task.setdefault(field, []).append({"at": now_str(), "text": text})


def latest(task, field, limit=1):
    items = task.get(field) or []
    return items[-limit:] if items else []


# ---------------------------------------------------------------- 任务

def cmd_new(cfg, args):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    tid = stamp
    n = 2
    while os.path.exists(task_path(cfg, tid)):
        tid = "%s-%d" % (stamp, n)
        n += 1

    task = {
        "id": tid,
        "title": args.title,
        "goal": args.goal or "",
        "deliverable": args.deliverable or "",
        "domain": args.domain or "",
        "criteria": args.criteria or "",
        "status": "active",
        "style": "",
        "decisions": [],
        "todos": [],
        "artifacts": [],
        "blockers": [],
        "log": [],
        "created_at": now_str(),
        "updated_at": now_str(),
    }
    if args.decision:
        append_item(task, "decisions", args.decision)
    save_task(cfg, task)
    print(tid)
    print("已建任务：%s" % args.title)
    if not (args.goal or args.deliverable or args.criteria):
        print("提示：目标/交付物/验收标准还是空的——先补齐，接手的 AI 才不会跑偏。")
    return 0


def cmd_set(cfg, args):
    task = load_task(cfg, args.id)
    changed = []

    for field in ("goal", "deliverable", "domain", "criteria", "next", "status", "style"):
        val = getattr(args, field)
        if val is not None:
            task[field] = val
            changed.append(field)

    for argname, field in LIST_FIELDS:
        for text in getattr(args, argname, None) or []:
            append_item(task, field, text)
            changed.append(field)

    if not changed:
        die("没有给任何要改的字段，看看 --help")
    save_task(cfg, task)
    print("已更新 %s：%s" % (task["id"], "、".join(dict.fromkeys(changed))))
    return 0


def cmd_list(cfg, args):
    tasks = all_tasks(cfg) if args.all else active_tasks(cfg)
    if not tasks:
        print("（没有%s任务）" % ("" if args.all else "进行中的"))
        return 0
    for t in tasks:
        print("%-16s %-8s %-10s %s" % (
            t["id"], t.get("status", "?"), t.get("updated_at", ""), short(t.get("title", ""), 40),
        ))
    return 0


def cmd_show(cfg, args):
    t = load_task(cfg, args.id)
    print("=" * 62)
    print("%s  [%s]" % (t.get("title", ""), t.get("id", "")))
    print("=" * 62)
    for label, key in (("目标", "goal"), ("交付物", "deliverable"), ("领域", "domain"),
                       ("验收", "criteria"), ("状态", "status"), ("风格", "style")):
        val = t.get(key)
        if val:
            print("%s：%s" % (label, val))
    for field, label in (("decisions", "已定决策"), ("todos", "待办"), ("artifacts", "产物"),
                         ("blockers", "阻塞"), ("log", "过程")):
        items = t.get(field) or []
        if not items:
            continue
        print("\n【%s】" % label)
        for it in items:
            print("  - [%s] %s" % (it.get("at", ""), it.get("text", "")))
    print("\n创建：%s   最近更新：%s" % (t.get("created_at", ""), t.get("updated_at", "")))
    return 0


def cmd_resume(cfg, args):
    tasks = [load_task(cfg, args.id)] if args.id else active_tasks(cfg)
    if not tasks:
        print("（没有进行中的任务——按新任务走 SKILL.md 第一节）")
        return 0

    for t in tasks:
        print("─" * 58)
        print("[%s] %s  ·%s· %s" % (t.get("id"), short(t.get("title", ""), 34),
                                    t.get("status", "?"), t.get("updated_at", "")))
        if t.get("goal"):
            print("  目标：%s" % short(t["goal"], 90))
        if t.get("deliverable"):
            print("  交付物：%s" % short(t["deliverable"], 70))
        if t.get("style"):
            print("  风格档：%s" % short(t["style"], 30))
        for d in latest(t, "decisions", 6):
            print("    - %s" % short(d.get("text", ""), 76))
        if latest(t, "decisions", 1):
            pass
        for d in latest(t, "todos", 5):
            print("    · 待办：%s" % short(d.get("text", ""), 74))
        if t.get("next"):
            print("  下一步：%s" % short(t["next"], 90))
        for b in latest(t, "blockers", 3):
            print("    ! 阻塞：%s" % short(b.get("text", ""), 74))
        for a in latest(t, "artifacts", 6):
            print("    □ 已产出：%s" % short(a.get("text", ""), 82))
    print("─" * 58)
    print("接着干即可，不要再问已经写在上面的内容。")
    return 0


def cmd_done(cfg, args):
    t = load_task(cfg, args.id)
    t["status"] = "done"
    if args.note:
        append_item(t, "log", "收尾：%s" % args.note)
    save_task(cfg, t)
    print("已收尾：%s" % t["id"])
    return 0


# ---------------------------------------------------------------- 交付前自检（花叔：手册不是强制力）

def _extract_path(text):
    """从一条自由文本里抽出看起来像文件路径的片段。"""
    import re as _re
    m = _re.search(r"[A-Za-z]:[\\/][^\s，。；）)]+", text or "")
    return m.group(0) if m else ""


def cmd_preflight(cfg, args):
    """交付前自检——把 SKILL.md 里写的判据变成真跑的代码。

    退出码：0 = 可交付；2 = 有阻断项，不许交付。
    与 `audit`（B1/B2/B3 自写脚本检查点）互补：audit 管"代码写没写规范"，preflight 管"任务能不能交"。
    """
    t = load_task(cfg, args.id)
    failures, warnings = [], []

    # 阻断：没有 decisions → 换 AI 必重问
    if not t.get("decisions"):
        failures.append("没有任何 decision——换 AI 一定会把已定的事重问一遍")

    # 提示：四要素缺项
    for field, label in (("goal", "目标"), ("deliverable", "交付物"), ("criteria", "验收标准")):
        if not t.get(field):
            warnings.append("%s 还没填" % label)

    # 提示：产物路径不存在
    for a in t.get("artifacts", []) or []:
        p = _extract_path(a.get("text", ""))
        if p and not os.path.exists(p):
            warnings.append("产物路径不存在：%s" % p)

    # 一致性：列出最近 6 条决策，让 AI 自己对照
    recent = [d.get("text", "") for d in (t.get("decisions") or [])[-6:]]

    if getattr(args, "json", False):
        print(json.dumps({
            "id": t["id"], "title": t.get("title", ""),
            "status": t.get("status", ""),
            "failures": failures, "warnings": warnings,
            "recent_decisions": recent,
            "pass": not failures,
        }, ensure_ascii=False, indent=2))
        return 0 if not failures else 2

    print("=" * 62)
    print("接力包 · 交付前自检 [%s]  %s" % (t["id"], t.get("status", "?")))
    print("=" * 62)
    print("任务：%s" % t.get("title", ""))
    print()

    if failures:
        print("✗ 阻断项（不过不许交付）：")
        for f in failures:
            print("  - %s" % f)
    else:
        print("✓ 阻断项：无")

    if warnings:
        print()
        print("-- 提示项（建议补，不阻断）：")
        for w in warnings:
            print("  - %s" % w)

    print()
    print("最近 6 条已定决策（新产物逐条对照，冲突就显式问用户）：")
    if recent:
        for d in recent:
            print("  · %s" % d)
    else:
        print("  （无）")

    print()
    if failures:
        print("结论：不过。补完上面的 ✗ 再交付。")
        return 2
    print("结论：可交付。")
    return 0


# ---------------------------------------------------------------- 画像

def profile_path(cfg):
    return os.path.join(cfg["state_root"], cfg.get("profile_file", "用户画像.md"))


def read_profile(cfg):
    p = profile_path(cfg)
    if not os.path.isfile(p):
        return []
    items = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("- "):
                text = line[2:].strip()
                if text == "（空）":       # 占位行不是真条目，别算进去
                    continue
                items.append(text)
    return items


def write_profile(cfg, items):
    p = profile_path(cfg)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    lines = [
        "# 用户画像",
        "",
        "> 由「接力包」维护。只存**稳定、可跨任务复用**的偏好，不存一次性指令。",
        "> 本文件仅存在于本地，不上传任何服务。",
        "",
        "最近更新：%s" % now_str(),
        "",
    ]
    lines += ["- %s" % it for it in items] or ["- （空）"]
    lines.append("")
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(lines))


def cmd_profile(cfg, args):
    items = read_profile(cfg)
    if args.action == "show":
        if not items:
            print("（画像为空）路径：%s" % profile_path(cfg))
            return 0
        for i, it in enumerate(items, 1):
            print("%2d. %s" % (i, it))
        print("\n文件：%s" % profile_path(cfg))
        return 0

    if args.action == "set":
        if not args.text:
            die("profile set 需要一个条目文本")
        if args.text in items:
            print("已存在，未重复添加。")
            return 0
        items.append(args.text)
        write_profile(cfg, items)
        print("已沉淀：%s" % args.text)
        return 0

    if args.action == "del":
        if not args.text:
            die("profile del 需要条目序号")
        try:
            idx = int(args.text) - 1
        except ValueError:
            die("序号要是数字")
        if not (0 <= idx < len(items)):
            die("序号超出范围（当前 %d 条）" % len(items))
        removed = items.pop(idx)
        write_profile(cfg, items)
        print("已移除：%s" % removed)
        return 0

    die("未知的 profile 动作：%s" % args.action)


# ---------------------------------------------------------------- 风格画像（跨客户端）

STYLE_HINTS = (
    ("严谨", "常用**严谨档**：偏好结论+证据+边界+反例"),
    ("自适应", "常用**自适应档**：偏好贴他自己的表达习惯"),
    ("参照", "常用**参照档**：偏好对齐当下热门同类产品"),
)

# 从卡里的自由文本抽风格信号（确定性规则，不调用任何模型）
SIGNAL_RULES = (
    ("先说结论", ("结论", "先说结果", "直接给")),
    ("要边界/反例", ("边界", "反例", "局限", "例外")),
    ("要证据/来源", ("证据", "来源", "出处", "引用", "验过", "实测")),
    ("要可执行动作", ("改法", "步骤", "怎么做", "给个动作", "落地")),
    ("要最短路径", ("简短", "精炼", "少废话", "直接做", "别啰嗦", "省")),
    ("要表格/结构", ("表格", "清单", "结构化", "分点", "对比表")),
    ("要中文", ("中文", "简体", "不要英文")),
    ("不要编造", ("不要编", "别编", "没有就直说", "不许编造", "标未验证")),
    ("不要上传/本地优先", ("不上传", "本地", "别联网", "离线")),
)


def _all_text(task):
    """把一张卡里所有自由文本拼起来，供规则匹配。"""
    parts = [task.get("title", ""), task.get("goal", ""), task.get("deliverable", ""),
             task.get("domain", ""), task.get("criteria", ""), task.get("style", ""),
             task.get("next", "")]
    for field in ("decisions", "todos", "artifacts", "blockers", "log"):
        for it in task.get(field) or []:
            parts.append(it.get("text", "") if isinstance(it, dict) else str(it))
    return "\n".join(p for p in parts if p)


def cmd_style(cfg, args):
    """从**历史任务卡现算**用户风格画像。

    跨客户端可用：任何能读本地文件的客户端跑这一条即可，
    不需要该客户端曾参与过任何一次对话。
    """
    tasks = all_tasks(cfg)
    if args.active_only:
        tasks = [t for t in tasks if t.get("status") in ACTIVE_STATES]
    if not tasks:
        print("（还没有任务卡，算不出风格画像）")
        print("先开几个任务：relay.py go \"需求原文\"")
        return 0

    style_tally, sig_tally = {}, {}
    for t in tasks:
        s = (t.get("style") or "").strip()
        if s:
            style_tally[s] = style_tally.get(s, 0) + 1
        text = _all_text(t)
        for name, keys in SIGNAL_RULES:
            if any(k in text for k in keys):
                sig_tally[name] = sig_tally.get(name, 0) + 1

    n = len(tasks)
    # 显式沉淀的偏好权重最高
    explicit = read_profile(cfg)

    print("=" * 62)
    print("接力包 · 风格画像（从 %d 张任务卡现算）" % n)
    print("=" * 62)

    print("\n【已显式沉淀的偏好】%d 条" % len(explicit))
    if explicit:
        for it in explicit:
            print("  - %s" % it)
    else:
        print("  （空。看到稳定偏好时用 profile set 记一条）")

    print("\n【风格档使用频次】")
    if style_tally:
        for k, v in sorted(style_tally.items(), key=lambda kv: -kv[1]):
            print("  %-10s × %d" % (k, v))
    else:
        print("  （还没在卡里定过档位；默认走自适应档）")
    for key, desc in STYLE_HINTS:
        if any(key in k for k in style_tally):
            print("    · %s" % desc)

    print("\n【行为信号（从卡里的决策/待办/阻塞文本抽取）】")
    if sig_tally:
        for k, v in sorted(sig_tally.items(), key=lambda kv: -kv[1]):
            pct = v * 100.0 / n
            bar = "#" * max(1, int(round(pct / 5)))
            print("  %-14s %3d/%d  %5.1f%%  %s" % (k, v, n, pct, bar))
    else:
        print("  （卡里还没有可提取的自由文本）")

    print("\n【给接手 AI 的建议档位】")
    if style_tally:
        top = max(style_tally.items(), key=lambda kv: kv[1])[0]
        print("  默认沿用：**%s**" % top)
    else:
        print("  默认：**自适应档**（不接受就说不）")
    strong = [k for k, v in sig_tally.items() if v * 2 >= n]
    if strong:
        print("  已跨越半数任务的稳定要求：%s" % "、".join(strong))
    print("\n  取数口径：全量卡 %d 张%s。" % (n, "（--active-only 只看进行中）" if args.active_only else ""))
    print("  本命令**只读本地文件、不联网、不调用模型**，任何客户端都能跑。")
    return 0


# ---------------------------------------------------------------- 风格档选择（跨客户端可判）

STYLE_OPTIONS = [
    ("严谨档", "结论+证据+边界+反例，适合逻辑推理/分析/排障"),
    ("自适应档", "贴用户既有表达习惯，默认档"),
    ("参照档", "对齐当下热门同类产品，适合产品设计/界面/文案"),
]


def cmd_ask_style(cfg, args):
    """新任务建卡后，帮用户选风格档。机器可判，不靠宿主 AI 自觉。

    - 已有 style → 显示已定，不再问
    - 没有 → 从历史卡算建议档位，列出三个选项和对应 set 命令
    """
    task = load_task(cfg, args.id)
    current = (task.get("style") or "").strip()

    # 从历史卡算建议档位
    tasks = all_tasks(cfg)
    style_tally = {}
    for t in tasks:
        s = (t.get("style") or "").strip()
        if s:
            style_tally[s] = style_tally.get(s, 0) + 1
    if style_tally:
        suggested = max(style_tally.items(), key=lambda kv: kv[1])[0]
    else:
        suggested = "自适应档"

    if getattr(args, "json", False):
        print(json.dumps({
            "id": task["id"],
            "current_style": current,
            "suggested": suggested,
            "options": [{"value": v, "desc": d} for v, d in STYLE_OPTIONS],
            "already_set": bool(current),
        }, ensure_ascii=False, indent=2))
        return 0

    print("=" * 62)
    print("风格档选择 · 任务 [%s]" % task["id"])
    print("=" * 62)
    print("任务：%s" % task.get("title", ""))
    print()

    if current:
        print("✓ 已定档位：%s" % current)
        print("  不需要再选。要改就跑：")
        print('  python "%s" set %s --style <档位>' % (os.path.join(SKILL_DIR, "scripts", "relay.py"), task["id"]))
        return 0

    print("建议档位：**%s**（从 %d 张历史卡算的）" % (suggested, len(tasks)))
    print()
    print("选哪个？跑下面任意一条即可：")
    print()
    for i, (val, desc) in enumerate(STYLE_OPTIONS, 1):
        mark = " ← 建议" if val == suggested else ""
        print("  %d. %s%s" % (i, val, mark))
        print("     %s" % desc)
        print('     → python "%s" set %s --style "%s"' % (
            os.path.join(SKILL_DIR, "scripts", "relay.py"), task["id"], val))
        print()
    print("不选就走默认：自适应档。")
    return 0


# ---------------------------------------------------------------- 自写脚本审计检查点

def cmd_audit(cfg, args):
    """自写脚本的 B1/B2/B3 检查点：记录 + 校验，未过则非零退出。

    设计依据：光把"必须审计"写进 SKILL.md 是**没有强制力**的
    （手册不是强制力）。所以把检查点变成一张**必须填全的表**，
    机器可判：填不全 → 退出码非零 → AI 拿不到"绿灯"。
    """
    task = load_task(cfg, args.id)
    checks = task.setdefault("audit", {})

    if args.b1 is not None:
        checks["b1_规范检索"] = {"ok": True, "note": args.b1}
    if args.b2 is not None:
        checks["b2_真实执行"] = {"ok": True, "note": args.b2}
    if args.b3 is not None:
        checks["b3_结论入卡"] = {"ok": True, "note": args.b3}
    if args.script:
        checks["script"] = args.script

    for k in ("b1_规范检索", "b2_真实执行", "b3_结论入卡"):
        if k not in checks:
            checks[k] = {"ok": False, "note": ""}
    if args.script:
        checks["script"] = args.script
    save_task(cfg, task)

    missing = [k for k in ("b1_规范检索", "b2_真实执行", "b3_结论入卡")
               if not checks.get(k, {}).get("ok")]
    if not checks.get("script"):
        missing.append("script（用 --script 写上脚本路径）")

    print("=" * 62)
    print("自写脚本审计 · 任务 %s" % task["id"])
    print("=" * 62)
    rows = [("脚本", checks.get("script") or "—", bool(checks.get("script")))]
    for k in ("b1_规范检索", "b2_真实执行", "b3_结论入卡"):
        it = checks.get(k) or {}
        if not isinstance(it, dict):
            it = {}
        rows.append((k, it.get("note") or "—", bool(it.get("ok"))))
    for label, note, good in rows:
        print("  [%s] %-14s %s" % ("PASS" if good else "MISS", label, note))

    if missing:
        print("\n结论：**未过**。缺：%s" % "、".join(missing))
        print("B2 必须含**至少一次真实入口执行**；'语法没问题'不算。")
        sys.exit(2)
    print("\n结论：**三绿通过**，可以交付。")
    return 0


# ---------------------------------------------------------------- 初始化 / 单入口 / 自检

def ensure_state(cfg):
    os.makedirs(tasks_dir(cfg), exist_ok=True)
    if not os.path.isfile(profile_path(cfg)):
        write_profile(cfg, [])
    return cfg["state_root"]


def cmd_init(cfg, args):
    root = ensure_state(cfg)
    print("=" * 62)
    print("接力包 · 初始化完成")
    print("=" * 62)
    print("\n状态目录：%s" % root)
    print("  （你自己的任务与画像都在这里，不随技能分发，换机器需自己搬）")
    print("\n接下来什么都不用配。日常只用一条命令：")
    print("  python \"%s\" go" % os.path.join(SKILL_DIR, "scripts", "relay.py"))
    print("\n想看详细诊断：relay.py doctor")
    return 0


def _go_new_task(cfg, text):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    tid = stamp
    n = 2
    while os.path.exists(task_path(cfg, tid)):
        tid = "%s-%d" % (stamp, n)
        n += 1
    task = {
        "id": tid,
        "title": short(text, 40),
        "goal": text,
        "deliverable": "",
        "domain": "",
        "criteria": "",
        "status": "active",
        "style": "",
        "decisions": [],
        "todos": [],
        "artifacts": [],
        "blockers": [],
        "log": [{"at": now_str(), "text": "原始需求：%s" % text}],
        "created_at": now_str(),
        "updated_at": now_str(),
    }
    save_task(cfg, task)
    print(">>> 已开新任务卡 [%s]" % tid)
    print("    %s" % short(text, 70))
    print()
    print("动手前还缺三件事——拿到了就记下来，别留在对话里：")
    print("  1. 交付物是什么形态（文档 / 代码 / 表格 / 结论 / 系统）")
    print("  2. 验收标准（怎么算做完了）")
    print("  3. 风格档（严谨档 / 自适应档）")
    print()
    print("记的时候直接跑这条（改成你要的内容）：")
    print('  python "%s" set %s --deliverable "..." --criteria "..." --style "严谨档"'
          % (os.path.join(SKILL_DIR, "scripts", "relay.py"), tid))
    print()
    print("★ 已经定了的事，顺手记成 --decision，换 AI 时才不会重问一遍：")
    print('  python "%s" set %s --decision "已定：..."' % (os.path.join(SKILL_DIR, "scripts", "relay.py"), tid))
    return 0


def cmd_go(cfg, args):
    if args.init:
        return cmd_init(cfg, args)

    ensure_state(cfg)

    if args.text:
        return _go_new_task(cfg, args.text)

    tasks = active_tasks(cfg)

    if getattr(args, "json", False):
        out = {
            "active_count": len(tasks),
            "active_tasks": [
                {
                    "id": t.get("id"), "title": t.get("title"),
                    "status": t.get("status"), "updated_at": t.get("updated_at"),
                    "goal": t.get("goal"), "deliverable": t.get("deliverable"),
                    "style": t.get("style", ""),
                    "recent_decisions": [d.get("text") for d in (t.get("decisions") or [])[-5:]],
                    "next": t.get("next", ""),
                }
                for t in tasks
            ],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if tasks:
        print(">>> 有 %d 个进行中的任务。下面是续接包——" % len(tasks))
        print(">>> 直接接着干，不要再问已经写在这里的目标 / 决策 / 边界。")
        print()
        return cmd_resume(cfg, argparse.Namespace(id=None))

    total = len(all_tasks(cfg))
    print(">>> 当前没有进行中的任务，可以正常开新任务。")
    if total:
        print("（历史任务 %d 个，都已收尾；看全部：relay.py list --all）" % total)
    print("开新任务：把需求直接说给 AI 即可，不用记命令。")
    return 0


def cmd_doctor(cfg, args):
    OK, WARN = "  [OK]  ", "  [--]  "
    print("=" * 62)
    print("接力包 · 自检")
    print("=" * 62)

    print("\n【运行环境】")
    print(OK + "Python %s" % sys.version.split()[0])
    print(OK + "脚本位置 %s" % os.path.abspath(__file__))

    print("\n【状态目录】你的任务与画像存在这里（不随技能分发）")
    root = cfg["state_root"]
    env_set = bool((os.environ.get("RELAY_HOME") or "").strip())
    print("       %s" % root)
    print("       ← %s" % ("环境变量 RELAY_HOME" if env_set else "自动推导（默认位置，换机器算出来也一样）"))
    try:
        ensure_state(cfg)
        print(OK + "可写")
    except Exception as exc:
        print("  [!!]  不可写：%s" % exc)
        print("       → 换个位置：设环境变量 RELAY_HOME，或在 config.json 里写 state_root")
        return 1

    print("\n【已有的家底】")
    print(OK + "任务卡 %d 张（进行中 %d）" % (len(all_tasks(cfg)), len(active_tasks(cfg))))
    print(OK + "已沉淀偏好 %d 条" % len(read_profile(cfg)))

    print("\n【能力索引】决定第 ① 级路由能不能查到本地技能")
    idx = os.path.join(root, cfg.get("cap_index_file", "cap_index.json"))
    if os.path.isfile(idx):
        try:
            data = read_json(idx)
            cnt = data.get("counts", {})
            print(OK + "已建（%s）：%s" % (data.get("generated_at", "?"),
                                          "、".join("%s %d" % kv for kv in sorted(cnt.items())) or "空"))
        except Exception:
            print(WARN + "存在但读不出来 → 重建：cap_index.py build")
    else:
        print(WARN + "还没建 → 跑一次 cap_index.py build 即可（没装技能也不影响接力）")

    print("\n" + "-" * 62)
    print("结论：接力功能不依赖技能根、不依赖知识库，状态目录可写就能用。")
    return 0


# ---------------------------------------------------------------- CLI

def build_parser():
    ap = argparse.ArgumentParser(
        prog="relay.py",
        description="接力包 · 任务状态本地读写（零配置；只写本地，不联网）",
    )
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("go", help="★ 单入口：看状态 / 开新任务 / 初始化")
    p.add_argument("text", nargs="?", help="新任务的原始需求；不给则只看状态")
    p.add_argument("--init", action="store_true", help="首次使用：建目录、初始化")
    p.add_argument("--json", action="store_true", help="输出机器可读 JSON（给 agent 消费）")
    p.set_defaults(func=cmd_go)

    p = sub.add_parser("init", help="首次使用：建状态目录")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("doctor", help="自检：能不能用、缺什么、状态在哪")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("new", help="新建任务")
    p.add_argument("title")
    p.add_argument("--goal")
    p.add_argument("--deliverable")
    p.add_argument("--domain")
    p.add_argument("--criteria")
    p.add_argument("--decision")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("set", help="更新任务")
    p.add_argument("id")
    p.add_argument("--goal")
    p.add_argument("--deliverable")
    p.add_argument("--domain")
    p.add_argument("--criteria")
    p.add_argument("--next")
    p.add_argument("--status", choices=["active", "paused", "done"])
    p.add_argument("--style")
    p.add_argument("--decision", action="append")
    p.add_argument("--todo", action="append")
    p.add_argument("--artifact", action="append")
    p.add_argument("--blocker", action="append")
    p.add_argument("--log", action="append")
    p.set_defaults(func=cmd_set)

    p = sub.add_parser("list", help="列出任务")
    p.add_argument("--all", action="store_true", help="含已收尾的")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="看某个任务的全部字段")
    p.add_argument("id")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("resume", help="输出续接包（接手时第一条命令）")
    p.add_argument("id", nargs="?")
    p.set_defaults(func=cmd_resume)

    p = sub.add_parser("done", help="收尾")
    p.add_argument("id")
    p.add_argument("--note")
    p.set_defaults(func=cmd_done)

    p = sub.add_parser("profile", help="用户画像")
    p.add_argument("action", choices=["show", "set", "del"])
    p.add_argument("text", nargs="?")
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("style", help="★ 从历史任务卡现算风格画像（跨客户端可用）")
    p.add_argument("--active-only", action="store_true", help="只看进行中的任务")
    p.set_defaults(func=cmd_style)

    p = sub.add_parser("audit", help="★ 自写脚本 B1/B2/B3 检查点（未过则退出码 2）")
    p.add_argument("id", help="任务 id")
    p.add_argument("--script", help="脚本路径")
    p.add_argument("--b1", help="B1 规范检索：查过哪个规范技能/依据")
    p.add_argument("--b2", help="B2 真实执行：跑的是哪个入口、看到什么输出")
    p.add_argument("--b3", help="B3 结论入卡：写进了哪条 --decision")
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("preflight", help="★ 交付前自检：任务卡能否交付（未过则退出码 2）")
    p.add_argument("id", help="任务 id")
    p.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p.set_defaults(func=cmd_preflight)

    p = sub.add_parser("ask-style", help="★ 新任务选风格档（机器可判，不靠宿主自觉）")
    p.add_argument("id", help="任务 id")
    p.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p.set_defaults(func=cmd_ask_style)

    return ap


def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return 0
    return args.func(load_config(), args)


if __name__ == "__main__":
    sys.exit(main())
