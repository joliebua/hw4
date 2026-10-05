import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import * as api from './api'
import { askDan, loadChatHistory, resetConversation } from './chat'
import type { ChatMessage, ProductSummary, Showcase, StoreFacets, User, ViewingProduct } from './types'

/** App-wide state shared by every page: store facets, account, and the chat. */
interface Shop {
  facets: StoreFacets | null
  user: User | null
  authChecked: boolean
  onAuthed: (user: User) => void
  signOut: () => Promise<void>

  chatOpen: boolean
  setChatOpen: (open: boolean | ((o: boolean) => boolean)) => void
  messages: ChatMessage[]
  chatBusy: boolean
  sendChat: (text: string) => Promise<void>
  resetChat: () => void
  picks: ProductSummary[]
  showcase: Showcase | null
  clearResults: () => void

  /** "My size": saved to the account when signed in, kept in this browser for guests. */
  mySize: string | null
  setMySize: (size: string | null) => void

  /** The product open on a product page, reported by ProductPage. */
  viewing: ViewingProduct | null
  setViewing: (v: ViewingProduct | null) => void

  toast: string
  flash: (text: string) => void
}

const ShopContext = createContext<Shop | null>(null)

let nextMessageId = 1

const MY_SIZE_KEY = 'campus-customs-my-size'
const browserSize = () => localStorage.getItem(MY_SIZE_KEY)

export function ShopProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const location = useLocation()

  const [facets, setFacets] = useState<StoreFacets | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [authChecked, setAuthChecked] = useState(false)

  const [chatOpen, setChatOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [chatBusy, setChatBusy] = useState(false)
  const [picks, setPicks] = useState<ProductSummary[]>([])
  const [showcase, setShowcase] = useState<Showcase | null>(null)

  const [viewing, setViewing] = useState<ViewingProduct | null>(null)
  const [mySize, setMySizeState] = useState<string | null>(browserSize)
  const [toast, setToast] = useState('')

  const flash = useCallback((text: string) => {
    setToast(text)
    window.setTimeout(() => setToast(''), 2600)
  }, [])

  useEffect(() => {
    api.fetchFacets().then(setFacets, () => undefined)
    // null means "browsing as a guest".
    api
      .fetchMe()
      .then(setUser, () => setUser(null))
      .finally(() => setAuthChecked(true))
  }, [])

  // Signed-in shoppers get their saved chat back (and Handsome Dan remembers it);
  // signing out clears the panel.
  useEffect(() => {
    if (!authChecked) return
    if (!user) {
      setMessages([])
      setConversationId(null)
      setPicks([])
      setShowcase(null)
      return
    }
    let cancelled = false
    loadChatHistory().then(
      (h) => {
        if (cancelled) return
        setConversationId(h.conversation_id)
        setMessages(
          h.messages.map((m) => ({
            id: nextMessageId++,
            role: m.role,
            text: m.content,
            products: m.products,
            restored: true,
          })),
        )
      },
      () => undefined,
    )
    return () => {
      cancelled = true
    }
  }, [user, authChecked])

  // "My size": guests use this browser's copy. Signed-in shoppers use their
  // account's; if the account has none yet, the size picked as a guest moves over.
  useEffect(() => {
    if (!authChecked) return
    if (!user) {
      setMySizeState(browserSize())
      return
    }
    api.fetchMySize().then(
      ({ size }) => {
        const local = browserSize()
        if (!size && local) api.saveMySize(local).then(() => setMySizeState(local), () => undefined)
        else setMySizeState(size)
      },
      () => undefined,
    )
  }, [user, authChecked])

  const setMySize = useCallback(
    (size: string | null) => {
      setMySizeState(size)
      if (size) localStorage.setItem(MY_SIZE_KEY, size)
      else localStorage.removeItem(MY_SIZE_KEY)
      if (user) api.saveMySize(size).catch(() => flash("Couldn't save your size. Please try again."))
    },
    [user, flash],
  )

  const onAuthed = useCallback(
    (u: User) => {
      setUser(u)
      flash(`Welcome, ${u.first_name}! ✿`)
    },
    [flash],
  )

  const signOut = useCallback(async () => {
    await api.logout().catch(() => undefined)
    setUser(null)
    flash('Signed out. Come back soon!')
    navigate('/')
  }, [flash, navigate])

  const sendChat = useCallback(
    async (text: string) => {
      if (chatBusy) return
      setChatOpen(true)
      setMessages((m) => [...m, { id: nextMessageId++, role: 'user', text }])
      setChatBusy(true)
      try {
        // Tell Handsome Dan where the shopper is, so "this" on a product page makes sense.
        const onProductPage = viewing && location.pathname === `/products/${viewing.product_id}`
        const res = await askDan(text, conversationId, {
          path: location.pathname + location.search,
          product_id: onProductPage ? viewing.product_id : null,
          selected_size: onProductPage ? viewing.selected_size : null,
          my_size: mySize,
        })
        setConversationId(res.conversation_id)
        setMessages((m) => [...m, { id: nextMessageId++, role: 'assistant', text: res.reply, products: res.products }])
        // Search results and picks go on the page; a plain answer leaves the page as it was.
        if (res.showcase) {
          setShowcase(res.showcase)
          setPicks(res.products)
        } else if (res.products.length > 0) {
          setShowcase(null)
          setPicks(res.products)
        }
      } catch (e) {
        setMessages((m) => [...m, { id: nextMessageId++, role: 'assistant', text: (e as Error).message, error: true }])
      } finally {
        setChatBusy(false)
      }
    },
    [chatBusy, conversationId, viewing, location, mySize],
  )

  const resetChat = useCallback(() => {
    if (conversationId) resetConversation(conversationId).catch(() => undefined)
    setConversationId(null)
    setMessages([])
    setPicks([])
    setShowcase(null)
  }, [conversationId])

  const value: Shop = {
    facets,
    user,
    authChecked,
    onAuthed,
    signOut,
    chatOpen,
    setChatOpen,
    messages,
    chatBusy,
    sendChat,
    resetChat,
    picks,
    showcase,
    clearResults: () => {
      setPicks([])
      setShowcase(null)
    },
    mySize,
    setMySize,
    viewing,
    setViewing,
    toast,
    flash,
  }

  return <ShopContext.Provider value={value}>{children}</ShopContext.Provider>
}

export function useShop(): Shop {
  const shop = useContext(ShopContext)
  if (!shop) throw new Error('useShop must be used inside <ShopProvider>')
  return shop
}
