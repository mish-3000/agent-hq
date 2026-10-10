import { useEffect, useState } from 'react'

// Matches the backend: 1024 is the Agent Skills limit for a description.
const MAX_JOB_LENGTH = 1024

function NewAgentModal({ onCreate, onClose }) {
  const [name, setName] = useState('')
  const [job, setJob] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && !submitting && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, submitting])

  async function submit(event) {
    event.preventDefault()
    if (!name.trim() || !job.trim() || submitting) return
    setSubmitting(true)
    setError(null)
    try {
      await onCreate(name.trim(), job.trim())
    } catch (e) {
      setError(e.message)
      setSubmitting(false)
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && !submitting && onClose()}>
      <form className="modal" onSubmit={submit} role="dialog" aria-modal="true" aria-labelledby="new-agent-title">
        <h2 id="new-agent-title">New agent</h2>

        <label className="field">
          <span>Name</span>
          <input
            autoFocus
            value={name}
            placeholder="sales-agent"
            maxLength={64}
            spellCheck={false}
            autoCapitalize="off"
            autoComplete="off"
            onChange={(e) => {
              setName(e.target.value)
              setError(null)
            }}
          />
          <small>Lowercase letters, numbers and hyphens.</small>
        </label>

        <label className="field">
          <span>What&apos;s their job?</span>
          <textarea
            rows={5}
            value={job}
            maxLength={MAX_JOB_LENGTH}
            placeholder="You are the team's sales lead. Draft outreach emails, research prospects and summarize deals."
            onChange={(e) => {
              setJob(e.target.value)
              setError(null)
            }}
          />
        </label>

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        <div className="modal-actions">
          <button type="button" className="button secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </button>
          <button type="submit" className="button primary" disabled={!name.trim() || !job.trim() || submitting}>
            {submitting ? 'Creating…' : 'Create agent'}
          </button>
        </div>
      </form>
    </div>
  )
}

export default NewAgentModal
