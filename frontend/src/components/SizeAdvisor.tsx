import { useState } from 'react'
import { SIZES } from '../format'
import type { SizeRecommendation } from '../types'

interface Props {
  recommendation: SizeRecommendation | null
  mySize: string | null
  signedIn: boolean
  onSetMySize: (size: string | null) => void
  onChoose: (size: string) => void
}

/**
 * "Recommended size" box on the product page. Shows which size to buy and
 * why (saved size, size history, this item's stock). With no size known, it
 * asks the shopper which size they usually wear.
 */
export default function SizeAdvisor({ recommendation: rec, mySize, signedIn, onSetMySize, onChoose }: Props) {
  const [editing, setEditing] = useState(false)

  const picker = (
    <div className="my-size-picker" role="group" aria-label="Your usual size">
      {SIZES.map((s) => (
        <button
          key={s}
          className={`size-chip${mySize === s ? ' on' : ''}`}
          aria-pressed={mySize === s}
          onClick={() => {
            onSetMySize(s)
            setEditing(false)
          }}
        >
          {s}
        </button>
      ))}
    </div>
  )

  if (!rec || rec.basis === 'none' || editing) {
    return (
      <div className="size-advisor ask">
        <p className="advisor-title">📏 What size do you usually wear?</p>
        <p className="advisor-sub">
          Pick it once and we'll recommend a size on every item
          {signedIn ? ' (saved to your account)' : ' (saved in this browser)'}.
        </p>
        {picker}
        {editing && (
          <button className="link-btn small-link" onClick={() => setEditing(false)}>
            Cancel
          </button>
        )}
      </div>
    )
  }

  const basisLabel = rec.basis === 'history' ? 'Based on your past sizes' : 'Based on your size'

  return (
    <div className={`size-advisor${rec.exact_match ? '' : ' warn'}`} aria-live="polite">
      <div className="advisor-row">
        <div>
          <p className="advisor-title">
            {rec.recommended_size ? (
              <>
                Recommended size: <strong className="advisor-size">{rec.recommended_size}</strong>
              </>
            ) : (
              <>Sold out in every size</>
            )}
          </p>
          <p className="advisor-sub">
            <span className="advisor-basis">{basisLabel}.</span> {rec.reason}
          </p>
        </div>
        {rec.recommended_size && (
          <button className="btn btn-ghost small" onClick={() => onChoose(rec.recommended_size!)}>
            Select {rec.recommended_size}
          </button>
        )}
      </div>
      <p className="advisor-foot">
        Your size: <strong>{mySize ?? rec.usual_size}</strong>
        {rec.basis === 'history' && !mySize && ' (from your history)'} ·{' '}
        <button className="link-btn small-link" onClick={() => setEditing(true)}>
          {mySize ? 'Change' : 'Set my size'}
        </button>
      </p>
    </div>
  )
}
