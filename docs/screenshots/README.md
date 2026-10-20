# 核心页面证据截图

> 生成时间：2026-10-20 ｜ 页面：`apps/web/dist/core-simple.html` ｜ 视口：1440×1000

全部截图由 [capture_evidence.py](../../scripts/capture_evidence.py) 驱动真实 Chrome 生成，可在仓库根目录复现：

```powershell
python scripts\capture_evidence.py
```

最近一次运行记录：[evidence/screenshot-run.txt](../evidence/screenshot-run.txt)。

## 主链路

| 截图 | 证明内容 |
| --- | --- |
| [01-onboarding.png](01-onboarding.png) | 首次进入只要求显式关注标的，不根据点击猜测关注关系 |
| [02-follow-processing.png](02-follow-processing.png) | 关注 `002792` 后进入抓取、claim 抽取和事件归并 |
| [03-v1-fact-opinion.png](03-v1-fact-opinion.png) | 3 亿元、25%、四期交割、不并表；A 级来源下的观点与预测仍单独标识 |
| [04-v2-rumor.png](04-v2-rumor.png) | 2000 亿元被明确限定为传闻中的市场规模；无原文和独立来源时标 C |
| [05-v3-denial-p0.png](05-v3-denial-p0.png) | 官方否认只改叙事状态，不改核心收购状态，并生成 P0 通知 |
| [06-v4-market-time.png](06-v4-market-time.png) | 事情发生、首次披露、系统抓取、最近更新四类时间分开显示 |
| [07-v5-new-stage.png](07-v5-new-stage.png) | 09-22 签署协议作为同一 Storyline 的新 Event，不改写原 Event |
| [08-source-traceability.png](08-source-traceability.png) | 关键数字保留原文 quote 与 CNINFO 原文入口 |
| [09-second-event.png](09-second-event.png) | 关注 `300209` 后出现独立事件，不与通宇事件误合并 |

## 状态变化边界

以下场景使用页面内嵌 scenario 渲染器与同一确定性规则生成。场景数据仅用于验证更正、过期和冲突逻辑。

| 截图 | 证明内容 |
| --- | --- |
| [10-correction-p0.png](10-correction-p0.png) | 对价由 3 亿元更正为 2.8 亿元；旧值保留为 `superseded`，新值生效，P0 |
| [11-expiry-not-false.png](11-expiry-not-false.png) | 明确截止日到期但无完成公告时标为过期，不把交易写成“假” |
| [12-official-conflict.png](12-official-conflict.png) | 两个 A 级来源同槽位数值冲突时标 `disputed`，不自动选边 |

[contact-sheet.png](contact-sheet.png) 是 12 张截图的缩略总览。
