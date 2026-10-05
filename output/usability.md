# Usability improvements — Campus Customs website

Two front-end improvements chosen for Problem 9. Each section says what was
added, why it helps a shopper or the business, and how it was checked.

Status: **built and verified (Oct 5, 2026).**

---

## 1. "You might also like" on product pages

### What we added

- A **"You might also like"** row under the details on every product page.
  It shows up to 6 product cards (photo, name, price, short description,
  stock badge). Each card opens that item's page, so shoppers can hop from
  one similar item to the next.
- The matches come from the store database (`catalog.related`, served by
  `GET /api/products/{id}/related`). Each candidate is scored on, strongest
  first:
  1. **a shared distinctive name word**: the same residential college,
     team, school or family member ("Saybrook", "Hockey", "Nursing",
     "Grandpa"). Generic words like "Yale", "hoodie" or "crewneck" don't
     count;
  2. **the same collection**: family, sports, residential colleges, or grad
     schools;
  3. **the same kind of garment**;
  4. **shared uncommon tags** (tags on over a fifth of products, like
     "college apparel", are ignored);
  5. **the same main colour**.
- **Stock-aware:** items sold out everywhere sink to the bottom. If the
  shopper has a size (see 2), items sold out in **their size** drop too, and
  each card says "✓ In your size (L)" or "Sold out in L".

Examples from the live data:

| Viewing | First suggestions |
|---|---|
| Saybrook Logo T-Shirt | Saybrook Sweater Fleece Jacket, Saybrook College Crewneck, then other college logo tees |
| Ice Hockey Left Chest Hoodie | Yale Sports Hoodie Hockey, Tri-Blend Hockey Tee, field hockey pieces |
| School of Nursing Crest Tee | School of Management Crest Tee, School of Medicine 1/4 Zip, other school pieces |
| Yale Grandpa Hoodie | Dad, Mom, Aunt, Uncle hoodies, Grandpa Crewneck, Grandma Hoodie |

### Why it helps

**For shoppers:**

- **No dead ends.** If an item is sold out in their size or isn't quite
  right, the next-best options are one click away.
- **Matches how people shop for Yale gear.** Shoppers often care most about
  *who* it's for (their college, their team, Grandpa), not just "a hoodie".
  Ranking by shared college, team or family name puts the Saybrook
  crewneck next to the Saybrook tee, not a random tee.
- **Less wasted clicking.** With a size set, every suggestion says straight
  away whether it's available in that size.

**For the business:**

- **More items seen per visit, more chances to sell.** Cross-selling within
  an identity ("you like Saybrook, here's the Saybrook fleece") is the
  classic way to raise basket size.
- **Saves sales that would be lost to stock-outs** by pointing to similar
  items that *are* in stock.
- **No new data needed:** it reuses the catalogue's names, tags and live
  stock.

---

## 2. Recommended size

### What we added

- A **"Recommended size"** box on every product page, just above the size
  buttons. It names the size to buy and explains why in plain words, and
  that size is **pre-selected**. Example: "Recommended size: **XL**. Based
  on your size. L is the size you told us you wear, but this item is sold
  out in L. XL is the closest size in stock (one size up; 15 left)."
- **"My size": the size the customer says is theirs.**
  - The first time, the box asks "What size do you usually wear?" with
    XS–XXL buttons. The shopper can change it any time ("Change").
  - **Signed-in shoppers:** saved to their account (new `shopper_sizes`
    table), so it follows them across devices.
  - **Guests:** kept in their browser. On sign-up or login, a guest's size
    carries over if the account doesn't have one yet.
- **Size history: sizes the shopper has chosen before** (signed-in only,
  new `size_history` table):
  - every size they click on a product page (`selected`);
  - every size they ask Golden to check (`asked`);
  - purchases (`purchased`), weighted 4× a click. The shop has **no
    checkout yet**, so none exist; see Limits.

  Repeat clicks on the same item and size within a day count once.
