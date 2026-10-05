"""Handsome Dan — the Campus Customs shopping agent (entry point and wiring).

Wires the PydanticAI agent together: the system prompt from
`prompts/prompt.md`, the tools from `tools.py`, and the structured output
type `ShopReply` from `models.py`. The model is reached through the Portkey
gateway with `PORTKEY_API_KEY` from a `.env` file.

The agent never knows a price or a stock level on its own. Its tools read the
store database, and the output validator below rejects a reply that
  * quotes a dollar amount the database didn't supply,
  * gives a stock count ("only 3 left") no tool returned,
  * looked up a sold-out size but doesn't say "sold out", or
  * shows a product card no tool returned.
The model is told what went wrong and asked to fix it.

Every turn the agent is told who is chatting and where they are:
  * `ShopDeps.user`: the signed-in shopper (id, name, email) or None for a guest;
  * `ShopDeps.page`: the page they're on, resolved from the widget's
    PageContext, including the product on screen and any size they picked.
`shopper_context` turns both into a short instruction block, and the tools in
tools.py read them (get_shopper_profile, get_viewed_product, recall_previous_chats).

Conversations are kept in memory by conversation ID. For signed-in shoppers
every turn is also saved to the `chat_messages` table (tools.py), so their
chat survives a page reload or a new visit. Guests can chat; nothing is saved.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from itertools import combinations_with_replacement
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from dotenv import load_dotenv

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from openai import AsyncOpenAI  # noqa: E402
from pydantic_ai import Agent, ModelRetry, RunContext  # noqa: E402
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded  # noqa: E402
from pydantic_ai.messages import (  # noqa: E402
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models.openai import OpenAIChatModel  # noqa: E402
from pydantic_ai.providers.openai import OpenAIProvider  # noqa: E402
from pydantic_ai.usage import UsageLimits  # noqa: E402

from models import (  # noqa: E402
    AuditEntry,
    AuditEvent,
    AuditToolCall,
    ChatHistory,
    ChatHistoryMessage,
    ChatResponse,
    PageContext,
    ShopReply,
    Showcase,
    User,
)
from tools import (  # noqa: E402
    SHOP_TOOLS,
    RecordedSearch,
    ShopDeps,
    ViewedPage,
    chat_cards,
    get_product,
    get_summaries,
    recent_chat_messages,
    save_chat_turn,
)

BACKEND_DIR = Path(__file__).resolve().parent
PROMPT_FILE = BACKEND_DIR / "prompts" / "prompt.md"

# Closest .env wins: backend/, then Homework 4/, then up to the course root.
# load_dotenv never overrides a value that's already set.
for folder in [BACKEND_DIR, *BACKEND_DIR.parents]:
    if (folder / ".env").is_file():
        load_dotenv(folder / ".env")

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")

# A shopping question needs two to four model requests (search, maybe a
# detail lookup, then the answer). Twelve leaves room for a validator retry
# without letting a runaway loop burn the budget.
MAX_AGENT_REQUESTS = 12
MAX_PRODUCTS_SHOWN = 6
HISTORY_MESSAGES_KEPT = 30  # per conversation, sent back to the model
SAVED_MESSAGES_RESTORED = 20  # from chat_messages when a signed-in shopper returns
MAX_CONVERSATIONS = 500  # in memory; oldest dropped first

# Sent when the model provider's safety filter blocks a message (for example
# a jailbreak attempt). The turn isn't added to the conversation.
FILTERED_REPLY = (
    "I can't help with that one, but I'd love to help you shop! "
    "Tell me who you're shopping for or what you're looking for, and I'll find some options."
)

# 13–19 digits, optionally split by spaces or dashes: card-number shaped.
CARD_NUMBER = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")


def redact(message: str) -> str:
    """Strip card-like numbers before a message reaches the model or the database."""
    return CARD_NUMBER.sub("[card number removed]", message)


PRICE_PATTERN = re.compile(r"\$\s?(\d{1,4}(?:,\d{3})*(?:\.\d{1,2})?)")

# Stock counts in a reply: "12 left", "5 in stock", "8 available", "15 on
# hand", "4 remaining", "3 in XL", "2 in size M". (Not bare "only 2", which
# also matches harmless phrases like "just 2 options".)
QUANTITY_PATTERNS = [
    re.compile(
        r"\b(\d{1,4})\s+(?:left|in stock|available|on hand|remaining|units?|pieces?)\b", re.IGNORECASE
    ),
    re.compile(r"\b(\d{1,4})\s+(?:in|of)\s+(?:size\s+)?(?:XS|S|M|L|XL|XXL)\b"),
]
SOLD_OUT_WORDS = ("sold out", "out of stock", "none left", "not in stock", "no stock", "0 left", "unavailable")


# --------------------------------------------------------------------------- #
# Audit trail: output/audit_trail.json (JSON Lines, append-only)
#
# Each line is one AuditEntry, appended as each step of the agent loop finishes
# and never rewritten, so the file grows across runs and restarts and a crashed
# run still leaves its completed steps. Shoppers appear as 'guest' or
# 'user:<id>', never by name or email; messages are redacted and truncated.
# --------------------------------------------------------------------------- #

AUDIT_FILE = Path(
    os.getenv("CAMPUS_CUSTOMS_AUDIT", Path(__file__).resolve().parent.parent / "output" / "audit_trail.json")
)
SUMMARY_CHARS = 200

_lock = threading.Lock()


def _compact(value: Any) -> Any:
    """Lead with what matters in a tool result, so truncation keeps the facts."""
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if isinstance(value, list):
        return [_compact(v) for v in value]
    if not isinstance(value, dict):
        return value
    if "answer" in value:  # StockCheck: the plain-English facts first
        return {"answer": value["answer"]}
    if "products" in value and "total_matches" in value:  # SearchResults
        return {
            "search_id": value.get("search_id"),
            "total_matches": value["total_matches"],
            "returned": value.get("returned"),
            "products": [f"{p.get('name')} ${p.get('price'):g}" for p in value["products"]],
        }
    if "stock_by_size" in value:  # ProductFacts
        return {
            "name": value.get("name"),
            "price": value.get("price"),
            "stock": {s["size"]: s["quantity"] for s in value["stock_by_size"]},
        }
    if "recommended_size" in value:  # SizeRecommendation
        return {"recommended_size": value["recommended_size"], "reason": value.get("reason")}
    return value


def summarise(value: Any, limit: int = SUMMARY_CHARS) -> str:
    """Compact one-line text for the log: key facts first, JSON, truncated."""
    if value is None:
        return ""
    value = _compact(value)
    if not isinstance(value, str):
        try:
            value = json.dumps(value, default=str, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError):
            value = str(value)
    value = " ".join(value.split())
    return value if len(value) <= limit else value[: limit - 1] + "…"


class AuditLogger:
    """Appends one AuditEntry per step of one agent run."""

    def __init__(self, *, conversation_id: str, shopper: str, page: str, model: str, path: Path | None = None):
        self.path = path or AUDIT_FILE
        self.run_id = uuid.uuid4().hex[:12]
        self.conversation_id = conversation_id
        self.shopper = shopper
        self.page = page
        self.model = model
        self.iteration = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        event: AuditEvent,
        *,
        stop_reason: str,
        tool_calls: list[AuditToolCall] | None = None,
        message_summary: str = "",
        reply_summary: str = "",
        duration_seconds: float = 0.0,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        error: str = "",
    ) -> AuditEntry:
        entry = AuditEntry(
            run_id=self.run_id,
            conversation_id=self.conversation_id,
            shopper=self.shopper,
            page=self.page,
            iteration=self.iteration,
            event=event,
            model=self.model,
            tool_calls=tool_calls or [],
            stop_reason=stop_reason,
            message_summary=message_summary,
            reply_summary=reply_summary,
            duration_seconds=round(duration_seconds, 3),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            error=error,
        )
        line = entry.model_dump_json() + "\n"
        with _lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
        self.iteration += 1
        return entry


def read_trail(path: Path | None = None) -> list[AuditEntry]:
    """Load the trail back into models, skipping any unreadable line."""
    path = path or AUDIT_FILE
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                entries.append(AuditEntry.model_validate_json(line))
            except ValueError:
                continue
    return entries


class AgentUnavailable(RuntimeError):
    """Raised when the model can't be reached (e.g. no API key)."""


