# 🌸 Sakura Shop — Telegram Mini App & Bot 🌸

> **Kanal:** [@sakuraaa_chinese_shop](https://t.me/sakuraaa_chinese_shop)  
> **Egasi:** [@fkhrdnvvvva](https://t.me/fkhrdnvvvva)  
> **Tavsif:** Toshkentdagi Xitoy brendlari, aesthetic kiyimlar, jempirlar, pariklar va nozik aksessuarlar uchun to'liq ishlab chiqilgan, zamonaviy Telegram Mini App do'koni.

---

## 🇺🇿 O'zbekcha Qo'llanma

### 🌟 Imkoniyatlar
1. **🌸 Aesthetic Dizayn:** Pushti sakura palitrasi (`#FFE4EC`, `#FFB7C5`, `#E75480`), suzuvchi sakura barglari effekti (Canvas), inline SVG sakura shoxlari va shaffof glassmorphism kartalar.
2. **🛍️ Mini App Do'koni:**
   - 2 ustunli katalog, tezkor qidiruv, #hashtag kategoriyalar.
   - "Kun mahsuloti 🌸", "🆕 Yangi kelganlar" va "🔥 Hit" karusellari.
   - Mahsulot sahifasi: rasmlar galereyasi va zoom, o'lcham va rang tanlash, kargoni avtomatik hisoblash (`ceil(og'irlik / 100) * 12.000 so'm`).
   - Savat va Telegram `MainButton` orqali buyurtma berish.
   - Istaklar ro'yxati (Wishlist) va mijozlar fikrlari (#отзыв).
3. **👑 Oson Admin Boshqaruvi:**
   - **Xavfsiz biriktirish:** Do'kon egasi maxfiy bir martalik link orqali do'konni o'zlashtiradi (`claim_<OWNER_SETUP_CODE>`).
   - **Sehrli import:** Kanaldagi eski postni botga forward qilib, 5 soniyada yangi mahsulotga aylantirish.
   - **1-bosishda kanalga joylash:** Mahsulotni do'konga qo'shgach, to'g'ridan-to'g'ri kanalga chiroyli formatda va `🛍️ Do'konda ko'rish` tugmasi bilan post qilish.
   - **Mini App ichidagi Admin paneli:** Statistika, rasmlarni to'g'ridan-to'g'ri galereyadan yuklash (Telegram getFile orqali tekinga keshlanadi), tezkor "Sotildi ❌ / Mavjud ✅" tugmasi, buyurtmalarni qabul qilish.

---

### 🚀 O'rnatish va Ishga Tushirish

#### 1. Bot yaratish (@BotFather orqali)
1. Telegramda `@BotFather` ga kiring va `/newbot` buyrug'ini yuboring.
2. Bot nomi va username'ini kiriting (masalan: `SakuraShopMiniBot`).
3. Berilgan `BOT_TOKEN`ni nusxalang.
4. Inline qidiruvni yoqish: `@BotFather`da `/setinline` buyrug'ini bosing, botingizni tanlang va qidiruv matnini yozing: `Kiyimlarni qidirish... 🌸`.
5. Mini App menyu tugmasini sozlash:
   - `/setmenubutton` -> botingizni tanlang -> `🌸 Do'kon` deb yozing -> Mini App havolangizni (masalan: `https://your-domain.onrender.com`) yuboring.
6. Mini App yaratish:
   - `/newapp` -> botingizni tanlang -> Title: `Sakura Shop 🌸` -> Description: `Aesthetic kiyimlar va aksessuarlar` -> Rasm yuklang -> WebApp URL kiriting.

#### 2. Botni do'kon egasining o'z hisobiga o'tkazish (Transfer Ownership)
Do'kon egasi to'liq xavfsiz va mustaqil bo'lishi uchun botni uning Telegram hisobiga o'tkazib berishingiz mumkin:
1. `@BotFather`ga kiring va `/mybots` buyrug'ini yuboring.
2. Botingizni tanlang -> **Bot Settings** -> **Transfer Ownership**.
3. Do'kon egasining username'ini kiriting (`@fkhrdnvvvva`).
4. Bot egasining 2FA parolini tasdiqlang. Bot endi 100% uning shaxsiy mulkiga aylanadi!

#### 3. Do'konni biriktirish (Claim link)
1. `.env` faylida kuchli `OWNER_SETUP_CODE` belgilang (masalan: `sakura_secret_key_889900`).
2. Do'kon egasiga maxsus bir martalik havola yuboring:
   `https://t.me/<BOT_USERNAME>?start=claim_<OWNER_SETUP_CODE>`
3. Egasi ushbu linkni bosishi bilan bot uni bazada doimiy "owner" deb saqlaydi va claim kodini abadiy yopadi.

#### 4. Kanalni ulash
1. Do'kon egasi botni o'zining `@sakuraaa_chinese_shop` kanaliga **Administrator** qilib qo'shadi.
2. Bot egasining shaxsiy yozishmasiga (DM) avtomatik ravishda: *"🌸 Yangi kanal aniqlandi. Ulaymi?"* xabarini yuboradi.
3. Egasi **✅ Ha, ulash** tugmasini bosishi bilan kanal do'konga ulanadi.

---

### 🌐 Render.com ga Deploy Qilish (Step-by-Step)

Render bepul HTTPS taqdim etadi (Telegram Mini App uchun HTTPS majburiy):

1. Loyihani GitHub'ga yuklang (Private yoki Public repository).
2. [Render.com](https://render.com) ga kiring va **New +** -> **Web Service** ni tanlang.
3. GitHub repository'ingizni ulang.
4. Sozlamalarni kiriting:
   - **Environment:** `Docker`
   - **Region:** `Frankfurt (EU Central)` yoki o'zingizga yaqin hudud.
   - **Instance Type:** `Free` yoki `Starter`.
5. **Environment Variables (Muhit o'zgaruvchilari):**
   - `BOT_TOKEN`: @BotFather'dan olingan token
   - `OWNER_SETUP_CODE`: do'kon egasi uchun maxfiy kod
   - `WEBAPP_URL`: Render'dagi xizmatingiz havolasi (`https://sakura-shop.onrender.com`)
   - `DATABASE_URL`: `sqlite+aiosqlite:////app/data/sakura_shop.db`
   - `HOST`: `0.0.0.0`
   - `PORT`: `8000`
   - `MEDIA_CACHE_DIR`: `/app/media_cache`
6. **Disks (Doimiy xotira):**
   - Agar Starter rejasida bo'lsangiz: **Disks** bo'limida Disk qo'shing:
     - Name: `sakura_data`
     - Mount Path: `/app/data`
     - Size: `1 GB`
7. **Deploy:** **Create Web Service** tugmasini bosing. Docker avtomatik ravishda React frontendni va FastAPI backendni build qilib ishga tushiradi!

---

## 🇬🇧 English Documentation

### Architecture
- **Bot:** Python 3.12 + aiogram 3 (FSM wizards, dynamic channel detection, inline query mode).
- **Backend:** FastAPI with unified async lifespan, Pydantic v2 settings & request validation.
- **Database:** SQLAlchemy 2.0 Async + SQLite (PostgreSQL ready via `DATABASE_URL`) + Alembic migrations.
- **Mini App:** React 18, TypeScript, Vite, Tailwind CSS, Telegram WebApp SDK.
- **Images:** Telegram `getFile` reverse proxy + local disk caching (zero external hosting cost).

### Environment Variables
| Variable | Description |
|---|---|
| `BOT_TOKEN` | Telegram Bot token from @BotFather |
| `OWNER_SETUP_CODE` | One-time secret token for `/start claim_<CODE>` |
| `WEBAPP_URL` | Public HTTPS domain where the Mini App is served |
| `DATABASE_URL` | Async DB connection string (default: SQLite) |
| `DEV_ADMIN_ID` | Optional numeric Telegram ID for local testing |
| `MEDIA_CACHE_DIR` | Directory for cached Telegram images (default: `./media_cache`) |

### Local Run
```bash
# 1. Install backend dependencies
pip install -r requirements.txt

# 2. Build Mini App frontend
cd webapp
npm install
npm run build
cd ..

# 3. Seed demo products & generate images
python -m db.seed
python -m db.generate_images

# 4. Run automated test suite (13 passing tests)
pytest -v

# 5. Start unified application
python run.py
```
App will be accessible at `http://localhost:8000`. Use `cloudflared` or `ngrok` for HTTPS tunnel when testing inside Telegram.
