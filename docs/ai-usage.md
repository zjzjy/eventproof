# AI 使用与验证记录

> 模型：阿里云百炼 `qwen3.8-flash` ｜ Prompt：`claim_extract_v1` ｜ 日期：2026-10-20

## 1. 角色边界

AI 只做语义抽取和分类：

- 从公告片段中抽取原子 claim；
- 区分 fact / opinion / speculation / rumor / denial / correction；
- 返回 subject / predicate / object / value / unit / quote；
- 不决定“这是真的”；证据评分、状态迁移、通知规则由确定性代码执行；
- 不生成没有原文出处的数字、主体或时间。

## 2. 调用记录

4 份文档各调用一次，`temperature=0`，`enable_thinking=false`，`response_format=json_object`。

| 文档 | Prompt tokens | Completion tokens | 估算成本 |
| --- | ---: | ---: | ---: |
| 对外投资公告 | 435 | 1,079 | ¥0.002593 |
| 08-05 异常波动公告 | 368 | 342 | ¥0.001052 |
| 08-07 澄清公告 | 423 | 832 | ¥0.002087 |
| 08-08 异常波动公告 | 407 | 517 | ¥0.001441 |
| **合计** | **1,633** | **2,770** | **¥0.007173** |

成本按保守单价估算（输入 ¥1/百万 token、输出 ¥2/百万 token），实际以百炼账单为准。预算硬停 8 元，当前远低于上限。

原始输出保存在 `fixtures/tongyu/precomputed.json` 的 `llm_calls` 字段，包含 `input_hash`、`prompt_version`、tokens、cost 和每份文档的 claims。

## 3. 校验规则

1. 输出必须是合法 JSON；否则该次调用失败。
2. `claim_type` 必须属于六类；中文类型映射到英文枚举。
3. `quote` 必须能在文档片段归一化后找到连续子串；找不到就丢弃。
4. `text` 少于 4 个字符时用 quote 兜底；没有 quote 的 claim 不进入事件。
5. 数字/比例/日期必须来自 quote；本切片人工抽检了 3 亿元、25%、18,152,657 股、10,891,594 股、15%、20% 等关键数字。
6. 同一份文档先抽 claim，再由确定性代码做去重、角色分配和评分。

## 4. 人工复核与裁剪

LLM 首轮输出 22 条 claim，包含重复的传闻和过细的交易条款。人工复核后保留 15 条 LLM claims，并从官方公告人工补入 2 条管理层观点/预测，最终 17 条：

- 保留交易金额、25% 比例、股数、第一期 15%、分四期、不并表等关键槽位；
- 删除 08-08 异常波动公告中重复引用的 3 条传闻；
- 删除澄清公告中“拟入股 25%”的 rumor claim，因为 25% 比例已被官方公告确认，不是假传闻；
- 在最终摘要中明确写出“传闻中 25% 入股比例与公告一致”，避免把整条传闻一刀切为假。

这不是“AI 自动完成”的伪装：原始 LLM 输出、裁剪规则、人工补入的 2 条官方观点/预测，以及最终 17 条 claim 都可从 `precomputed.json` 追溯。

## 5. 关键样例

输入片段：

> 公司拟以自有资金人民币30,000.00万元，通过股份受让方式购买深圳市佳贤通信科技股份有限公司合计约25.00%的股权……

模型输出（节选）：

```json
{
  "text": "公司拟以自有资金人民币30,000.00万元购买股权",
  "claim_type": "fact",
  "subject": "通宇通讯",
  "predicate": "拟购买",
  "object": "佳贤通信股权",
  "value": 30000,
  "unit": "万元",
  "quote": "公司拟以自有资金人民币30,000.00万元"
}
```

输入片段：

> 公司关注到部分网络媒体上流传“佳贤通信与英伟达合作开发6G AI-RAN基站……”

模型输出（节选）：

```json
{
  "text": "网络媒体流传佳贤通信与英伟达合作开发6G AI-RAN基站",
  "claim_type": "rumor",
  "quote": "部分网络媒体上流传“佳贤通信与英伟达合作开发6G AI-RAN基站”"
}
```

## 6. 失败模式与处理

| 失败 | 现象 | 处理 |
| --- | --- | --- |
| 输出过细 | 一份公告抽出 10 条，包含“交易方式为股份受让”等低信息 claim | 人工裁剪关键槽位 |
| 重复传闻 | 08-08 公告再次引用同一传闻，模型重复输出 | 去重 + 人工删除 |
| 类型误判 | “拟入股 25%”在传闻段被标成 rumor | 人工改为已确认事实，并在摘要说明 |
| PDF 乱码 | CNINFO PDF 字体 ToUnicode 异常 | 不用 PDF 文本，改用 iFinD 片段 + PDF URL；OCR P1 |
| 预算风险 | 模型可能输出长 reasoning | `enable_thinking=false` + max_tokens + 成本记录 |

## 7. 没有做什么

- 没有训练/微调模型；
- 没有用 LLM 做最终真值裁决；
- 没有做 LLM 同一性裁决（当前是显式引用 + 槽位匹配）；
- 没有做正式 claim 分类 F1 / 合并 F1 标注集；
- 没有把模型调用放在部署运行时（当前全部预计算）。

## 8. 复现

```powershell
# .env 需要 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL_FAST
python scripts\precompute.py
python scripts\merge_source_meta.py
```

`.env` 已被 `.gitignore` 忽略，key 不入库。当前仓库的 `precomputed.json` 是已生成的产物，评审不需要 key 也能运行 demo。

## 9. 演示视频中的 AI 与其他自动化

演示视频不是人工口播，也不使用生成式模型编造页面内容：

- 画面来自真实 `core-simple.html` 的 Playwright 自动操作，包含首次关注、四次“同步最新”、通知、第二事件和来源核对；
- 光标圆点由页面初始化脚本注入，所有点击都通过 Playwright 鼠标事件产生；
- 女声由 Edge TTS `zh-CN-XiaoxiaoNeural` 生成，语速 `+4%`；若网络失败，脚本回退到本机 `Microsoft Huihui` 女声；
- 生成式百炼模型只用于此前的公告 claim 抽取，不参与视频画面、结论或数字生成；
- 字幕逐段对应当前旁白文本，场景与时长记录在 `video/manifest.json`，可按 `input_hash`、prompt 版本、claim quote 和 CNINFO URL 回查；
- Edge TTS 不产生百炼 token 费用；视频生成脚本不读取 `.env`，也不调用付费 LLM。

复现：

```powershell
python -m pip install -r requirements-video.txt
python -m playwright install ffmpeg
python scripts\make_demo_video.py
```

验证结果：9 段旁白、`zh-CN-XiaoxiaoNeural`、成片 156.7 秒、1440×900、30 fps、H.264/AAC；字幕 `video/output/eventproof-demo.srt`。
