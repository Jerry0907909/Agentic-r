# 前端契约级 Mock 开发规范

## 1. 目标

在未安装 MySQL、Neo4j、Ollama 且没有 DashScope Key 的电脑上，提供可独立启动的本地 Mock API，使 React 前端能够完成页面开发、流式交互、会话管理和错误态验证；切换到真实后端时不修改前端业务代码。

## 2. 架构决策

Mock 使用独立 FastAPI 应用 `mock_api.app:app`，监听与真实后端相同的 `127.0.0.1:8000`。它复用 `api.schemas` 与 `api.errors`，但不得导入 `db`、`agent`、`llm`、`retrieval` 或 `tools`。

开发时运行：

```powershell
cd backend
..\.venv\Scripts\python.exe -m mock_api
```

真实联调时停止 Mock，然后在同一端口运行：

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn api.chat_api:app --reload --port 8000
```

前端始终请求相对路径 `/api/*`，并由 Vite 代理到 `127.0.0.1:8000`。前端不得增加 `isMock`、`mockData` 或基于运行模式的组件分支。

## 3. 必须覆盖的接口

| 方法 | 路径 | Mock 行为 |
| --- | --- | --- |
| POST | `/api/ask` | 模拟医学资料 RAG 流，只输出向量来源 |
| POST | `/api/ask_graph` | 模拟图谱流，只输出图谱来源 |
| GET | `/api/conversations` | 按 `updated_at` 倒序分页 |
| POST | `/api/conversations` | 创建内存会话，返回 201 |
| PATCH | `/api/conversations/{id}` | 重命名；不存在返回 40401 |
| DELETE | `/api/conversations/{id}` | 删除会话及消息；成功返回空 204 |
| GET | `/api/conversations/{id}/messages` | 按创建顺序分页；不存在返回 40401 |
| GET | `/api/health` | 始终返回 200，所有字段值为 `mock` |

## 4. 流式协议

响应类型必须为 `application/x-ndjson; charset=utf-8`，响应头必须包含：

```text
X-Accel-Buffering: no
Cache-Control: no-cache
```

新会话的事件顺序固定为：

```text
sid → c... → s → u
```

已有会话不发送 `sid`。流中错误的顺序为 `c... → err`，发送 `err` 后立即结束，不再发送 `s` 或 `u`。每个事件占一行并以换行符结束，中文不得转成 `\uXXXX`。

## 5. 可重复的测试场景

Mock 根据问题全文选择场景，不扩展真实 API 参数：

| 问题内容 | 行为 |
| --- | --- |
| 普通文本 | 分块返回成功回答、来源和用量 |
| `[mock:error]` | 先返回一段正文，再返回 `err` |
| `[mock:empty]` | 返回无来源的回答和用量，不发送 `s` |
| `[mock:slow]` | 每个正文分块间隔 500ms，用于测试“停止生成” |

除 `[mock:slow]` 外，正文分块间隔为 30ms。模拟回答必须明确包含“Mock”，不得伪装成真实医疗结论。两种模式必须使用不同正文：`rag` 面向用户标识“医疗健康回答”并说明依据来自医学资料，`graph` 明确标识“知识图谱回答”。

## 6. 内存状态规则

- 使用 UUID v4 作为会话 ID，使用单调递增整数作为消息 ID
- 使用带时区 ISO 8601 时间；列表按 `updated_at` 倒序
- 首轮问题自动成为会话标题，去除换行后截取前 20 个字符
- 每轮保存 user 与 assistant 两条消息，并更新 `message_count` 与 `total_tokens`
- 删除会话时同时删除消息
- 状态仅在当前 Mock 进程内存在，重启后清空
- 使用锁保护读写，保证流式写入和普通 CRUD 请求不会产生破坏性竞争

## 7. 契约与合并规则

- `docs/接口文档.md` 是字段和行为的唯一真相源
- Mock 与真实后端共用 `api.schemas`，禁止复制一份独立 Pydantic 模型
- Mock OpenAPI 生成的 `frontend/src/types/api.d.ts` 必须与当前已提交类型无差异
- 接口签名变更必须同时修改真实实现、Mock 实现、接口文档和生成类型
- Mock 不提供降级生产能力，不得部署到生产，也不得在真实后端异常时自动接管

## 8. 验收标准

1. 未启动 MySQL、Neo4j、Ollama 时，Mock API 能在 8000 端口启动。
2. 八个接口的成功状态码、错误信封和响应模型与接口文档一致。
3. `/api/ask` 与 `/api/ask_graph` 能被现有 `stream.ts` 逐行消费。
4. 会话创建、首轮自动命名、续聊、重命名、删除和历史回看形成闭环。
5. `[mock:error]`、`[mock:empty]`、`[mock:slow]` 可以复现前端错误、空来源和中止场景。
6. 后端单元测试、前端 lint、前端 build 全部通过。
7. 停止 Mock 并启动遵守同一契约的真实后端后，前端不需要代码改动。
