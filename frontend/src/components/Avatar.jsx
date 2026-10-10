import { avatarHue, initials } from '../format.js'

function Avatar({ skillName }) {
  return (
    <div
      className="avatar"
      style={{ '--hue': avatarHue(skillName) }}
      aria-hidden="true"
    >
      {initials(skillName)}
    </div>
  )
}

export default Avatar
