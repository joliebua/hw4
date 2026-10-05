import { useEffect, useState, type MouseEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, fetchProduct, fetchSizeRecommendation, recordSizePick } from '../api'
import { StockBadge } from '../components/ProductCard'
import Bulldog from '../components/Bulldog'
import RelatedProducts from '../components/RelatedProducts'
import SizeAdvisor from '../components/SizeAdvisor'
import { capitalize, categoryLabel, price } from '../format'
import { useShop } from '../shop'
import type { ProductDetail, SizeRecommendation } from '../types'

/** Single-item page: large photo on the left, full product text on the right. */
export default function ProductPage() {
  const { productId = '' } = useParams()
  const { sendChat, setViewing, user, authChecked, mySize, setMySize } = useShop()
  const [product, setProduct] = useState<ProductDetail | null>(null)
  const [error, setError] = useState<{ status: number; message: string } | null>(null)
  const [size, setSize] = useState('')
  // True once the shopper clicks a size themselves (then we stop auto-selecting).
  const [sizeTouched, setSizeTouched] = useState(false)
  const [rec, setRec] = useState<SizeRecommendation | null>(null)

  useEffect(() => {
    let cancelled = false
    setProduct(null)
    setError(null)
    setSize('')
    setSizeTouched(false)
    setRec(null)
    fetchProduct(productId).then(
      (p) => !cancelled && setProduct(p),
      (e: Error) => !cancelled && setError({ status: e instanceof ApiError ? e.status : 0, message: e.message }),
    )
    return () => {
      cancelled = true
    }
  }, [productId])

  useEffect(() => {
    if (product) document.title = `${product.name} · Campus Customs`
  }, [product])

  // Recommended size: refetch when the product, "My size" or the login changes.
  useEffect(() => {
    if (!product || !authChecked) return
    let cancelled = false
    fetchSizeRecommendation(product.product_id, mySize).then(
      (r) => {
        if (cancelled) return
        setRec(r)
        // Pre-select it, unless the shopper already picked a size here.
        if (!sizeTouched && r.recommended_size) setSize(r.recommended_size)
      },
      () => undefined,
    )
    return () => {
      cancelled = true
    }
    // sizeTouched is read, not a trigger.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product, mySize, user, authChecked])

  /** Zoom the photo toward the cursor (desktop hover). */
  function zoomTo(e: MouseEvent<HTMLDivElement>) {
    const box = e.currentTarget.getBoundingClientRect()
    e.currentTarget.style.setProperty('--zx', `${((e.clientX - box.left) / box.width) * 100}%`)
    e.currentTarget.style.setProperty('--zy', `${((e.clientY - box.top) / box.height) * 100}%`)
    e.currentTarget.classList.add('zooming')
  }

  /** A size the shopper chose (click or "Select M"): remember it for their size history.
   *  Clicking always selects, even an already pre-selected size, so the pick is recorded. */
  function chooseSize(next: string) {
    setSizeTouched(true)
    setSize(next)
    if (user && product) recordSizePick(product.product_id, next).catch(() => undefined)
  }

  // Tell the chat which product (and size) is on screen; clear it on leaving.
  useEffect(() => {
    if (!product) return
    setViewing({ product_id: product.product_id, name: product.name, selected_size: size || null })
  }, [product, size, setViewing])
  useEffect(() => () => setViewing(null), [setViewing])

  if (error) {
    return (
      <div className="page empty">
        <h1>{error.status === 404 ? "We couldn't find that item" : 'Something went wrong'}</h1>
        <p>
          {error.status === 404 ? 'It may have been removed from the shop.' : error.message}{' '}
          <Link to="/products">Back to all products</Link>
        </p>
      </div>
    )
  }

  if (!product) {
    return <div className="page empty">Loading…</div>
  }

  const chosen = product.stock_by_size.find((s) => s.size === size)

  return (
    <div className="page product-page">
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <Link to="/products">Products</Link>
        <span aria-hidden>›</span>
        <Link to={`/products?category=${product.category}`}>{categoryLabel(product.category)}</Link>
        <span aria-hidden>›</span>
        <span aria-current="page">{product.name}</span>
      </nav>

      <div className="product-layout">
        <div
          className="product-photo"
          onMouseMove={zoomTo}
          onMouseLeave={(e) => e.currentTarget.classList.remove('zooming')}
          title="Hover to zoom"
        >
          <img src={product.image_url} alt={product.name} />
          <span className="zoom-hint" aria-hidden>
            🔍 Hover to zoom
          </span>
        </div>

        <div className="product-info">
          <span className="card-category">{capitalize(product.garment_type)}</span>
          <h1>{product.name}</h1>

          <div className="detail-price-row">
            <span className="detail-price hang-tag big">{price(product.price)}</span>
            <StockBadge product={product} />
          </div>

          <p className="detail-desc">{product.description}</p>

          <SizeAdvisor
            recommendation={rec}
            mySize={mySize}
            signedIn={!!user}
            onSetMySize={setMySize}
            onChoose={chooseSize}
          />

          <h2 className="detail-label">Sizes &amp; stock</h2>
          <div className="size-grid" role="radiogroup" aria-label="Choose a size">
            {product.stock_by_size.map((s) => {
              const level = s.quantity === 0 ? ' out' : s.quantity <= 3 ? ' low' : ''
              return (
                <button
                  key={s.size}
                  role="radio"
                  aria-checked={size === s.size}
                  disabled={s.quantity === 0}
                  className={`size-pill${level}${size === s.size ? ' chosen' : ''}`}
                  onClick={() => chooseSize(s.size)}
                >
                  <strong>{s.size}</strong>
                  <span>{s.quantity === 0 ? 'Sold out' : `${s.quantity} left`}</span>
                </button>
              )
            })}
          </div>
          <p className="size-note">
            {chosen
              ? `Size ${chosen.size}: ${chosen.quantity} in stock.`
              : product.total_stock > 0
                ? `${product.total_stock} in stock across ${product.sizes_in_stock.length} sizes. Pick a size to check it.`
                : 'Sold out in every size right now.'}
          </p>

          <dl className="detail-specs">
            <dt>Colours</dt>
            <dd>{product.colors.map(capitalize).join(', ')}</dd>
            <dt>Style</dt>
            <dd>{capitalize(product.garment_type)}</dd>
          </dl>

          {product.search_tags.length > 0 && (
            <div className="tag-row" aria-label="Tags">
              {product.search_tags.map((t) => (
                <Link key={t} to={`/products?q=${encodeURIComponent(t)}`} className="tag">
                  {t}
                </Link>
              ))}
            </div>
          )}

          <div className="detail-actions">
            <button
              className="btn btn-primary"
              onClick={() =>
                sendChat(`Tell me about the ${product.name}${size ? ` in size ${size}` : ''} — what would go well with it?`)
              }
            >
              <Bulldog size={22} /> Ask Dan about this
            </button>
            <Link to="/products" className="btn btn-ghost">
              ← Keep browsing
            </Link>
          </div>
        </div>
      </div>

      <RelatedProducts productId={product.product_id} mySize={mySize} />
    </div>
  )
}
