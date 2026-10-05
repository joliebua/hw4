"""Pydantic / PydanticAI structured types shared by the API, the tools and the agent."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Products — what the shop pages and the agent's tools return
# --------------------------------------------------------------------------- #


class StockStatus(str, Enum):
    IN_STOCK = "in stock"
    LOW_STOCK = "low stock"
    SOLD_OUT = "sold out"


class SizeStock(BaseModel):
    size: str
    quantity: int = Field(ge=0)


class ProductSummary(BaseModel):
    """A product card: Products grid, Dan's picks, and chat thumbnails."""

    product_id: str
    name: str
    category: str = Field(description="Browsing shelf: t-shirt, long-sleeve, crewneck, hoodie, quarter-zip, jacket.")
    garment_type: str
    price: float = Field(description="Price in US dollars, straight from the store database.")
    short_description: str
    image_url: str
    total_stock: int
    stock_status: StockStatus
    sizes_in_stock: list[str]


class ProductDetail(ProductSummary):
    """The single-item page, and the agent's detailed lookup."""

    description: str
    colors: list[str]
    search_tags: list[str]
    stock_by_size: list[SizeStock]


# --------------------------------------------------------------------------- #
# Lookup results — what the agent's tools return
#
# Leaner than the page models: no image URLs or search tags (the model can't
# use them and might paste them), but every number the model may repeat —
# price and quantities — exactly as stored, plus sold-out sizes spelled out so
# "out of stock" is never left for the model to infer.
# --------------------------------------------------------------------------- #


class SizeAvailability(BaseModel):
    size: str = Field(description="XS, S, M, L, XL or XXL.")
    quantity: int = Field(ge=0, description="Units on hand in this size.")
    in_stock: bool = Field(description="True if quantity > 0.")


class ProductMatch(BaseModel):
    """One search result: enough to recommend an item and quote it truthfully."""

    product_id: str = Field(description="Use this ID for get_product_details, check_stock and product_ids.")
    name: str
    garment_type: str = Field(description="What the item actually is, e.g. 'pullover hoodie'.")
    price: float = Field(description="Price in US dollars, exactly as stored.")
    short_description: str
    total_stock: int = Field(description="Units on hand across all sizes.")
    stock_status: StockStatus
    sizes_in_stock: list[str]
    sold_out_sizes: list[str]


class SearchResults(BaseModel):
    """search_catalog's answer: the matches, and whether the list is complete."""

    search_id: str = Field(
        description="Pass this as `show_results_of` to display this search's matches as cards on the page."
    )
    total_matches: int = Field(description="How many products match in the whole database.")
    returned: int = Field(description="How many are in `products` (may be fewer than total_matches).")
    complete: bool = Field(description="True if `products` holds every match. If false, don't call the list complete.")
    products: list[ProductMatch]


class ProductFacts(BaseModel):
    """Everything the agent may say about one product."""

    product_id: str
    name: str
    garment_type: str
    description: str = Field(description="Full product description from the catalogue.")
    colors: list[str]
    price: float = Field(description="Price in US dollars, exactly as stored.")
    total_stock: int
    stock_status: StockStatus
    stock_by_size: list[SizeAvailability] = Field(description="Quantity on hand for every size, XS to XXL.")
    sold_out_sizes: list[str]


class StockCheck(BaseModel):
    """Answer to "is it in stock (in size X)?" for one product."""

    product_id: str
    name: str
    price: float = Field(description="Price in US dollars, exactly as stored.")
    size_requested: str | None = Field(description="The size asked about, or null for all sizes.")
    quantity: int | None = Field(description="Units on hand in size_requested; null when no size was asked.")
    in_stock: bool = Field(description="Requested size has stock (or, with no size, any size has stock).")
    available_sizes: list[SizeAvailability] = Field(description="Sizes with stock, and how many of each.")
    sold_out_sizes: list[str]
    total_stock: int
    answer: str = Field(
        description="A plain-English statement of the facts. If the size is sold out, it says so; repeat it clearly."
    )


# --------------------------------------------------------------------------- #
# Sizes
# --------------------------------------------------------------------------- #

SizeName = Literal["XS", "S", "M", "L", "XL", "XXL"]


class SizeRecommendation(BaseModel):
    """Which size to buy for one product, and why (sizes.recommend)."""

    product_id: str
    recommended_size: str | None = Field(description="The size to suggest for this item; null if unknown or sold out.")
    usual_size: str | None = Field(description="The shopper's usual size, before checking this item's stock.")
    basis: Literal["my_size", "history", "none"] = Field(
        description="my_size: their saved/stated size; history: sizes they've chosen before; none: unknown."
    )
    reason: str = Field(description="Plain-English explanation, including stock. Repeat it, don't embellish.")
    in_stock: bool = Field(description="True if recommended_size has stock.")
    quantity: int | None = Field(description="Units on hand in recommended_size.")
    exact_match: bool = Field(description="False when their usual size is sold out and a neighbour was suggested.")


class MySize(BaseModel):
    size: SizeName | None


class SizeEvent(BaseModel):
    product_id: str = Field(max_length=120)
    size: SizeName


class Facet(BaseModel):
    value: str
    count: int


class Collection(BaseModel):
    key: str
    label: str
    count: int


class StoreFacets(BaseModel):
    categories: list[Facet]
    collections: list[Collection]
    product_count: int
    min_price: float
    max_price: float


# --------------------------------------------------------------------------- #
# Accounts
# --------------------------------------------------------------------------- #


class User(BaseModel):
    """What the API (and the agent) may know about a shopper. Never the password hash."""

    id: int
    first_name: str
    last_name: str
    name: str
    email: str