# --------------------------------------------------------------------------- #
# Agent
# --------------------------------------------------------------------------- #


def portkey_api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise AgentUnavailable("PORTKEY_API_KEY is not set. Add it to a .env file in Homework 4/ or a parent folder.")
    return key


def system_prompt() -> str:
    return PROMPT_FILE.read_text()


@lru_cache(maxsize=1)
def get_agent() -> Agent[ShopDeps, ShopReply]:
    """Build the agent once, on first use, so the API can start without a key."""
    client = AsyncOpenAI(
        api_key=portkey_api_key(),
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-provider": "openai"},
    )
    agent = Agent(
        model=OpenAIChatModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client)),
        deps_type=ShopDeps,
        output_type=ShopReply,
        instructions=system_prompt(),
        tools=SHOP_TOOLS,
        retries=2,  # shared by tool calls and the output validator
    )
    agent.instructions(shopper_context)
    agent.output_validator(grounded_reply)
    return agent


def shopper_context(ctx: RunContext[ShopDeps]) -> str:
    """Per-turn context added to the system prompt: who is chatting and where they are."""
    deps = ctx.deps
    lines = [f"Today is {date.today():%B %d, %Y}."]

    if deps.user:
        u = deps.user
        lines.append(
            f"Who you're talking to: {u.first_name} {u.last_name} <{u.email}>, signed in. "
            f"Call them {u.first_name}. Their chats are saved, so earlier messages may be in this conversation."
        )
    else:
        lines.append("Who you're talking to: a guest (not signed in). Their chat is not saved.")
        if deps.my_size:
            lines.append(f"They've told the site their usual size is {deps.my_size} (stored in their browser).")

    page = deps.page
    if page is None:
        lines.append("Page: unknown.")
    elif page.area == "product" and page.product_id:
        size = f" They have size {page.selected_size} selected." if page.selected_size else ""
        lines.append(
            f'Page: the product page for "{page.product_name}" (product_id {page.product_id}).{size} '
            '"This", "it", "this one" or "this hoodie/shirt" means this product: use get_viewed_product '
            "or pass this product_id to check_stock."
        )
    elif page.area == "products":
        if page.filters:
            shown = ", ".join(f"{k}={v}" for k, v in page.filters.items())
            lines.append(f"Page: the Products page, filtered by {shown}.")
        else:
            lines.append("Page: the Products page (all products).")
    else:
        lines.append(f"Page: the {page.area.replace('-', ' ')} page.")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Page context from the widget