- **How the size is chosen** (`backend/sizes.py`):
  1. A saved size counts 10. Each history event adds its weight (purchase
     4, pick or ask 1), over the last 50 events. The highest total is the
     shopper's **usual size**. So a saved size wins over a little history,
     but several purchases in another size would win. Guests use their
     browser size.
  2. **This item's stock** is then checked. If the usual size is sold out,
     the box says so and recommends the **nearest size in stock**, trying
     one size up first (sizing up is the safer miss in apparel).
  3. The explanation says which signal was used: "Based on your size" or
     "Based on your past sizes".
- **Golden knows it too.** The new `recommend_size` tool means "what size
  should I get in this?" in the chat gives the same answer as the box.
- **Everywhere sizes show up:** "You might also like" favours items in the
  shopper's size and labels each card.

### Why it helps

**For shoppers:**

- **Answers "which size?" before they ask.** It's the most common question
  for apparel, and until now shoppers had to read six stock boxes on every
  item.
- **Catches sold-out sizes for them.** It says plainly "sold out in L" and
  offers the closest size that is available, instead of letting them pick
  L and hit a dead end.
- **Set once, used everywhere.** One click sets their size for every
  product page, every suggestion, and Golden's answers.
- **Learns quietly.** A signed-in shopper who keeps picking M gets M
  recommended, even if they never set a size.
- **Explains itself.** Every recommendation says why ("your saved size",
  "you've picked M 2 times before"), so shoppers can trust it or change it.

**For the business:**

- **Fewer abandoned visits and fewer wrong-size orders.** Size uncertainty
  is a main reason apparel shoppers hesitate, and the main reason for
  returns.
- **Moves shoppers from sold-out sizes to available stock** instead of
  losing the sale.
- **Builds a useful, consented customer signal.** Saved sizes and size
  history show which sizes customers actually want, which can guide
  restocking later.
- **Ready for real purchase data:** the moment a checkout records
  `purchased` sizes, they count most, with no other changes.

---

## How it was checked

All numbers were checked against `data/campus_customs.db`.

**As a guest, Saybrook Logo T-Shirt (sold out in L):**

- The box asked "What size do you usually wear?".
- After picking **L** it said "Recommended size: XL… sold out in L. XL is
  the closest size in stock (one size up; 15 left)", and pre-selected XL.
- "You might also like" showed the Saybrook fleece and Saybrook crewneck
  first, each marked "✓ In your size (L)".
- **Clicking a "You might also like" card** opened the Saybrook College
  Crewneck page, with L recommended and pre-selected (2 left).

**Signed in as the test user:**

- The guest's L moved to the account (`GET /api/me/size` returned L).
- With the saved size cleared, the box asked for a size. Picking M on the
  Yale Mom Hoodie and the Yale Dad Hoodie added 2 `selected` rows to
  `size_history`.
- The Yale Grandpa Crewneck (M sold out, L = 8) then said "Based on your
  past sizes. You've picked M 2 times before, but this item is sold out in
  M. L is the closest size in stock (one size up; 8 left)."
- Asking Golden "What size should I get in this?" on that page gave the
  same answer.

**Bug found and fixed while testing:** clicking a size that was already
pre-selected used to *un*-select it, so that pick was never recorded. Size
buttons now always select, and every click counts.

**Also checked:**

- Phone layout (375 px): no sideways scrolling; the box stacks above the
  size grid.
- Browser console: no errors.
- Tests:
  - `backend/test_sizes.py`: 8 passed (related ranking and route; guest,
    saved-size, history and purchase weighting; sold-out to next size up;
    duplicate clicks; login required).
  - `backend/test_agent.py`: 26 passed.
  - `backend/test_auth.py`: 7 passed.

---

## Limits

- **No purchase history exists yet.** The database has no orders table and
  the site has no checkout, so "sizes bought before" can't be used today.
  No purchases were made up. `size_history` accepts `purchased` entries and
  the recommender weights them highest (the tests prove it with records
  made inside the test), so a future checkout only needs to call
  `sizes.record(user_id, product_id, size, "purchased")`.
- **No fit data.** We don't know whether an item runs small or large, so
  the recommendation never claims that. It recommends the shopper's own
  size, or the nearest size in stock, and says which.
- **Guests' sizes stay in their browser** and aren't stored on the server.
  Size history is for signed-in shoppers only.
