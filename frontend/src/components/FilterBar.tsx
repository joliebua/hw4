import { SIZES, categoryLabel, price } from '../format'
import type { Filters, Sort, StoreFacets } from '../types'

interface Props {
  facets: StoreFacets | null
  filters: Filters
  onChange: (patch: Partial<Filters>) => void
  onClear: () => void
}

const PRICE_STEPS = [40, 60, 80]

export default function FilterBar({ facets, filters, onChange, onClear }: Props) {
  const active =
    filters.q || filters.category || filters.collection || filters.size || filters.maxPrice != null || filters.inStock

  return (
    <section className="filters" aria-label="Filter products">
      {filters.collection && (
        <div className="collection-banner">
          <span>
            Collection: <strong>{facets?.collections.find((c) => c.key === filters.collection)?.label ?? filters.collection}</strong>
          </span>
          <button className="link-btn" onClick={() => onChange({ collection: '' })}>
            Show everything
          </button>
        </div>
      )}
      <div className="chip-row" role="group" aria-label="Category">
        <button className={`chip${!filters.category ? ' on' : ''}`} onClick={() => onChange({ category: '' })}>
          All
        </button>
        {facets?.categories.map((c) => (
          <button
            key={c.value}
            className={`chip${filters.category === c.value ? ' on' : ''}`}
            onClick={() => onChange({ category: filters.category === c.value ? '' : c.value })}
          >
            {categoryLabel(c.value)} <span className="chip-count">{c.count}</span>
          </button>
        ))}
      </div>

      <div className="filter-row">
        <div className="filter-group" role="group" aria-label="Size">
          <span className="filter-label">Size</span>
          {SIZES.map((s) => (
            <button
              key={s}
              className={`size-chip${filters.size === s ? ' on' : ''}`}
              onClick={() => onChange({ size: filters.size === s ? '' : s })}
              aria-pressed={filters.size === s}
            >
              {s}
            </button>
          ))}
        </div>

        <div className="filter-group" role="group" aria-label="Price">
          <span className="filter-label">Under</span>
          {PRICE_STEPS.map((p) => (
            <button
              key={p}
              className={`size-chip${filters.maxPrice === p ? ' on' : ''}`}
              onClick={() => onChange({ maxPrice: filters.maxPrice === p ? null : p })}
              aria-pressed={filters.maxPrice === p}
            >
              {price(p)}
            </button>
          ))}
        </div>

        <label className="toggle">
          <input type="checkbox" checked={filters.inStock} onChange={(e) => onChange({ inStock: e.target.checked })} />
          In stock only
        </label>

        <label className="sort">
          <span className="filter-label">Sort</span>
          <select value={filters.sort} onChange={(e) => onChange({ sort: e.target.value as Sort })}>
            <option value="relevance">Best match</option>
            <option value="name">Name</option>
            <option value="price_asc">Price: low to high</option>
            <option value="price_desc">Price: high to low</option>
          </select>
        </label>

        {active && (
          <button className="link-btn" onClick={onClear}>
            Clear all
          </button>
        )}
      </div>
    </section>
  )
}
