import { useState } from 'react'
import type { StatsResponse } from '../types'
import { api } from '../api'
import { ConfirmDialog } from './ConfirmDialog'

interface Props {
  stats: StatsResponse | null
  onIngestDone: () => void
  onToast: (msg: string, kind?: 'success' | 'error' | 'info') => void
}

export function Header({ stats, onIngestDone, onToast }: Props) {
  const [ingesting, setIngesting] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [analyzeDialog, setAnalyzeDialog] = useState<{
    pending: number
    estimated_calls: number
    model: string
  } | null>(null)

  const handleIngest = async () => {
    setIngesting(true)
    try {
      const res = await api.ingest()
      if (res.ok) {
        onToast(`取り込み完了: 新着 ${res.new_messages ?? 0} 件`, 'success')
        onIngestDone()
      } else {
        onToast(`取り込みエラー: ${res.error ?? '不明なエラー'}`, 'error')
      }
    } catch (e: any) {
      onToast(`取り込みエラー: ${e.message}`, 'error')
    } finally {
      setIngesting(false)
    }
  }

  const handleAnalyzeClick = async () => {
    try {
      const pending = await api.analyzePending()
      setAnalyzeDialog(pending)
    } catch (e: any) {
      onToast(`分析件数の取得に失敗: ${e.message}`, 'error')
    }
  }

  const handleAnalyzeRun = async () => {
    setAnalyzeDialog(null)
    setAnalyzing(true)
    try {
      const res = await api.analyzeRun()
      if (res.ok) {
        onToast(`分析完了: ${res.analyzed} 件処理`, 'success')
      } else {
        onToast(res.error ?? '分析を実行できませんでした', 'error')
      }
      onIngestDone()
    } catch (e: any) {
      onToast(`分析エラー: ${e.message}`, 'error')
    } finally {
      setAnalyzing(false)
    }
  }

  const imp = stats?.by_importance

  return (
    <>
      <header className="header">
        <div className="header-brand">InboxAgent</div>

        {stats && (
          <div className="header-stats">
            <span className="stat-chip">
              総数 <span className="val">{stats.total}</span>
            </span>
            <span className="stat-chip">
              分析済み <span className="val">{stats.analyzed}</span>
            </span>
            <span className="stat-chip">
              未完タスク <span className="val">{stats.open_tasks}</span>
            </span>
            {imp && imp['緊急'] > 0 && (
              <span className="stat-chip urgent">
                緊急 <span className="val">{imp['緊急']}</span>
              </span>
            )}
            {imp && imp['要対応'] > 0 && (
              <span className="stat-chip action">
                要対応 <span className="val">{imp['要対応']}</span>
              </span>
            )}
          </div>
        )}

        <div className="header-actions">
          <button
            className="btn-secondary btn btn-sm"
            onClick={handleIngest}
            disabled={ingesting || analyzing}
          >
            {ingesting ? (
              <>
                <span className="spinning">⟳</span> 取り込み中…
              </>
            ) : (
              '取り込み'
            )}
          </button>
          <button
            className="btn-primary btn btn-sm"
            onClick={handleAnalyzeClick}
            disabled={ingesting || analyzing}
          >
            {analyzing ? (
              <>
                <span className="spinning">⟳</span> 分析中…
              </>
            ) : (
              '分析'
            )}
          </button>
        </div>
      </header>

      {analyzeDialog && (
        <ConfirmDialog
          title="AI分析を実行しますか？"
          body={`未分析 ${analyzeDialog.pending} 件・推定 ${analyzeDialog.estimated_calls} 回のAI呼び出し（モデル: ${analyzeDialog.model}）`}
          onConfirm={handleAnalyzeRun}
          onCancel={() => setAnalyzeDialog(null)}
          confirmLabel="分析実行"
        />
      )}
    </>
  )
}
