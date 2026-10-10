// "research-agent" -> "Research Agent"
export function displayName(skillName) {
  return skillName
    .split(/[-_]/)
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(' ')
}

export function initials(skillName) {
  return displayName(skillName)
    .split(' ')
    .slice(0, 2)
    .map((word) => word[0])
    .join('')
}

const AVATAR_HUES = [168, 200, 260, 330, 20, 45, 100]

export function avatarHue(skillName) {
  let hash = 0
  for (const ch of skillName) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  return AVATAR_HUES[hash % AVATAR_HUES.length]
}

export function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  })
}
