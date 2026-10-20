# 事证 EventProof · 项目上下文

> 最后更新：2026-10-20 ｜ 本次会话：完成核心垂直切片（事件串 + 证据 + diff + 通知 + as-of）

## 项目背景

这是“投资事件情报与证据时间线”的 48 小时候选人项目。目标不是做资讯流，而是做一条可追溯、可回放、会随证据更新的投资事件证据链：同一事件的识别/合并/版本演化，事实/观点/推测/传闻的区分与证据权重，四类时间的处理，以及确认、否认、更正、过期时的结论变化与通知。

验收硬约束：

- 可访问、可操作的 Web URL；源代码仓库 + README；60–180 秒演示视频；AI 使用与验证记录；测试说明。
- 关键数字与结论必须可追溯到原文、来源和时间。
- 48 小时内完成；单用户 demo 优先；不做投资建议。

## 上下文

- 题目附件：`候选人附件_投资事件情报与证据时间线.md`
- 高层设计：`docs/00-高层设计.md`（产品模型、算法、技术栈、环境、功能、模块、48h 计划）
- 零成本部署：`docs/01-零成本部署方案.md`（Render Free + SQLite 启动 seed + UptimeRobot；Neon 仅持久化时可选）
- 核心主线与表现形式：`docs/02-核心主线与表现形式.md`（一句话主线、四个问题、英雄场景、线框、10 元模型预算）
- 开发前准备清单：`docs/03-开发前准备.md`（本机环境、三项用户准备、两项可延后事项、默认决策）
- 英雄事件：通宇通讯（002792）收购佳贤通信 25% 股权 + “佳贤与英伟达合作 6G AI-RAN、瞄准 2000 亿市场”传闻澄清；素材在 `fixtures/tongyu/sources.json`，原始 PDF 在 `fixtures/raw/tongyu/`。
- 当前已有可运行垂直切片：`apps/api`（FastAPI + SQLite + seed/API + 事件引擎 + 场景 API）、`apps/web`（固定核心页 + 完整 React 事件串/证据/diff/通知/简报）、`apps/api/tests`（24 passed：14 API + 10 engine）。
- 运行：本地 `http://127.0.0.1:8000` 已跑通；后端 `.venv`，前端构建到 `apps/web/dist` 由 FastAPI 托管。
- 交付文档：`README.md`、`docs/ai-usage.md`、`docs/testing.md`、`notes/ui-review.md`。
- 极简核心链路：`apps/web/dist/core-simple.html`，打开 `/core.html` 会跳转；单页展示 4 个演化节点、A/B/C/D 证据等级、时间口径和 1 条 P0 通知；时间口径在演化上方，P0 并入否认节点，口径折叠在页面底部。无日期切换和柱状图。完整版仍保留但不再是主路径。
- iFinD 已可用，扶摇仍未接入。
- iFinD 官方 SKILL 已安装到 `C:\Users\Hanah\.codex\skills\ifind-finance-data`（v1.4.0），密钥已配置；`listTools("stock")` 自检通过（HTTP 200，10 个工具），`news` 服务 3 个工具：`search_notice`、`search_news`、`search_trending_news`。
- 本机可用：Node 22、Python 3.12、Docker 27、Git 2.47；工作区已 `git init`，当前 commit `29eefff`。
- 本机缺口：Docker daemon 未启动、无本地 Postgres/psql、无 Ollama、无 git 仓库；`gh` 在当前沙箱读不到配置。
- LLM 已配置：阿里云百炼 OpenAI 兼容接口，`qwen3.8-flash`；最小 JSON 抽取测试通过（3 条 claim，444 tokens，`enable_thinking=false`）。key 在 `.env`，不入库。
- PDF 解析注意：CNINFO 的 4 份公告 PDF 可下载，但 pypdf/pdfplumber/PyMuPDF 提取中文均为乱码（字体 ToUnicode 问题）；当前用 iFinD 检索片段 + CNINFO 原文 URL 作为证据，PDF 保留作原始件。OCR 列为 P1。
- 开发数据库决策：SQLite（零依赖）；容器启动时从 `precomputed.json` 重建，适合单用户只读 demo。Postgres adapter/Neon 是 P1，当前代码未实现。
- 实际技术栈：React 19 + Vite + TS + 手写 CSS；FastAPI 0.150 + Pydantic 2 + SQLite；没有 Tailwind/SQLAlchemy/Alembic（当前切片刻意减依赖）。
- 部署：Render Free Web Service（单容器同时托管 React 静态文件和 FastAPI，750 小时/月，15 分钟休眠、约 1 分钟唤醒）+ UptimeRobot Free（5 分钟保活）；公网地址用 `*.onrender.com`，不买服务器/域名。SQLite 启动 seed，重启恢复。
- 正式提交入口：GitHub Pages `https://zjzjy.github.io/eventproof/core-simple.html`；已验证 200，页面底部有四个“规则演练”链接，场景页走静态回退。
- 可选动态入口：Cloudflare Quick Tunnel（电脑/uvicorn/cloudflared 必须在线，重启后 URL 会变；不作为唯一提交 URL）。
- Hugging Face Docker Space 现在需要付费计划，不作为当前方案；`hf-space` 分支保留。
- 数据策略：`fixture / live / hybrid` 三档；真实公开文档快照兜底；连接器做适配器，不把业务逻辑绑死在单一供应商。
- AI 实际：百炼 `qwen3.8-flash`，4 次调用，1,633 prompt + 2,770 completion tokens，估算 ¥0.0072；LLM 产出 15 条 + 人工复核补入 2 条官方观点/预测 = 17 条 claim；原始输出在 `precomputed.json.llm_calls`。部署只读结果，不调用模型。

## 进度

