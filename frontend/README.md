# Agentic RAG 前端

基于 Vite、React 19、TypeScript、Tailwind CSS 和 shadcn/ui 风格基础组件构建。

## 本地运行

```bash
npm install
npm run dev
```

开发服务器默认运行在 `http://127.0.0.1:5173`，并将 `/api` 代理到 `http://127.0.0.1:8000`。

## 常用命令

```bash
npm run dev        # 开发服务器
npm run build      # TypeScript 检查 + 生产构建
npm run lint       # ESLint
npm run api:types  # 从运行中的 FastAPI 更新接口类型
```

## 已实现

- Agentic RAG / 医疗疾病问答双模式隔离
- NDJSON 流式回答，正确处理 UTF-8 分块和半行缓冲
- 会话列表、历史消息、重命名与删除
- Neo4j 图谱 / 向量文档来源卡片
- 云端模型 token 与耗时展示
- 浏览器语音输入与不支持提示
- 中止生成、错误保留、自动滚底
- 深浅主题、桌面/移动端响应式布局
- 医疗内容免责声明

后端接口契约以 `../docs/接口文档.md` 为准。
