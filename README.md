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
│   └── src/prep_core/ # FeedbackEngine · SRS · ProgressStore · Rubric · audio(faster-whisper)
├── tools/             # 共享 App —— 托福和 GRE 都用同一套
│   ├── writing-coach/ # AI 作文批改/润色 (FastAPI + 网页)
│   └── speaking-app/  # 口语练习:跟读 + 模拟面试 (浏览器录音 + Whisper + AI 打分)
├── toefl/             # 托福专属:rubrics、plan、speaking 素材、词表
│   ├── rubrics/       # academic_discussion / integrated_writing / speaking
│   ├── speaking/      # 跟读句库 + 面试题库
│   └── plan/          # 14 天计划
├── gre/               # GRE 专属 (一个多月后填:Issue/Argument rubric、词表)
└── data/              # 录音、进度日志 (gitignored)
```

**复用之道**:凡是与考试无关的能力都在 `prep-core`;App 是考试无关的(靠 `RUBRICS_DIR` / `SPEAKING_DIR` 指到对应科目的数据)。加 GRE 时:建 `gre/rubrics/*.json` + 词表,App 和内核**零改动**。

## 环境(Great Lakes 登录节点)

```bash
source env.sh                     # module load python/3.12.1 ffmpeg/7.1.0 + 激活 .venv
pip install -r requirements.txt   # 首次;含 editable 的 ./prep-core[audio]
```

**API key / 计费**:`.env`(gitignored)放 `ANTHROPIC_API_KEY`(见 `.env.example`)。App 在**进程内**读 `.env`,**不导出到 shell** —— 否则同一 shell 里的 Claude Code 会改用这个 key 按 token 计费,绕过 Max 订阅。App 调 API 花的是 **API 的钱(约 $0.03–0.05/篇)**,不在订阅覆盖内。

## 用法

```bash
# 写作批改
cd tools/writing-coach && uvicorn app:app --reload --port 8001   # http://localhost:8001
# 口语练习(需麦克风 → 在笔记本上跑;集群上跑要 ssh -L 端口转发到 localhost)
cd tools/speaking-app && uvicorn app:app --reload --port 8002    # http://localhost:8002
```

## 进度

- [x] Monorepo 建好并连 GitHub 远程(仓库待改名 `toefl-learning` → `toefl-gre-prep`)
- [x] `prep-core` 内核(FeedbackEngine 结构化输出 + adaptive thinking / SRS / Progress / Rubric / faster-whisper)— 4 单测通过
- [x] writing-coach(FastAPI + 网页,端到端跑通,接 key 即真实评分)
- [x] speaking-app(浏览器录音 + Whisper 转写 + AI 打分,管道端到端跑通)
- [ ] 用真实 API key 跑通一次真实评分(需你设 `.env`)
- [ ] 真实麦克风口语测试(在你笔记本上)
- [ ] GRE:建 `gre/` rubric + 词表,复用两个 App
