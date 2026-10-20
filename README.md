# 事证 EventProof · 投资事件证据时间线

> 把一条投资消息，还原成一条可追溯、可回放、会随证据更新的证据链。

> **只看最核心的一条链路**：本地打开 `http://127.0.0.1:8000/core.html`，说明见 [README-core.md](README-core.md)。

事证不是资讯流，也不是聊天机器人。它把公告、新闻、研报和传闻汇聚成同一事件的版本链，区分事实、观点、推测和传闻，在事件被确认、否认、更正或过期时改变结论，并只对实质变化通知用户。

当前仓库是 **48 小时垂直切片**：本地 SQLite 可运行，已用真实公开材料跑通一条完整事件线；公网 URL 待 Render 免费层部署。

## 1. 目标用户

- 买方研究员 / 基金经理助理：早上 15 分钟扫一遍关注标的的实质变化。
- 卖方分析师：事件复盘、客户问答、写点评时快速定位最初来源和关键数字。
- 个人专业投资者：判断一条消息是旧闻、传闻还是官方确认。
- 合规 / 内容团队：需要每条结论都有出处、时间和版本。

## 2. 核心主线

**一条消息进来 → 判断它是不是同一事件的新版本 → 拆成可核验的主张 → 给每条主张绑定证据和权重 → 推导事件当前状态 → 实质变化时通知用户 → 支持按“当时已知”回放。**

主线只回答四个问题：

| 问题 | 产品动作 | 界面 |
| --- | --- | --- |
| 这是不是同一件事？ | 合并重复报道、关联阶段、必要时拆分 | 事件串、合并依据 |
| 哪些是事实，哪些只是说法？ | claim 级分类：事实/观点/推测/传闻/否认/更正 | 主张卡片 |
| 现在是什么状态，凭什么？ | 证据强度、冲突、核实状态 | 置顶结论卡、证据抽屉 |
| 什么时候变的，变了什么？ | revision、diff、P0/P1 通知 | 版本记录、通知抽屉、as-of 回放 |

## 3. 当前演示事件

**通宇通讯（002792）收购佳贤通信 25% 股权 + 英伟达 6G 合作传闻澄清**

| 时间 | 文档 | 关键内容 |
| --- | --- | --- |
| 2026-08-05 | 对外投资公告 | 拟以 3 亿元受让佳贤通信约 25% 股权，分四期交割，不并表 |
| 2026-08-05 | 股票异常波动公告 | 7/31、8/3、8/4 三个交易日收盘涨幅偏离值累计超 20% |
| 2026-08-07 | 市场传闻澄清公告 | 否认佳贤与英伟达存在研发合作关系；否认意向采购/供货协议；产品仍处前期研发 |
| 2026-08-08 | 股票异常波动公告 | 8/5–8/7 三个交易日收盘涨幅偏离值累计超 20% |

这个事件的关键不是“收购是真的”，而是**同一条传闻里，25% 入股比例与公告一致，但英伟达合作和 2000 亿市场被公司否认**。事件串把真、假、未核实拆开，而不是用一篇文章概括。

## 4. 已实现

- 事件串（默认视图）：置顶结论 + 按披露时间排列的来源楼层 + 主张卡片 + 原文引用。
- 简报视图：四类时间、我们知道/不知道、主张表、版本链。
- Claim 级分类：事实、观点、推测、传闻、否认、更正。
- 证据权重：权威性、直接性、独立性、具体性、佐证度、抽取置信六因子；传闻上限 35，单一非官方来源上限 55。
- 同一事件合并依据：显式引用 + 主体/标的/比例槽位匹配；记录在 `merge_decisions`。
- 版本链：v1 公告 → v2 传闻待核实 → v3 官方否认 → v4 市场反应；每次 revision 只追加。
- 版本 diff：新增主张、状态变化（未核实 → 已否认）、触发文档。
- 通知：P1 重大交易公告、P0 官方否认、P1 市场异动；每条都有“为什么通知我”。
- As-of 回放：回到 08-06 只看公告；回到 08-07 17:55 看到传闻但未核实；回到 08-07 18:00 看到否认。
- 证据包导出：Markdown，含原文 URL、quote、权重拆解、版本、模型和免责声明。
- 初始数据重置：`POST /api/demo/reset`（需要 `X-Admin-Token`）。

## 5. 快速运行

### 5.1 后端

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
cd apps\api
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

启动时会自动从 `fixtures/tongyu/precomputed.json` 建 SQLite（`data/eventproof.db`）并灌入种子数据。

### 5.2 前端

```powershell
cd apps\web
npm install
npm run dev
```

