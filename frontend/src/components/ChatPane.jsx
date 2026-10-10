import { useEffect, useRef, useState } from 'react'
import Avatar from './Avatar.jsx'
import { displayName, formatTime } from '../format.js'

function ChatPane({ skill, messages, isPending, onSend, onBack }) {
  const [draft, setDraft] = useState('')
  const endRef = useRef(null)
  const inputRef = useRef(null)

  // Keep the newest message (or the typing indicator) in view.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages.length, isPending])

  useEffect(() => {
    if (!isPending) inputRef.current?.focus()
  }, [isPending])

  function resizeInput() {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`
  }

  function submit(event) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || isPending) return
    onSend(text)
    setDraft('')
    requestAnimationFrame(resizeInput)
  }

  function handleKeyDown(event) {
    // Enter sends; Shift+Enter adds a new line.
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      submit(event)
    }
  }

  return (
    <section className="chat-pane">
      <header className="chat-header">
        <button type="button" className="back-button" onClick={onBack} aria-label="Back to chats">
          ‹
        </button>
        <Avatar skillName={skill.name} />
        <div className="chat-header-text">
          <h2>{displayName(skill.name)}</h2>
          <p>{isPending ? 'typing…' : skill.description}</p>
        </div>
      </header>

      <div className="message-list" role="log" aria-live="polite">
        {messages.length === 0 && (
          <p className="system-line">Send a message to start chatting with {displayName(skill.name)}.</p>
        )}

        {messages.map((m) => (
          <div key={m.id} className="message-group">
            {m.toolUsed && (
              <p className="system-line tool-status">
                {m.toolUsed}
                {m.url && (
                  <>
                    {' · '}
                    <a href={m.url} target="_blank" rel="noreferrer">
                      view on GitHub
                    </a>
                  </>
                )}
              </p>
            )}
            <div className={`bubble ${m.role === 'user' ? 'outgoing' : 'incoming'}`}>
              <span className="bubble-text">{m.text || <em>(empty reply)</em>}</span>
              <span className="bubble-time">{formatTime(m.at)}</span>
            </div>
            {m.error && <p className="system-line error">Not delivered: {m.error}</p>}
          </div>
        ))}

        {isPending && (
          <div className="bubble incoming typing-bubble" aria-label={`${displayName(skill.name)} is typing`}>
            <span className="dot" />
            <span className="dot" />
            <span className="dot" />
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form className="composer" onSubmit={submit}>
        <textarea
          ref={inputRef}
          rows={1}
          value={draft}
          placeholder="Type a message"
          aria-label="Message"
          onChange={(e) => {
            setDraft(e.target.value)
            resizeInput()
          }}
          onKeyDown={handleKeyDown}
        />
        <button type="submit" className="send-button" disabled={!draft.trim() || isPending} aria-label="Send">
          <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
            <path fill="currentColor" d="M3.4 20.4 21 12 3.4 3.6 3.4 10.1 15 12 3.4 13.9z" />
          </svg>
        </button>
      </form>
    </section>
  )
}

export default ChatPane
