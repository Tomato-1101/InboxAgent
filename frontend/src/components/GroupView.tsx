import { useEffect, useState } from 'react'
import type { Group } from '../types'
import { api } from '../api'

interface Props {
  onGroupsChange: () => void
}

interface FormState {
  name: string
  color: string
  rule_hint: string
  sort_order: number
}

const EMPTY_FORM: FormState = {
  name: '',
  color: '#3b5bdb',
  rule_hint: '',
  sort_order: 0,
}

export function GroupView({ onGroupsChange }: Props) {
  const [groups, setGroups] = useState<Group[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<string | null>(null) // group.id or 'new'
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      setGroups(await api.groups())
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const startNew = () => {
    setEditing('new')
    setForm(EMPTY_FORM)
  }

  const startEdit = (g: Group) => {
    setEditing(g.id)
    setForm({ name: g.name, color: g.color, rule_hint: g.rule_hint, sort_order: g.sort_order })
  }

  const cancelEdit = () => {
    setEditing(null)
    setForm(EMPTY_FORM)
  }

  const handleSave = async () => {
    if (!form.name.trim()) return
    setSaving(true)
    try {
      if (editing === 'new') {
        await api.createGroup(form)
      } else if (editing) {
        await api.updateGroup(editing, form)
      }
      await load()
      onGroupsChange()
      cancelEdit()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`グループ「${name}」を削除しますか？\nこのグループに紐づくメールはグループなしになります。`)) {
      return
    }
    try {
      await api.deleteGroup(id)
      await load()
      onGroupsChange()
    } catch (e: any) {
      setError(e.message)
    }
  }

  return (
    <div className="group-view">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div className="page-title">グループ管理</div>
        <button className="btn-primary btn btn-sm" onClick={startNew} disabled={editing !== null}>
          + 追加
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}
      {loading && <div className="loading-text">読み込み中…</div>}

      {/* 新規フォーム */}
      {editing === 'new' && (
        <GroupForm
          form={form}
          onChange={setForm}
          onSave={handleSave}
          onCancel={cancelEdit}
          saving={saving}
          isNew
        />
      )}

      <div className="group-list">
        {groups.map((g) => (
          <div key={g.id}>
            {editing === g.id ? (
              <GroupForm
                form={form}
                onChange={setForm}
                onSave={handleSave}
                onCancel={cancelEdit}
                saving={saving}
              />
            ) : (
              <div className="group-card">
                <div
                  className="group-card-color"
                  style={{ background: g.color }}
                />
                <div className="group-card-info">
                  <div className="group-card-name">{g.name}</div>
                  {g.rule_hint && (
                    <div className="group-card-hint">{g.rule_hint}</div>
                  )}
                </div>
                <div className="group-card-actions">
                  <button
                    className="btn-secondary btn btn-sm"
                    onClick={() => startEdit(g)}
                    disabled={editing !== null}
                  >
                    編集
                  </button>
                  <button
                    className="btn-danger btn btn-sm"
                    onClick={() => handleDelete(g.id, g.name)}
                    disabled={editing !== null}
                  >
                    削除
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {!loading && groups.length === 0 && editing !== 'new' && (
        <div className="empty-state">グループはありません</div>
      )}
    </div>
  )
}

function GroupForm({
  form,
  onChange,
  onSave,
  onCancel,
  saving,
  isNew,
}: {
  form: FormState
  onChange: (f: FormState) => void
  onSave: () => void
  onCancel: () => void
  saving: boolean
  isNew?: boolean
}) {
  return (
    <div className="group-form">
      <div style={{ fontWeight: 600, fontSize: 13 }}>
        {isNew ? '新規グループ' : 'グループを編集'}
      </div>
      <div className="form-row">
        <div className="form-field" style={{ flex: 2 }}>
          <label>グループ名</label>
          <input
            className="form-input"
            value={form.name}
            onChange={(e) => onChange({ ...form, name: e.target.value })}
            placeholder="例: 取引先"
          />
        </div>
        <div className="form-field" style={{ flex: 0 }}>
          <label>色</label>
          <input
            type="color"
            value={form.color}
            onChange={(e) => onChange({ ...form, color: e.target.value })}
            style={{ width: 40, height: 32, border: '1px solid #e2e5ea', borderRadius: 4, cursor: 'pointer' }}
          />
        </div>
        <div className="form-field" style={{ flex: 1 }}>
          <label>並び順</label>
          <input
            className="form-input"
            type="number"
            value={form.sort_order}
            onChange={(e) => onChange({ ...form, sort_order: Number(e.target.value) })}
          />
        </div>
      </div>
      <div className="form-field">
        <label>ルールヒント（AIの振り分けヒント）</label>
        <input
          className="form-input"
          value={form.rule_hint}
          onChange={(e) => onChange({ ...form, rule_hint: e.target.value })}
          placeholder="例: 社外取引先からの問い合わせ"
        />
      </div>
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <button className="btn-secondary btn btn-sm" onClick={onCancel}>
          キャンセル
        </button>
        <button
          className="btn-primary btn btn-sm"
          onClick={onSave}
          disabled={saving || !form.name.trim()}
        >
          {saving ? '保存中…' : '保存'}
        </button>
      </div>
    </div>
  )
}