# --------------------------------------------------------------------------- #

PAGE_AREAS = {"/": "home", "/products": "products", "/about": "about", "/login": "login", "/create-account": "create-account"}
PAGE_FILTERS = ("q", "category", "collection", "size", "max_price", "in_stock", "sort")
SIZES = {"XS", "S", "M", "L", "XL", "XXL"}


def resolve_page(page: PageContext | None) -> ViewedPage | None:
    """Turn the widget's page hint into trusted context.

    The browser could send anything, so: the product ID must exist in the
    database (its name comes from the database, not the browser); only known
    Products-page filters are kept, each trimmed; the size must be a real size.
    """
    if page is None:
        return None
    parts = urlsplit(page.path or "/")
    path = parts.path or "/"

    if path.startswith("/products/"):
        product_id = page.product_id or path.removeprefix("/products/").strip("/")
        product = get_product(product_id) if product_id else None
        if product is None:
            return ViewedPage(path=path, area="other")
        size = (page.selected_size or "").upper()
        return ViewedPage(
            path=path,
            area="product",
            product_id=product.product_id,
            product_name=product.name,
            selected_size=size if size in SIZES else None,
        )

    area = PAGE_AREAS.get(path.rstrip("/") or "/", "other")
    filters = {}
    if area == "products":
        query = parse_qs(parts.query)
        filters = {k: query[k][0][:40] for k in PAGE_FILTERS if query.get(k)}
    return ViewedPage(path=path, area=area, filters=filters)


# --------------------------------------------------------------------------- #
# Truth check
# --------------------------------------------------------------------------- #


def _to_float(amount: str) -> float:
    return round(float(amount.replace(",", "")), 2)


def _allowed_amounts(deps: ShopDeps) -> set[float]:
    """Dollar amounts the reply may quote: database prices, small multiples and
    sums of them (two tees, a hoodie plus a crewneck), and amounts the shopper
    typed themselves (a budget of "$50")."""
    prices = sorted(deps.seen_prices)
    allowed = set(prices)
    allowed |= {round(p * q, 2) for p in prices for q in (2, 3, 4)}
    if len(prices) <= 40:
        allowed |= {round(a + b, 2) for a, b in combinations_with_replacement(prices, 2)}
    allowed |= {_to_float(m) for m in PRICE_PATTERN.findall(deps.user_message)}
    return allowed


