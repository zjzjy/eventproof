# 测试说明

> 测试时间：2026-10-20 ｜ 环境：Windows 11 / Python 3.12.7 / Node 22 / SQLite

## 1. 自动化测试

```powershell
cd apps\api
$env:PYTHONPATH="D:\Code\投资跟踪\apps\api"
..\..\.venv\Scripts\python.exe -m pytest tests -q
```

结果：**24 passed**（14 个 API 测试 + 10 个事件引擎测试）。

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

## 2. 手动主链路验收

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
- 无 admin token 重置返回 401；
- 无效 as-of 早于 v1 返回 404；
- 通知/事件不存在返回 404。

尚未实现、列为下一步：

- 429 / 超时 / 重试 / 熔断；
- 坏 HTML/PDF 隔离与重跑；
- LLM 非法 JSON 的修复重试；
- 两个官方来源冲突的 disputed 状态；
- 行情数据缺失时的 impact=unverified 路径（当前只展示公告披露的异动事实）；
- 公开 demo 的写操作限流。

## 4. 合规检查

- 页面和 README 均声明“不构成投资建议”；
- 传闻卡片有“已被否认/未核实”标签，未把它写成事实；
- 每条 claim 有原文 quote 和 CNINFO URL；
- 只展示短引用，不全文转载；
- iFinD 内容使用已由用户确认可用于公开 demo 的短引用；
- 证据强度明确写“不是真值概率”。

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
| SHA-256 | `f721c71539d741c4a9a2945c7fabdf0b4cb3802103c629460d16d910196b5c0d` |
| 时长 | **151.621 秒**，满足 60–180 秒 |
| 画面 | 1440×900，30 fps，H.264 High，yuv420p |
| 音频 | AAC LC，48 kHz stereo；平均 −20.1 dB，峰值 −2.7 dB，无削波 |
| 女声 | Edge TTS `zh-CN-XiaoxiaoNeural`，语速 `+4%` |
| 光标 | 页面内可见黑色圆点，点击有扩散反馈 |
| 画面来源 | Playwright 驱动真实 Chrome 操作，不是静态图拼接 |
| 解码检查 | `ffmpeg -v error -i ... -f null -` 无错误 |
| 字幕 | `video/output/eventproof-demo.srt` |

关键帧人工走查：

- 0.8 秒：onboarding 已出现，光标圆点在页面内；
- 20 秒：v1 结论、四类时间、事实/观点/推测和 A 级理由同屏；
- 58 秒：v2 传闻与 C 级理由、2000 亿元市场规模解释可见；
- 100 秒：v3 否认、P0 通知和 v4 市场反应已进入演化链；
- 132 秒：关注 300209 后打开行云科技独立事件；
- 150 秒：判断口径与可追溯说明可见。

场景列表、旁白全文、TTS 引擎和逐段时长保存在 `video/manifest.json`。`video/raw/` 与 `video/audio/` 是可重建中间件，不入库；最终 MP4、字幕、旁白配置和清单入库。
