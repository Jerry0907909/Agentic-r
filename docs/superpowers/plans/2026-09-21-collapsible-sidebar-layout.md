# Collapsible Sidebar Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将桌面会话侧栏从 304px 收窄为 264px，并提供可持久化的 72px 折叠图标栏，让顶栏品牌列和主内容随宽度同步重排。

**Architecture:** `App` 持有唯一的桌面折叠状态并写入 `localStorage`；`Header` 消费状态并在品牌 Logo 同一行提供开合控制；`Sidebar` 根据同一状态渲染完整列表或图标栏，不再放置开合按钮。移动端抽屉始终使用完整 264px 内容，不复用桌面折叠视觉，避免两套交互互相污染。

**Tech Stack:** React 19、TypeScript 5.7、Tailwind CSS 3.4、Lucide React、现有 Tooltip/Button 组件

**Spec:** `docs/前端设计规范.md`

## Global Constraints

- 不增加依赖，不修改后端、API、`.env`、数据库或 Mock 契约。
- 桌面展开宽度固定为 264px，折叠宽度固定为 72px；移动端抽屉宽度固定为 264px、最大 88vw。
- 折叠状态键名固定为 `agentic-rag-sidebar-collapsed`，字符串 `true` 表示折叠。
- 所有图标按钮保持至少 44×44px、具有可访问名称与可见焦点态。
- 侧栏与顶栏品牌列必须使用同一个折叠状态，主内容依靠 `minmax(0, 1fr)` / `flex-1` 自动扩展。

---

### Task 1: 建立桌面折叠状态与持久化

**Files:**
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Produces: `sidebarCollapsed: boolean`、`setSidebarCollapsed`，传给 `Header` 和 `Sidebar`。
- Persists: `localStorage['agentic-rag-sidebar-collapsed']`。

- [ ] **Step 1: 在 App 中惰性初始化折叠状态**

```tsx
const [sidebarCollapsed, setSidebarCollapsed] = useState(
  () => localStorage.getItem('agentic-rag-sidebar-collapsed') === 'true',
)
```

- [ ] **Step 2: 持久化桌面折叠状态**

```tsx
useEffect(() => {
  localStorage.setItem('agentic-rag-sidebar-collapsed', String(sidebarCollapsed))
}, [sidebarCollapsed])
```

- [ ] **Step 3: 把同一状态传给 Header 和 Sidebar**

```tsx
<Header sidebarCollapsed={sidebarCollapsed} />
<Sidebar
  collapsed={sidebarCollapsed}
/>
```

`Header` 同时接收 `onToggleSidebar={() => setSidebarCollapsed((value) => !value)}`。

- [ ] **Step 4: 运行前端静态检查**

Run: `cd frontend; npm run lint`

Expected: PASS，无未使用状态或缺失 Props。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: persist desktop sidebar state"
```

### Task 2: 让顶栏品牌列跟随侧栏宽度

**Files:**
- Modify: `frontend/src/components/Header.tsx`

**Interfaces:**
- Consumes: `sidebarCollapsed: boolean`。
- Produces: 桌面 `264px / 72px` 品牌列；移动端结构保持原样。

- [ ] **Step 1: 扩展 HeaderProps**

```tsx
type HeaderProps = {
  activeTab: AgentType
  busy: boolean
  dark: boolean
  sidebarCollapsed: boolean
  onToggleSidebar: () => void
  onOpenSidebar: () => void
  onTabChange: (tab: AgentType) => void
  onToggleTheme: () => void
}
```

- [ ] **Step 2: 动态设置桌面网格列宽**

```tsx
<div
  className={cn(
    'flex flex-wrap items-center gap-2.5 sm:flex-nowrap md:grid md:gap-0 md:transition-[grid-template-columns] md:duration-200 motion-reduce:transition-none',
    sidebarCollapsed
      ? 'md:grid-cols-[72px_minmax(0,1fr)]'
      : 'md:grid-cols-[264px_minmax(0,1fr)]',
  )}
