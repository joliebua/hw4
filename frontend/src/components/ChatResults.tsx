import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useShop } from '../shop'
import ProductCard from './ProductCard'

/**
 * Products the chat put on the page.
 *
 * - `showcase`: every match of a search Handsome Dan ran ("show me hoodies"), as
 *   product cards, with Handsome Dan's top picks highlighted.
 * - otherwise `picks`: just Handsome Dan's top picks for a specific answer.
 *
 * Every card is a link to its single-item page (/products/:id). Opening one
 * collapses this section to a one-line bar so the large photo and full details
 * stay at the top; new results from the chat always arrive expanded.
 */
export default function ChatResults() {
  const { picks, showcase, clearResults, mySize } = useShop()
  const { pathname } = useLocation()
  const ref = useRef<HTMLElement>(null)

  const onProductPage = /^\/products\/[^/]+$/.test(pathname)
  const [collapsed, setCollapsed] = useState(onProductPage)
  const cards = showcase?.products ?? picks
  const pickIds = new Set(picks.map((p) => p.product_id))

  // Opening a product page collapses the results; leaving it expands them.
  useEffect(() => setCollapsed(onProductPage), [pathname, onProductPage])

  // Fresh results from the chat: expand and bring them into view.
  useEffect(() => {
    if (cards.length === 0) return
    setCollapsed(false)
    ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    // Only when the results themselves change, not on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showcase, picks])

  if (cards.length === 0) return null

  const title = showcase ? showcase.title : "Dan's picks"

  if (collapsed) {
    return (
      <div className="results-bar">
        <span>
          <span className="sparkle">🐾</span> {title} · {showcase ? showcase.total_matches : picks.length} items
        </span>
        <button className="link-btn" onClick={() => setCollapsed(false)}>
          Show Dan's results
        </button>
      </div>
    )
  }

  const shown = cards.length
  const total = showcase?.total_matches ?? shown

  return (
    <section className={`picks${showcase ? ' showcase' : ''}`} ref={ref} aria-label={title} aria-live="polite">
      <div className="section-head">
        <div>
          <h2>
            <span className="sparkle">🐾</span> {title}
          </h2>
          <p className="results-meta">
            {showcase
              ? `Dan found ${total} ${total === 1 ? 'item' : 'items'}${shown < total ? ` · showing ${shown}` : ''}. Click any card for the full details.`
              : 'Dan picked these for you. Click any card for the full details.'}
          </p>
        </div>
        <div className="results-actions">
          {showcase && (
            <Link to={showcase.browse_url} className="link-btn">
              See these on the Products page →
            </Link>
          )}
          <button className="link-btn" onClick={clearResults}>
            Hide
          </button>
        </div>
      </div>
      <div className="picks-row">
        {cards.map((p, i) => (
          <ProductCard key={p.product_id} product={p} picked={pickIds.has(p.product_id)} mySize={mySize} index={i} />
        ))}
      </div>
    </section>
  )
}