def grounded_reply(ctx: RunContext[ShopDeps], reply: ShopReply) -> ShopReply:
    unseen = [pid for pid in reply.product_ids if pid not in ctx.deps.seen_ids]
    if unseen:
        raise ModelRetry(
            f"product_ids {unseen} were not returned by a tool this turn. "
            "Look them up with search_catalog or get_product_details, or remove them."
        )

    quoted = {_to_float(m) for m in PRICE_PATTERN.findall(reply.message)}
    invented = sorted(quoted - _allowed_amounts(ctx.deps))
    if invented:
        raise ModelRetry(
            f"Your message quotes {', '.join(f'${a:g}' for a in invented)}, which is not a price "
            "returned by the store database this turn. Call a tool and quote its price exactly."
        )

    quantities = {int(n) for pattern in QUANTITY_PATTERNS for n in pattern.findall(reply.message)}
    allowed_qty = ctx.deps.seen_quantities | {int(n) for n in re.findall(r"\d+", ctx.deps.user_message)}
    made_up = sorted(quantities - allowed_qty)
    if made_up:
        raise ModelRetry(
            f"Your message gives stock counts {made_up} that no tool returned this turn. "
            "Call check_stock and quote the quantities exactly."
        )

    if ctx.deps.sold_out_checks and not any(w in reply.message.lower() for w in SOLD_OUT_WORDS):
        gone = "; ".join(f"{name} in size {size}" for name, size in ctx.deps.sold_out_checks)
        raise ModelRetry(
            f"check_stock found these SOLD OUT: {gone}. Say clearly that the size is sold out "
            "(use the words 'sold out'), then offer the sizes that are still in stock."
        )

    if reply.show_results_of is not None:
        if reply.show_results_of not in ctx.deps.searches:
            known = ", ".join(ctx.deps.searches) or "none"
            raise ModelRetry(
                f"show_results_of={reply.show_results_of!r} is not a search_id from this turn "
                f"(searches this turn: {known}). Use a search_id returned by search_catalog, or null."
            )
        if not reply.results_title:
            raise ModelRetry("Give a short results_title (e.g. 'Navy hoodies') when you set show_results_of.")

    reply.product_ids = list(dict.fromkeys(reply.product_ids))[:MAX_PRODUCTS_SHOWN]
    return reply


# --------------------------------------------------------------------------- #
# Search results → product cards on the page
# --------------------------------------------------------------------------- #


def browse_url(args: dict) -> str:
    """The same search as a Products-page link (filters that page understands)."""
    q = " ".join(w for w in (args.get("color"), args.get("query")) if w)
    params = {
        "q": q,
        "category": args.get("category"),
        "collection": args.get("collection"),
        "size": args.get("size"),
        "max_price": f"{args['max_price']:g}" if args.get("max_price") is not None else None,
        "in_stock": "true" if args.get("in_stock_only") else None,
        "sort": args.get("sort") if args.get("sort") not in (None, "relevance") else None,
    }
    query = urlencode({k: v for k, v in params.items() if v})
    return "/products" + (f"?{query}" if query else "")


def build_showcase(search: RecordedSearch, title: str) -> Showcase | None:
    """Cards for every match of the chosen search, rebuilt from the database."""
    if not search.product_ids:
        return None
    return Showcase(
        title=title,
        total_matches=search.total_matches,
        products=get_summaries(search.product_ids),
        browse_url=browse_url(search.args),
    )


# --------------------------------------------------------------------------- #
# Conversations
# --------------------------------------------------------------------------- #


@dataclass
class Conversation:
    owner_id: int | None  # user id, or None for a guest
    messages: list[ModelMessage] = field(default_factory=list)


_conversations: OrderedDict[str, Conversation] = OrderedDict()


def _remember(conversation_id: str, convo: Conversation) -> None:
    _conversations[conversation_id] = convo
    _conversations.move_to_end(conversation_id)
    while len(_conversations) > MAX_CONVERSATIONS:
        _conversations.popitem(last=False)


