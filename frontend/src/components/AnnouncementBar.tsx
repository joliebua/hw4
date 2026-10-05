import { useShop } from '../shop'

/** Storefront ticker across the top of every page. Only true statements. */
export default function AnnouncementBar() {
  const { facets, setChatOpen } = useShop()
  const items = [
    '57 Broadway · New Haven',
    facets ? `${facets.product_count} pieces on the shelves` : 'Every residential college on the shelves',
    'Live stock in every size, XS–XXL',
    'Ask Handsome Dan: he knows every size in stock',
    'Boola Boola!',
  ]
  const row = items.map((t, i) => (
    <span key={i} className="ticker-item">
      {t}
      <span className="ticker-dot" aria-hidden>
        ●
      </span>
    </span>
  ))
  return (
    <div className="ticker" role="region" aria-label="Store announcements">
      <div className="ticker-track">
        <span className="ticker-run">{row}</span>
        <span className="ticker-run" aria-hidden>
          {row}
        </span>
      </div>
      <button className="ticker-cta" onClick={() => setChatOpen(true)}>
        Ask Dan →
      </button>
    </div>
  )
}
