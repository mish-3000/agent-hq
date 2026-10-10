import { useEffect, useState } from 'react'
import { getSkills, sendChat } from './api.js'
import Sidebar from './components/Sidebar.jsx'
import ChatPane from './components/ChatPane.jsx'
import './App.css'

// A message is { id, role: 'user' | 'model', text, at, toolUsed?, url?, error? }.
// Only role and text are sent to the backend as history.

function App() {
  const [skills, setSkills] = useState(null)
  const [skillsError, setSkillsError] = useState(null)
  const [activeSkill, setActiveSkill] = useState(null)
  const [chats, setChats] = useState({}) // { [skillName]: Message[] }
  const [pending, setPending] = useState({}) // { [skillName]: true while waiting for a reply }

  useEffect(() => {
    getSkills()
      .then(setSkills)
      .catch((e) => setSkillsError(e.message))
  }, [])

  function updateChat(skillName, update) {
    setChats((prev) => ({ ...prev, [skillName]: update(prev[skillName] ?? []) }))
  }

  async function handleSend(skillName, text) {
    // Messages that failed to send never reached the model, so leave them out of history.
    const history = (chats[skillName] ?? [])
      .filter((m) => !m.error)
      .map(({ role, text }) => ({ role, text }))

    const userId = crypto.randomUUID()
    updateChat(skillName, (msgs) => [...msgs, { id: userId, role: 'user', text, at: Date.now() }])
    setPending((p) => ({ ...p, [skillName]: true }))

    try {
      const data = await sendChat(skillName, text, history)
      updateChat(skillName, (msgs) => [
        ...msgs,
        {
          id: crypto.randomUUID(),
          role: 'model',
          text: data.reply,
          at: Date.now(),
          toolUsed: data.tool_used,
          url: data.url,
        },
      ])
    } catch (e) {
      updateChat(skillName, (msgs) =>
        msgs.map((m) => (m.id === userId ? { ...m, error: e.message } : m)),
      )
    } finally {
      setPending((p) => ({ ...p, [skillName]: false }))
    }
  }

  const skill = skills?.find((s) => s.name === activeSkill)

  return (
    <div className={`app${skill ? ' chat-open' : ''}`}>
      <Sidebar
        skills={skills}
        error={skillsError}
        chats={chats}
        pending={pending}
        activeSkill={activeSkill}
        onSelect={setActiveSkill}
      />
      {skill ? (
        <ChatPane
          key={skill.name}
          skill={skill}
          messages={chats[skill.name] ?? []}
          isPending={!!pending[skill.name]}
          onSend={(text) => handleSend(skill.name, text)}
          onBack={() => setActiveSkill(null)}
        />
      ) : (
        <section className="empty-pane">
          <h2>Agent HQ</h2>
          <p>Pick an agent on the left to start a chat.</p>
        </section>
      )}
    </div>
  )
}

export default App