打开 `http://127.0.0.1:5173`。

生产模式：

```powershell
cd apps\web
npm run build
cd ..\api
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

FastAPI 会直接托管 `apps/web/dist`，打开 `http://127.0.0.1:8000`。

### 5.3 重新跑 AI 预计算（可选）

先在 `.env` 配置：

```env
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=...
LLM_MODEL_FAST=qwen3.8-flash
```

然后：

```powershell
python scripts\precompute.py
python scripts\merge_source_meta.py
```

当前仓库已包含 `fixtures/tongyu/precomputed.json`，**不需要 key 也能跑 demo**。

## 6. 数据与 AI

### 6.1 数据

- 4 份 CNINFO 官方 PDF：`fixtures/tongyu/sources.json` 记录了标题、披露日期、原文 URL、片段。
- 证据 quote 来自 iFinD 公告检索片段；PDF 原文保留在 `fixtures/raw/tongyu/`。
- **已知边界**：CNINFO PDF 的中文字体 ToUnicode 异常，`pypdf` / `pdfplumber` / `PyMuPDF` 提取均为乱码；当前使用 iFinD 片段 + CNINFO URL，OCR 列为 P1。
- 用户已确认 iFinD 内容可做公开 demo 的短引用；页面只展示必要摘录与原文链接，不全文转载。

### 6.2 AI 角色

- 模型：阿里云百炼 `qwen3.8-flash`，`enable_thinking=false`。
- Prompt：`claim_extract_v1`，每条 claim 必须返回原文 quote。
- 4 次调用，合计 1,633 prompt tokens + 2,770 completion tokens；按保守估算 ¥0.0072，预算硬停 8 元。
- 校验：quote 必须是原文归一化子串；无有效 quote 的 claim 丢弃；原始输出保存在 `precomputed.json` 的 `llm_calls`。
- AI 做语义抽取，**不做真值裁决**；证据评分、状态迁移、通知规则由确定性代码执行。

完整的 AI 使用与验证记录见 [docs/ai-usage.md](docs/ai-usage.md)。

## 7. 关键设计

### 7.1 四类 + 两类

| 类型 | 定义 | 示例 |
| --- | --- | --- |
| fact | 可核验的陈述 | “拟以 3 亿元受让 25% 股权” |
| opinion | 评价/判断 | “该交易增厚 EPS” |
| speculation | 未来推测 | “预计明年放量” |
| rumor | 未经证实的流传说法 | “佳贤与英伟达合作开发 6G AI-RAN” |
| denial | 对既有说法的否定 | “不存在研发合作关系” |
| correction | 对既有说法的更正 | “对价应为 8 亿元” |

### 7.2 证据权重

```
strength = 100 × (
  0.30 × 权威性 + 0.20 × 直接性 + 0.15 × 独立性
  + 0.10 × 具体性 + 0.15 × 佐证度 + 0.10 × 抽取置信
)
```

- 传闻上限 35；单一非官方来源上限 55。
- 观点不计入事实强度；否认/更正不随时间衰减。
- 界面明确写“证据强度不是真值概率”。

### 7.3 时间

- `occurred_at`：事情发生（本事件为 2026-08-04，日期级）。
- `disclosed_at`：来源披露（2026-08-05，日期级）。
- `first_ingested_at`：系统首次抓取（2026-08-05 18:00，演示推断）。
- `updated_at`：最近实质变化（2026-08-08 18:00）。
- `knowledge_at`：每个 revision 被系统确认的时间，用于 as-of 回放。

具体时分为演示推断，界面标注“推断”；不伪造原始精度。

### 7.4 同一事件

本切片使用显式引用 + 槽位匹配：

- 08-07 澄清公告显式引用 08-05 对外投资公告；
- 主体=通宇通讯，标的=佳贤通信，比例=25%，金额=3 亿元；
- 08-08 异常波动公告再次引用同一传闻 → 挂接为市场反应，不重复计算独立来源。

LLM 同一性裁决、相似度召回和人工合并审核队列是下一步。

## 8. API

| Method | Path | 说明 |
| --- | --- | --- |
| GET | `/health` | 进程健康检查，不查 DB |
| GET | `/api/events` | 事件列表 |
| GET | `/api/events/{id}?as_of=` | 事件详情 + 版本 + claims + 文档 |
| GET | `/api/events/{id}/diff?from_version=&to_version=` | 版本 diff |
| GET | `/api/events/{id}/merge` | 合并依据 |
| GET | `/api/notifications` | 通知列表 |
| POST | `/api/notifications/{id}/read` | 标记已读 |
| GET | `/api/events/{id}/export` | Markdown 证据包 |
| POST | `/api/demo/reset` | 重置 demo 数据（需 `X-Admin-Token`） |

