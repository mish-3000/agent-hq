import { initials } from '../format.js'

function Avatar({ skillName }) {
  return (
    <div className="avatar" aria-hidden="true">
      {initials(skillName)}
    </div>
  )
}

export default Avatar
