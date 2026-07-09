# TOEFL & GRE Prep

个人托福 + GRE 备考 **monorepo**。一个仓库同时装两科 + 共享代码工具：短期(两周)冲刺**托福 2026 新版**，之后接 **GRE**;听说读写里主攻**口语 / 写作**两块短板。

> 底子:两年前托福 107/120(旧满分制)。托福逐日计划见 [toefl/plan/14-day-plan.md](toefl/plan/14-day-plan.md)。

## 为什么要重新学:2026 新托福 vs. 我两年前考的版本

我 2024 年考的已经是 **2023-07 改版**后的格式。所以对我来说 **真正的新东西是 2026-01-21 这波改革**:

| 维度 | 2023-07 版(我考过的) | **2026-01 版(本轮要练的)** |
|------|----------------------|------------------------------|
| 总时长 | ~116 分钟 | **~90 分钟** |
| 阅读 / 听力 | 固定题 | **多阶段自适应(adaptive)** |
| 口语 | 4 个任务 | **改成 2 类新任务:Listen and Repeat(跟读)+ Take an Interview(模拟面试)** |
| 计分 | 0–120 | **新增 1–6 band(对齐 CEFR),四科平均**;0–120 仍保留 |

**结论**:口语题型全新,必须专门练(speaking-app);阅读听力适应自适应;写作沿用 Academic Discussion(writing-coach)。

## 仓库结构(monorepo,全在 `main`)

```
toefl-gre-prep/
├── prep-core/         # 共享内核 (pip -e 可装, 考试无关)
│   └── src/prep_core/ # FeedbackEngine · providers(多后端) · generate(实时出题)
│                      #   · SRS · ProgressStore · Rubric · audio(faster-whisper)
├── tools/             # 共享 App —— 托福和 GRE 都用同一套
│   ├── writing-coach/ # AI 作文批改/润色 (FastAPI + 网页) :8001
│   ├── speaking-app/  # 口语:跟读 + 模拟面试 (浏览器录音 + Whisper + AI 打分) :8002
│   └── vocab-srs/     # 背单词:SM-2 间隔重复翻卡 (托福/GRE 共用) :8003
├── toefl/             # 托福专属数据
│   ├── rubrics/{writing,speaking}/  # 2026 官方 0–5 分维度 (write_email / academic_discussion
│   │                                #   / speaking_interview / speaking_listen_repeat)
│   ├── speaking/      # 跟读句库(60) + 面试题库(20 话题×4 问)
│   ├── writing/       # 邮件(20) + 学术讨论(20) 题库
│   ├── vocab/         # 托福词表(100)
│   └── plan/          # 14 天计划
├── gre/vocab/         # GRE 词表(100);其余 GRE 专属内容一个多月后填
├── docs/              # 2026-toefl-format.md —— 核实过的官方格式+评分(单一事实源)
└── data/              # 录音、进度、SRS 状态 (gitignored)
```

**复用之道**:凡是与考试无关的能力都在 `prep-core`;App 靠 `RUBRICS_DIR` / `SPEAKING_DIR` / 词表路径指到对应科目。加 GRE 时:建 `gre/rubrics/*.json` + 已有 `gre/vocab`,App 和内核**零改动**。

## AI 后端:免费优先,可一键切换

`FeedbackEngine` 和实时出题都走可插拔后端,由 `.env` 里的 `LLM_PROVIDER` 选(不填则自动挑第一个有 key 的,顺序 gemini→groq→anthropic):

| provider | 费用 | 说明 |
|----------|------|------|
| **gemini**(默认) | **免费** | Google AI Studio key(不用绑卡),质量最好的免费选项。注意:免费额度下输入可能被 Google 用于训练+人工审核。 |
| **groq** | **免费** | Llama-3.3-70B,~1 秒出反馈,**合同不训练你的数据**(隐私更好)。 |
| **anthropic** | 付费 | Claude,质量最高,**按 token 单独计费(不走订阅/Apple Pay)**。 |
| **offline** | 免费 | 无 key 时的确定性桩,只测管道,不是真实评分。 |

语音全程免费本地:**faster-whisper**(转写)+ 浏览器 **Web Speech API**(读题)。题库既是"离线也能练"的素材,也是实时生成失败时的兜底。

## 环境(Great Lakes 登录节点)

```bash
source env.sh                     # module load python/3.12.1 ffmpeg/7.1.0 + 激活 .venv
pip install -r requirements.txt   # 首次;含 editable 的 ./prep-core[audio]
```

**免费上手**:`cp .env.example .env`,填 `GEMINI_API_KEY`(去 https://aistudio.google.com/apikey 免费领,不用绑卡)即可真实评分 + 实时出题。想更注重隐私就改填 `GROQ_API_KEY` 并设 `LLM_PROVIDER=groq`。App 在**进程内**读 `.env`,**不导出到 shell** —— 否则同一 shell 里的 Claude Code 会改用这个 key 按 token 计费,绕过 Max 订阅。**Anthropic API 是独立账户按 token 付费,不走 Apple Pay、不从订阅扣**;不填卡就只是调用失败,不会偷偷扣款。

## 用法

```bash
# 写作批改
cd tools/writing-coach && uvicorn app:app --reload --port 8001   # http://localhost:8001
# 口语练习(需麦克风 → 在笔记本上跑;集群上跑要 ssh -L 端口转发到 localhost)
cd tools/speaking-app && uvicorn app:app --reload --port 8002    # http://localhost:8002
# 背单词(SM-2 间隔重复,托福/GRE 共用)
cd tools/vocab-srs && uvicorn app:app --reload --port 8003       # http://localhost:8003
```

## 进度

- [x] Monorepo + GitHub 远程(仓库已改名 `toefl-gre-prep`;`.env` 待填 key)
- [x] `prep-core` 内核:**多后端引擎**(gemini/groq/anthropic/offline)+ **实时出题** + SRS + Progress + Rubric + faster-whisper — 4 单测通过
- [x] 核实并落地 **2026 官方格式 + 四科评分**(`docs/2026-toefl-format.md`);rubric 更新为官方 0–5 维度(删 Integrated Writing,加 Write-an-Email)
- [x] 大题库:跟读 60 / 面试 20 话题 / 邮件 20 / 讨论 20 / 词表 100×2
- [x] writing-coach / speaking-app / vocab-srs 三个 App 端到端跑通(离线桩验证)
- [ ] 填 `GEMINI_API_KEY` 跑一次真实评分 + 实时出题(需你领免费 key)
- [ ] 真实麦克风口语测试(在你笔记本上)
- [ ] GRE:建 `gre/rubrics/*.json`(Issue/Argument),复用三个 App
