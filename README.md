# 接力包（relay-kit）

> 一件事做一半，换个 AI 继续 —— **进度不丢**。
> 零配置：不需要知识库、不需要改配置文件，装上就能用。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.7%2B-green.svg)
![Status](https://img.shields.io/badge/status-v0.1.0-yellow.svg)

---

## 一句话

你在 Claude Code 里做了一半的事，换到 Codex 或 Cursor 接着做，不用重新解释"我们做到哪了"。

**进度存在文件里，不在对话里。** 对话会截断、会压缩、会换客户端；文件不会。

---

## 为什么需要这个

| 场景 | 没有接力包 | 有接力包 |
|---|---|---|
| 换个 AI 接着做 | "我们做到哪了？" 重新讲一遍 | AI 直接读状态，接着干 |
| 需求模糊就开工 | 做完才发现方向错了 | 先问清再动手 |
| AI 瞎写代码 | 写完直接交 | 验证试跑后才交付 |
| 同一件事反复问 | 每次都要解释 | 沉淀到本地，不用再说 |

---

## 谁适合用

- 在 **多 AI 客户端之间切换**工作的人（Claude Code / Codex / Cursor / Gemini CLI / 其他读本地文件的 AI）
- 经常做到一半被打断，下次不想从头讲的人
- 想让 AI **先问清需求再动手**，而不是闷头做完才发现方向错了
- 重视**数据隐私**，不想任务内容上传云端的人

## 谁不适合用

- **纯网页版 AI 用户**（ChatGPT 网页版、Claude.ai 网页版等读不到本地文件的客户端）——参与不了接力
- **只想问问题、不想做长任务**的人——这是给"干活"用的，不是聊天机器人
- **多人协作场景**——当前是单机单用户设计，多设备/多人同步不在路线图上

---

## 三步装上

```bash
# 1. 克隆或下载本仓库
git clone https://github.com/<你的用户名>/relay-kit.git
cd relay-kit

# 2. 跑安装（需要 Python 3.7+，无其他依赖）
python 安装.py

# 3. 新开一个 AI 会话
```

完事。之后正常说话就行，不用记任何命令。

**最小要求**：Python 3.7+ / Windows / macOS / Linux。不需要 Node、不需要 Docker、不需要联网。

---

## 它会做什么

### ① 你说"接着上次做"
AI 先读状态文件，**直接接着干**，不会再问一遍已经写在卡里的事。

### ② 你说"帮我做个 XX"
AI **不会直接开工**。它先拆四件事（要什么产物 / 哪个领域 / 什么动作 / 怎么算做完），只问它还缺的那几条——最多 3 条。

### ③ 交付前自检
- **preflight**：没写 decision 直接退出码 2，不许交付
- **audit**：自写脚本必须过 B1/B2/B3 三道检查点
- 发现前后矛盾**显式问你**，不静默改

### ④ 沉淀你的习惯
只存本地，不上传。比如"回复始终用简体中文"，说一次就够了。

---

## 怎么工作的

```
┌──────────┐  写   ┌───────────────┐  读   ┌──────────┐
│  AI 甲   │ ────▶ │  ~/.relay/    │ ◀──── │  AI 乙   │
│ (Claude) │       │  你的任务状态  │       │ (Codex)  │
└──────────┘       └───────────────┘       └──────────┘
```

**前提**：这几个 AI 跑在同一台电脑上（都能读到那个文件）。纯网页版 AI 看不到本地文件，参与不了。

**换电脑**：把 `~/.relay` 文件夹拷过去就行。

---

## 安全

- ✅ 只写本地文件，**零网络调用**
- ✅ 可卸载：`python 安装.py --uninstall`
- ✅ 爆炸半径极小：只碰 `~/.relay` 和注入块标记之间
- ✅ 不收集数据、不上传、不埋点

**你可以自己审计**：

```bash
# 预期：没有任何输出（核心代码不 import 网络/子进程相关模块）
# 注：scripts/smoke_test.py 是测试脚本，内部用 subprocess 调用 relay.py 做端到端验证，不参与核心运行时
grep -rnE "import (urllib|requests|socket|http)|subprocess|eval\(|exec\(" scripts/relay.py scripts/cap_index.py 安装.py
```

---

## 命令速查

| 命令 | 做什么 |
|---|---|
| `python relay.py go` | ★ 单入口：看状态 / 开新任务 |
| `python relay.py go "需求"` | 开新任务卡 |
| `python relay.py ask-style <id>` | 选风格档（严谨/自适应/参照） |
| `python relay.py preflight <id>` | 交付前自检（不过退出码 2） |
| `python relay.py audit <id>` | 自写脚本 B1/B2/B3 检查 |
| `python relay.py style` | 从历史卡现算你的风格画像 |
| `python scripts/smoke_test.py` | 一条龙验证安装是否正常 |

---

## 文件结构

```
relay-kit/
├── SKILL.md              # 技能主文件
├── 安装.py               # 一键安装
├── 秒上手.md             # 给第一次用的人
├── config.json           # 配置（一般不用改）
├── CHANGELOG.md          # 版本历史
├── scripts/
│   ├── relay.py          # 任务状态读写
│   ├── cap_index.py      # 本地能力索引
│   └── smoke_test.py     # 一条龙验证
└── references/
    ├── 状态文件格式.md     # 给想自己写工具的人
    └── 分发说明.md        # 怎么打包给别人
```

---

## 常见问题

**Q：要联网吗？**
不用。全程本地文件读写。

**Q：要装依赖吗？**
不用。Python 标准库。

**Q：会上传我的任务内容吗？**
不会。代码里没有任何网络调用。你可以用上面的审计命令自己验证。

**Q：换 AI 后它还是问"做到哪了"？**
新开一个会话。客户端不会热重载技能。

**Q：我不想写注入块？**
加 `--no-agents`。代价是每次要自己说一句"先跑 relay.py go"。

**Q：任务存在哪里？会不会和我的技能目录混在一起？**
不会。任务状态在 `~/.relay/`（用户主目录下的隐藏文件夹），技能目录里只有代码和文档。打包技能目录发给别人，不会带出你的任何个人数据。

---

## Contributing

欢迎提 issue 和 PR。提交前请跑一次 `python scripts/smoke_test.py` 确保没破东西。

---

## License

MIT