def _trim(messages: list[ModelMessage]) -> list[ModelMessage]:
    """Drop the oldest turns, cutting only at a shopper message so a tool call
    is never separated from its result."""
    if len(messages) <= HISTORY_MESSAGES_KEPT:
        return messages
    for i in range(len(messages) - HISTORY_MESSAGES_KEPT, len(messages)):
        m = messages[i]
        if isinstance(m, ModelRequest) and any(isinstance(p, UserPromptPart) for p in m.parts):
            return messages[i:]
    return messages[-1:]


def _conversation_for(conversation_id: str | None, user: User | None) -> tuple[str, Conversation]:
    """The shopper's existing conversation, or a fresh one. A conversation that
    belongs to another account is never reused."""
    owner = user.id if user else None
    if conversation_id and conversation_id in _conversations:
        convo = _conversations[conversation_id]
        if convo.owner_id == owner:
            return conversation_id, convo
        if convo.owner_id is None and owner is not None:
            convo.owner_id = owner  # a guest who logged in mid-chat keeps their chat
            return conversation_id, convo
    return uuid.uuid4().hex, Conversation(owner_id=owner)


# --------------------------------------------------------------------------- #
# Saved chat history (chat_messages table, signed-in shoppers only)
# --------------------------------------------------------------------------- #


def load_history(user: User | None) -> ChatHistory:
    """The signed-in shopper's recent chat, ready to show in the widget and to
    continue: the returned conversation is seeded with the same messages."""
    if user is None:
        return ChatHistory(conversation_id=None, messages=[])
    rows = recent_chat_messages(user.id, SAVED_MESSAGES_RESTORED)
    seeded: list[ModelMessage] = []
    shown: list[ChatHistoryMessage] = []
    for r in rows:
        if r["role"] == "user":
            seeded.append(ModelRequest(parts=[UserPromptPart(content=r["content"])]))
        else:
            seeded.append(ModelResponse(parts=[TextPart(content=r["content"])]))
        shown.append(
            ChatHistoryMessage(
                role=r["role"],
                content=r["content"],
                # Cards are rebuilt from the database so prices and stock are current.
                products=get_summaries([c["product_id"] for c in chat_cards(r["products_json"])]),
                created_at=r["created_at"],
            )
        )
    conversation_id = uuid.uuid4().hex
    _remember(conversation_id, Conversation(owner_id=user.id, messages=seeded))
    return ChatHistory(conversation_id=conversation_id, messages=shown)


# --------------------------------------------------------------------------- #
# One chat turn
# --------------------------------------------------------------------------- #


async def chat(
    message: str, conversation_id: str | None, user: User | None, page: PageContext | None = None
) -> ChatResponse:
    message = redact(message)
    agent = get_agent()
    conversation_id, convo = _conversation_for(conversation_id, user)
    deps = ShopDeps(
        user=user,
        user_message=message,
        page=resolve_page(page),
        my_size=page.my_size.upper() if page and page.my_size and page.my_size.upper() in SIZES else None,
    )

    logger = AuditLogger(
        conversation_id=conversation_id,
        shopper=f"user:{user.id}" if user else "guest",
        page=_page_label(deps.page),
        model=MODEL_NAME,
    )
    logger.record(AuditEvent.RUN_START, stop_reason="started", message_summary=summarise(message, 160))

    try:
        result = await _run_audited(agent, message, deps, convo.messages, logger)
    except ModelHTTPError as e:
        if "content_filter" not in str(e.body):
            logger.record(AuditEvent.RUN_END, stop_reason="error", error=summarise(f"ModelHTTPError {e.status_code}"))
            raise
        logger.record(AuditEvent.RUN_END, stop_reason="safety_filter", reply_summary=summarise(FILTERED_REPLY))
        _remember(conversation_id, convo)
        return ChatResponse(conversation_id=conversation_id, reply=FILTERED_REPLY, products=[], tools_used=["safety_filter"])
    except UsageLimitExceeded as e:
        logger.record(AuditEvent.RUN_END, stop_reason="loop_limit", error=summarise(str(e)))
        raise
    except Exception as e:
        logger.record(AuditEvent.RUN_END, stop_reason="error", error=summarise(f"{type(e).__name__}: {e}"))
        raise

    convo.messages = _trim(result.all_messages())
    _remember(conversation_id, convo)

    output = result.output
    if user is not None:  # guests are never saved
        cards = [{"product_id": p.product_id, "name": p.name} for p in get_summaries(output.product_ids)]
        save_chat_turn(user.id, message, output.message, cards)

    showcase = None
    if output.show_results_of:
        showcase = build_showcase(deps.searches[output.show_results_of], output.results_title or "Dan's results")

    tokens_in, tokens_out = _usage(result)
    logger.record(
        AuditEvent.RUN_END,
        stop_reason="completed",
        reply_summary=summarise(output.message),
        tool_calls=[
            AuditToolCall(
                tool_name="final_result",
                args_summary=summarise(
                    {"product_ids": output.product_ids, "show_results_of": output.show_results_of}, 160
                ),
                result_summary=f"{len(output.product_ids)} picks"
                + (f", showcase '{showcase.title}' ({len(showcase.products)} cards)" if showcase else ""),
            )
        ],
        input_tokens=tokens_in,
        output_tokens=tokens_out,
    )

    return ChatResponse(
        conversation_id=conversation_id,
        reply=output.message,
        # Cards come from the database, not from anything the model wrote.
        products=get_summaries(output.product_ids),
        showcase=showcase,
        tools_used=list(dict.fromkeys(deps.tools_used)),
    )


