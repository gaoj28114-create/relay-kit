#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""接力包 · 本地能力索引

扫描本机已装技能与指定目录里的可复用脚本，生成一份 JSON 索引。
目的是让 AI 用**一次读取**代替"逐个打开 SKILL.md 去比对"——省上下文也省时间。

**技能根自动探测**：换台机器也能扫到，不用手改配置。

只做本地文件扫描：不联网、不上传、无第三方依赖。

用法：
    python cap_index.py build                  # 重建索引
    python cap_index.py search "截图 OCR"       # 检索
    python cap_index.py search --json "视频 字幕"
    python cap_index.py roots                  # 看看扫到了哪些目录
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
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

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(SKILL_DIR, "config.json")

SKIP_DIR_NAMES = {
    "node_modules", ".git", "__pycache__", "venv", ".venv", "site-packages",
    "dist", "build", ".obsidian",
}
FRONTMATTER_LIMIT = 40
DESC_LIMIT = 220


def default_state_root():
    env = (os.environ.get("RELAY_HOME") or "").strip()
    if env:
        return os.path.abspath(os.path.expanduser(env))
    return os.path.join(os.path.expanduser("~"), ".relay")


def discover_skill_roots():
    """自动探测本机技能根——这是"换台机器也能用"的关键。

    依据 Agent Skills 生态现状：~/.agents/skills 是跨工具共享目录，
    另有各客户端自己的技能根。
    """
    home = os.path.expanduser("~")
    cands = [
        os.path.join(home, ".agents", "skills"),
        os.path.join(home, ".claude", "skills"),
        os.path.join(home, ".codex", "skills"),
        os.path.join(home, ".cursor", "skills"),
        os.path.join(home, ".gemini", "skills"),
        os.path.join(home, ".copilot", "skills"),
        os.path.join(home, ".workbuddy", "skills"),
    ]
    # 当前工作目录及其父目录下的项目级技能
    try:
        cwd = os.getcwd()
    except Exception:
        cwd = ""
    if cwd:
        for up in (cwd, os.path.dirname(cwd)):
            if up:
                cands.append(os.path.join(up, ".agents", "skills"))
                cands.append(os.path.join(up, ".doubao", "skills"))
    out, seen = [], set()
    for p in cands:
        p = os.path.abspath(p)
        k = p.casefold()
        if k in seen:
            continue
        seen.add(k)
        if os.path.isdir(p):
            out.append(p)
    return out


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
    cfg.setdefault("cap_index_file", "cap_index.json")
    if not cfg.get("state_root"):
        cfg["state_root"] = default_state_root()
    if not cfg.get("skill_roots"):
        cfg["skill_roots"] = discover_skill_roots()
    return cfg


def index_path(cfg):
    return os.path.join(cfg["state_root"], cfg.get("cap_index_file", "cap_index.json"))


def clip(text, limit=DESC_LIMIT):
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


# ------------------------------------------------------- frontmatter

def read_frontmatter(path):
    """不依赖 PyYAML 的轻量 frontmatter 解析：只取 name / description。"""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            head = []
            for i, line in enumerate(f):
                if i > FRONTMATTER_LIMIT:
                    break
                head.append(line.rstrip("\n"))
    except Exception:
        return {}

    if not head or head[0].strip() != "---":
        return {}

    out = {}
    for line in head[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^(name|description)\s*:\s*(.*)$", line)
        if not m:
            continue
        val = m.group(2).strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[m.group(1)] = val
    return out


# ------------------------------------------------------- 扫描

def scan_skills(cfg):
    items, seen = [], set()
    for root in cfg.get("skill_roots", []):
        if not os.path.isdir(root):
            continue
        try:
            entries = sorted(os.listdir(root))
        except Exception:
            continue
        for name in entries:
            folder = os.path.join(root, name)
            if not os.path.isdir(folder) or name in SKIP_DIR_NAMES:
                continue
            md = os.path.join(folder, "SKILL.md")
            if not os.path.isfile(md):
                continue
            key = name.casefold()
            if key in seen:
                continue
            seen.add(key)
            fm = read_frontmatter(md)
            items.append({
                "kind": "skill",
                "name": fm.get("name") or name,
                "desc": clip(fm.get("description", "")),
                "path": folder,
                "root": root,
            })
    return items


def scan_scripts(cfg):
    items = []
    exts = (".py", ".ps1", ".cmd", ".bat", ".sh")
    for d in cfg.get("script_dirs", []):
        if not os.path.isdir(d):
            continue
        for root, dirs, files in os.walk(d):
            dirs[:] = [x for x in dirs if x not in SKIP_DIR_NAMES and not x.startswith(".")]
            for fn in files:
                if not fn.lower().endswith(exts):
                    continue
                path = os.path.join(root, fn)
                doc = ""
                if fn.lower().endswith(".py"):
                    try:
                        with open(path, "r", encoding="utf-8", errors="replace") as f:
                            for i, line in enumerate(f):
                                if i > 25:
                                    break
                                s = line.strip()
                                if s.startswith('"""') and len(s) > 5:
                                    doc = clip(s.strip('"'), 160)
                                    break
                    except Exception:
                        pass
                items.append({"kind": "script", "name": fn, "desc": doc, "path": path})
    return items


def scan_notes(cfg):
    """可选：用户自己的笔记目录（有就扫，没有就跳过）。"""
    items = []
    notes = cfg.get("notes_dir")
    if not notes or not os.path.isdir(notes):
        return items
    for name in sorted(os.listdir(notes)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(notes, name)
        summary = ""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f):
                    if i > 30:
                        break
                    s = line.strip()
                    if s and not s.startswith(("#", ">", "|", "-", "*")):
                        summary = clip(s, 160)
                        break
        except Exception:
            pass
        items.append({"kind": "note", "name": name[:-3], "desc": summary, "path": path})
    return items


def build_index(cfg):
    items = scan_skills(cfg) + scan_scripts(cfg) + scan_notes(cfg)
    data = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "roots": cfg.get("skill_roots", []),
        "counts": {},
        "items": items,
    }
    for it in items:
        data["counts"][it["kind"]] = data["counts"].get(it["kind"], 0) + 1
    p = index_path(cfg)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return data, p


