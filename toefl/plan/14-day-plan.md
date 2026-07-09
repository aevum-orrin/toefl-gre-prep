# 14 天托福冲刺计划（2026 新版）

底子 107，重点补 **口语 + 写作**，同时适配 2026 自适应阅读/听力和新口语题型。

## 分数诊断（第 0 天先做）

先做 1 套 2026 新格式全真模考（TPO 或官方 Practice），拿到四科 band，定位真实短板——
"感觉口语写作差"不一定准，用数据说话。

## 每日节奏（可按实际调整）

| 天 | 主题 | 上午 | 下午 | 晚上（AI 工具） |
|----|------|------|------|-----------------|
| D1 | 诊断 + 熟悉新题型 | 全真模考 | 复盘四科错因 | 录一段口语基线，跑 speaking-app 打分 |
| D2 | 口语·Listen & Repeat | 官方样题精听跟读 | 影子跟读 20min | speaking-app 跟读打分 + writing-coach 批 1 篇讨论 |
| D3 | 口语·Take an Interview | 面试题库(一话题4问) | 计时作答录音 | speaking-app AI 反馈发音/流利度(✨可实时出新题) |
| D4 | 写作·Academic Discussion | 结构模板 + 论点库 | 限时 10min 成文 ×2 | writing-coach 润色 + 对比范文 |
| D5 | 写作·Write an Email | 邮件语域/礼貌用语 + 题库 20 题 | 限时 7min 成文 ×2 | writing-coach 查语域/是否达成目的 |
| D6 | 阅读·自适应策略 | reading-listening 计时精读 | 题型归类错题 | vocab-srs 背当日生词 |
| D7 | 听力·自适应 + 讲座笔记 | reading-listening 讲座精听(TTS 朗读) | 笔记复盘 | 全周错题重刷 |
| D8 | 半程模考 | 新格式全真模考 | 四科复盘 | 更新短板权重 |
| D9–D12 | 按短板加权轮转 | 口语/写作各 1 轮 | 阅读/听力补弱 | 每晚 AI 批改 + SRS |
| D13 | 全真模考（冲刺） | 模考 | 精修口语写作模板 | 最后一轮高频词 |
| D14 | 调整 + 轻量复盘 | 过模板/错题本 | 休息、调作息 | 考前状态确认 |

## 可复用架构（TOEFL ↔ GRE）

**Monorepo**：一个仓库 `toefl-gre-prep`，两科 + 共享代码都是并列子文件夹（全在 `main`）。

```
toefl-gre-prep/
├── prep-core/   共享内核 (pip install -e ./prep-core)
├── tools/       共享 App (writing-coach, speaking-app, vocab-srs, reading-listening)
├── toefl/       托福数据 (rubrics, speaking, writing, reading, listening, vocab, plan)
└── gre/         GRE 数据 (vocab 已备; rubric 一个多月后填)
```

- **`prep-core` 提供**：`FeedbackEngine`(多后端: gemini/groq/anthropic/offline + rubric)、
  `QuestionGenerator`(实时出题)、`SRS`、`Transcriber`(faster-whisper)、`ProgressStore`。
- **AI 免费优先**：默认 Gemini 免费额度;语音用本地 faster-whisper + 浏览器 TTS，全程零成本。
- **加 GRE**：建 `gre/rubrics/*.json`(Issue/Argument)，词表已就绪，四个 App **零改动**。

## 四个工具（都是本地网页，端口 8001–8004）

### writing-coach :8001
- 选 2026 写作任务(Write an Email / Academic Discussion)→ 载入官方题库或自己贴 → 0–5 分 + 分维度批改 + 润色范文。

### speaking-app :8002（需麦克风 → 笔记本上跑）
- Listen & Repeat：TTS 播句 → 录音 → Whisper 转写 → 词命中率打分。
- Take an Interview：一话题 4 问 → 计时录音 → AI 按官方 rubric 反馈；✨可实时生成新题。

### vocab-srs :8003
- SM-2 间隔重复背词，托福/GRE 词表共用，Anki 式四按钮。

### reading-listening :8004（免费，无需 key）
- Reading：学术/生活文本 + 四选一，自动判分 + 解析。
- Listening：浏览器 TTS 朗读讲座/对话(不显示原文)→ 四选一，自动判分。
