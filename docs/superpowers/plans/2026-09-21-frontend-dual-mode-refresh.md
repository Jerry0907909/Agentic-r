# Frontend Dual-Mode Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep two equally prominent chat modes while making their purpose, shared history, evidence, and Mock status clear to users.

**Architecture:** Preserve the two existing API endpoints and per-mode draft/selection state. Render all conversations in one sidebar with mode labels; selecting a conversation updates active mode. Consolidate user-facing mode copy and semantic visual tokens in frontend components without backend changes.

**Tech Stack:** React 19, TypeScript, Tailwind CSS 3, Vite 6, Lucide.

**Spec:** `docs/前端设计规范.md`, `docs/需求分析.md` F1, `docs/系统设计.md` §5.

## Global Constraints

- Both `rag` and `graph` remain equal top-level entry points.
- `/api/ask` and `/api/ask_graph` and NDJSON remain unchanged.
- The sidebar shows every conversation and marks its agent type.
- The frontend has no Mock-specific endpoint or data branch; health data may identify Mock status.
- No `.env`, schema, CI/CD, or authentication changes.
- Do not commit as part of this task.

---

### Task 1: Update the source-of-truth rules

**Files:** `docs/前端设计规范.md`, `docs/需求分析.md`, `docs/系统设计.md`.

**Interfaces:** Defines `rag → 智能综合问答`, `graph → 知识图谱查询`, sidebar behavior, health presentation, and visual tokens.

- [x] Write the design spec before code, preserving equal modes and documenting session-mode immutability.
- [x] Update F1 and UI/UX design references to point to the new spec.
- [ ] Check the three documents for conflicting requirements after implementation.

### Task 2: Clarify mode and history navigation

**Files:** `frontend/src/App.tsx`, `frontend/src/components/Header.tsx`, `frontend/src/components/Sidebar.tsx`, `frontend/src/components/EmptyState.tsx`, `frontend/src/components/Composer.tsx`.

**Interfaces:** `Sidebar` receives all `Conversation[]`; `onSelect` receives a `Conversation`, allowing `App` to set `activeTab` from `conversation.agent_type`. `Header` receives `healthState: 'ok' | 'mock' | 'degraded' | 'loading'` and displays both mode labels with equal visual weight.

- [ ] Change the sidebar selection callback to accept the complete conversation and display a mode badge on each item.
- [ ] Remove active-mode filtering in `App`; preserve per-mode drafts and selection, and select the conversation's mode when opened.
- [ ] Replace technical labels and mode descriptions in `Header`, `EmptyState`, and `Composer`.
- [ ] Run `npm run build` and verify type compatibility.

### Task 3: Create a restrained visual system and evidence hierarchy

**Files:** `frontend/src/index.css`, `frontend/tailwind.config.ts`, `frontend/src/components/ui/button.tsx`, `frontend/src/components/MessageBubble.tsx`, `frontend/src/components/SourceCard.tsx`, `frontend/src/components/UsageBadge.tsx`.

**Interfaces:** Semantic CSS tokens for graph, document, Mock, danger, focus, radius and spacing; existing `Source` and `Usage` models remain unchanged.

- [ ] Add light/dark semantic tokens; keep blue primary and improve contrast.
- [ ] Make controls accessible to touch and keyboard, with mobile input at 16px.
- [ ] Give evidence cards a readable preview and collapsible detail; hide score for graph sources.
- [ ] Run `npm run lint` and `npm run build` without disabling rules.

### Task 4: Verify interaction and handoff

**Files:** No additional implementation files unless verification reveals a defect.

- [ ] Run backend `unittest` suite to ensure Mock contract remains intact.
- [ ] Exercise health, stream and history through the live Vite proxy; verify all-history navigation and Mock indicator in the UI when browser inspection is available.
- [ ] Review at 375 / 768 / 1024 / 1440 widths, light and dark modes, and keyboard focus.
- [ ] Run `git diff --check`, review the diff and report any remaining limitations.

## Self-Review Record

- Scope maps to the five component responsibilities in `docs/前端设计规范.md`.
- No API, schema, authentication, or external dependency is added.
- Mode labels and state names are used consistently across tasks.
