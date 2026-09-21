# 温暖健康视觉改造 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有双模式医疗问答框架改造成面向普通用户的“温暖健康”ToC 界面，同时保持全部对话行为和接口契约不变。

**Architecture:** 保留 `App` 的状态与数据流，以 Tailwind 语义令牌统一浅色/深色主题；分别重塑顶栏模式入口、空状态、会话侧栏、消息与输入区。所有改动限定在文档和现有前端组件内，不增加依赖、不修改后端。

**Tech Stack:** React 19、TypeScript、Tailwind CSS 3、Lucide React、Vite

**Spec:** `docs/前端设计规范.md`

## Global Constraints

- 两个模式必须并列且同等级，继续映射 `/api/ask` 与 `/api/ask_graph`。
- 不增加登录，不修改后端、`.env`、数据库、接口类型和 Mock 契约。
- 主色为深鼠尾草绿，背景为暖米白，暖橙只作点睛；Mock 紫色只用于环境状态。
- 控件触控目标至少 44×44px，焦点可见，支持 `prefers-reduced-motion`。
- 适配 375px、768px、1024px、1440px，并保留浅色与深色主题。

---

### Task 1: 建立温暖健康主题令牌

**Files:**
- Modify: `frontend/src/index.css`
- Modify: `frontend/tailwind.config.ts`

**Interfaces:**
- Consumes: 现有 `background`、`card`、`primary`、`graph`、`document` 等 Tailwind 语义色名。
- Produces: 新增 `surface`、`accent`、`accent-foreground` 令牌及统一的柔和阴影、交互动效。

- [x] **Step 1: 替换浅色与深色 CSS 变量**

  将浅色主题映射为米白背景、白色卡片、墨绿文字、鼠尾草绿主色和暖橙强调色；为深色主题提供独立降饱和映射。

- [x] **Step 2: 扩展 Tailwind 语义令牌**

  在 `tailwind.config.ts` 注册 `surface`、`accent`、`accent-foreground`，并将阴影拆分为 `soft` 与 `lifted` 两级。

- [x] **Step 3: 验证样式配置可编译**

  Run: `cd frontend; npm run build`

  Expected: TypeScript 与 Vite 构建成功，无未知 Tailwind 配置错误。

### Task 2: 重塑品牌区与双模式入口

**Files:**
- Modify: `frontend/src/components/Header.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `activeTab`、`busy`、`healthState` 与既有回调。
- Produces: “医知助手”用户品牌和两个同尺寸、含图标与说明的模式卡片。

- [x] **Step 1: 改造 Header 结构**

  使用 `HeartPulse`、`Sparkles`、`Network` 等 Lucide 图标构成用户化品牌与模式入口；保留主题、服务状态、移动端侧栏控制。

- [x] **Step 2: 降低技术元数据权重**

  会话标题栏只显示标题、消息数与模式，不在页面主层级展示 Token 数。

- [x] **Step 3: 检查键盘和禁用态**

  两个模式使用原生 `button` 与 `aria-pressed`；流式期间另一模式维持语义禁用。

### Task 3: 重塑空状态和输入区

**Files:**
- Modify: `frontend/src/components/EmptyState.tsx`
- Modify: `frontend/src/components/Composer.tsx`

**Interfaces:**
- Consumes: 当前 `mode`、示例提问回调、语音识别与发送回调。
- Produces: 面向任务的欢迎区、暖色点睛示例卡和悬浮式提问面板。

- [x] **Step 1: 更新空状态文案和层级**

  综合问答使用“今天想了解什么健康问题？”，图谱查询使用“想查清哪种医疗关系？”；每张示例卡保留完整可点击区域和明确箭头。

- [x] **Step 2: 改造输入区表面**

  将整条后台式底栏改为有最大宽度的浮动输入卡，保留模式提示、语音、发送、停止、字数和快捷键说明。

- [x] **Step 3: 验证移动端输入可用性**

  textarea 移动端字号保持 16px，所有图标按钮点击区域不小于 44×44px。

### Task 4: 统一会话、消息与来源视觉

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx`
- Modify: `frontend/src/components/MessageBubble.tsx`
- Modify: `frontend/src/components/SourceCard.tsx`
- Modify: `frontend/src/components/UsageBadge.tsx`
- Modify: `frontend/src/components/Toast.tsx`
- Modify: `frontend/src/components/ui/button.tsx`

**Interfaces:**
- Consumes: 现有会话、消息、来源、用量和提示数据结构。
- Produces: 低后台感历史列表、清晰的用户/助手层级、保留图标和文字双重区分的来源卡。

- [x] **Step 1: 调整侧栏层级**

  使用暖色表面和轻边框，保持日期分组、模式标签、重命名和删除行为不变。

- [x] **Step 2: 调整消息与来源卡**

  用户消息使用主色气泡，助手使用白色阅读卡；来源折叠卡分别使用图谱青绿和资料灰蓝。

- [x] **Step 3: 统一按钮和 Toast 状态**

  所有控件使用一致圆角、焦点环和语义色，关闭按钮提供至少 44×44px 点击区域。

### Task 5: 完整验证

**Files:**
- Verify only

**Interfaces:**
- Consumes: 全部前端改造结果与现有 Mock 服务。
- Produces: 可编译、可访问、响应式且不改变接口的最终版本。

- [x] **Step 1: 运行后端回归测试**

  Run: `cd backend; ..\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v`

  Expected: 13 项测试全部通过。

- [x] **Step 2: 运行前端静态检查和构建**

  Run: `cd frontend; npm run lint; npm run build`

  Expected: lint 与 build 均成功；仅允许既有 bundle size 警告。

- [x] **Step 3: 检查差异格式**

  Run: `git diff --check`

  Expected: 无尾随空格或冲突标记。

- [x] **Step 4: 进行响应式视觉检查**

  在 375px、768px、1024px、1440px 下检查浅色、深色、双模式、侧栏、输入焦点与 Mock 状态；确认无水平溢出和遮挡。
