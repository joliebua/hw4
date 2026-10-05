# AI Prompts Log — Homework 4

**Course:** MGT 409 — AI Foundations for Managers
**Student:** Jolie Bua
**Assistant:** Claude Code (Opus 5.5)

This file logs the prompts I typed while completing Homework 4. One section per problem.
Each section lists the problem number and title, my initial prompt in my own words, and — where
a follow-up was needed — the follow-up prompt plus one sentence on what was lacking after the
first attempt. The running site, database writes, and screenshots serve as evidence of the work;
no extra proof is kept here beyond the prompts.

---

## Setup — Establishing the working folder and prompt log

**Prompt 1 (initial):**
> We will be working on Homework 4 so everything in this workflow should end up there

**Prompt 2 (follow-up):**
> update AI_prompts.md as we go (create it for this assignment and update it as we work). As we have done in the past, put one section for each problem including problem number and title, at least prompt i typed (in my own words), and one follow-up prompt if needed and what was lacking that required the follow up. the running site, database writes, and screenshots are evidence and assignment will not require extra proof outside of these prompts.

**What was lacking after the first prompt:** The first prompt set the destination folder but did not ask for the prompt log to follow the same per-problem structure used in earlier homeworks, so I spelled out the required sections and that it should be kept updated as we work.

---

## Problem 1 — Campus Customs customer website and chatbot

**Prompt 1 (initial):**
> thats not even funny. anyway here is the scenario for homework: Campus Customs (from homework 3) needs a customer website with a helpful chatbot. We will be building a React + Vite TypeScipt front end and a Python FastAPI backend whose brain is PydanticAI agent. Shoppers should be able to browse products, create an account, chat about merch, see matching items appear on page, and get truthful answers about price and stock from local database. use the portkey_api_key for this prooject.

**Prompt 2 (follow-up):**
> look at database in the data folder (campus_customs.db) send me the fields catalogue, inventory, and users so I can understand them

**What was lacking after the first prompt:** The first prompt produced a working database, but I didn't have a clear explanation of what each table and field in the catalogue, inventory and users tables holds, so I asked for a field-by-field breakdown.

**Prompt 3 (follow-up):**
> sorry can you find the file campus_customs.db in the data-2 folder and send me the fields "catalogue" "inventory" and "users"

**What was lacking after the previous prompt:** I hadn't said which folder I meant, so the answer described the database the app generated instead of the provided `data-2/campus_customs.db`, which has different tables and fields.

**Prompt 4 (follow-up):**
> start output/harness.md and  from the whole database not just the three i asked for before write each table  and its fields and one short line on why each field matters for shop and chatbot.

**What was lacking after the previous prompt:** The field list only lived in the chat and covered three of the four tables, so I asked for a written record of every table and field, with why each matters for the shop and chatbot, saved in a harness file.

---

## Problem 2 — Front end pages and nav bar

**Prompt 1 (initial):**
> create a react + vite + typescript front end for Campus Customs, put a nav bar at the top that links to main pages (home, products, about us, log in, create account). Pull campus customs-style wording from https://yalebulldogblue.com for home and about us. write these pages in our own voice that is different and not copied from original site text.

**Prompt 2 (follow-up):** _None needed yet._

---

## Problem 3 — Product pages, floating chat stub, and products API

**Prompt 1 (initial):**
> on products page show product images from catalogue (use image paths in database) with basic product info (name, price, short description). make each product open a single-item page (large image on left side, full product text on right - description price, sizes/stock, when you have them). clicking a card on Products should take the stopper there. add chat interface in bottom right of site (floating chat panel). it doesn't need to talk to agent yet (stub that will call backend later is enough for problem). Will need a small API soon to read databses. start with simple FastAPI app in backend/main.py to serve products and images. it will then grow into the agen backend in problem 5

**Prompt 2 (follow-up):** _None needed yet._

---

## Problem 4 — Create-account and log-in flow

**Prompt 1 (initial):**
> build typical create-account/login flow
>
> create acct: first & last name, email, password, confirm password
> log in: email and password
>
> new accts go to users table. make sure it stores passwords securely so hackers (including AI) cannot access them.
>
> see database already has test user you can use while building:

**Prompt 2 (follow-up):**
> email: test@campuscustoms.yale.edu
> password: password
>
> confirm you can log in as that user and that a brand-new acct also works. update ouput/harness.md with how authentification workds (what youstore for a user and how passwords are protected)

**What was lacking after the first prompt:** The first prompt left out the test user's login details and didn't ask for proof that both the existing and a new account work, or for a written record of how authentication and password storage work, so I added the credentials, the checks, and the harness update.

---

## Problem 5 — Shop chatbot: PydanticAI agent behind FastAPI