# --------------------------------------------------------------------------- #
# Chat
# --------------------------------------------------------------------------- #


class PageContext(BaseModel):
    """Where the shopper is on the site when they send a message (sent by the widget).

    Treated as an untrusted hint: the product ID is checked against the
    database and only known filter names are read from the path.
    """

    path: str = Field(default="/", max_length=300, description="Pathname + query, e.g. /products?category=hoodie.")
    product_id: str | None = Field(default=None, max_length=120, description="Product open on a product page.")
    selected_size: str | None = Field(default=None, max_length=4, description="Size picked on that product page.")
    my_size: str | None = Field(default=None, max_length=4, description="A guest's 'My size' from their browser.")


class ChatRequest(BaseModel):
    """A message from the website's chat widget."""

    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=64)
    page: PageContext | None = None


class ShopperProfile(BaseModel):
    """What the agent knows about who's chatting (get_shopper_profile)."""

    signed_in: bool
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    member_since: str | None = Field(default=None, description="Account creation date (YYYY-MM-DD).")
    saved_messages: int = Field(default=0, description="How many chat messages are saved for this shopper.")


class PastChatMessage(BaseModel):
    """One saved message from the shopper's earlier chats (recall_previous_chats)."""

    role: str = Field(description="'user' (the shopper) or 'assistant' (you).")
    content: str
    products_shown: list[str] = Field(default_factory=list, description="Names of products shown with that reply.")
    created_at: str


class ShopReply(BaseModel):
    """The agent's structured output for every chat turn."""

    message: str = Field(
        description=(
            "Your reply to the shopper in friendly plain prose (light markdown allowed). "
            "Every price, stock level or size availability you mention must come from a tool "
            "result in this turn."
        )
    )
    product_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Your top picks, best first, at most 6: shown as thumbnails in the chat and highlighted "
            "on the page. Only IDs returned by a tool in this turn. Empty if none fit."
        ),
    )
    show_results_of: str | None = Field(
        default=None,
        description=(
            "When the shopper asks to see or browse a type of item ('show me hoodies', 'what Saybrook "
            "stuff do you have?'), the search_id of the search_catalog result to display on the page "
            "as product cards. Null for questions about one specific item, stock checks or small talk."
        ),
    )
    results_title: str | None = Field(
        default=None,
        max_length=60,
        description="Short heading for those cards, e.g. 'Navy hoodies' or 'Gifts for Grandpa'. Required with show_results_of.",
    )


class Showcase(BaseModel):
    """A search's matches, put on the page as product cards."""

    title: str
    total_matches: int = Field(description="How many products matched in the database.")
    products: list[ProductSummary] = Field(description="Cards, rebuilt from the database (up to 24).")
    browse_url: str = Field(description="The same search on the Products page, e.g. /products?category=hoodie.")


class ChatResponse(BaseModel):
    """What POST /api/chat returns to the widget."""

    conversation_id: str
    reply: str
    products: list[ProductSummary] = Field(
        description="Cards for the agent's top picks, rebuilt from the database."
    )
    showcase: Showcase | None = Field(
        default=None, description="Search results to show on the page as product cards, if the agent chose to."
    )
    tools_used: list[str]


class ChatHistoryMessage(BaseModel):
    role: str
    content: str
    products: list[ProductSummary] = Field(default_factory=list)
    created_at: str


class ChatHistory(BaseModel):
    conversation_id: str | None
    messages: list[ChatHistoryMessage]


# --------------------------------------------------------------------------- #
# Audit trail (output/audit_trail.json — JSON Lines, append-only)
# --------------------------------------------------------------------------- #


class AuditEvent(str, Enum):
    """What kind of agent-loop step a record describes."""

    RUN_START = "run-start"
    MODEL_REQUEST = "model-request"  # tool results (or a retry note) going back to the model
    MODEL_RESPONSE = "model-response"  # the model answered: tool calls and/or final output
    RUN_END = "run-end"
    ERROR = "error"


class AuditToolCall(BaseModel):
    """One tool call or tool result within a step, summarised for the log."""

    tool_name: str = Field(description="Which tool (or 'final_result' for the structured answer).")
    args_summary: str = Field(default="", description="Arguments the model passed, truncated.")
    result_summary: str = Field(default="", description="What came back, truncated.")
    ok: bool = Field(default=True, description="False if the tool raised or the validator asked for a retry.")


class AuditEntry(BaseModel):
    """One line of output/audit_trail.json.

    JSON Lines: one entry per line, appended as each step of the agent loop
    finishes and never rewritten, so the file grows across runs and a crashed
    run still leaves every completed step on disk.
    """

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="UTC.")
    run_id: str = Field(description="Groups the entries of one chat turn.")
    conversation_id: str
    shopper: str = Field(description="'guest' or 'user:<id>'. Never an email or name.")
    page: str = Field(default="", description="Page area and product the shopper was on.")
    iteration: int = Field(description="Zero-based step within the run.")
    event: AuditEvent
    model: str
    tool_calls: list[AuditToolCall] = Field(default_factory=list)
    stop_reason: str = Field(
        description=(
            "Why this step ended: the model's finish reason (stop, tool_call, length, content_filter) on "
            "model responses; tool_results / retry on requests; completed, loop_limit, safety_filter or "
            "error on the run-end record."
        )
    )
    message_summary: str = Field(default="", description="The shopper's message (redacted, truncated), run-start only.")
    reply_summary: str = Field(default="", description="The final reply (truncated), run-end only.")
    duration_seconds: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: str = ""
