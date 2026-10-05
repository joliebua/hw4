import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchProducts } from '../api'
import FilterBar from '../components/FilterBar'
import ProductCard from '../components/ProductCard'
import { useShop } from '../shop'
import type { Filters, ProductSummary, Sort } from '../types'

const SORTS: Sort[] = ['relevance', 'name', 'price_asc', 'price_desc']

/** Every filter lives in the URL, so Home's tiles, Handsome Dan's "See these on the
 *  Products page" links, shared links and the Back button all just work. */
function filtersFrom(params: URLSearchParams): Filters {
  const maxPrice = Number(params.get('max_price'))
  const sort = params.get('sort') as Sort
  return {
    q: params.get('q') ?? '',
    category: params.get('category') ?? '',
    collection: params.get('collection') ?? '',
    size: (params.get('size') ?? '').toUpperCase(),
    maxPrice: params.has('max_price') && maxPrice > 0 ? maxPrice : null,
    inStock: params.get('in_stock') === 'true',
    sort: SORTS.includes(sort) ? sort : 'relevance',
  }
}

function paramsFrom(f: Filters): URLSearchParams {
  const p = new URLSearchParams()
  if (f.q.trim()) p.set('q', f.q)
  if (f.category) p.set('category', f.category)
  if (f.collection) p.set('collection', f.collection)
  if (f.size) p.set('size', f.size)
  if (f.maxPrice != null) p.set('max_price', String(f.maxPrice))
  if (f.inStock) p.set('in_stock', 'true')
  if (f.sort !== 'relevance') p.set('sort', f.sort)
  return p
}

export default function Products() {
  const { facets, picks, sendChat, mySize } = useShop()
  const [params, setParams] = useSearchParams()
  const filters = useMemo(() => filtersFrom(params), [params])

  const [searchText, setSearchText] = useState(filters.q)
  const [products, setProducts] = useState<ProductSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const pickIds = new Set(picks.map((p) => p.product_id))

  // Keep the search box in step when the URL changes from outside (a link, Back).
  useEffect(() => setSearchText(filters.q), [filters.q])

  // Typing updates the URL after a short pause.
  useEffect(() => {
    if (searchText === filters.q) return
    const t = window.setTimeout(() => setParams(paramsFrom({ ...filters, q: searchText }), { replace: true }), 250)
    return () => window.clearTimeout(t)
  }, [searchText, filters, setParams])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchProducts(filters)
      .then((rows) => {
        if (cancelled) return
        setProducts(rows)
        setLoadError('')
      })
      .catch((e: Error) => !cancelled && setLoadError(e.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [filters])

  function updateFilters(patch: Partial<Filters>) {
    setParams(paramsFrom({ ...filters, q: searchText, ...patch }))
  }

  return (
    <div className="page products">
      <div className="page-head">
        <div>
          <h1>Shop the collection</h1>
          <p className="page-sub">Live prices and stock, straight from the shop floor.</p>
        </div>
        <div className="search">
          <input
            type="search"
            placeholder="Search hoodies, colleges, sports…"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            aria-label="Search products"
          />
        </div>
      </div>

      <FilterBar
        facets={facets}
        filters={filters}
        onChange={updateFilters}
        onClear={() => {
          setSearchText('')
          setParams(new URLSearchParams())
        }}
      />

      <div className="result-row">
        <span className="result-count">{loading ? 'Loading…' : `${products.length} items`}</span>
      </div>

      {loadError && <p className="form-error">Couldn't load products: {loadError}</p>}
      {!loading && !loadError && products.length === 0 && (
        <p className="empty">
          No matches. Try fewer filters — or{' '}
          <button className="link-btn" onClick={() => sendChat(`I'm looking for ${filters.q || 'something special'}`)}>
            ask Dan
          </button>
          .
        </p>
      )}
      <div className={`grid${loading ? ' dim' : ''}`}>
        {products.map((p, i) => (
          <ProductCard key={p.product_id} product={p} picked={pickIds.has(p.product_id)} mySize={mySize} index={i} />
        ))}
      </div>
    </div>
  )
}
