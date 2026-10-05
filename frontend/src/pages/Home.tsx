import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchProducts } from '../api'
import Bulldog from '../components/Bulldog'
import ProductCard from '../components/ProductCard'
import { price } from '../format'
import { useShop } from '../shop'
import type { ProductSummary } from '../types'

const FEATURED = [
  'super-heavyweight-crewneck-arched-yale-crest',
  'yale-mom-hoodie',
  '2025-yale-vs-harvard-t-shirt',
  'district-vit-hoodie-vintage-bulldog',
]

const SHOP_BY = [
  {
    title: 'For the whole family',
    blurb: 'Mom, Dad, Grandpa, Aunt, Cousin — a hoodie with their name on the Yale family tree.',
    to: '/products?collection=family',
    pennant: 'FAMILY',
  },
  {
    title: 'Game day',
    blurb: 'Hockey, squash, sailing, soccer and more. Cheer for your team in the right gear.',
    to: '/products?collection=sports',
    pennant: 'GAME DAY',
  },
  {
    title: 'Your residential college',
    blurb: 'From Saybrook to Grace Hopper, wear the college you call home.',
    to: '/products?collection=colleges',
    pennant: 'COLLEGES',
  },
  {
    title: 'Grad & professional schools',
    blurb: 'Law, Medicine, Nursing, Art, Architecture and more — for the late nights that made you.',
    to: '/products?collection=schools',
    pennant: 'GRAD SCHOOLS',
  },
]

const PROMISES = [
  {
    title: 'Every corner of Yale',
    text: 'Colleges, teams, schools and family designs. Whatever your Yale looks like, we probably stock it.',
  },
  {
    title: 'Cozy is the dress code',
    text: 'Heavyweight crewnecks, soft tri-blend tees and hoodies made for library marathons and cold bleachers.',
  },
  {
    title: 'Straight answers',
    text: 'Handsome Dan, our shop bulldog, checks real prices and real stock before he answers. No guesses.',
  },
]

export default function Home() {
  const { facets, setChatOpen, sendChat } = useShop()
  const [featured, setFeatured] = useState<ProductSummary[]>([])

  useEffect(() => {
    fetchProducts().then(
      (all) => setFeatured(FEATURED.map((id) => all.find((p) => p.product_id === id)).filter((p) => p !== undefined)),
      () => undefined,
    )
  }, [])

  return (
    <div className="page home">
      <section className="storefront" aria-label="Campus Customs storefront">
        <div className="awning" aria-hidden />
        <div className="storefront-body">
          <div className="hero-copy">
            <div className="shop-sign">
              <span>Campus Customs</span>
              <span className="shop-sign-sub">Yale apparel · 57 Broadway</span>
            </div>
            <h1>
              Bulldog pride, worn <em>your</em> way.
            </h1>
            <p>
              {facets ? `${facets.product_count} pieces` : 'Pieces'} for students, alumni, families and fans, from your
              first week on Old Campus to your tenth reunion. Find your college, your team or your school, or ask Handsome
              Dan. He knows every size on the shelf.
            </p>
            <div className="hero-actions">
              <Link to="/products" className="btn btn-primary">
                Shop the collection
              </Link>
              <button className="btn btn-ghost" onClick={() => setChatOpen(true)}>
                <Bulldog size={22} /> Ask Handsome Dan
              </button>
            </div>
          </div>

          <div className="window" aria-label="In the window">
            <div className="window-rail" aria-hidden />
            {featured.slice(0, 3).map((p, i) => (
              <Link
                key={p.product_id}
                to={`/products/${encodeURIComponent(p.product_id)}`}
                className={`hanger hanger-${i}`}
                aria-label={`${p.name}, ${price(p.price)}`}
              >
                <span className="hanger-hook" aria-hidden />
                <img src={p.image_url} alt="" />
                <span className="hanger-tag">{price(p.price)}</span>
              </Link>
            ))}
            <p className="window-decal" aria-hidden>
              <span>Come on in</span>
              <small>Open · 57 Broadway</small>
            </p>
            <button className="window-dan" onClick={() => setChatOpen(true)} aria-label="Chat with Handsome Dan">
              <Bulldog size={84} animated />
              <span className="window-dan-bubble">Need a size? Ask me!</span>
            </button>
          </div>
        </div>
      </section>

      <section aria-label="Shop by">
        <div className="section-head">
          <h2>Find your people</h2>
        </div>
        <div className="tiles">
          {SHOP_BY.map((t) => (
            <Link key={t.title} to={t.to} className="tile">
              <span className="pennant" aria-hidden>
                {t.pennant}
              </span>
              <h3>{t.title}</h3>
              <p>{t.blurb}</p>
              <span className="tile-cta">Shop now →</span>
            </Link>
          ))}
        </div>
      </section>

      {featured.length > 0 && (
        <section aria-label="Featured products">
          <div className="section-head">
            <h2>Fresh off the rack</h2>
            <Link to="/products" className="link-btn">
              See everything →
            </Link>
          </div>
          <div className="grid">
            {featured.map((p, i) => (
              <ProductCard key={p.product_id} product={p} index={i} />
            ))}
          </div>
        </section>
      )}

      <section className="promises" aria-label="Why Campus Customs">
        {PROMISES.map((p) => (
          <div key={p.title} className="promise">
            <h3>{p.title}</h3>
            <p>{p.text}</p>
          </div>
        ))}
      </section>

      <section className="cta-band">
        <div>
          <h2>Shopping for someone else?</h2>
          <p>Tell Handsome Dan who it's for and their size. He'll fetch real options that are actually in stock.</p>
        </div>
        <button className="btn btn-primary" onClick={() => sendChat("I'm shopping for a gift — what would you suggest?")}>
          🎁 Get gift ideas from Dan
        </button>
      </section>
    </div>
  )
}
