import { ArrowUpRight, Network, Stethoscope } from 'lucide-react'
import type { ReactNode } from 'react'
import type { AgentType } from '@/types/stream'

const prompts = {
  rag: [
    { label: '症状咨询', question: '最近总是咳嗽，需要注意什么？' },
    { label: '慢病管理', question: '糖尿病患者日常饮食要注意什么？' },
    { label: '症状辨别', question: '感冒和流感有什么区别？' },
  ],
  graph: [
    { label: '就诊科室', question: '百日咳应该挂什么科？' },
    { label: '疾病用药', question: '高血压常用药物有哪些？' },
    { label: '疾病关联', question: '肺炎可能伴随哪些疾病？' },
  ],
}

export function EmptyState({ mode, onSelect, composer }: { mode: AgentType; onSelect: (prompt: string) => void; composer?: ReactNode }) {
  return (
    <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col justify-start px-4 py-8 md:justify-center md:py-12">
      <div className="mb-6 text-center md:mb-8">
        <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-[22px] bg-accent/12 text-accent ring-1 ring-primary/50">
          {mode === 'rag' ? <Stethoscope aria-hidden="true" className="h-7 w-7" /> : <Network aria-hidden="true" className="h-7 w-7" />}
        </div>
        <h1 className="text-balance text-2xl font-bold tracking-tight sm:text-3xl">
          {mode === 'rag' ? '今天哪里不舒服，或想了解什么健康问题？' : '想查清哪种医疗关系？'}
        </h1>
      </div>

      {composer && <div className="mb-6 md:mb-8">{composer}</div>}

      <div className="grid gap-3 sm:grid-cols-3">
        {prompts[mode].map((prompt, index) => (
          <button
            key={prompt.question}
            type="button"
            style={{ animationDelay: `${index * 200}ms` }}
            className="home-prompt-enter group flex min-h-28 cursor-pointer flex-col rounded-2xl border border-border bg-card p-4 text-left shadow-soft transition-[border-color,box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:border-primary/35 hover:shadow-lifted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            onClick={() => onSelect(prompt.question)}
          >
            <span className="mb-2 text-[11px] font-bold tracking-wide text-accent">{prompt.label}</span>
            <span className="text-sm font-medium leading-6 text-foreground">{prompt.question}</span>
            <ArrowUpRight aria-hidden="true" className="mt-auto h-4 w-4 self-end text-muted-foreground transition-colors group-hover:text-primary" />
          </button>
        ))}
      </div>

    </div>
  )
}
