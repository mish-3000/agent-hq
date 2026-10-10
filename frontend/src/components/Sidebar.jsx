import Avatar from './Avatar.jsx'
import { displayName, formatTime } from '../format.js'

function Sidebar({ skills, error, chats, pending, activeSkill, onSelect }) {
  return (
    <aside className="sidebar">
      <header className="sidebar-header">
        <h1>Agent HQ</h1>
      </header>

      <nav className="chat-list" aria-label="Agents">
        {error && <p className="sidebar-note error">{error}</p>}
        {!error && skills === null && <p className="sidebar-note">Loading agents…</p>}
        {!error && skills?.length === 0 && (
          <p className="sidebar-note">No agents found in backend/skills/.</p>
        )}

        {skills?.map((skill) => {
          const messages = chats[skill.name] ?? []
          const last = messages.at(-1)
          const isPending = pending[skill.name]
          return (
            <button
              key={skill.name}
              type="button"
              className={`chat-row${skill.name === activeSkill ? ' active' : ''}`}
              onClick={() => onSelect(skill.name)}
              aria-current={skill.name === activeSkill ? 'true' : undefined}
            >
              <Avatar skillName={skill.name} />
              <div className="chat-row-body">
                <div className="chat-row-top">
                  <span className="chat-row-name">{displayName(skill.name)}</span>
                  {last && <span className="chat-row-time">{formatTime(last.at)}</span>}
                </div>
                <div className={`chat-row-preview${isPending ? ' typing' : ''}`}>
                  {isPending
                    ? 'typing…'
                    : last
                      ? `${last.role === 'user' ? 'You: ' : ''}${last.text}`
                      : skill.description}
                </div>
              </div>
            </button>
          )
        })}
      </nav>
    </aside>
  )
}

export default Sidebar
