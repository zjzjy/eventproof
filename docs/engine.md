# 事件引擎设计

> 实现位置：`apps/api/app/engine.py`。纯函数，不依赖数据库和网络，方便先验证规则再接 ingestion。

## 1. 匹配

`match_event(document, events)` 按以下顺序判断：

1. 文档显式引用事件（`refs` / `source_doc_ids`）→ 同一事件。
2. 显式引用且文档带阶段（sign / close / terminate / approve）→ 同一 Storyline 的 `follow_up`，不合并。
3. 主体、动作、标的槽位一致 → 候选合并。
4. 主体相同但关键槽位冲突 → `review`，不自动合并。
5. 主体相同、标的/对象不同 → `related`，不合并。
6. 没有命中 → 新事件。

返回 `decision`、`relation`、`score`、`shared_slots`、`differences`、`reason`，可写入审计。

## 2. 变更类型

- `update`：新增事实/证据，追加 claim 和版本。
- `rumor`：新增传闻，claim 状态 `unverified`，默认 P2。
- `denial`：官方否认；目标 claim 标 `denied`，保留原文；P0。
- `correction`：关键数字更正；旧 claim 标 `superseded`，新 claim 生效；P0。
- `new_stage`：签署/交割/终止等下一阶段；新建 linked Event，不合并原 Event；P1。
- `expiry`：有明确截止日且到期未完成；标 `expired`，不写成“假”；P1。

## 3. 核心与叙事分开

`derive_status` 分开计算：

- `core`：收购本身是否确认/否认。
- `narrative`：传闻是未核实/已否认/无。
- `impact`：市场反应是否观察到。

所以“否认英伟达合作”不会把整个收购事件标成 denied；只有否认核心收购命题才会。

## 4. 通知

- P0：官方否认、关键更正、核心反转。
- P1：新事实、新阶段、过期、完成/终止。
- P2：新增传闻、重复报道。

通知带 `why`、`diff_json`、`revision_id`，可按事件 + change hash 去重。

## 5. 已写测试

`apps/api/tests/test_engine.py` 覆盖：

- 显式引用合并；
- 同主体不同标的只关联；
- 新阶段 linked Event；
- 子 claim 否认不改变核心状态；
- 核心否认改变核心状态；
- 更正保留旧值并生成新 claim；
- 过期必须显式截止日；
- 无 claims 的重复文档不生成版本；
- 变更类型推断。

当前测试已实际运行：**24 passed**（14 API + 10 engine）。执行命令：

```powershell
cd apps\api
$env:PYTHONPATH="D:\Code\投资跟踪\apps\api"
..\..\.venv\Scripts\python.exe -m pytest tests -q
```

## 6. 接入 API

`POST /api/engine/apply` 接收 `{event, document, now}`；`POST /api/engine/expire` 接收 `{event, deadline, now}`。场景页使用 `GET /api/events/{id}/scenario/{name}`，由后端组装基准事件和模拟文档后调用引擎；四个场景页已验证由引擎返回版本和通知。
