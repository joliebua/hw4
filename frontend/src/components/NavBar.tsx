import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { useShop } from '../shop'
import Bulldog from './Bulldog'

const PAGES = [
  { to: '/', label: 'Home', end: true },
  { to: '/products', label: 'Products', end: false },
  { to: '/about', label: 'About Us', end: false },
]

export default function NavBar() {
  const { user, signOut } = useShop()
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()

  // Close the mobile menu whenever the route changes.
  useEffect(() => setMenuOpen(false), [location.pathname])

  const linkClass = ({ isActive }: { isActive: boolean }) => `nav-link${isActive ? ' active' : ''}`

  return (
    <header className="topbar">
      <Link to="/" className="brand" aria-label="Campus Customs home">
        <span className="brand-mark" aria-hidden>
          <Bulldog size={40} />
        </span>
        <span className="brand-words">
          <span className="brand-name">Campus Customs</span>
          <span className="brand-sub">57 Broadway · New Haven</span>
        </span>
      </Link>

      <button
        className="menu-toggle"
        onClick={() => setMenuOpen((o) => !o)}
        aria-expanded={menuOpen}
        aria-controls="site-nav"
        aria-label="Menu"
      >
        {menuOpen ? '×' : '☰'}
      </button>

      <nav id="site-nav" className={`site-nav${menuOpen ? ' open' : ''}`} aria-label="Main">
        <div className="nav-pages">
          {PAGES.map((p) => (
            <NavLink key={p.to} to={p.to} end={p.end} className={linkClass}>
              {p.label}
            </NavLink>
          ))}
        </div>

        <div className="nav-account">
          {user ? (
            <>
              <span className="hello">Hi, {user.first_name}</span>
              <button className="nav-link" onClick={signOut}>
                Sign out
              </button>
            </>
          ) : (
            <>
              <NavLink to="/login" className={linkClass}>
                Log in
              </NavLink>
              <NavLink to="/create-account" className="btn btn-primary small">
                Create account
              </NavLink>
            </>
          )}
        </div>
      </nav>
    </header>
  )
}