**Prompt 1 (initial):**
> build shop chatbot as PydanticAI agent behind FastAPI plugged into front-end chat widget. put the API app in backend/main.py (this is the file run with Uvicorn). Keep agent as these four files next to it (same as homework 3 that we did):
>
> backend/prompts/prompt.md (system prompt - grow file later)
> backend/agent.py (agent entry/wiring)
> backend/tools.py (tools agent can call)
> backend/models.py (Pydantic/PydanticAI structured types
>
> in main.py expose chat route so message from website returns reply from agent (and anything else needed for products and authentication). use AI model API key for agent. put Campus Customs voice and safety basics into prompts/prompt.md. start or update types in models.py for chat replies/product cards as needed. in output/harness.md add how front end talks to FastAPI and how agent is loaded (prompt file and model)
>
> make sure backend runs from backend/ folder:
> uvicorn main:app --reload --port 8000

**Prompt 2 (follow-up):** _None needed yet._

---

## Problem 6 — Database lookup tools for price, description and stock

**Prompt 1 (initial):**
> now agent will need tools that looks up real info from campus_customs.db like product description, price, and how many are in stock (by size when asked for). agent must use database and not invent prices or quants. if size is out of stock, clearly state.
>
> expand prompts/prompt.md so agent knows to call tools for price and stock questions. add or update return types in models.py. in output/harness.md list each tool and explain which model fields were chosen for lookup results and why

**Prompt 2 (follow-up):** _None needed yet._

---

## Problem 7 — Chat search results appear on the page as product cards

**Prompt 1 (initial):**
> now for a fun feature. when customer asks about type of item the agent should search the catalogue and website should dyanmically show those matching items as product cards (image, name, price, short info). after dynamic product cards are loaded by new feature, make sure same single-item page behavior built in problem 3 still works. each product card including ones the chat just put on the page should still open detail view (large image & full info) when clicked. update prompts/prompt.md and output/harness.md so its clear how search results reach page

**Prompt 2 (follow-up):** _None needed yet._

---

## Problem 8 — Saved chat history, shopper identity and page context

**Prompt 1 (initial):**
> when a shopper is logged in save the chat history in database in appropriate table and reload when they return. agent should know who is chatting (name & email). this should go in agent deps or equivalent clear pattern and the tools the agent can call. pass enough page context that if someone is on product page and asks "do you have this in pink?" the agent knows what item they mean. you can put code into the agent context. Guests can caht but history only works for logged-in users. document in output/harness.md how use chat history is stored, what customer fields the agent sees adn how page context is passed.

**Prompt 2 (follow-up):** _None needed yet._

---

## Problem 9 — Front-end usability improvements

**Prompt 1 (initial):**
> We are going to improve the shop now. I want to implement 2 front-end usability improvements. please give me recommendations on what we can implement for me to choose from

**Prompt 2 (follow-up):**
> lets do the "you might also like" on product pages and a recommended size to buy based on sizes that have been bought before/the size the customer identifies as their size.
>
> write output/usability.md before/as you build. for each of the improvements say what you added and why it helps a shopper or the business. when done send me the website so i can verify these work

**What was lacking after the first prompt:** The first prompt only asked for options, so I followed up to choose the two improvements, describe how the size recommendation should work, and ask for a usability write-up plus the running site to verify.

---

## Problem 10 — Creative storefront design and Handsome Dan

**Prompt 1 (initial):**
> i like the design going on right now, we need it to be creative so it feels like a real campus customs store front (fonts, colors, hierarchy, motion, product presentation, chat feel) so make sure the design includes that. there are more points for imaginative and innovation design. like if the chat bot is named "handsome dan".
>
> write output/design.md with what was changed and why it should help customers stick around and buy. concrete and short.

**Prompt 2 (follow-up):** _None needed yet._

---

## Problem 11 — Live app check for graders

**Prompt 1 (initial):**
> test live site and document in output/app_check.html (page that I can double-click open). include clear screenshots and short captions for:
>
> 1. chat checking inventory level of an item (honest stock/price from DB)
> 2. dynamic search-results cards appearing after category question like hoodies
> 3. one of usability features we added in problem 9
>
> this will be for the graders so make it easy to grade (heading for each check, screenshot, 1-2 sentences on what screenshots prove. put the screenshot image files in output/app_check_images/ and link them from app_check.html with relative paths (ex: app_check_images/inventory.png

**Prompt 2 (follow-up):** _None needed yet._

---

## Problem 12 — Audit trail, safety rules and final harness

**Prompt 1 (initial):**
> now keep an append-only output/audit_trail.json of agent-loop activity with time, tool name, short arguments/results, stop reason. don't wipe it between run. also use the safety rules we have used in the past like user protection and internet use (and anything that might be a good add for this project) and put them in prompts/prompt.md
>
> finish output/harness.md so its clear how system works. model fields in model.py and why they were chosen, tools and abilities, safety rules, and specs (loop limits, result caps, models, how to run it front & back)

**Prompt 2 (follow-up):** _None needed yet._

---

## Problem 13 — Package as hw4/ and publish to GitHub

**Prompt 1 (initial):**
> put the code in a folder named hw4 and push it to a public GitHub repository. I will need to submit the repo URL to canvas so please provide that. do not put real. .env, campus_customs.db or product images in GitHub repo. use .gitignore. include .env.example with placeholders only. attached is the expected file layout. the agent itself is four files under backend/: prompts/prompt.md, agent.py, tools.py and models.py. README.md should explain how to run front end and back end after placing the data pack

**Prompt 2 (follow-up):** _None needed yet._
