import { CornerDownLeft, Mic, MicOff, Square } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Tooltip } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

type SpeechResult = {
  isFinal: boolean
  0: { transcript: string }
}
type SpeechEvent = { resultIndex: number; results: ArrayLike<SpeechResult> }
type Recognition = {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((event: SpeechEvent) => void) | null
  onend: (() => void) | null
  onerror: (() => void) | null
  start: () => void
  stop: () => void
  abort: () => void
}
type RecognitionConstructor = new () => Recognition

function recognitionConstructor(): RecognitionConstructor | null {
  const speechWindow = window as typeof window & {
    SpeechRecognition?: RecognitionConstructor
    webkitSpeechRecognition?: RecognitionConstructor
  }
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition ?? null
}

type ComposerProps = {
  value: string
  busy: boolean
  mode: 'rag' | 'graph'
  onChange: (value: string) => void
  onSend: () => void
  onStop: () => void
  onNotice: (message: string) => void
}

export function Composer({
  value,
  busy,
  mode,
  onChange,
  onSend,
  onStop,
  onNotice,
}: ComposerProps) {
  const [listening, setListening] = useState(false)
  const recognitionRef = useRef<Recognition | null>(null)
  const speechSupported = recognitionConstructor() !== null

  useEffect(() => () => recognitionRef.current?.abort(), [])

  const toggleSpeech = () => {
    if (!speechSupported) {
      onNotice('当前浏览器不支持语音识别，请使用最新版 Chrome 或 Edge')
      return
    }
    if (listening) {
      recognitionRef.current?.stop()
      return
    }

    const Constructor = recognitionConstructor()
    if (!Constructor) return
    const recognition = new Constructor()
    const base = value ? `${value.trimEnd()} ` : ''
    recognition.lang = 'zh-CN'
    recognition.interimResults = true
    recognition.continuous = false
    recognition.onresult = (event) => {
      let transcript = ''
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        transcript += event.results[index][0].transcript
      }
      onChange(base + transcript)
    }
    recognition.onend = () => setListening(false)
    recognition.onerror = () => {
      setListening(false)
      onNotice('语音识别未成功，请检查麦克风权限后重试')
    }
    recognitionRef.current = recognition
    setListening(true)
    recognition.start()
  }

  return (
    <div className="border-t border-border bg-card/90 px-4 py-3 backdrop-blur-xl md:px-8">
      <div className="mx-auto max-w-4xl">
        <div className="flex items-end gap-2 rounded-2xl border border-border bg-background p-2 shadow-soft transition-shadow focus-within:border-primary/50 focus-within:ring-4 focus-within:ring-primary/10">
          <Tooltip content={speechSupported ? (listening ? '停止语音识别' : '语音输入') : '请使用 Chrome 或 Edge'}>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              disabled={busy || !speechSupported}
              onClick={toggleSpeech}
              className={cn('shrink-0 rounded-xl', listening && 'animate-pulse-ring bg-primary/10 text-primary')}
              aria-label={listening ? '停止语音识别' : '开始语音输入'}
            >
              {speechSupported ? <Mic className="h-4.5 w-4.5" /> : <MicOff className="h-4.5 w-4.5" />}
            </Button>
          </Tooltip>

          <textarea
            rows={1}
            value={value}
            disabled={busy}
            maxLength={2000}
            className="max-h-36 min-h-10 flex-1 resize-none bg-transparent px-1 py-2 text-sm leading-6 outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
            placeholder={mode === 'rag' ? '问一个医疗问题，支持多轮追问…' : '查询疾病、症状、药物或检查关系…'}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                if (value.trim()) onSend()
              }
            }}
          />

          {busy ? (
            <Button type="button" variant="danger" size="icon" onClick={onStop} className="shrink-0 rounded-xl" aria-label="停止生成">
              <Square className="h-3.5 w-3.5 fill-current" />
            </Button>
          ) : (
            <Button
              type="button"
              size="icon"
              onClick={onSend}
              disabled={!value.trim()}
              className="shrink-0 rounded-xl"
              aria-label="发送问题"
            >
              <CornerDownLeft className="h-4.5 w-4.5" />
            </Button>
          )}
        </div>
        <div className="mt-2 flex justify-between px-1 text-[10px] text-muted-foreground">
          <span>Enter 发送 · Shift + Enter 换行</span>
          <span>{value.length}/2000</span>
        </div>
      </div>
    </div>
  )
}
