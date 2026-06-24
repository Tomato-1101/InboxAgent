import { useEffect, useState } from 'react'

export interface ToastMessage {
  id: number
  text: string
  kind: 'success' | 'error' | 'info'
}

interface Props {
  messages: ToastMessage[]
  onRemove: (id: number) => void
}

export function Toast({ messages, onRemove }: Props) {
  return (
    <div className="toast-container">
      {messages.map((m) => (
        <ToastItem key={m.id} msg={m} onRemove={onRemove} />
      ))}
    </div>
  )
}

function ToastItem({ msg, onRemove }: { msg: ToastMessage; onRemove: (id: number) => void }) {
  useEffect(() => {
    const t = setTimeout(() => onRemove(msg.id), 4000)
    return () => clearTimeout(t)
  }, [msg.id, onRemove])

  return (
    <div className={`toast ${msg.kind}`} onClick={() => onRemove(msg.id)}>
      {msg.text}
    </div>
  )
}

let _next = 1

export function useToast() {
  const [messages, setMessages] = useState<ToastMessage[]>([])

  const push = (text: string, kind: ToastMessage['kind'] = 'info') => {
    const id = _next++
    setMessages((prev) => [...prev, { id, text, kind }])
  }

  const remove = (id: number) => {
    setMessages((prev) => prev.filter((m) => m.id !== id))
  }

  return { messages, push, remove }
}