## 9. 测试

```powershell
cd apps\api
$env:PYTHONPATH="D:\Code\投资跟踪\apps\api"
..\..\.venv\Scripts\python.exe -m pytest tests -q
```

当前结果：**22 passed**（13 个 API 测试 + 9 个事件引擎测试）。覆盖健康检查、事件列表/详情、v1/v2/v3 as-of、v2→v3 diff、证据包、通知已读/重置、管理员 token、四个场景 API，以及同一事件匹配、更新、子 claim 否认、核心否认、更正、过期和 linked Event。

手动验收路径：打开首页 → 点“看否认 diff” → 关弹窗 → 点传闻 claim 看证据抽屉 → 切 v2/v3 → 打开通知 → 标记已读 → 切“简报” → 导出证据包。

完整测试说明见 [docs/testing.md](docs/testing.md)。

## 10. 部署（零成本）

- 已发布静态备用入口：`https://zjzjy.github.io/eventproof/core-simple.html`（GitHub Pages）。
- Render 免费层当前要求信用卡验证；不绑卡时改用 Hugging Face Docker Space，`hf-space` 分支已准备好 7860 端口和 Space 配置。
- `Dockerfile`：Node 构建前端，Python 运行 FastAPI，单容器同时托管静态文件和 API。
- `render.yaml`：Render Free Web Service，`plan: free`，`healthCheckPath: /health`，无需服务器、域名或信用卡。
- 启动时从 `fixtures/tongyu/precomputed.json` 建 SQLite；Render 免费实例文件系统是临时的，重启会恢复种子数据，适合只读 demo。
- UptimeRobot 每 5 分钟 ping `/health`，避免 15 分钟休眠。
- 如果要多用户持久化写操作，再接 Neon/Postgres；当前切片没有实现 Postgres adapter。

部署步骤见 [docs/01-零成本部署方案.md](docs/01-零成本部署方案.md)。

## 11. 已知边界与未做

**已知边界**

- 目前只有 1 个事件、4 份文档、15 条 claim，不是全市场产品。
- 证据权重是可解释启发式，不是校准概率；未做正式 F1 评测。
- 同一事件合并当前是显式引用 + 槽位匹配，不是通用 LLM 裁决。
- 具体时分是演示推断；原始披露只有日期级。
- PDF 中文提取乱码，当前依赖 iFinD 片段；OCR 未做。
- SQLite 在 Render 免费实例上不持久；通知已读状态重启会恢复。
- 公开 demo 只做短引用，不全文转载 iFinD/CNINFO 内容。
- 不构成投资建议，不生成买卖/目标价。

**未做**

- 实时轮询、全量 connector、去重/转载识别流水线。
- 更正/过期/撤回的完整演示数据（状态机已设计，当前只展示更新 + 否认 + 市场反应）。
- LLM 同一性裁决、冲突检测、摘要回归。
- 行情/财务影响验证（T0/CAR）、扶摇接入。
- 有引用的问答、自定义告警、邮件/webhook。
- 多用户/RBAC、Postgres adapter、OCR、移动端精修。
- 60–180 秒演示视频（待录制）。

## 12. 目录

```
apps/api/app/          FastAPI、SQLite、seed、API
apps/api/tests/        pytest（22 passed：13 API + 9 engine）
apps/web/src/          React 事件串、证据抽屉、diff、通知、简报
fixtures/tongyu/       sources.json + precomputed.json
fixtures/raw/tongyu/   4 份 CNINFO PDF（原始件）
scripts/               precompute.py、merge_source_meta.py
docs/                  设计、零成本部署、核心主线、AI 记录、测试
notes/                 UI 走查笔记
Dockerfile             Render 单容器
render.yaml            Render Free Blueprint
```

## 13. 交付物状态

| 交付物 | 状态 |
| --- | --- |
| 可运行 Web | 本地已跑通；公网 URL 待 Render 部署 |
| 源代码仓库 | 本地已 `git init` + commit；待 GitHub remote/push |
| README | 本文件 |
| 60–180s 视频 | 待录制 |
| AI 使用与验证记录 | `docs/ai-usage.md` |
| 测试说明 | `docs/testing.md` |
| 高层设计 | `docs/00-高层设计.md` |
| 零成本部署 | `docs/01-零成本部署方案.md` |

## 14. 免责声明

本产品只做公开信息的事件整理、证据追溯和版本记录，不构成任何投资建议。所有关键数字和结论都应回到原文链接核对；证据强度不是事实为真的概率。
