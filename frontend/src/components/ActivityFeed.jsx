import { useEffect, useState } from 'react'
import { getActivity } from '../api.js'
import Avatar from './Avatar.jsx'
import { displayName, formatTime, timeAgo } from '../format.js'

const REFRESH_MS = 3000

// Polls GET /activity while mounted (i.e. while the Activity tab is open).
function ActivityFeed({ skills, onSelect }) {
  const [entries, setEntries] = useState(null)
  const [error, setError] = useState(null)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    let cancelled = false
    async function refresh() {
      if (document.visibilityState === 'hidden') return
      try {
        const data = await getActivity()
        if (!cancelled) {
          setEntries(data)
          setError(null)
          setNow(Date.now())
        }
      } catch (e) {
        if (!cancelled) setError(e.message)
      }
    }
    refresh()
    const timer = setInterval(refresh, REFRESH_MS)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [])

  const known = new Set((skills ?? []).map((s) => s.name))

  return (
    <div className="activity-feed" aria-live="polite">
      {error && <p className="sidebar-note error">Couldn&apos;t load activity: {error}</p>}
      {!error && entries === null && <p className="sidebar-note">Loading activity…</p>}
      {entries?.length === 0 && (
        <p className="sidebar-note">
          No tool activity yet. Ask an agent to search the web, write code, or consult another agent.
        </p>
      )}

      {entries?.map((entry, i) => (
        <button
          key={`${entry.timestamp}-${entry.agent}-${entry.action}-${i}`}
          type="button"
          className="activity-row"
          onClick={() => known.has(entry.agent) && onSelect(entry.agent)}
          disabled={!known.has(entry.agent)}
          title={known.has(entry.agent) ? `Open chat with ${displayName(entry.agent)}` : undefined}
        >
          <Avatar skillName={entry.agent} />
          <div className="activity-body">
            <p>
              <strong>{displayName(entry.agent)}</strong> {entry.action}
            </p>
            <time dateTime={entry.timestamp} title={formatTime(entry.timestamp)}>
              {timeAgo(entry.timestamp, now)}
            </time>
          </div>
        </button>
      ))}
    </div>
  )
}

export default ActivityFeed