- 已完成：题目拆解；产品定位；Storyline → Event → Claim → Evidence 四层模型；状态/时间/版本设计；同一事件合并与拆分规则；claim 分类与证据权重公式；通知分级；技术栈与环境选型；P0/P1/P2 功能清单；48h 排期；测试与合规模块。
- 已完成：iFinD SKILL 安装包下载、解压、复制到 Codex 技能目录；文件结构与 Node/Python 环境已核验。
- 已完成：iFinD 密钥写入与官方自检；stock/news 服务均可通信，临时自检脚本已清理。
- 已完成：零成本部署设计（Render + Neon + UptimeRobot）；明确单服务、`/health` 不查 DB、AI 预计算。
- 已完成：核心主线与表现形式；确定“一条消息 → 同一事件 → claim → 证据 → 状态 → diff/通知 → as-of 回放”的主线，以及桌面研究工作台而非聊天的形态。
- 已完成：百炼模型连通性与 JSON 抽取验证；`qwen3.8-flash` 可用，`.env` 已配置。
- 已完成：iFinD 检索到英雄事件并下载 4 份官方 PDF；整理出公告、澄清、两次异常波动的原文片段与 URL。
- 已完成：FastAPI API：events/detail/as-of/diff/notifications/export/reset + engine/apply/expire + events/{id}/scenario/{name}；SQLite 启动 seed；24 个 pytest 全过（14 API + 10 engine）。
- 已完成：React 事件串：置顶结论、四类 claim、六因子证据抽屉、v2→v3 diff、通知抽屉、as-of 预设、简报视图、证据包导出。
- 已完成：视觉走查 1440×1000；修复标题换行、文档顺序、favicon 404；确认“案卷感”而不是“股吧感”。
- 已完成：GitHub Pages 完整演示链：首次关注 002792 → 同步处理 → v1–v5 演化 → 通知 → 关注事件/抽屉；规则演练入口和 scenario 参数已从页面移除，状态用 localStorage，底部可重置。
- 已完成：关注入口与多事件抽屉：002792 通宇通讯 + 300209 行云科技；来源徽标、关注事件 toggle、关注标的表单；静态页用 localStorage。
- 已完成（已跑测）：后端纯函数引擎 `apps/api/app/engine.py`（match_event/apply_document/expire_event）与 `apps/api/tests/test_engine.py`；API `/api/engine/apply`、`/api/engine/expire` 已加并生效。
- 已完成：24 passed；五个场景页已通过引擎/API，版本/P0/P1/通知来自引擎返回；观点/推测已补入，官方冲突标记 disputed。
- 进行中：部署 Render、录 60–180s 视频；真实 ingestion/connector 仍是下一步。
- 已验证：本地 `http://127.0.0.1:8000` 返回 200；1 个事件、4 份文档、17 条 claim、4 个 revision；pytest 24 passed。

## TODO

1. **P0** 建 GitHub remote 并 push 当前 commit；本地已 `git init` + commit。
2. **P0** 注册 Render + UptimeRobot（不需要 Neon），用 `render.yaml`/`Dockerfile` 部署，拿到 `*.onrender.com` URL。
3. **P0** 录 60–180 秒演示视频：收件箱 → 事件串 → 证据抽屉 → v2→v3 diff → 通知 → as-of → 导出。
4. **P0** 补更正/过期/撤稿的演示数据或运行时动作（状态机已设计，当前只展示更新 + 否认 + 市场反应）。
5. **P1** 补 3–5 个事件、20–30 篇文档，做 claim 分类/合并标注集与正式指标。
6. **P1** 接行情/财务影响验证（T0/CAR）；扶摇未接。
7. **P1** PDF OCR（当前 CNINFO 字体 ToUnicode 乱码）、Postgres adapter、实时 connector、限流。

## 走的弯路

1. 全局 FastAPI 0.115 与 Starlette 1.3 不兼容，启动报 `Router.__init__() got an unexpected keyword argument 'on_startup'` → 不改全局 Python，建项目 `.venv` 安装 FastAPI 0.150/Starlette 1.9。
2. npm 默认缓存目录 `C:\Users\Hanah\AppData\Local\npm-cache` 在沙箱内 EPERM → 使用 `D:\Code\投资跟踪\.npm-cache`。
3. CNINFO PDF 中文 ToUnicode 异常，pypdf/pdfplumber/PyMuPDF 均乱码 → 用 iFinD 检索片段 + CNINFO URL；OCR 列为 P1。
4. 文档同一天披露时按 id 排序导致异常波动公告排到投资公告前面 → 增加 `sort_order` 并重新 seed。
5. 已明确不采用“文章级打标签 + 向量相似度直接合并”：它无法区分一篇文章里的事实/观点/传闻，也容易把同一交易的不同阶段误合并。

## 优化

- P1：有引用的问答、自定义告警、邮件/企微 webhook、实体关系图、研报观点聚合。
- 规模上来后：词法检索迁移到 Meilisearch/Elasticsearch；任务队列迁移到 Redis/Celery；多用户 RBAC。
- 评测：扩大标注集到 100+ 事件；对证据权重做校准（目前是可解释启发式，不是概率）。
- 免费部署：只保留一个 Render Web Service；定时抓取默认关闭，演示用管理员按钮；若 Render 额度收紧，切换 Koyeb Free/Hugging Face Spaces 或静态快照。
- 表现形式已确认：事件串（BBS 结构）作为事件详情默认叙事层，顶部固定结论卡；保留论坛阅读节奏，去掉 UGC/热度/论坛皮肤。
- 生产化：SQLite → Postgres adapter；预计算 → 实时 connector + 队列；规则合并 → LLM 同一性裁决 + 人工审核；PDF OCR。