# ------------------------------------------------------- 检索

def load_index(cfg):
    p = index_path(cfg)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def tokenize(query):
    raw = re.split(r"[\s,，、/|+；;：:（）()【】\[\]]+", (query or "").strip())
    toks = []
    for t in raw:
        t = t.strip()
        if not t:
            continue
        toks.append(t.casefold())
        # 中文长词补 2 字片段，缓解没有分词器的问题
        if len(t) >= 4 and re.search(r"[\u4e00-\u9fff]", t):
            for i in range(0, len(t) - 1, 2):
                seg = t[i:i + 2]
                if len(seg) == 2:
                    toks.append(seg.casefold())
    return list(dict.fromkeys(toks))


def score_item(item, toks):
    name = (item.get("name") or "").casefold()
    desc = (item.get("desc") or "").casefold()
    path = (item.get("path") or "").casefold()
    s = 0
    for t in toks:
        if not t:
            continue
        if t in name:
            s += 6
        if t in desc:
            s += 3
        if t in path:
            s += 1
    return s


def cmd_search(cfg, args):
    data = load_index(cfg)
    if data is None:
        print("[warn] 索引不存在，正在自动构建…", file=sys.stderr)
        data, _ = build_index(cfg)
    toks = tokenize(args.query)
    if not toks:
        print('请给一个检索词，例如：cap_index.py search "字幕 翻译"')
        return 0

    scored = []
    for it in data.get("items", []):
        s = score_item(it, toks)
        if s > 0:
            scored.append((s, it))
    scored.sort(key=lambda x: (-x[0], x[1]["kind"], x[1]["name"]))
    hits = scored[: max(1, args.top)]

    if args.json:
        print(json.dumps([{"score": s, **it} for s, it in hits], ensure_ascii=False, indent=1))
        return 0

    if not hits:
        print("本地没有匹配项。")
        print('→ 按 SKILL.md 第二节，下一步走第 ③ 级：npx skills find "%s"' % args.query)
        return 0

    kind_cn = {"skill": "技能", "script": "脚本", "note": "笔记"}
    print("本地命中 %d 项（索引更新于 %s）：" % (len(hits), data.get("generated_at", "?")))
    for s, it in hits:
        print("\n[%s] %s  (score %d)" % (kind_cn.get(it["kind"], it["kind"]), it["name"], s))
        if it.get("desc"):
            print("   %s" % it["desc"])
        print("   %s" % it["path"])
    print("\n→ 命中就能用；要用就按它的 SKILL.md 执行，别重造。")
    return 0


def cmd_stats(cfg, args):
    data = load_index(cfg)
    if data is None:
        data, _ = build_index(cfg)
    print("索引：%s" % index_path(cfg))
    print("更新：%s" % data.get("generated_at", "?"))
    for k, v in sorted(data.get("counts", {}).items()):
        print("  %-8s %d" % (k, v))
    return 0


def cmd_build(cfg, args):
    data, p = build_index(cfg)
    print("已重建：%s" % p)
    for k, v in sorted(data["counts"].items()):
        print("  %-8s %d" % (k, v))
    if not data["counts"].get("skill"):
        print("\n[注意] 一个技能都没扫到——检查下面这些目录是否存在：")
        for r in cfg.get("skill_roots", []):
            print("   %s%s" % ("[有] " if os.path.isdir(r) else "[无] ", r))
    return 0


def cmd_roots(cfg, args):
    print("自动探测到的技能根：")
    roots = cfg.get("skill_roots", [])
    if not roots:
        print("  （一个都没有——先装个技能，或在本技能 config.json 里写死 skill_roots）")
    for r in roots:
        print("  %s" % r)
    print("\n提示：如果你放在别处，在 config.json 里加 \"skill_roots\": [\"你的路径\"]")
    return 0


# ------------------------------------------------------- CLI

def build_parser():
    ap = argparse.ArgumentParser(
        prog="cap_index.py",
        description="接力包 · 本地能力索引（只扫本地，不联网）",
    )
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("build", help="重建索引")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("search", help="检索本地能力")
    p.add_argument("query")
    p.add_argument("--top", type=int, default=8)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("stats", help="看索引概况")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("roots", help="看看扫到了哪些技能目录")
    p.set_defaults(func=cmd_roots)

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
