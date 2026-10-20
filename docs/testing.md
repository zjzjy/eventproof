# 测试说明

> 测试时间：2026-10-20 ｜ 环境：Windows 11 / Python 3.12.7 / Node 22 / SQLite

## 1. 自动化测试

```powershell
cd apps\api
$env:PYTHONPATH="D:\Code\投资跟踪\apps\api"
..\..\.venv\Scripts\python.exe -m pytest tests -q
```

结果：**32 passed**（15 个 API 测试 + 11 个事件引擎测试 + 6 个异常处理测试）。

| 用例 | 断言 |
| --- | --- |
| 健康检查 | `/health`、`/api/health` 均 200 |
| 事件列表/详情 | 1 个事件，4 份文档，17 条 claim，v4 |
| as-of 08-06 | v1，8 条 claim，0 条 denied |
| as-of 08-07 17:57 | v2，10 条 claim，2 条 unverified，narrative=unverified |
| as-of 08-07 18:01 | v3，2 条 denied，narrative=denied |
| v2→v3 diff | 新增 4 条，状态变化 2 条，reason 含 denied |
| 证据包 | 含 CNINFO URL、原文引用、免责声明、模型名 |
| 通知已读/重置 | unread 3→2→3；无 admin token 重置返回 401 |
| 非法 as-of | 返回 422，不产生 500 |

事件引擎测试（`apps/api/tests/test_engine.py`）：

| 用例 | 断言 |
| --- | --- |
| 显式引用合并 | 文档引用事件 → merge，score ≥ 0.9 |
| 同主体不同标的 | decision=link，relation=related |
| 新阶段 | 生成 linked Event，原 Event claims 不变，P1 |
| 子 claim 否认 | 传闻 denied，核心仍 confirmed，P0 |
| 核心否认 | 核心状态 denied，P0 |
| 官方冲突 | 两个 A 级来源同槽位不同值，core=disputed，P0 |
| 更正 | 旧 claim superseded，新 claim active，P0 |
| 过期 | 必须显式截止日；无截止日 noop；到期后 expired，P1 |
| 空 claims | duplicate，不生成 revision |
| 类型推断 | denial/correction/new_stage/rumor 正确推断 |

场景 API 测试（`test_api.py`）：

| 用例 | 断言 |
| --- | --- |
| correction | action=updated、v5、P0、旧值 superseded、新值 active、core confirmed |
| core-denial | core_status=denied、P0、title=核心收购被否认 |
| conflict | core_status=disputed、P0、title=官方来源存在冲突 |
| expiry | action=expired、lifecycle=expired、P1、不写成假 |
| new-stage | action=linked_event、revision v1、P1 |
| 未知场景 | 404 |

异常处理测试（`apps/api/tests/test_resilience.py`）：

| 用例 | 断言 |
| --- | --- |
| HTTP 429 | 指数退避后重试，成功则继续 |
| HTTP 超时 | 最多 3 次，耗尽后抛出可识别错误 |
| 坏 HTML / PDF / 挑战页 | 拒收，不进入 claim 抽取 |
| 非法 LLM JSON | 拒收；支持去掉 Markdown JSON 围栏 |
| 单实例限流 | 窗口内超限时拒绝 |

## 2. 手动主链路验收

### 2.1 公网核心页

1. 打开 `https://zjzjy.github.io/eventproof/core-simple.html`。
2. 确认先显示“关注一个标的”，输入 `002792` 并关注。
3. 确认 v1 同时显示 3 亿元、25%、四期交割、不并表，以及观点、推测和 A 级来源理由。
4. 连续点击“同步最新”，确认 v2 传闻 C、v3 官方否认 + P0、v4 市场反应、v5 linked Event。
5. 点击顶部通知数，确认跳到对应变化位置。
6. 打开关注抽屉并输入 `300209`，确认第二个事件独立展示。
7. 点击关键数字后的 CNINFO 链接，确认能够回到公告原文。

对应截图见 `docs/screenshots/01`–`09`。

### 2.2 完整本地工作台

1. 打开 `http://127.0.0.1:8000/`，确认事件串默认展示，第一楼为“对外投资购买股权公告”。
2. 点击“看否认 diff”，确认 v2→v3：新增 4 条主张、2 条传闻从未核实变为已否认、触发文档链接可点。
3. 关闭 diff，点击一条传闻 claim，确认右侧证据抽屉显示 quote、来源层级、披露/进入系统时间、六因子拆解、传闻上限 35、已被官方否认。
4. 点击 v2“08-07 传闻”，确认结论卡变为“传闻待核实”，事件串只显示 3 份文档、10 条 claim，未出现否认 claim。
5. 点击 v3“08-07 否认”，确认结论卡变为“传闻已否认”，2 条传闻状态变为 denied。
6. 打开通知抽屉，确认 P0 官方否认、P1 公告、P1 市场异动；点击“标记已读”，未读数从 3 变 2。
7. 切换到“简报”，确认四类时间、我们知道/不知道、主张表、版本链。
8. 点击“导出证据包”，确认 Markdown 包含每条 claim 的 quote、CNINFO URL、版本、模型与免责声明。
9. 调用 `POST /api/demo/reset`（带 `X-Admin-Token`），确认 unread 恢复为 3。

视觉走查记录见 `notes/ui-review.md`。

## 3. 数据/接口异常

当前切片已覆盖：

