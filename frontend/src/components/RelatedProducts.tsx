import { useEffect, useState } from 'react'
import { fetchRelated } from '../api'
import type { ProductSummary } from '../types'
import ProductCard from './ProductCard'

interface Props {
  productId: string
  mySize: string | null
}

/** "You might also like": similar items under the product details. */
export default function RelatedProducts({ productId, mySize }: Props) {
  const [items, setItems] = useState<ProductSummary[] | null>(null)

  useEffect(() => {
    let cancelled = false
    setItems(null)
    fetchRelated(productId, mySize, 6).then(
      (rows) => !cancelled && setItems(rows),
      () => !cancelled && setItems([]),
    )
    return () => {
      cancelled = true
    }
  }, [productId, mySize])

  if (items === null || items.length === 0) return null

  return (
    <section className="related" aria-label="You might also like">
      <div className="section-head">
        <div>
          <h2>You might also like</h2>
          <p className="results-meta">
            Similar picks{mySize ? `, with ones in your size (${mySize}) first` : ''}.
          </p>
        </div>
      </div>
      <div className="related-row">
        {items.map((p, i) => (
          <ProductCard key={p.product_id} product={p} mySize={mySize} index={i} />
        ))}
      </div>
    </section>
  )
}
