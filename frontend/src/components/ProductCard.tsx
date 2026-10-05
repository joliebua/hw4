import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { SIZES, categoryLabel, price } from '../format'
import type { ProductSummary } from '../types'

interface Props {
  product: ProductSummary
  picked?: boolean
  /** Show whether the shopper's size is in stock. */
  mySize?: string | null
  /** Position in its grid, for a staggered entrance. */
  index?: number
}

export function StockBadge({ product }: { product: ProductSummary }) {
  const cls = product.stock_status.replace(' ', '-')
  const label =
    product.stock_status === 'low stock' ? `Only ${product.total_stock} left` : product.stock_status
  return <span className={`stock-badge ${cls}`}>{label}</span>
}

/** XS–XXL at a glance: sizes in stock are solid, sold-out sizes are struck through. */
function SizeRun({ product, mySize }: { product: ProductSummary; mySize?: string | null }) {
  return (
    <span className="size-run" aria-label={`In stock: ${product.sizes_in_stock.join(', ') || 'none'}`}>
      {SIZES.map((s) => (
        <span
          key={s}
          className={`size-run-item${product.sizes_in_stock.includes(s) ? '' : ' gone'}${mySize === s ? ' mine' : ''}`}
        >
          {s}
        </span>
      ))}
    </span>
  )
}

/** A product tile; the whole card links to the single-item page. */
export default function ProductCard({ product, picked, mySize, index = 0 }: Props) {
  const soldOut = product.stock_status === 'sold out'
  return (
    <Link
      to={`/products/${encodeURIComponent(product.product_id)}`}
      className={`product-card${picked ? ' picked' : ''}${soldOut ? ' sold-out' : ''}`}
      style={{ '--i': Math.min(index, 12) } as CSSProperties}
    >
      <div className="card-image">
        <img src={product.image_url} alt={product.name} loading="lazy" />
        {picked && <span className="pick-ribbon">🐾 Dan's pick</span>}
        {soldOut && (
          <span className="sold-stamp" aria-hidden>
            Sold out
          </span>
        )}
        {!soldOut && (
          <span className="stock-sticker">
            <StockBadge product={product} />
          </span>
        )}
        <span className="hang-tag">{price(product.price)}</span>
      </div>
      <div className="card-body">
        <span className="card-category">{categoryLabel(product.category)}</span>
        <h3>{product.name}</h3>
        <p className="card-desc">{product.short_description}</p>
        <div className="card-meta">
          <SizeRun product={product} mySize={mySize} />
        </div>
        {mySize && (
          <p className={`card-my-size${product.sizes_in_stock.includes(mySize) ? '' : ' out'}`}>
            {product.sizes_in_stock.includes(mySize) ? `✓ In your size (${mySize})` : `Sold out in ${mySize}`}
          </p>
        )}
      </div>
    </Link>
  )
}
