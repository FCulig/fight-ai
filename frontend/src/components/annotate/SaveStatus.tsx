interface SaveStatusProps {
  saving: boolean;
}

export default function SaveStatus({ saving }: SaveStatusProps) {
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 7, padding: '7px 13px', borderRadius: 10,
      border: '1px solid var(--border-glass)', background: 'var(--surface-inner)',
      color: 'var(--text-secondary)', fontSize: 12.5, fontWeight: 700,
    }}>
      <span
        className="material-symbols-outlined"
        style={{ fontSize: 17, color: saving ? 'var(--text-muted)' : 'var(--green-500)', animation: saving ? 'spin 1s linear infinite' : undefined }}
      >
        {saving ? 'sync' : 'cloud_done'}
      </span>
      {saving ? 'Saving…' : 'All changes saved'}
    </div>
  );
}
