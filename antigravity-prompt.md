# Prompt for Antigravity — "Sakura Shop" Telegram Bot + Mini App

Copy everything below the line into Antigravity.

---

You are building a complete, production-ready Telegram shop for **Sakura shop** (channel: https://t.me/sakuraaa_chinese_shop), a small Tashkent-based shop selling Chinese brand and aesthetic clothing and accessories (sweaters/"jempir", wigs, scarves, etc.). The owner's Telegram is **@fkhrdnvvvva**. Customers don't pay in the app. They browse, pick items, and then message her to buy.

Build it end to end: plan → code → run locally → test → deployment instructions. Don't leave TODOs or placeholder logic.

## 1. Brand & vibe (match the channel)

- **Language:** Uzbek (Latin script) by default, matching the channel. Add an English/Русский toggle in the Mini App settings; put all strings in one `i18n` file.
- **Tone:** cute, warm, lots of emojis (🌸💗🎀✨🛍️), same as the channel posts.
- **Price format:** dot thousands separator plus "so'm", e.g. `99.000 so'm`.
- **Fixed shop terms** (editable by admin in settings):
  - 📦 Kargo: `12.000 so'm / 100g`
  - ⏳ Yetkazib berish: `10–15 kun`
  - 🚚 Dastavka: `O'zbekiston bo'ylab`
  - 💳 `100% oldindan to'lov` (100% prepayment)
  - 📍 Toshkent
- **Order line on every product:** `Buyurtma berish uchun @fkhrdnvvvva ga yozing 💌`
- **Categories as hashtags,** like the channel: `#jempir`, `#wig`, `#scarf`, `#sumka`, `#aksessuar`, plus any new ones the admin creates.

## 2. Visual design — pink + sakura 🌸

- **Palette:** blush `#FFE4EC`, sakura pink `#FFB7C5`, deep rose `#E75480`, cream `#FFF8F5`, soft plum text `#5B3A4A`. Rounded corners (16–24px), soft pink shadows, glassmorphism cards.
- **Signature effect:** CSS/canvas **falling sakura petals** drifting across the header. Make it lightweight, pausable, and respectful of `prefers-reduced-motion`.
- **Branches:** SVG sakura branch illustrations in the header and empty states (draw them inline as SVG, no external image dependencies).
- **Fonts:** "Quicksand" or "Nunito" for body text, a cute display font like "Pacifico" for the "Sakura shop" logo (Google Fonts).
- **Theme:** respect Telegram theme params, but keep the pink identity in dark mode too (dark plum background, pink accents).
- **Polish:** micro-interactions like heart-pop on wishlist, petal burst on "add to bag", skeleton loaders, and Telegram `HapticFeedback` on taps.

## 3. Tech stack

- **Bot:** Python 3.12 + **aiogram 3**.
- **Backend API:** **FastAPI** (same repo). It serves the Mini App static files and a REST API.
- **DB:** SQLite via SQLAlchemy 2 async + Alembic. Must be easy to switch to Postgres through `DATABASE_URL`.
- **Mini App:** **React + Vite + TypeScript + Tailwind**, using `window.Telegram.WebApp` (telegram-web-app.js). Build it to static files served by FastAPI.
- **Images:** when the admin uploads a photo, store the Telegram `file_id`. The backend proxies `getFile` and caches files on disk, so there's no external storage to pay for.
- **Config:** `.env` with `BOT_TOKEN`, `OWNER_SETUP_CODE` (a long random secret), `WEBAPP_URL`, `DATABASE_URL`, and an optional `DEV_ADMIN_ID` for my own testing. Validate them at startup with pydantic-settings. **There are no hardcoded admin IDs or channel IDs.** Admins and the channel are linked at runtime (see section 6).
- **Delivery:** `Dockerfile` + `docker-compose.yml` + a README with deploy steps for **Render or Railway** (HTTPS is required for the Mini App). Use a persistent disk/volume for the SQLite file and image cache.

## 4. Data model

- `Product`: id, title, description, price (int, so'm), old_price (nullable, for sales), category, photos (ordered list of file_ids), sizes (optional list), colors (optional list), weight_grams (optional, to estimate cargo), in_stock (bool), is_new, is_hit, views, created_at, channel_message_id (nullable).
- `Category`: slug, name, emoji, sort_order.
- `Wishlist`: user_id, product_id.
- `CartItem` (server-side, per user): product_id, size, color, qty.
- `Order`: id, user_id, items snapshot (JSON), total, status (new / accepted / cancelled), created_at.
- `Review`: photos, text, customer name, approved (bool). This mirrors the channel's `#отзыв` posts.
- `Setting`: key/value (cargo price, delivery text, contact username, welcome text, banner).
- `User`: telegram id, name, username, language, first_seen, last_seen, blocked_bot.

## 5. Customer features

**Bot (`/start`):**
- Cute greeting with a pink sakura banner image (generate it) and buttons:
  - 🌸 **Do'konni ochish** — opens the Mini App (WebApp button plus the bot's menu button).
  - 🆕 Yangi mahsulotlar
  - 💌 Admin bilan bog'lanish → `https://t.me/fkhrdnvvvva`
  - ⭐ Fikrlar (reviews)
  - 📢 Kanal → channel link
- Deep links: `/start product_<id>` and Mini App `startapp=product_<id>` open that product directly.
- Inline mode: `@botname scarf` shows matching products as cards that can be shared into any chat.

**Mini App:**
- **Home:** petal header, search bar, horizontal category chips (hashtags), "🆕 Yangi" and "🔥 Hit" carousels, a "Kun mahsuloti 🌸" (product of the day) hero card, and a product grid (2 columns, lazy-loaded images, "Sotildi" badge on out-of-stock items).
- **Product page:** swipeable photo gallery with zoom, price (with crossed-out old price when on sale), size/color pickers, a cargo estimate from weight (`ceil(weight/100) × 12.000`), the delivery terms block, and buttons ❤️ Wishlist, 🛍️ Savatga, and 💌 Hoziroq so'rash ("ask now").
- **Bag (Savat):** list of items, qty +/-, total plus estimated cargo. The Telegram **MainButton** says "Buyurtma berish 💌". On tap:
  1. Save an `Order` and build a neat order summary (items, sizes/colors, totals, customer name/@username).
  2. The bot sends the summary to **every admin** with buttons "✅ Qabul qilindi" / "❌ Bekor" and a link to the customer's profile. Tapping these updates the order status and notifies the customer.
  3. The bot sends the customer the same summary plus "Rahmat! 🌸 Admin tez orada siz bilan bog'lanadi", a button that opens the chat with @fkhrdnvvvva, and the summary in a copyable code block so they can paste it to her.
  4. Clear the bag and show a cute petal-burst success screen.
- **Wishlist ❤️**, **Reviews ⭐** gallery, and **Settings** (language, reduced motion).
- Empty states with sakura illustrations and cute copy.

## 6. Admin panel (must be very easy, she's not technical)

**How the owner becomes admin (I don't know her Telegram ID, so the bot must handle this itself):**
- The bot starts in "unclaimed" mode. A one-time link `https://t.me/<bot>?start=claim_<OWNER_SETUP_CODE>` makes whoever opens it the **owner**. The bot stores that user's numeric ID in the DB, then permanently disables the code. Never grant admin by username alone, because usernames can change or be taken.
- The welcome message for the new owner says: "Bu do'kon endi sizniki 🌸 / This shop is now yours", followed by a 3-step tour of the admin panel.
- The owner can add or remove other admins from ⚙️ Sozlamalar ("forward me a message from that person" or "share a contact").
- The owner can **reset ownership / delete all data** from settings. It's her shop, so she must be able to fully take it over.

**Linking her channel (optional, owner-controlled):**
- Channel features stay hidden until she adds the bot as an admin of her channel herself. Detect the `my_chat_member` update, ask the owner in DM "Kanalni ulaymi? / Link this channel?", and save `channel_id` only after she confirms. Only accept channels added by the owner. If the bot is removed from the channel, unlink automatically.

Only users stored as owner/admin in the DB can access the panel. Verify **Telegram WebApp `initData` with HMAC-SHA256** on every API call, and reject stale `auth_date` values (older than 24h). Do every admin check on the server.

**A) Inside the bot, the fastest way:**
- `/admin` opens the menu: ➕ Yangi mahsulot, 📦 Mahsulotlar, 🗂 Kategoriyalar, ⭐ Fikrlar, 🧾 Buyurtmalar, 📊 Statistika, 📣 Xabar yuborish (broadcast), ⚙️ Sozlamalar.
- **Add product wizard** (aiogram FSM): send 1–10 photos (albums supported) → title → price → category (buttons) → sizes (or skip) → colors (or skip) → weight (or skip) → description (or skip) → **preview exactly as it will look** → ✅ Saqlash / ✏️ Tahrirlash / ❌ Bekor. Every step has "⬅️ Orqaga" (back) and "/cancel".
- **Magic shortcut:** if the admin forwards one of her existing channel posts to the bot, parse the hashtag, price, and photos and prefill the wizard. This makes importing old products take seconds.
- After saving: "📢 Kanalga ham joylaymi?" ("Post to the channel too?"). If yes, the bot posts the product to the channel **in the exact channel format** (album + caption):
  ```
  #scarf 🌸

  💰 Narxi: 45.000 so'm
  📦 Kargo: 12.000 so'm / 100g
  ⏳ 10–15 kun
  🚚 Dastavka: O'zbekiston bo'ylab

  Buyurtma berish uchun @fkhrdnvvvva ga yozing 💌
  ```
  Then post a follow-up URL button "🛍️ Do'konda ko'rish" that deep-links to the product in the bot (`https://t.me/<bot>?startapp=product_<id>`). The bot must be a channel admin for this.
- Product list with pagination and search. For each product: edit any field, replace/reorder photos, toggle in-stock / "Sotildi ❌", set sale (old price), mark new/hit, delete (with confirmation).
- Review moderation: forward a customer screenshot to the bot to make it a review, then approve or hide it.

**B) Inside the Mini App:** a pink "👑 Admin" tab, visible only to admins, with the same CRUD in a nice UI. It includes drag-to-reorder photos, photo upload from the phone gallery (the backend sends the photo to the admin's chat via the bot to obtain a `file_id`, then deletes that message), quick stock toggles, an orders list, and a stats dashboard: users, new users this week, top viewed products, most wishlisted, orders per day.

**Broadcast:** send text or a photo to all bot users. Rate-limit it to about 25 messages/sec, mark users who blocked the bot, and show a live progress and final report.

## 7. Quality & safety

- Validate every API input with Pydantic. Limit text lengths, price range, and image sizes/types.
- Handle Telegram errors such as `TelegramRetryAfter`, blocked users, and expired/invalid file_ids.
- Make the Mini App work on iOS/Android Telegram and Telegram Desktop. Handle viewport, safe areas, BackButton, MainButton, and theme changes.
- Add structured logging, and send admins a short DM when an unhandled error happens.
- Seed the DB with 3 demo products in the channel style (#jempir 99.000, #wig 125.000, #scarf 45.000) so the shop doesn't look empty on first run.
- Write tests (pytest): initData verification (valid / tampered / expired), claim link works once and only once, channel linking ignores non-owners, price formatting (`99000 → "99.000 so'm"`), cargo calculation, order message builder, channel caption builder, and admin endpoints rejecting non-admins.

## 8. Deliverables

1. Full repo with clear structure (`bot/`, `api/`, `webapp/`, `db/`, `tests/`).
2. README **in simple Uzbek and English** that covers: creating the bot with @BotFather, generating the owner claim link, how the owner can transfer the bot itself to her account via BotFather (Bot Settings → Transfer Ownership), adding the bot as a channel admin (done by the owner), setting the Mini App URL and menu button in BotFather (`/newapp`, `/setmenubutton`), enabling inline mode, and deploying to Render step by step.
3. A short **"Admin uchun qo'llanma"** (admin guide in Uzbek): how to add a product in under 30 seconds, edit, mark sold, and post to the channel.
4. Run everything locally (use a tunnel like cloudflared/ngrok for HTTPS), run the tests, and show me screenshots of the Home, Product, Bag, and Admin screens before finishing.

Make it feel like a little pink sakura boutique inside Telegram, something the owner is proud to show her customers. 🌸
