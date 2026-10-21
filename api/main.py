import os
import asyncio
import logging
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from api.config import settings
from api.routes import (
    products,
    categories,
    cart,
    orders,
    wishlist,
    reviews,
    settings as settings_route,
    media,
    admin,
    contest,
)
from bot.bot import setup_routers, setup_bot_commands, notify_admins_of_error
from bot.loader import bot, dp
from bot.services.contest_scheduler import run_contest_scheduler
from db.generate_images import generate_demo_images
from db.seed import seed_database
from db.session import init_db, engine
from bot.services.ownership import setup_code_is_safe

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sakura_shop")

bot_polling_task = None
contest_scheduler_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize DB and seed demo data
    logger.info("Initializing database...")
    await init_db()
    generate_demo_images(settings.MEDIA_CACHE_DIR)
    await seed_database()
    logger.info("Database and demo media initialized successfully.")
    # On Render, "sqlite" here means DATABASE_URL is missing and data is wiped on every restart.
    logger.info(f"Database backend: {engine.dialect.name}")
    if not setup_code_is_safe():
        logger.warning(
            "OWNER_SETUP_CODE is empty, shorter than 16 chars or the public default: "
            "first-owner claim is disabled. Set a long random value in the environment."
        )

    # 2. Start Bot Polling and Contest Scheduler if configured
    global bot_polling_task, contest_scheduler_task
    if bot and dp:
        setup_routers(dp)
        await setup_bot_commands(bot)

        async def start_polling():
            try:
                logger.info("Starting Telegram Bot polling with chat_member updates...")
                await dp.start_polling(
                    bot,
                    allowed_updates=[
                        "message",
                        "callback_query",
                        "inline_query",
                        "my_chat_member",
                        "chat_member",
                    ],
                )
            except asyncio.CancelledError:
                logger.info("Bot polling cancelled.")
            except Exception as e:
                logger.error(f"Bot polling error: {e}")

        bot_polling_task = asyncio.create_task(start_polling())
        contest_scheduler_task = asyncio.create_task(run_contest_scheduler(bot))
    else:
        logger.info("Bot token not configured or mock mode. Skipping bot polling.")

    yield

    # Shutdown
    if contest_scheduler_task:
        contest_scheduler_task.cancel()
        try:
            await contest_scheduler_task
        except asyncio.CancelledError:
            pass
    if bot_polling_task:
        bot_polling_task.cancel()
        try:
            await bot_polling_task
        except asyncio.CancelledError:
            pass
    if bot:
        await bot.session.close()
    logger.info("Sakura Shop server shut down gracefully.")


app = FastAPI(
    title="Sakura Shop API",
    description="Backend API and Mini App server for Sakura Shop Telegram Store 🌸",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for Telegram WebApp
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Exception Handler with admin alert
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    err_tb = traceback.format_exc()
    logger.error(f"Unhandled exception on {request.method} {request.url.path}:\n{err_tb}")
    # Notify admins asynchronously
    asyncio.create_task(notify_admins_of_error(f"{request.method} {request.url.path}\n{str(exc)}"))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Kutilmagan server xatoligi yuz berdi. Iltimos, keyinroq qayta urinib ko'ring."},
    )


# Mount API Routes
app.include_router(products.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(cart.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(wishlist.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
app.include_router(settings_route.router, prefix="/api")
app.include_router(media.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(contest.router, prefix="/api")
app.include_router(contest.admin_router, prefix="/api")


# Health check
@app.get("/api/health")
@app.get("/health")
async def health_check():
    return {"status": "ok", "shop": "Sakura Shop 🌸", "version": "1.0.0"}


# Mount Static Frontend
dist_dir = Path(__file__).resolve().parent.parent / "webapp" / "dist"
if dist_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="assets")

    @app.get("/")
    async def serve_index():
        return FileResponse(str(dist_dir / "index.html"))

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        requested_file = dist_dir / full_path
        if requested_file.is_file():
            return FileResponse(str(requested_file))
        # Fallback to index.html for SPA
        return FileResponse(str(dist_dir / "index.html"))
else:
    @app.get("/")
    async def index_placeholder():
        return {
            "message": "Sakura Shop API is running 🌸",
            "frontend_status": "Vite React Mini App is compiling or not built yet.",
            "api_docs": "/docs",
        }
