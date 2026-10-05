import { useEffect } from 'react'
import { Link, Route, Routes, useLocation } from 'react-router-dom'
import AnnouncementBar from './components/AnnouncementBar'
import AuthForm from './components/AuthForm'
import ChatPanel from './components/ChatPanel'
import Bulldog from './components/Bulldog'
import ChatResults from './components/ChatResults'
import NavBar from './components/NavBar'
import About from './pages/About'
import Home from './pages/Home'
import ProductPage from './pages/ProductPage'
import Products from './pages/Products'
import { useShop } from './shop'
import './App.css'
import './storefront.css'

const TITLES: Record<string, string> = {
  '/': 'Campus Customs — Bulldog pride, worn your way',
  '/products': 'Products · Campus Customs',
  '/about': 'About Us · Campus Customs',
  '/login': 'Log in · Campus Customs',
  '/create-account': 'Create account · Campus Customs',
}

function NotFound() {
  return (
    <div className="page empty">
      <h1>Page not found</h1>
      <p>
        That page wandered off. <Link to="/">Head home</Link> or <Link to="/products">browse the collection</Link>.
      </p>
    </div>
  )
}

export default function App() {
  const { toast } = useShop()
  const { pathname } = useLocation()
  const onAuthPage = pathname === '/login' || pathname === '/create-account'

  useEffect(() => {
    // Product pages set their own title once the item loads.
    if (TITLES[pathname]) document.title = TITLES[pathname]
    window.scrollTo(0, 0)
  }, [pathname])

  return (
    <div className="app">
      <AnnouncementBar />
      <NavBar />

      <main className="main">
        {!onAuthPage && <ChatResults />}
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/products" element={<Products />} />
          <Route path="/products/:productId" element={<ProductPage />} />
          <Route path="/about" element={<About />} />
          <Route path="/login" element={<div className="page auth-page"><AuthForm mode="login" /></div>} />
          <Route path="/create-account" element={<div className="page auth-page"><AuthForm mode="register" /></div>} />
          <Route path="*" element={<NotFound />} />
        </Routes>

        <footer className="footer">
          <span>
            <Bulldog size={28} /> Campus Customs
          </span>
          <nav aria-label="Footer">
            <Link to="/products">Products</Link>
            <Link to="/about">About Us</Link>
            <span>57 Broadway, New Haven, CT 06511</span>
          </nav>
        </footer>
      </main>

      <ChatPanel />

      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
    </div>
  )
}
