# Design — the Campus Customs storefront

Goal: make the site feel like walking into a real campus shop at
57 Broadway, not a generic template, so visitors stay longer and buy. The
retro-glam base (cream, pink, sunflower, daisies) stays; Yale blue, varsity
lettering and Handsome Dan the shop bulldog now lead.

Main files: `frontend/src/storefront.css`,
`frontend/src/components/Bulldog.tsx`, `AnnouncementBar.tsx`,
`ProductCard.tsx`, `ChatPanel.tsx`, `pages/Home.tsx`.

| Area | What changed | Why it helps customers stay and buy |
|---|---|---|
| **Mascot / chat persona** | **Golden is now Handsome Dan**, the shop bulldog, named after Yale's mascot and drawn in code (SVG): fawn face, underbite, Yale-blue collar with a gold "Y" tag. He blinks and tilts his head. His prompt voice is loyal and cheerful, with at most one dog pun per reply and none in sold-out or safety messages. If asked, he says he's an AI and not an official Yale service. | A character people already love is more inviting to talk to than "the assistant", and more shoppers ask = more guided sales. The rules keep the charm from getting in the way of clear answers. |
| **Chat feel** | Yale-blue pinstripe header with a gold underline and a green "online" dot. Dan's avatar beside each of his replies; shopper bubbles in Yale blue. The typing indicator is bouncing 🐾 paws. Suggestion chips with emoji. A launcher showing Dan with "Ask Handsome Dan · Sizes, gifts, stock". A **one-time nudge** after 6 seconds ("Woof! Looking for your size or a gift?") that never repeats in the session once dismissed or opened. | The chat is the store's best salesperson. A friendly face and a clear "what I can do" line get people to start a conversation; the one-time nudge reaches hesitant shoppers without nagging. |
| **Colours** | **Yale blue (#00356B)** is now the brand colour: buttons, headings, nav underline, chat. Cream, pink and gold stay as accents; felt red is for emphasis and SOLD OUT. | Instantly reads as "Yale shop", which builds trust that this is the right place for real campus gear. One strong primary colour makes "Shop", "Ask Dan" and "Select size" easy to spot. |
| **Fonts & hierarchy** | Three jobs, three faces: **Graduate** (collegiate varsity block) for labels, signs, pennants, the ticker and Dan's name; **Fraunces** (warm serif) for headlines and prices; **DM Sans** for reading. The order on every card: photo → hang-tag price → name → one line → sizes. | Varsity lettering is what campus gear actually looks like. Clear hierarchy means a shopper gets "what, how much, is my size there" in one glance, so less effort to decide. |
| **Storefront hero** | The Home hero is now a **shop front**: a striped Yale-blue **awning** with a scalloped edge; a tilted **shop sign** ("Campus Customs · Yale apparel · 57 Broadway"); a lit **shop window** with three real products swinging on hangers with gold price tags; gold-leaf **"Come on in"** lettering on the glass; and Dan peeking from the corner with "Need a size? Ask me!". Each hanging product links to its page. | A memorable first screen makes people explore rather than bounce. Real products and prices in the window give a reason to click within seconds. |
| **Ticker** | A Yale-blue scrolling ticker above the nav with only true lines (address, 102 pieces, live stock in every size, "Ask Handsome Dan", Boola Boola!). It pauses on hover, and a gold "Ask Dan →" button sits at the end. | Feels like a busy shop and repeats the two reasons to trust it: real stock and a helper, without inventing promotions. |
| **Pennants** | The "Find your people" tiles carry **felt pennants** (Family, Game Day, Colleges, Grad Schools) in Yale blue, felt red, green and brown that wave on hover. | Pennants are the most recognisable campus-shop object, and they make the four main ways to shop stand out as entry points. |
| **Product presentation** | Prices on **gold hang tags** (with a punched hole) that flip on hover. A **size run XS–XXL** on every card, with sold-out sizes struck through and the shopper's own size ringed in gold. A stock sticker on the photo. A rubber-stamp **"SOLD OUT"** on items with no stock. "🐾 Dan's pick" ribbons. Product pages: a framed photo with a gold offset shadow and **hover-to-zoom** toward the cursor. | Shoppers see price and size availability before clicking, so fewer dead-end clicks and quicker decisions. Zoom answers "what does the print look like?" without leaving the page. Hang tags and stamps make the grid feel like a rack in a real shop. |
| **Motion** | Cards **deal in** one after another; window hangers sway; Dan blinks, tilts, peeks and bobs on the launcher; pennants wave on hover; buttons press down like real buttons. All motion turns off for visitors with **reduced motion** set. | Small movement draws the eye to products and to the chat without demanding attention, and makes the shop feel alive. Respecting reduced motion keeps it comfortable for everyone. |
| **Brand mark & favicon** | Dan in a gold ring next to "Campus Customs · 57 Broadway · New Haven" in the nav, footer and browser tab. | One consistent face across the tab, the nav and the chat makes the shop easy to recognise and come back to. |

## Checked (Oct 5, 2026)

- Desktop (1440 px) and phone (375 px): no sideways scrolling, no console
  errors.
- Live chat: asked "Who are you? And is this in a medium?" on the Yale
  Grandpa Crewneck page. Dan introduced himself as an AI named after
  Yale's mascot, not an official Yale service, and said plainly that the
  crewneck is "sold out in M", listing the sizes still in stock with
  counts from the database.
- Tests: `test_agent.py` 26, `test_sizes.py` 8 and `test_auth.py` 7, all
  passing.

*Not affiliated with Yale University or Harry Styles. Handsome Dan is used
here as a fond, clearly-labelled tribute to Yale's mascot.*
