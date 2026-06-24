import { useEffect, useState } from 'react'
import type { TaskListItem } from '../types'
import { api } from '../api'

interface Props {
  onEmailSelect: (id: string) => void
  onViewChange: (v: 'emails') => void
}

function formatDue(d: string | null) {
  if (!d) return null
  return new Date(d).toLocaleDateString('ja-JP', {
    month: 'numeric',
    day: 'numeric',
  })
}

export function TaskView({ onEmailSelect, onViewChange }: Props) {
  const [tasks, setTasks] = useState<TaskListItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showDone, setShowDone] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = showDone ? await api.tasks() : await api.tasks(false)
      setTasks(res.items)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [showDone])

  const handleToggle = async (id: string) => {
    try {
      const res = await api.toggleTask(id)
      setTasks((prev) =>
        prev.map((t) => (t.id === id ? { ...t, done: res.done } : t))
      )
    } catch (e: any) {
      setError(e.message)
    }
  }

  const replyTasks = tasks.filter((t) => t.kind === 'reply_pending')
  const actionTasks = tasks.filter((t) => t.kind === 'action')

  return (
    <div className="task-view">
      <div className="task-view-header">
        <div className="page-title">タスク</div>
        <div className="toggle-row" style={{ gap: 8, marginBottom: 0 }}>
          <span>完了済みも表示</span>
          <label className="toggle-switch">
            <input
              type="checkbox"
              checked={showDone}
              onChange={() => setShowDone((v) => !v)}
            />
            <span className="toggle-track" />
          </label>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}
      {loading && <div className="loading-text">読み込み中…</div>}

      {!loading && (
        <>
          {replyTasks.length > 0 && (
            <div>
              <div className="task-section-title">
                返信待ち
                <span className="badge" style={{ background: '#fef3c7', color: '#92400e', border: '1px solid #fde68a' }}>
                  {replyTasks.length}
                </span>
              </div>
              <div className="task-group">
                {replyTasks.map((t) => (
                  <TaskCard key={t.id} task={t} onToggle={handleToggle} onEmailSelect={(id) => {
                    onEmailSelect(id)
                    onViewChange('emails')
                  }} />
                ))}
              </div>
            </div>
          )}

          {actionTasks.length > 0 && (
            <div>
              <div className="task-section-title">
                アクション
                <span className="badge" style={{ background: '#eff6ff', color: '#2563eb', border: '1px solid #bfdbfe' }}>
                  {actionTasks.length}
                </span>
              </div>
              <div className="task-group">
                {actionTasks.map((t) => (
                  <TaskCard key={t.id} task={t} onToggle={handleToggle} onEmailSelect={(id) => {
                    onEmailSelect(id)
                    onViewChange('emails')
                  }} />
                ))}
              </div>
            </div>
          )}

          {tasks.length === 0 && !loading && (
            <div className="empty-state">タスクはありません</div>
          )}
        </>
      )}
    </div>
  )
}

function TaskCard({
  task,
  onToggle,
  onEmailSelect,
}: {
  task: TaskListItem
  onToggle: (id: string) => void
  onEmailSelect: (id: string) => void
}) {
  return (
    <div className={`task-card ${task.done ? 'done-card' : ''}`}>
      <input
        type="checkbox"
        checked={task.done}
        onChange={() => onToggle(task.id)}
      />
      <span className="task-card-title">{task.title}</span>
      {task.email_id && task.email_subject && (
        <span
          className="task-email-link"
          onClick={() => task.email_id && onEmailSelect(task.email_id)}
          title={task.email_subject}
        >
          {task.email_subject}
        </span>
      )}
      {task.due_date && (
        <span className="task-due">{formatDue(task.due_date)}</span>
      )}
    </div>
  )
}
