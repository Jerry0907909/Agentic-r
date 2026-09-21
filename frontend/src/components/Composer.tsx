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
  placement?: 'home' | 'conversation'
  value: string
  busy: boolean
  mode: 'rag' | 'graph'
  onChange: (value: string) => void
  onSend: () => void
  onStop: () => void
  onNotice: (message: string) => void
}

export function Composer({
  placement = 'conversation',
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
    <div className={cn('shrink-0', placement === 'home' ? 'w-full' : 'bg-gradient-to-t from-background via-background to-background/70 px-3 pb-3 pt-2 md:px-8 md:pb-5')}>
      <div className="mx-auto max-w-4xl rounded-[22px] border border-border/90 bg-card p-2 shadow-lifted transition-[border-color,box-shadow] focus-within:border-primary/45 focus-within:ring-4 focus-within:ring-primary/10">
        <div className="flex items-center gap-1.5 sm:gap-2">
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
              {speechSupported ? <Mic aria-hidden="true" className="h-4.5 w-4.5" /> : <MicOff aria-hidden="true" className="h-4.5 w-4.5" />}
            </Button>
          </Tooltip>

          <textarea
            rows={1}
            value={value}
            disabled={busy}
            maxLength={2000}
            className="max-h-36 min-h-11 min-w-0 flex-1 resize-none border-0 bg-transparent px-1 py-2 text-base leading-7 outline-none placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-0 disabled:cursor-not-allowed sm:text-[15px]"
            aria-label="输入医疗问题"
            placeholder={mode === 'rag' ? '描述症状，或询问疾病、用药等问题…' : '查询疾病、症状、药物或检查关系…'}
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
              <Square aria-hidden="true" className="h-3.5 w-3.5 fill-current" />
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
              <CornerDownLeft aria-hidden="true" className="h-4.5 w-4.5" />
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