>
```

- [ ] **Step 3: 在品牌行放置侧栏开合按钮**

```tsx
<div className={cn(
  'relative flex min-h-12 min-w-0 items-center gap-2.5 md:h-full md:border-r md:border-border/80 md:px-4 md:py-3',
  sidebarCollapsed && 'md:justify-start md:pl-2 md:pr-0',
)}>
  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-accent/14 text-accent ring-1 ring-primary/50">
    <HeartPulse aria-hidden="true" className="h-5 w-5" />
  </span>
  <div className={cn('hidden min-w-0 sm:block', sidebarCollapsed && 'md:hidden')}>
    <div className="truncate text-[15px] font-bold tracking-tight">医知助手</div>
    <div className="truncate text-[11px] text-muted-foreground">可信医疗知识问答</div>
  </div>
  <Button
    className="absolute -right-[22px] z-20 hidden h-11 w-11 rounded-full border border-primary/25 bg-card text-primary shadow-soft md:inline-flex"
    variant="ghost"
    size="icon"
    onClick={onToggleSidebar}
    aria-label={sidebarCollapsed ? '展开会话列表' : '折叠会话列表'}
  >
    {sidebarCollapsed ? <PanelLeftOpen aria-hidden="true" /> : <PanelLeftClose aria-hidden="true" />}
  </Button>
</div>
```

右侧主导航使用 `md:pl-8` 预留按钮空间，确保 768px 下按钮与模式入口不重叠。

- [ ] **Step 4: 运行类型与构建检查**

Run: `cd frontend; npm run build`

Expected: PASS；HeaderProps 与 App 调用一致。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Header.tsx
git commit -m "feat: reflow header with sidebar"
```

### Task 3: 实现 264px 展开态与 72px 图标栏

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx`

**Interfaces:**
- Consumes: `collapsed: boolean`、`onToggleCollapsed: () => void`。
- Preserves: `onNew`、`onSelect`、`onRename`、`onDelete` 现有行为。
- Produces: 桌面展开/折叠双视图；移动端完整抽屉。

- [ ] **Step 1: 增加折叠 Props 和图标导入**

```tsx
import { MessageSquareText, Network, Pencil, Plus, Stethoscope, Trash2, X } from 'lucide-react'

type SidebarProps = {
  conversations: Conversation[]
  selectedId: string | null
  open: boolean
  loading: boolean
  collapsed: boolean
  onClose: () => void
  onNew: () => void
  onSelect: (conversation: Conversation) => void
  onRename: (conversation: Conversation) => void
  onDelete: (conversation: Conversation) => void
}
```

- [ ] **Step 2: 定义折叠态历史顺序**

```tsx
const compactConversations = [...conversations].sort((left, right) => {
  if (left.agent_type !== right.agent_type) return left.agent_type === 'rag' ? -1 : 1
  return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime()
})
```

展开态继续使用 264px 完整会话内容；折叠态使用 72px 图标内容，并只遍历 `compactConversations`。

- [ ] **Step 3: 展开态新建按钮占满内容宽度**

```tsx
<Button className="w-full justify-start shadow-soft" onClick={onNew}>
  <Plus aria-hidden="true" className="h-4 w-4" />
  新建对话
</Button>
```

完整顶部结构固定为：

```tsx
<div className="flex items-center gap-2 p-3 pb-2">
  <Button className="w-full justify-start shadow-soft" onClick={onNew}>
    <Plus aria-hidden="true" className="h-4 w-4" />
    新建对话
  </Button>
  <Button className="md:hidden" variant="ghost" size="icon" onClick={onClose} aria-label="关闭会话列表">
    <X aria-hidden="true" className="h-5 w-5" />
  </Button>
