import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { login, register } from '../api'
import { useShop } from '../shop'
import type { RegisterForm } from '../types'

interface Props {
  mode: 'login' | 'register'
}

const MIN_PASSWORD = 8

const EMPTY: RegisterForm = { first_name: '', last_name: '', email: '', password: '', confirm_password: '' }

function PasswordField({
  label,
  value,
  onChange,
  autoComplete,
  hint,
  invalid,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  autoComplete: string
  hint?: string
  invalid?: boolean
}) {
  const [show, setShow] = useState(false)
  return (
    <label>
      {label}
      <span className="password-wrap">
        <input
          type={show ? 'text' : 'password'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          required
          maxLength={128}
          autoComplete={autoComplete}
          aria-invalid={invalid || undefined}
        />
        <button type="button" className="show-toggle" onClick={() => setShow((s) => !s)} aria-label={show ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}>
          {show ? 'Hide' : 'Show'}
        </button>
      </span>
      {hint && <small className={invalid ? 'hint-bad' : undefined}>{hint}</small>}
    </label>
  )
}

export default function AuthForm({ mode }: Props) {
  const { user, authChecked, onAuthed } = useShop()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/products'

  const [form, setForm] = useState<RegisterForm>(EMPTY)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k: keyof RegisterForm) => (v: string) => setForm((f) => ({ ...f, [k]: v }))

  const isRegister = mode === 'register'
  const tooShort = isRegister && form.password.length > 0 && form.password.length < MIN_PASSWORD
  const mismatch = isRegister && form.confirm_password.length > 0 && form.confirm_password !== form.password

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (isRegister) {
      if (form.password.length < MIN_PASSWORD) return setError(`Password must be at least ${MIN_PASSWORD} characters.`)
      if (form.password !== form.confirm_password) return setError("Passwords don't match.")
    }
    setBusy(true)
    try {
      const u = isRegister ? await register(form) : await login(form.email, form.password)
      onAuthed(u)
      navigate(from, { replace: true })
    } catch (err) {
      setError((err as Error).message)
      // Never leave a typed password sitting in the form after a failed attempt.
      setForm((f) => ({ ...f, password: '', confirm_password: '' }))
    } finally {
      setBusy(false)
    }
  }

  if (!authChecked) return <div className="auth-card">Loading…</div>

  if (user) {
    return (
      <div className="auth-card">
        <h1>You're logged in</h1>
        <p className="auth-sub">
          Logged in as <strong>{user.name}</strong> ({user.email}).
        </p>
        <Link to="/products" className="btn btn-primary">
          Keep shopping
        </Link>
      </div>
    )
  }

  return (
    <div className="auth-card">
      <h1>{isRegister ? 'Join the Campus Customs crew' : 'Welcome back'}</h1>
      <p className="auth-sub">
        {isRegister
          ? 'Create an account to pick up where you left off and get a personal hello from Handsome Dan.'
          : 'Log in with your email and password.'}
      </p>

      <form onSubmit={submit} className="auth-form">
        {isRegister && (
          <div className="name-row">
            <label>
              First name
              <input value={form.first_name} onChange={(e) => set('first_name')(e.target.value)} required maxLength={50} autoComplete="given-name" />
            </label>
            <label>
              Last name
              <input value={form.last_name} onChange={(e) => set('last_name')(e.target.value)} required maxLength={50} autoComplete="family-name" />
            </label>
          </div>
        )}
        <label>
          Email
          <input type="email" value={form.email} onChange={(e) => set('email')(e.target.value)} required autoComplete="email" />
        </label>
        <PasswordField
          label="Password"
          value={form.password}
          onChange={set('password')}
          autoComplete={isRegister ? 'new-password' : 'current-password'}
          hint={isRegister ? `At least ${MIN_PASSWORD} characters. A short phrase is easy to remember and hard to guess.` : undefined}
          invalid={tooShort}
        />
        {isRegister && (
          <PasswordField
            label="Confirm password"
            value={form.confirm_password}
            onChange={set('confirm_password')}
            autoComplete="new-password"
            hint={mismatch ? "Passwords don't match yet." : undefined}
            invalid={mismatch}
          />
        )}

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button className="btn btn-primary" disabled={busy}>
          {busy ? 'One moment…' : isRegister ? 'Create account' : 'Log in'}
        </button>
      </form>

      <p className="auth-switch">
        {isRegister ? (
          <>
            Already have an account?{' '}
            <Link to="/login" state={location.state}>
              Log in
            </Link>
          </>
        ) : (
          <>
            New here?{' '}
            <Link to="/create-account" state={location.state}>
              Create an account
            </Link>
          </>
        )}
      </p>
    </div>
  )
}
