import { ArrowUpRight, Network, Search, ShieldCheck } from 'lucide-react'
import type { AgentType } from '@/types/stream'

const prompts = {
  rag: ['百日咳有哪些典型症状？', '糖尿病患者日常饮食要注意什么？', '感冒和流感有什么区别？'],
  graph: ['百日咳应该挂什么科？', '高血压常用药物有哪些？', '肺炎可能伴随哪些疾病？'],
}

export function EmptyState({ mode, onSelect }: { mode: AgentType; onSelect: (prompt: string) => void }) {
  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col justify-center px-4 py-10">
      <div className="mb-8 text-center">
        <div className="mx-auto mb-5 grid h-16 w-16 place-items-center rounded-2xl bg-gradient-to-br from-primary to-indigo-500 text-white shadow-xl shadow-primary/20">
          {mode === 'rag' ? <Search className="h-7 w-7" /> : <Network className="h-7 w-7" />}
        </div>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          {mode === 'rag' ? '今天想了解什么？' : '探索医疗知识图谱'}
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-muted-foreground">
          {mode === 'rag'
            ? '系统会自动选择混合检索或图谱查询，并展示回答依据。'
            : '从 Neo4j 知识图谱中查询疾病、症状、药物、检查与科室之间的关系。'}
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        {prompts[mode].map((prompt) => (
          <button
            key={prompt}
            type="button"
            className="group rounded-2xl border border-border bg-card p-4 text-left text-sm leading-6 shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-soft"
            onClick={() => onSelect(prompt)}
          >
            <span>{prompt}</span>
            <ArrowUpRight className="mt-4 h-4 w-4 text-muted-foreground transition-colors group-hover:text-primary" />
          </button>
        ))}
      </div>

      <div className="mt-7 flex items-center justify-center gap-2 text-[11px] text-muted-foreground">
        <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
        答案支持来源溯源 · 医疗内容仅供课程演示
      </div>
    </div>
  )
}