</div>
```

- [ ] **Step 4: 折叠态保留新建与历史选择**

```tsx
<Tooltip content="新建对话">
  <Button className="h-12 w-12 rounded-2xl" size="icon" onClick={onNew} aria-label="新建对话">
    <Plus aria-hidden="true" className="h-4 w-4" />
  </Button>
</Tooltip>
```

折叠历史项先按 `rag` 在前、`graph` 在后排序，同类按 `updated_at` 降序；`ConversationIcon` 在 map 内由 `conversation.agent_type === 'graph' ? Network : Stethoscope` 得到：

```tsx
<Tooltip key={conversation.id} content={conversation.title || '新会话'}>
  <button
    type="button"
    aria-label={`打开会话：${conversation.title || '新会话'}`}
    aria-current={selectedId === conversation.id ? 'page' : undefined}
    className={cn(
      'grid h-11 w-11 place-items-center rounded-xl border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
      selectedId === conversation.id
        ? 'border-primary/25 bg-primary/10 text-primary'
        : 'border-transparent text-muted-foreground hover:border-border hover:bg-card',
    )}
    onClick={() => onSelect(conversation)}
  >
    <ConversationIcon aria-hidden="true" className="h-4 w-4" />
  </button>
</Tooltip>
```

折叠态不渲染日期、轮次、重命名、删除与底部课程说明。

- [ ] **Step 5: 桌面与移动端分别渲染**

```tsx
<div className="hidden h-full md:block">{renderContent(collapsed, false)}</div>
{open && (
  <div className="fixed inset-0 z-40 md:hidden">
    <button
      className="absolute inset-0 bg-slate-950/35 backdrop-blur-sm"
      onClick={onClose}
      aria-label="关闭遮罩"
    />
    <div className="relative h-full w-[264px] max-w-[88vw] shadow-2xl">
      {renderContent(false, true)}
    </div>
  </div>
)}
```

- [ ] **Step 6: 运行 lint 与 build**

Run: `cd frontend; npm run lint; npm run build`

Expected: 两项均 PASS。

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/Sidebar.tsx
git commit -m "feat: add collapsible conversation rail"
```

### Task 4: 响应式与交互验收

**Files:**
- Verify: `frontend/src/App.tsx`
- Verify: `frontend/src/components/Header.tsx`
- Verify: `frontend/src/components/Sidebar.tsx`
- Verify: `docs/前端设计规范.md`

**Interfaces:**
- Verifies: 264px / 72px 布局、状态持久化、移动端抽屉、会话操作、无水平溢出。

- [ ] **Step 1: 验证展开态**

在 1024px 与 1440px 宽度确认侧栏和品牌列均为 264px，模式入口相对主内容居中，历史标题与操作完整可见。

- [ ] **Step 2: 验证折叠态**

确认侧栏和品牌列均为 72px，主内容即时扩展；图标栏可新建、打开健康/图谱历史，Tooltip、焦点态和选中态可见。

- [ ] **Step 3: 验证状态持久化**

折叠后刷新页面，确认 `localStorage['agentic-rag-sidebar-collapsed'] === 'true'` 且页面保持折叠；展开后刷新，确认该值为 `'false'` 且页面保持展开。

- [ ] **Step 4: 验证移动端不受桌面状态影响**

在 375px 与 767px 宽度确认菜单按钮打开 264px 抽屉，能选择历史并关闭，不出现 72px 移动抽屉或水平滚动；在 768px 确认切换为桌面侧栏。

- [ ] **Step 5: 运行最终自动验证**

Run: `cd frontend; npm run lint; npm run build`

Run: `git diff --check`

Expected: 全部命令退出码为 0；仅允许 Vite 既有 bundle size warning。

- [ ] **Step 6: Commit**

```bash
git add docs/前端设计规范.md docs/superpowers/plans/2026-09-21-collapsible-sidebar-layout.md frontend/src/App.tsx frontend/src/components/Header.tsx frontend/src/components/Sidebar.tsx
git commit -m "feat: finish collapsible sidebar layout"
```
