interface Props {
  title: string
  body?: string
  preview?: string
  onConfirm: () => void
  onCancel: () => void
  confirmLabel?: string
  danger?: boolean
}

export function ConfirmDialog({
  title,
  body,
  preview,
  onConfirm,
  onCancel,
  confirmLabel = '実行',
  danger = false,
}: Props) {
  return (
    <div className="dialog-overlay" onClick={onCancel}>
      <div className="dialog" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-title">{title}</div>
        {body && <div className="dialog-body">{body}</div>}
        {preview && <pre className="dialog-preview">{preview}</pre>}
        <div className="dialog-actions">
          <button className="btn-secondary btn" onClick={onCancel}>
            キャンセル
          </button>
          <button
            className={danger ? 'btn-danger btn' : 'btn-primary btn'}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
