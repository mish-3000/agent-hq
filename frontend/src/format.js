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

// "just now", "42s ago", "5m ago", "3h ago", then the time of day.
export function timeAgo(timestamp, now = Date.now()) {
  const seconds = Math.max(0, Math.round((now - new Date(timestamp).getTime()) / 1000))
  if (seconds < 5) return 'just now'
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return formatTime(timestamp)
}

export function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  })
}
