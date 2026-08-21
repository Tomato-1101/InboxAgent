import { useCallback, useEffect, useState } from 'react'
import './App.css'
import type { EmailItem, Group, Importance, StatsResponse } from './types'
import { api } from './api'
import { Header } from './components/Header'
import { Sidebar } from './components/Sidebar'
import type { ViewType } from './components/Sidebar'
import { EmailList } from './components/EmailList'
import { EmailDetail } from './components/EmailDetail'
import { TaskView } from './components/TaskView'
import { GroupView } from './components/GroupView'
import { SettingsView } from './components/SettingsView'
import { Toast, useToast } from './components/Toast'

export default function App() {
  const { messages: toasts, push: pushToast, remove: removeToast } = useToast()

  // グローバル状態
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [groups, setGroups] = useState<Group[]>([])

  // ビュー
  const [view, setView] = useState<ViewType>('emails')

  // メールビュー状態
  const [emails, setEmails] = useState<EmailItem[]>([])
  const [emailsLoading, setEmailsLoading] = useState(false)
  const [emailsError, setEmailsError] = useState<string | null>(null)
  const [selectedEmailId, setSelectedEmailId] = useState<string | null>(null)
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null)
  const [importanceFilters, setImportanceFilters] = useState<Set<Importance>>(new Set())
  const [needsReplyOnly, setNeedsReplyOnly] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  // 1文字ごとに API を叩かないよう検索語だけ 300ms 遅らせる
  const [debouncedQuery, setDebouncedQuery] = useState('')

  const loadStats = useCallback(async () => {
    try {
      setStats(await api.stats())
    } catch (_) {}
  }, [])

  const loadGroups = useCallback(async () => {
    try {
      setGroups(await api.groups())
    } catch (_) {}
  }, [])

  const loadEmails = useCallback(async () => {
    setEmailsLoading(true)
    setEmailsError(null)
    try {
      const params: Parameters<typeof api.emails>[0] = { limit: 200 }
      if (selectedGroupId) params.group_id = selectedGroupId
      if (importanceFilters.size > 0) {
        // 複数選択もサーバ側フィルタ（カンマ区切り）。取得済み200件の絞り込みにしない。
        params.importance = [...importanceFilters].join(',')
      }
      if (needsReplyOnly) params.needs_reply = true
      if (debouncedQuery.trim()) params.q = debouncedQuery.trim()
      const res = await api.emails(params)
      setEmails(res.items)
    } catch (e: any) {
      setEmailsError(e.message)
    } finally {
      setEmailsLoading(false)
    }
  }, [selectedGroupId, importanceFilters, needsReplyOnly, debouncedQuery])

  // 検索語のデバウンス
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(searchQuery), 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  // 初回ロード
  useEffect(() => {
    loadStats()
    loadGroups()
  }, [loadStats, loadGroups])

  // メール一覧：フィルタ変更で再取得
  useEffect(() => {
    if (view === 'emails') {
      loadEmails()
    }
  }, [view, loadEmails])

  const handleRefresh = () => {
    loadStats()
    loadEmails()
  }

  const handleImportanceToggle = (imp: Importance) => {
    setImportanceFilters((prev) => {
      const next = new Set(prev)
      if (next.has(imp)) {
        next.delete(imp)
      } else {
        next.add(imp)
      }
      return next
    })
  }

  const handleTaskEmailSelect = (id: string) => {
    setSelectedEmailId(id)
  }

  const handleViewChange = (v: ViewType) => {
    setView(v)
  }

  return (
    <div className="app-layout">
      <Header
        stats={stats}
        onIngestDone={handleRefresh}
        onToast={pushToast}
      />

      <div className="app-body">
        <Sidebar
          view={view}
          onViewChange={handleViewChange}
          groups={groups}
          selectedGroupId={selectedGroupId}
          onGroupSelect={setSelectedGroupId}
          importanceFilters={importanceFilters}
          onImportanceToggle={handleImportanceToggle}
          needsReplyOnly={needsReplyOnly}
          onNeedsReplyToggle={() => setNeedsReplyOnly((v) => !v)}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          emailCount={emails.length}
        />

        <div className="main-content">
          {view === 'emails' && (
            <div className="view-frame">
              <div className="email-list-pane">
                <div className="email-list-header">
                  <span>{emails.length} 件</span>
                </div>
                <EmailList
                  emails={emails}
                  selectedId={selectedEmailId}
                  onSelect={setSelectedEmailId}
                  loading={emailsLoading}
                  error={emailsError}
                />
              </div>
              <EmailDetail
                emailId={selectedEmailId}
                onToast={pushToast}
                onEmailSelect={setSelectedEmailId}
              />
            </div>
          )}

          {view === 'tasks' && (
            <div className="view-frame">
              <TaskView
                onEmailSelect={handleTaskEmailSelect}
                onViewChange={(v) => setView(v)}
              />
            </div>
          )}

          {view === 'groups' && (
            <div className="view-frame">
              <GroupView onGroupsChange={loadGroups} />
            </div>
          )}

          {view === 'settings' && (
            <div className="view-frame">
              <SettingsView onToast={pushToast} />
            </div>
          )}
        </div>
      </div>

      <Toast messages={toasts} onRemove={removeToast} />
    </div>
  )
}
