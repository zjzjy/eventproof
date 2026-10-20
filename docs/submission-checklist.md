# 提交材料清单

## 1. 入口

| 交付项 | 地址 |
| --- | --- |
| 可操作 Web 产品 | https://zjzjy.github.io/eventproof/core-simple.html |
| 源代码仓库 | https://github.com/zjzjy/eventproof |
| README | `README.md` |
| 核心链路说明 | `README-core.md` |
| 演示视频 | `video/output/eventproof-demo.mp4` |

## 2. 逐项对应

| 题目要求 | 产品/材料证据 |
| --- | --- |
| “同一事件”识别、合并与版本演化 | `apps/api/app/engine.py`；页面 v1–v5；`test_explicit_reference_merges`、`test_new_stage_links_follow_up` |
| 事实、观点、推测、传闻及权重 | `precomputed.json` 的 17 条 claim；A/B/C/D 来源等级；证据权重公式 |
| 发生、披露、抓取、更新时间 | `README.md` 7.3；核心页四类时间；视频中同一屏展示 |
| 更新如何改变结论 | v1 → v2 新增传闻，保留旧版本并生成新 revision |
| 否认如何改变结论 | 官方澄清后叙事状态 `denied`，核心收购仍 `confirmed`，P0 |
| 更正如何改变结论 | 旧值 `superseded`、新值 `active`、P0；`10-correction-p0.png` |
| 过期如何改变结论 | 明确截止日到期后 `expired`，不写成“假”，P1；`11-expiry-not-false.png` |
| 通知用户 | P0/P1 通知记录、原因、revision 和去重键；页面通知数量与变化条款 |
| 证据冲突 | 两份 A 级来源数值冲突时 `disputed`、P0，不自动选边；`12-official-conflict.png` |
| 与关注标的关系 | 显式关注 `002792` 后自动进入事件抽屉；`300209` 为独立事件，不误合并 |
| 关键数字可追溯 | `docs/evidence-traceability.md`、`fixtures/tongyu/sources.json`、页面 CNINFO 链接 |

## 3. README 必需内容

| 必需章节 | 位置 |
| --- | --- |
| 目标用户 | `README.md` 第 1 节 |
| 核心设计 | `README.md` 第 2、7 节 |
| AI 角色 | `README.md` 第 6.2 节、`docs/ai-usage.md` |
| 数据使用 | `README.md` 第 6.1 节、`fixtures/tongyu/` |
| 已知边界 | `README.md` 第 11 节 |
| 未做事项 | `README.md` 第 11 节 |

## 4. 验证材料

| 材料 | 位置 | 结果 |
| --- | --- | --- |
| 60–180 秒视频 | `video/output/eventproof-demo.mp4` | 150.877 秒，女声、硬字幕、光标圆点 |
| AI 使用与验证 | `docs/ai-usage.md` | 4 次百炼调用，1,633 + 2,770 tokens，估算 ¥0.0072 |
| 自动化测试 | `docs/testing.md` | 32 passed |
| 测试运行记录 | `docs/evidence/pytest.txt`、`pytest.xml` | 可复现的文本/XML 结果 |
| 数据/接口异常 | `docs/evidence/exception-cases.md` | 429、超时、坏 HTML/PDF、非法 JSON、缺失行情、as-of、限流 |
| 合规边界 | `docs/testing.md` 第 4 节、证据包测试 | 免责声明、短引用、无买卖建议 |
| UI 截图 | `docs/screenshots/` | 12 张真实页面截图与总览图 |

## 5. 复现

```powershell
# 后端测试
cd apps\api
$env:PYTHONPATH="D:\Code\投资跟踪\apps\api"
..\..\.venv\Scripts\python.exe -m pytest tests -q

# 证据截图
cd D:\Code\投资跟踪
python scripts\capture_evidence.py

# 演示视频
python -m pip install -r requirements-video.txt
python -m playwright install ffmpeg
python scripts\make_demo_video.py
```
