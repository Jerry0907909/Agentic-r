# Backend

## Mock 开发

Mock 不需要 MySQL、Neo4j、Ollama、FAISS 或 DashScope API Key。它使用进程内内存存储，重启服务后会话会清空。

```powershell
cd backend
..\.venv\Scripts\python.exe -m mock_api
```

Mock 与真实后端使用同一个 `8000` 端口，不能同时运行。前端无需切换配置：Vite 仍然把 `/api` 代理到 `http://127.0.0.1:8000`。

可用的前端场景：

- 普通文本：正常流式回答、来源和 token 用量
- `[mock:empty]`：无来源的回答
- `[mock:error]`：先输出部分回答，再发送 `err`
- `[mock:slow]`：每个正文分块间隔 500ms，用于测试停止生成

## 真实联调

真实模式需要先完成根 README 中的 MySQL、Neo4j、Ollama、索引和 `backend/.env` 配置。

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn api.chat_api:app --reload --port 8000
```

真实后端启动失败时不会自动切换到 Mock；请明确停止真实服务后再启动 Mock。
