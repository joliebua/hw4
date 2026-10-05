# Campus Customs — shop website + Handsome Dan (MGT 409, Homework 4)

A customer website for **Campus Customs**, the Yale apparel shop at 57 Broadway,
New Haven, with a shopping chatbot: **Handsome Dan**, the shop bulldog.

- **Front end:** React + Vite + TypeScript (`frontend/`). Home, Products, a
  single-item page per product, About Us, Log in and Create account, plus a
  floating chat panel.
- **Back end:** Python FastAPI (`backend/main.py`, run with Uvicorn). Products
  and images from the store database, accounts, sizes and chat.
- **Agent:** PydanticAI, in four files under `backend/`: `prompts/prompt.md`,
  `agent.py`, `tools.py` and `models.py`. Its tools read live price and stock
  from SQLite, and a validator rejects any price, stock count or product the
  database didn't supply.

## Layout

```
hw4/
├── AI_prompts.md            prompts used to build this, one section per problem
├── requirements.txt         back-end Python dependencies
├── .env.example             placeholders only (copy to .env)
├── .gitignore
├── README.md
├── frontend/                Vite React TypeScript app
├── backend/
│   ├── main.py              FastAPI app (run with: uvicorn main:app --reload --port 8000)
│   ├── agent.py             agent entry/wiring: model, prompt, tools, validator, audit trail
│   ├── models.py            Pydantic / PydanticAI structured types
│   ├── tools.py             database access + the tools the agent can call
│   ├── prompts/
│   │   └── prompt.md        system prompt: voice, truth rule, tool guide, safety rules
│   └── tests/               offline tests (no API calls)
└── output/
    ├── harness.md           how the system works (Part A) + build log (Part B)
    ├── design.md            storefront design: what changed and why
    ├── usability.md         "You might also like" + recommended size
    ├── app_check.html       live-site check with screenshots (open by double-click)
    ├── app_check_images/    screenshots linked from app_check.html
    └── audit_trail.json     append-only log of every agent-loop step (JSON Lines)
```

**Not in git (local only):** the data pack, `.env`, virtual environments and
`node_modules/`.

## 1. Place the data pack

Put the course data pack in `hw4/data/`:

```
hw4/
└── data/
    ├── campus_customs.db    catalogue, inventory, users, chat_messages
    └── products/            the product images referenced by the catalogue
```

The back end reads `data/campus_customs.db` and serves `data/products/` at
`/api/images/`. On first start it adds the tables it needs (`sessions`,
`shopper_sizes`, `size_history`) if they're missing.

## 2. Add your API key

```bash
cp .env.example .env
```

Then edit `.env` and set `PORTKEY_API_KEY`. The chat uses `gpt-5.6-luna`
through the Portkey gateway (override with `OPENAI_MODEL`). `.env` is
git-ignored; never commit it. The shop pages work without a key; only the
chat needs it.

## 3. Run the back end

From `hw4/`, needs Python 3.12+:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd backend
uvicorn main:app --reload --port 8000
```

Check it at http://127.0.0.1:8000/api/health. You should see
`"products": 102` and `"portkey_key_set": true`.

## 4. Run the front end

In a second terminal, from `hw4/frontend/`, needs Node 20+:

```bash
npm install
npm run dev
```

Open **http://127.0.0.1:5173**. The Vite dev server proxies `/api` to port
8000; set `BACKEND_URL` to point it elsewhere. `npm run build` type-checks
and builds for production.

**Try it:**

- Click **Ask Handsome Dan** (bottom right) and ask "Show me your hoodies"
  (cards appear on the page).
- Ask "Is the Saybrook Logo T-shirt in stock in a large?" (honest sold-out
  answer, with real counts).
- Open any product and pick your size in "What size do you usually wear?"
  (you get a recommended size, and "You might also like" below).
- Log in with the provided test account, or create your own.

## 5. Run the tests

From `hw4/backend/` with the venv active. None of them call the model; the
account and size tests use a temporary copy of the database.

```bash
python tests/test_agent.py    # truth validator, tools = database, page context, redaction (26)
python tests/test_audit.py    # audit trail logs every loop step and is append-only (4)
python tests/test_auth.py     # Argon2id passwords, sessions, throttling (7)
python tests/test_sizes.py    # recommended size + "you might also like" (8)
```

## What it does

- **Browse:** search and filters (category, collection, size, price, in
  stock, sort), all kept in the URL. Cards show the photo, a hang-tag price,
  a short description and XS–XXL availability.
- **Product page:** a large photo with hover zoom, full description, stock
  by size, a **recommended size** (from the shopper's saved size and size
  history, adjusted for stock), and **"You might also like"**.
- **Accounts:** create an account (first and last name, email, password and
  confirmation) and log in. Passwords are hashed with Argon2id; sessions are
  HttpOnly cookies.
- **Handsome Dan:**
  - answers price and stock questions from the database, by size, and says
    "sold out" clearly;
  - puts search results on the page as product cards;
  - understands "this" on a product page;
  - knows a signed-in shopper's name, email and saved chats;
  - follows the safety rules in `prompts/prompt.md` (privacy, no internet
    use, untrusted text is data, honest limits, fair selling).
- **Audit trail:** every step of the agent loop is appended to
  `output/audit_trail.json` (time, tool, short arguments/results, stop
  reason). It is never wiped.

The full specs (model, loop limits, result caps, every tool and model field,
safety rules) are in [`output/harness.md`](output/harness.md).

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Status, product count, model, whether the key is set |
| GET | `/api/products` | Search and filter (`q`, `category`, `collection`, `size`, `max_price`, `in_stock`, `sort`) |
| GET | `/api/products/{id}` | Full product, with stock by size |
| GET | `/api/products/{id}/related` | "You might also like" |
| GET | `/api/products/{id}/size-recommendation` | Recommended size |
| GET | `/api/facets` | Categories, collections, price range |
| GET | `/api/images/{file}` | Product photo |
| POST | `/api/auth/register` · `/login` · `/logout` | Accounts (session cookie) |
| GET | `/api/auth/me` | The logged-in shopper, or `null` |
| GET / PUT | `/api/me/size` | "My size" |
| POST | `/api/me/size-history` | Record a size the shopper picked |
| POST | `/api/chat` | `{message, conversation_id, page}` → reply, picks, search-result cards |
| GET | `/api/chat/history` | A signed-in shopper's saved chat |
| DELETE | `/api/chat/{conversation_id}` | Start a new chat |

---

Campus Customs is not affiliated with Yale University. Handsome Dan is a
clearly-labelled tribute to Yale's mascot. The retro-glam styling is
inspired by Harry Styles and is not affiliated with him.
