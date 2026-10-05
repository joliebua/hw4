export type StockStatus = 'in stock' | 'low stock' | 'sold out'

/** One product card on the Products page (GET /api/products). */
export interface ProductSummary {
  product_id: string
  name: string
  category: string
  garment_type: string
  price: number
  short_description: string
  image_url: string
  total_stock: number
  stock_status: StockStatus
  sizes_in_stock: string[]
}

export interface SizeStock {
  size: string
  quantity: number
}

/** The single-item page (GET /api/products/{id}). */
export interface ProductDetail extends ProductSummary {
  description: string
  colors: string[]
  search_tags: string[]
  stock_by_size: SizeStock[]
}

export interface Facet {
  value: string
  count: number
}

export interface Collection {
  key: string
  label: string
  count: number
}

export interface StoreFacets {
  categories: Facet[]
  collections: Collection[]
  product_count: number
  min_price: number
  max_price: number
}

export interface User {
  id: number
  first_name: string
  last_name: string
  name: string
  email: string
}

export interface RegisterForm {
  first_name: string
  last_name: string
  email: string
  password: string
  confirm_password: string
}

/** Search results Handsome Dan put on the page as product cards. */
export interface Showcase {
  title: string
  total_matches: number
  products: ProductSummary[]
  browse_url: string
}

export interface ChatResponse {
  conversation_id: string
  reply: string
  products: ProductSummary[]
  showcase: Showcase | null
  tools_used: string[]
}

export interface ChatHistory {
  conversation_id: string | null
  messages: { role: 'user' | 'assistant'; content: string; products: ProductSummary[]; created_at: string }[]
}

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  text: string
  products?: ProductSummary[]
  error?: boolean
  /** Loaded from saved history (an earlier visit). */
  restored?: boolean
}

/** Where the shopper is, sent with every chat message. */
export interface PageContext {
  path: string
  product_id: string | null
  selected_size: string | null
  my_size: string | null
}

/** Which size to buy for one product, and why (GET /api/products/{id}/size-recommendation). */
export interface SizeRecommendation {
  product_id: string
  recommended_size: string | null
  usual_size: string | null
  basis: 'my_size' | 'history' | 'none'
  reason: string
  in_stock: boolean
  quantity: number | null
  exact_match: boolean
}

/** The product open on a product page (for the chat's "this"). */
export interface ViewingProduct {
  product_id: string
  name: string
  selected_size: string | null
}

export type Sort = 'relevance' | 'name' | 'price_asc' | 'price_desc'

export interface Filters {
  q: string
  category: string
  collection: string
  size: string
  maxPrice: number | null
  inStock: boolean
  sort: Sort
}
