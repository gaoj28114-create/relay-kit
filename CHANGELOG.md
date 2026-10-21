# Changelog

本项目遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## v0.1.0 (2026-10-21)

首次公开发布。

### 新增
- **单入口命令 `go`**：无参看状态 / 带文本开新任务 / `--init` 新机器一键初始化
- **任务状态文件**：`~/.relay/tasks/*.json`，含 decisions / todos / artifacts / blockers / log
- **用户画像**：`~/.relay/用户画像.md`，只存本地、不上传
- **本地能力索引**：`cap_index.py` 自动探测技能根（`~/.agents/skills` / `~/.claude/skills` / `~/.codex/skills` 等），一次读 JSON 代替逐个开 SKILL.md
- **交付前自检**：
  - `preflight <id>`：没写 decision 直接退出码 2，不许交付
  - `audit <id>`：自写脚本 B1（查规范技能）/ B2（真跑）/ B3（结论写进 --decision）三道检查
- **风格画像**：`style` / `ask-style <id>` 从历史任务卡现算用户风格档
- **一键安装**：`python 安装.py` 自动探测技能根 → 建状态目录 → 写注入块 → 自检
- **可卸载**：`python 安装.py --uninstall` 干净移除

### 安全承诺
- 只 import Python 标准库（`argparse` / `io` / `json` / `os` / `re` / `shutil` / `sys` / `datetime`）
- 零网络调用：没有 `socket` / `urllib` / `requests` / `http` / `subprocess`
- 任务状态、用户画像、能力索引全部存在本地 `~/.relay/`，与技能目录分离
- 安装脚本只在 `AGENTS.md` / `CLAUDE.md` 的 `<!-- BEGIN relay-kit -->` 标记块之间追加，不碰用户其他内容

### 已知限制
- 纯网页版 AI（读不到本地文件系统）无法参与接力
- 跨客户端接力依赖模型遵守注入块指令，不是协议强制
- 换电脑需手动拷贝 `~/.relay` 目录
- 真实跨客户端端到端接力（豆包 → Claude Code）尚待更多用户实测
