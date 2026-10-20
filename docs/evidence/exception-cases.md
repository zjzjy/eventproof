# 数据与接口异常用例

> 运行时间：2026-10-20 ｜ 测试结果：32 passed

## 1. 实际覆盖

| 异常 | 预期行为 | 测试 |
| --- | --- | --- |
| HTTP 429 | 指数退避后重试，成功则继续 | `test_429_is_retried_then_succeeds` |
| HTTP 超时 | 最多重试 3 次，耗尽后明确报错 | `test_timeout_is_retried_and_reports_exhaustion` |
| 坏 HTML 页面 | 拒收，不进入 claim 抽取 | `test_bad_html_and_pdf_are_rejected` |
| 二进制 PDF | 拒收并提示需要 OCR/片段；不把乱码当正文 | `test_bad_html_and_pdf_are_rejected` |
| 验证码/挑战页 | 识别并拒收 | `test_bad_html_and_pdf_are_rejected` |
| LLM 非法 JSON | 拒绝进入事件引擎 | `test_invalid_llm_json_is_rejected` |
| Markdown JSON 围栏 | 去除围栏后解析 | `test_llm_json_fence_is_accepted` |
| 单实例限流 | 窗口内超过上限后拒绝 | `test_sliding_window_rate_limiter_blocks_excess_requests` |
| 行情数据缺失 | 保持 `impact_status=unverified` | `test_missing_market_evidence_keeps_impact_unverified` |
| 非法 as-of | 返回 422，不触发服务器 500 | `test_invalid_as_of_returns_422` |
| 未授权重置 | 返回 401 | `test_reset_requires_admin_token_when_configured` |
| 未知场景 | 返回 404 | `test_unknown_scenario_returns_404` |

实现位于 `apps/api/app/resilience.py`，测试位于 `apps/api/tests/test_resilience.py`。

## 2. 合规边界

- 证据包测试检查 CNINFO URL、原文引用、模型名和“不构成投资建议”；
- 继续断言导出中不出现“买入”或“卖出”；
- 传闻必须有状态，不能作为事实展示；
- 证据强度明确不是真值概率；
- 页面只展示短引用并链接原文。

## 3. 复现

```powershell
cd apps\api
$env:PYTHONPATH="D:\Code\投资跟踪\apps\api"
..\..\.venv\Scripts\python.exe -m pytest tests -q
```

机器可读结果：

- `docs/evidence/pytest.txt`
- `docs/evidence/pytest.xml`

## 4. 当前边界

当前限流器是单实例内存实现，GitHub Pages 静态只读演示没有写接口，因此未在公开页面启用。生产多实例应使用 Redis/网关级限流；该部分已在 README 的未做事项中声明。
