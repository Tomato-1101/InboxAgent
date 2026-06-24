import type { Group, Importance } from '../types'

export type ViewType = 'emails' | 'tasks' | 'groups' | 'settings'

interface Props {
  view: ViewType
  onViewChange: (v: ViewType) => void
  groups: Group[]
  selectedGroupId: string | null
  onGroupSelect: (id: string | null) => void
  importanceFilters: Set<Importance>
  onImportanceToggle: (imp: Importance) => void
  needsReplyOnly: boolean
  onNeedsReplyToggle: () => void
  searchQuery: string
  onSearchChange: (q: string) => void
  emailCount: number
}

const IMPORTANCE_LIST: { key: Importance; label: string; cls: string }[] = [
  { key: '緊急', label: '緊急', cls: 'active-urgent' },
  { key: '要対応', label: '要対応', cls: 'active-action' },
  { key: '参考', label: '参考', cls: 'active-ref' },
  { key: '通知', label: '通知', cls: 'active-notify' },
]

const NAV_ITEMS: { key: ViewType; label: string }[] = [
  { key: 'emails', label: 'メール' },
  { key: 'tasks', label: 'タスク' },
  { key: 'groups', label: 'グループ管理' },
  { key: 'settings', label: '設定' },
]

export function Sidebar({
  view,
  onViewChange,
  groups,
  selectedGroupId,
  onGroupSelect,
  importanceFilters,
  onImportanceToggle,
  needsReplyOnly,
  onNeedsReplyToggle,
  searchQuery,
  onSearchChange,
  emailCount,
}: Props) {
  return (
    <aside className="sidebar">
      <div className="sidebar-section">
        <div className="sidebar-section-title">ナビゲーション</div>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.key}
            className={`sidebar-item ${view === item.key ? 'active' : ''}`}
            onClick={() => onViewChange(item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {view === 'emails' && (
        <>
          <div className="sidebar-divider" />

          {/* グループフィルタ */}
          <div className="sidebar-section">
            <div className="sidebar-section-title">グループ</div>
            <button
              className={`sidebar-item ${selectedGroupId === null ? 'active' : ''}`}
              onClick={() => onGroupSelect(null)}
            >
              すべて
              <span className="badge">{emailCount}</span>
            </button>
            {groups.map((g) => (
              <button
                key={g.id}
                className={`sidebar-item ${selectedGroupId === g.id ? 'active' : ''}`}
                onClick={() => onGroupSelect(g.id)}
              >
                <span className="group-dot" style={{ background: g.color }} />
                {g.name}
              </button>
            ))}
          </div>

          <div className="sidebar-divider" />

          {/* 重要度フィルタ */}
          <div className="filter-section">
            <div className="filter-label">重要度</div>
            <div className="importance-filters">
              {IMPORTANCE_LIST.map((imp) => {
                const active = importanceFilters.has(imp.key)
                return (
                  <button
                    key={imp.key}
                    className={`imp-toggle ${active ? imp.cls : ''}`}
                    onClick={() => onImportanceToggle(imp.key)}
                  >
                    {imp.label}
                  </button>
                )
              })}
            </div>

            {/* 要返信トグル */}
            <div className="toggle-row">
              <span>要返信のみ</span>
              <label className="toggle-switch">
                <input
                  type="checkbox"
                  checked={needsReplyOnly}
                  onChange={onNeedsReplyToggle}
                />
                <span className="toggle-track" />
              </label>
            </div>

            {/* 検索 */}
            <input
              type="search"
              className="search-input"
              placeholder="件名・差出人を検索…"
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
            />
          </div>
        </>
      )}
    </aside>
  )
}
