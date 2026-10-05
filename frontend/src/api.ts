import type {
  Filters,
  ProductDetail,
  ProductSummary,
  RegisterForm,
  SizeRecommendation,
  StoreFacets,
  User,
} from './types'

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') || ''

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body) headers.set('Content-Type', 'application/json')

  // The session lives in an HttpOnly cookie the browser sends automatically;
  // page JavaScript never sees or stores it.
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers, credentials: 'include' })
  if (!res.ok) {
    let message = `Something went wrong (HTTP ${res.status}).`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail))
        message = body.detail.map((d: { msg: string }) => d.msg.replace(/^Value error, /, '')).join(' ')
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message)
  }
  return (res.status === 204 ? undefined : await res.json()) as T
}

// ---- products ---------------------------------------------------------------

export function fetchProducts(f: Partial<Filters> = {}): Promise<ProductSummary[]> {
  const params = new URLSearchParams()
  if (f.q?.trim()) params.set('q', f.q.trim())
  if (f.category) params.set('category', f.category)
  if (f.collection) params.set('collection', f.collection)
  if (f.size) params.set('size', f.size)
  if (f.maxPrice != null) params.set('max_price', String(f.maxPrice))
  if (f.inStock) params.set('in_stock', 'true')
  if (f.sort) params.set('sort', f.sort)
  return request(`/api/products?${params}`)
}

export const fetchProduct = (id: string) => request<ProductDetail>(`/api/products/${encodeURIComponent(id)}`)
export const fetchFacets = () => request<StoreFacets>('/api/facets')

/** "You might also like": similar products, preferring ones in stock in `size`. */
export function fetchRelated(id: string, size: string | null, limit = 6): Promise<ProductSummary[]> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (size) params.set('size', size)
  return request(`/api/products/${encodeURIComponent(id)}/related?${params}`)
}

// ---- sizes ------------------------------------------------------------------

/** Signed-in shoppers: saved size + history. Guests: pass their browser "My size". */
export function fetchSizeRecommendation(id: string, mySize: string | null): Promise<SizeRecommendation> {
  const params = new URLSearchParams()
  if (mySize) params.set('my_size', mySize)
  return request(`/api/products/${encodeURIComponent(id)}/size-recommendation?${params}`)
}

export const fetchMySize = () => request<{ size: string | null }>('/api/me/size')
export const saveMySize = (size: string | null) =>
  request<{ size: string | null }>('/api/me/size', { method: 'PUT', body: JSON.stringify({ size }) })
/** A signed-in shopper picked a size on a product page (feeds their size history). */
export const recordSizePick = (productId: string, size: string) =>
  request<void>('/api/me/size-history', { method: 'POST', body: JSON.stringify({ product_id: productId, size }) })

// ---- accounts ---------------------------------------------------------------

export const register = (form: RegisterForm) =>
  request<User>('/api/auth/register', { method: 'POST', body: JSON.stringify(form) })

export const login = (email: string, password: string) =>
  request<User>('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })

export const logout = () => request<void>('/api/auth/logout', { method: 'POST' })
export const fetchMe = () => request<User | null>('/api/auth/me')