# --------------------------------------------------------------------------- #
# The audited agent loop
# --------------------------------------------------------------------------- #


def _page_label(page: ViewedPage | None) -> str:
    if page is None:
        return ""
    if page.area == "product" and page.product_id:
        return f"product:{page.product_id}" + (f" size:{page.selected_size}" if page.selected_size else "")
    if page.filters:
        return "products?" + "&".join(f"{k}={v}" for k, v in page.filters.items())
    return page.area


def _usage(run) -> tuple[int | None, int | None]:
    usage = run.usage
    if callable(usage):  # a method in some pydantic-ai versions, a property in others
        usage = usage()
    return getattr(usage, "input_tokens", None), getattr(usage, "output_tokens", None)


async def _run_audited(agent, message: str, deps: ShopDeps, history_messages: list[ModelMessage], logger: AuditLogger):
    """Drive the agent loop one node at a time, appending an audit record per step.

    `agent.iter()` exposes the loop that `agent.run()` hides, so each step is
    written the moment it finishes. Loop limits still apply: UsageLimits stops a
    run after MAX_AGENT_REQUESTS model requests.
    """
    async with agent.iter(
        message,
        deps=deps,
        message_history=history_messages,
        usage_limits=UsageLimits(request_limit=MAX_AGENT_REQUESTS),
    ) as run:
        node = run.next_node
        while not Agent.is_end_node(node):
            started = time.perf_counter()
            node = await run.next(node)
            elapsed = time.perf_counter() - started

            calls: list[AuditToolCall] = []
            if Agent.is_call_tools_node(node):
                # The model just answered: which tools it asked for, and why it stopped.
                response = node.model_response
                for part in response.parts:
                    if getattr(part, "part_kind", "") == "tool-call":
                        calls.append(AuditToolCall(tool_name=part.tool_name, args_summary=summarise(part.args)))
                tokens_in, tokens_out = _usage(run)
                logger.record(
                    AuditEvent.MODEL_RESPONSE,
                    stop_reason=str(getattr(response, "finish_reason", None) or "stop"),
                    tool_calls=calls,
                    duration_seconds=elapsed,
                    input_tokens=tokens_in,
                    output_tokens=tokens_out,
                )
            elif Agent.is_model_request_node(node):
                # Tool results (or a validator retry) going back to the model.
                retry = False
                for part in node.request.parts:
                    kind = getattr(part, "part_kind", "")
                    if kind in ("tool-return", "retry-prompt"):
                        retry = retry or kind == "retry-prompt"
                        calls.append(
                            AuditToolCall(
                                tool_name=getattr(part, "tool_name", None) or "output_validator",
                                result_summary=summarise(getattr(part, "content", "")),
                                ok=kind == "tool-return",
                            )
                        )
                if calls:
                    logger.record(
                        AuditEvent.MODEL_REQUEST,
                        stop_reason="retry" if retry else "tool_results",
                        tool_calls=calls,
                        duration_seconds=elapsed,
                    )
        return run.result


def forget(conversation_id: str, user: User | None) -> None:
    """Drop a conversation from memory (the widget's "start a new chat")."""
    convo = _conversations.get(conversation_id)
    if convo and convo.owner_id == (user.id if user else None):
        del _conversations[conversation_id]
