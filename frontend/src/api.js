const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function request(path, options) {
  let res
  try {
    res = await fetch(`${API_URL}${path}`, options)
  } catch {
    throw new Error(`Can't reach the backend at ${API_URL}`)
  }
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = data?.detail
    throw new Error(
      typeof detail === 'string' ? detail : `Request failed (${res.status})`,
    )
  }
  return data
}

export function getSkills() {
  return request('/skills')
}

export function createSkill(name, description, rolePrompt) {
  return request('/skills', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description, role_prompt: rolePrompt }),
  })
}

export function sendChat(skillName, message, history) {
  return request(`/chat/${encodeURIComponent(skillName)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history }),
  })
}
