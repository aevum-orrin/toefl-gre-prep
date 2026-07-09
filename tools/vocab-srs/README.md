# vocab-srs — 背单词(SM-2 间隔重复)

托福 / GRE 共用的间隔重复背词网页,由 `prep_core.SRS`(SM-2 算法,和 Anki 早期同款)驱动。
只调度、不联网、不花钱。

```bash
source ../../env.sh
uvicorn app:app --reload --port 8003   # http://localhost:8003
```

## 怎么用
- 顶部切换 **TOEFL / GRE** 牌组(词表来自 `toefl/vocab/` 和 `gre/vocab/`)。
- 看到词 → 按 **Space** 翻面看释义/例句 → 按 Anki 式四个键给自己打分:
  - **Again(1)** 没记住 → 明天重来
  - **Hard(2)** / **Good(3)** / **Easy(4)** → 记住了,间隔按 SM-2 逐步拉长
- 键盘:`Space` 翻面,`1/2/3/4` 打分。

## 数据
- 词表(内容):`{term, definition, example, pos}` 的 JSON,放在对应科目的 `vocab/` 下,可随意扩充。
- 复习进度(调度状态):`data/srs/<deck>.json`(gitignored),每次打分自动存。
- 加新词:往词表 JSON 里加条目即可,启动时自动并入,已有词的复习进度不受影响。

> SM-2 足够个人冲刺用。将来想要更省复习量,可把调度函数换成 FSRS(Anki 现默认),
> App 其余部分不用动 —— 详见 `docs/` 里的调研笔记。