- 无有效 claim 时 `precompute.py` 抛错，不生成半成品事件；
- 无效 quote 直接丢弃；
- HTTP 429、超时、连接错误按指数退避重试，超过次数后失败关闭；
- 坏 HTML、二进制 PDF、验证码/挑战页不进入 claim 抽取；
- LLM 非法 JSON 由 `extract_json_object` 拒绝；
- 行情证据缺失时 `impact_status` 保持 `unverified`；
- 无 admin token 重置返回 401；
- 无效 as-of 早于 v1 返回 404；
- 非法 as-of 格式返回 422；
- 通知/事件不存在返回 404。

仍属于生产化边界：

- 当前限流器是单实例内存实现，多实例需要 Redis/网关级限流；
- 失败文档已能拒收，但自动重跑队列尚未实现；
- 429/超时已重试，跨服务熔断器尚未实现。

详细运行记录见 [evidence/exception-cases.md](evidence/exception-cases.md)、[evidence/pytest.txt](evidence/pytest.txt) 和 [evidence/pytest.xml](evidence/pytest.xml)。

## 4. 合规检查

- 页面和 README 均声明“不构成投资建议”；
- 传闻卡片有“已被否认/未核实”标签，未把它写成事实；
- 每条 claim 有原文 quote 和 CNINFO URL；
- 只展示短引用，不全文转载；
- iFinD 内容使用已由用户确认可用于公开 demo 的短引用；
- 证据强度明确写“不是真值概率”；
- 自动化测试断言导出证据包不含“买入”或“卖出”。

## 5. 已知失败

| 问题 | 影响 | 处理 |
| --- | --- | --- |
| CNINFO PDF 中文字体 ToUnicode 异常 | 无法直接解析 PDF 全文 | 用 iFinD 片段 + URL；OCR P1 |
| SQLite 在 Render 免费实例上不持久 | 重启后通知已读状态恢复 | demo 可接受；多用户持久化需 Postgres |
| 当前只有 1 个事件 | 无法评估跨事件合并准确率 | 扩标注集后再报 F1 |
| 具体时分为推断 | as-of 时间不是原始披露精度 | 界面标注“推断”，保留日期级 |

## 6. 复现环境

- Python 3.12.7，`.venv` 内安装 `requirements-dev.txt`；
- Node 22，`apps/web` 内 `npm install` + `npm run build`；
- 后端默认 SQLite `data/eventproof.db`，删除后启动会自动从 precomputed 重建；
- `.env` 只用于重新跑预计算，运行 demo 不需要 key。

## 7. 演示视频验收

生成命令：

```powershell
python -m pip install -r requirements-video.txt
python -m playwright install ffmpeg
python scripts\make_demo_video.py
```

实际结果：

| 检查项 | 结果 |
| --- | --- |
| 文件 | `video/output/eventproof-demo.mp4` |
| SHA-256 | `a2bea508c66501756e9de985c5db65a9b6b0024cc9dcaed797013ec0a58d047c` |
| 时长 | **150.877 秒**，满足 60–180 秒 |
| 画面 | 1440×900，30 fps，H.264 High，yuv420p |
| 音频 | AAC LC，48 kHz stereo；平均 −20.1 dB，峰值 −2.7 dB，无削波 |
| 女声 | Edge TTS `zh-CN-XiaoxiaoNeural`，语速 `+4%` |
| 光标 | 页面内可见黑色圆点，点击有扩散反馈 |
| 画面来源 | Playwright 驱动真实 Chrome 操作，不是静态图拼接 |
| 解码检查 | `ffmpeg -v error -i ... -f null -` 无错误 |
| 字幕 | 硬字幕已烧入画面；另保留 `eventproof-demo.srt` 与 `eventproof-demo.ass` |

关键帧人工走查：

- 0.8 秒：onboarding 已出现，光标圆点在页面内；
- 20 秒：v1 结论、四类时间、事实/观点/推测和 A 级理由同屏；
- 58 秒：v2 传闻与 C 级理由、2000 亿元市场规模解释可见；
- 100 秒：v3 否认、P0 通知和 v4 市场反应已进入演化链；
- 132 秒：关注 300209 后打开行云科技独立事件；
- 150 秒：判断口径与可追溯说明可见。

场景列表、旁白全文、TTS 引擎和逐段时长保存在 `video/manifest.json`。`video/raw/` 与 `video/audio/` 是可重建中间件，不入库；最终 MP4、字幕、旁白配置和清单入库。

## 8. 页面截图证据

运行：

```powershell
python scripts\capture_evidence.py
```

生成 12 张真实 Chrome 截图到 `docs/screenshots/`。完整索引见 [screenshots/README.md](screenshots/README.md)。
生成过程记录在 [evidence/screenshot-run.txt](evidence/screenshot-run.txt)。

| 截图 | 证明内容 |
| --- | --- |
| [01-onboarding.png](screenshots/01-onboarding.png) | 显式关注是链路起点 |
| [03-v1-fact-opinion.png](screenshots/03-v1-fact-opinion.png) | 事实、观点、推测与 A 级来源分开 |
| [04-v2-rumor.png](screenshots/04-v2-rumor.png) | C 级传闻与 2000 亿元口径 |
| [05-v3-denial-p0.png](screenshots/05-v3-denial-p0.png) | 官方否认、叙事状态变化和 P0 |
| [06-v4-market-time.png](screenshots/06-v4-market-time.png) | 四类时间与市场反应 |
| [08-source-traceability.png](screenshots/08-source-traceability.png) | quote 与 CNINFO 原文入口 |
| [10-correction-p0.png](screenshots/10-correction-p0.png) | 更正保留旧值并触发 P0 |
| [11-expiry-not-false.png](screenshots/11-expiry-not-false.png) | 过期不等于事实为假 |
| [12-official-conflict.png](screenshots/12-official-conflict.png) | 官方冲突标 disputed，不自动选边 |
