import { Fragment, useEffect, useRef, useState, type KeyboardEvent } from 'react'
import Markdown from 'react-markdown'
import { Link, useLocation } from 'react-router-dom'
import { price } from '../format'
import { useShop } from '../shop'
import Bulldog from './Bulldog'

const SUGGESTIONS = [
  '🎁 A cosy navy hoodie for my mom',
  '🏒 Anything for a hockey fan in XL?',
  '🏛️ Show me Saybrook gear',
  "💸 What's under $40?",
]

const NUDGE_KEY = "campus-customs-dan-nudged"

/** Floating chat window anchored to the bottom-right corner of every page. */
export default function ChatPanel() {
  const { chatOpen, setChatOpen, user, authChecked, messages, chatBusy, sendChat, resetChat, viewing } = useShop()
  const { pathname } = useLocation()
  const [draft, setDraft] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)
  // A one-time "hello" bubble beside the launcher, once per browser session.
  const [nudge, setNudge] = useState(false)

  useEffect(() => {
    if (sessionStorage.getItem(NUDGE_KEY)) return
    const t = window.setTimeout(() => setNudge(true), 6000)
    return () => window.clearTimeout(t)
  }, [])

  useEffect(() => {
    if (chatOpen && nudge) setNudge(false)
    if (chatOpen) sessionStorage.setItem(NUDGE_KEY, '1')
  }, [chatOpen, nudge])
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, chatBusy])

  useEffect(() => {
    if (chatOpen) inputRef.current?.focus()
  }, [chatOpen])

  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => e.key === 'Escape' && setChatOpen(false)
    if (chatOpen) window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [chatOpen, setChatOpen])

  function submit() {
    const text = draft.trim()
    if (!text || chatBusy) return
    sendChat(text)
    setDraft('')
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  const firstName = user?.first_name
  const viewingHere = viewing && pathname === `/products/${viewing.product_id}` ? viewing : null
  const firstNew = messages.findIndex((m) => !m.restored)
  const hasRestored = messages.some((m) => m.restored)

  return (
    <div className="chat-dock">
      {chatOpen && (
        <section className="chat-panel" role="dialog" aria-label="Chat with Handsome Dan">
          <header className="chat-header">
            <div className="chat-avatar" aria-hidden>
              <Bulldog size={52} animated />
            </div>
            <div>
              <h2>Handsome Dan</h2>
              <span className="chat-status">
                <span className="online-dot" aria-hidden /> Shop bulldog · knows every size in stock
              </span>
            </div>
            <div className="chat-header-actions">
              {messages.length > 0 && (
                <button onClick={resetChat} title="Start a new chat" aria-label="Start a new chat">
                  ↺
                </button>
              )}
              <button onClick={() => setChatOpen(false)} title="Minimise chat" aria-label="Minimise chat">
                –
              </button>
            </div>
          </header>

          <div className="chat-scroll" ref={scrollRef}>
            <div className="bubble assistant intro">
              <p>
                Hi{firstName ? ` ${firstName}` : ''}! I'm Handsome Dan, the Campus Customs bulldog. 🐾 Tell me who you're
                shopping for, a college or team, or your size, and I'll sniff out what's actually on the shelf.
              </p>
            </div>

            {messages.length === 0 && (
              <div className="suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => sendChat(s)} disabled={chatBusy}>
                    {s}
                  </button>
                ))}
              </div>
            )}

                {authChecked && !user && (
              <p className="chat-note">
                Chatting as a guest. <Link to="/login">Log in</Link> to save this chat for next time.
              </p>
            )}

            {messages.map((m, i) => (
              <Fragment key={m.id}>
                {m.restored && i === 0 && <div className="chat-divider">Your earlier chats</div>}
                {hasRestored && i === firstNew && <div className="chat-divider">New messages</div>}
                {m.role === 'assistant' && (
                  <span className="bubble-avatar" aria-hidden>
                    <Bulldog size={26} />
                  </span>
                )}
                <div className={`bubble ${m.role}${m.error ? ' error' : ''}`}>
                  {m.role === 'assistant' ? <Markdown>{m.text}</Markdown> : <p>{m.text}</p>}
                  {m.products && m.products.length > 0 && (
                    <div className="bubble-products">
                      {m.products.map((p) => (
                        <Link key={p.product_id} to={`/products/${encodeURIComponent(p.product_id)}`} title={p.name}>
                          <img src={p.image_url} alt="" />
                          <span>{price(p.price)}</span>
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              </Fragment>
            ))}

            {chatBusy && (
              <div className="bubble assistant typing" aria-label="Handsome Dan is typing">
                <span>🐾</span>
                <span>🐾</span>
                <span>🐾</span>
              </div>
            )}
          </div>

          {viewingHere && (
            <div className="chat-context" title="Dan knows which product you're looking at">
              Asking about: <strong>{viewingHere.name}</strong>
              {viewingHere.selected_size && <> · size {viewingHere.selected_size}</>}
            </div>
          )}
          <div className="chat-input">
            <textarea
              ref={inputRef}
              rows={1}
              value={draft}
              placeholder="Ask about merch, sizes, prices…"
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onKeyDown}
              maxLength={2000}
              aria-label="Message Handsome Dan"
            />
            <button className="send" onClick={submit} disabled={!draft.trim() || chatBusy} aria-label="Send">
              ↑
            </button>
          </div>
        </section>
      )}

      {nudge && !chatOpen && (
        <div className="chat-nudge" role="status">
          <button className="chat-nudge-text" onClick={() => setChatOpen(true)}>
            Woof! Looking for your size or a gift? I know what's in stock.
          </button>
          <button
            className="chat-nudge-close"
            onClick={() => {
              setNudge(false)
              sessionStorage.setItem(NUDGE_KEY, '1')
            }}
            aria-label="Dismiss"
          >
            ×
          </button>
        </div>
      )}

      <button
        className={`chat-launcher${chatOpen ? ' open' : ''}`}
        onClick={() => setChatOpen((o) => !o)}
        aria-label={chatOpen ? 'Close chat' : 'Chat with Handsome Dan'}
        aria-expanded={chatOpen}
      >
        {chatOpen ? (
          <span className="launcher-close" aria-hidden>
            ×
          </span>
        ) : (
          <>
            <span className="launcher-dan" aria-hidden>
              <Bulldog size={46} animated />
            </span>
            <span className="launcher-text">
              <strong>Ask Handsome Dan</strong>
              <small>Sizes, gifts, stock</small>
            </span>
          </>
        )}
      </button>
    </div>
  )
}
