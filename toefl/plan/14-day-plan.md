# 14 天托福冲刺计划（2026 新版）

底子 107，重点补 **口语 + 写作**，同时适配 2026 自适应阅读/听力和新口语题型。

## 分数诊断（第 0 天先做）

先做 1 套 2026 新格式全真模考（TPO 或官方 Practice），拿到四科 band，定位真实短板——
"感觉口语写作差"不一定准，用数据说话。

## 每日节奏（可按实际调整）

| 天 | 主题 | 上午 | 下午 | 晚上（AI 工具） |
|----|------|------|------|-----------------|
| D1 | 诊断 + 熟悉新题型 | 全真模考 | 复盘四科错因 | 录一段口语基线，跑 speaking-app 打分 |
| D2 | 口语·Listen & Repeat | 官方样题精听跟读 | 影子跟读 20min | writing-coach 批改 1 篇 Academic Discussion |
| D3 | 口语·Take an Interview | 常见面试题库 | 计时作答录音 | AI 逐句反馈发音/流利度 |
| D4 | 写作·Academic Discussion | 结构模板 + 论点库 | 限时 10min 成文 ×2 | AI 润色 + 对比范文 |
| D5 | 写作·Integrated | 听读笔记法 | 限时成文 | AI 查逻辑/引用完整性 |
| D6 | 阅读·自适应策略 | 2 篇计时精读 | 题型归类错题 | SRS 背当日生词 |
| D7 | 听力·自适应 + 讲座笔记 | 3 段讲座精听 | 笔记复盘 | 全周错题重刷 |
| D8 | 半程模考 | 新格式全真模考 | 四科复盘 | 更新短板权重 |
| D9–D12 | 按短板加权轮转 | 口语/写作各 1 轮 | 阅读/听力补弱 | 每晚 AI 批改 + SRS |
| D13 | 全真模考（冲刺） | 模考 | 精修口语写作模板 | 最后一轮高频词 |
| D14 | 调整 + 轻量复盘 | 过模板/错题本 | 休息、调作息 | 考前状态确认 |

## 可复用架构（TOEFL ↔ GRE）

**Monorepo**：一个仓库 `toefl-gre-prep`，两科 + 共享代码都是并列子文件夹（全在 `main`）。

```
toefl-gre-prep/
├── prep-core/   共享内核 (pip install -e ./prep-core)
├── tools/       共享 App (writing-coach, speaking-app) —— 两科都用
├── toefl/       托福数据 (rubrics, speaking, plan, 词表)
└── gre/         GRE 数据 (一个多月后填)
```

- **`prep-core` 提供**：`FeedbackEngine`(Claude API + rubric)、`SRS`、`Transcriber`(faster-whisper)、`ProgressStore`。
- **App 考试无关**：靠 `RUBRICS_DIR` / `SPEAKING_DIR` 指到对应科目的数据。
- **加 GRE**：建 `gre/rubrics/*.json`(Issue/Argument)+ 词表，App 和内核**零改动**。

## 两个工具的 MVP 范围

### writing-coach（桌面/本地网页）
- 输入作文 → 按 TOEFL rubric 出分 + 分点批改（Task Response / Coherence / Language Use）
- 一键"润色对比"：原句 vs. 改写，并解释为什么改
- 保存历史，追踪常犯错误
- 迁移 GRE：换 rubric（Issue/Argument 写作）即可

### speaking-app（先做本地网页 PWA）
- Listen & Repeat：播放句子 → 录音 → ASR 转写 → 对比打分（发音/完整度）
- Take an Interview：出面试题 → 计时录音 → AI 反馈（流利度/内容/语法）
- 迁移 GRE：GRE 无口语，此模块托福专用；但 Recorder/Transcriber/FeedbackEngine 全在 prep-core，不浪费
