import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from db.session import async_session_factory, init_db
from db.models import Category, Product, Setting, Review, User, Admin


async def seed_database() -> None:
    await init_db()
    async with async_session_factory() as session:
        # Check if already seeded
        result = await session.execute(select(Category))
        if result.scalars().first() is not None:
            return  # Already seeded

        # 1. Categories
        categories = [
            Category(slug="jempir", name="Jempir & Sviter", emoji="🧶", sort_order=1),
            Category(slug="wig", name="Pariklar (Wigs)", emoji="💇‍♀️", sort_order=2),
            Category(slug="scarf", name="Sharf & Ro'mol", emoji="🧣", sort_order=3),
            Category(slug="sumka", name="Sumkalar", emoji="👜", sort_order=4),
            Category(slug="aksessuar", name="Aksessuarlar", emoji="🎀", sort_order=5),
        ]
        session.add_all(categories)

        # 2. Settings
        default_settings = [
            Setting(key="cargo_rate", value="12000"),  # 12.000 so'm / 100g
            Setting(key="delivery_days", value="10–15 kun"),
            Setting(key="delivery_scope", value="O'zbekiston bo'ylab"),
            Setting(key="payment_terms", value="100% oldindan to'lov"),
            Setting(key="location", value="Toshkent"),
            Setting(key="contact_username", value="fkhrdnvvvva"),
            Setting(key="channel_url", value="https://t.me/sakuraaa_chinese_shop"),
            Setting(key="channel_id", value=""),
            Setting(key="owner_claimed_at", value=""),
            Setting(key="welcome_text", value="Sakura shop ga xush kelibsiz! 🌸 Xitoy brendlari va aesthetic kiyimlar do'koni."),
        ]
        session.add_all(default_settings)

        # 3. Products
        demo_products = [
            Product(
                title="Aesthetic Vintage Pushti Jempir 🌸",
                description="Yumshoq, qulay va iliq pushti jempir. Aesthetic koreys va xitoy uslubidagi qizlar uchun ajoyib tanlov! Qalin to'qilgan, qishki va kuzgi ob-havo uchun mos. 🎀",
                price=99000,
                old_price=135000,
                category="jempir",
                photos=["demo_jempir_1.png", "demo_jempir_2.png"],
                sizes=["S", "M", "L"],
                colors=["Sakura pushti 🌸", "Sutli oq 🤍", "Krem 🍦"],
                weight_grams=350,
                in_stock=True,
                is_new=True,
                is_hit=True,
                views=128,
            ),
            Product(
                title="Pastel Pushti Lolita Parik (Wig) 💇‍♀️",
                description="Yuqori sifatli termotola, tabiiy jilo va yumshoq jingalaklar. Cosplay va kundalik aesthetic obrazlar uchun mukammal! Oson taraladi va shaklini saqlaydi. ✨",
                price=125000,
                old_price=160000,
                category="wig",
                photos=["demo_wig_1.png", "demo_wig_2.png"],
                sizes=["Universal"],
                colors=["Pastel pushti 🌸", "Och binafsha 💜"],
                weight_grams=250,
                in_stock=True,
                is_new=True,
                is_hit=False,
                views=89,
            ),
            Product(
                title="Iliq Yulduzli Shoyi Sharf 🧣",
                description="Yumshoq jun va ipak aralashmasidan tayyorlangan zamonaviy sharf. Sovuq kunlarda issiq saqlaydi va har qanday kiyimga noziklik bag'ishlaydi. 💗",
                price=45000,
                old_price=60000,
                category="scarf",
                photos=["demo_scarf_1.png", "demo_scarf_2.png"],
                sizes=["200x50 sm"],
                colors=["Pushti-krem 🌸", "Kulrang-pushti 🎀"],
                weight_grams=180,
                in_stock=True,
                is_new=False,
                is_hit=True,
                views=215,
            ),
        ]
        session.add_all(demo_products)

        # 4. Reviews
        reviews = [
            Review(
                customer_name="Madina",
                text="Jempir keldi, sifati juda zo'r ekan! Yumshoq va xuddi rasmdagidek chiqdi, kargo ham tez yetib keldi. Rahmat kattakon! 🌸🎀",
                photos=["demo_review_1.png"],
                approved=True,
            ),
            Review(
                customer_name="Nilufar 🎀",
                text="Parik va sharf oldim, rangi juda nozik va yoqimli. Yetkazib berish aytilgan muddatda keldi. Do'konga baraka bersin! ✨💗",
                photos=[],
                approved=True,
            ),
        ]
        session.add_all(reviews)

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed_database())
