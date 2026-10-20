import os
from PIL import Image, ImageDraw, ImageFont


def generate_demo_images(output_dir: str = "./media_cache"):
    os.makedirs(output_dir, exist_ok=True)

    items = [
        ("demo_jempir_1.png", "Aesthetic Jempir 🌸", "#FFE4EC", "#E75480", "🧶 99.000 so'm"),
        ("demo_jempir_2.png", "Jempir Tafsilotlari 💗", "#FFF0F5", "#FF69B4", "Sakura Pink S-M-L"),
        ("demo_wig_1.png", "Pastel Lolita Wig 💇‍♀️", "#FFF5F7", "#D43F8D", "💇‍♀️ 125.000 so'm"),
        ("demo_wig_2.png", "Parik Ko'rinishi ✨", "#FFEBF2", "#C71585", "Pastel & Binafsha"),
        ("demo_scarf_1.png", "Yulduzli Shoyi Sharf 🧣", "#FFF8F5", "#E75480", "🧣 45.000 so'm"),
        ("demo_scarf_2.png", "Sharf Matosi 🌸", "#FFE4EC", "#DB7093", "200x50 sm"),
        ("demo_review_1.png", "Mijoz fikri 💌", "#FFF0F5", "#E75480", "⭐️⭐️⭐️⭐️⭐️ 5/5"),
        ("bot_banner.png", "🌸 SAKURA SHOP 🌸", "#FFE4EC", "#C71585", "Xitoy brendlari & Aesthetic kiyimlar ✨"),
    ]

    for filename, title, bg_color, accent_color, subtitle in items:
        file_path = os.path.join(output_dir, filename)
        if os.path.exists(file_path):
            continue

        width, height = (800, 800) if "banner" not in filename else (1000, 500)
        img = Image.new("RGB", (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)

        # Draw cute soft circular flower petals in corners
        draw.ellipse([20, 20, 180, 180], fill="#FFD1DC")
        draw.ellipse([width - 180, 20, width - 20, 180], fill="#FFD1DC")
        draw.ellipse([20, height - 180, 180, height - 20], fill="#FFD1DC")
        draw.ellipse([width - 180, height - 180, width - 20, height - 20], fill="#FFD1DC")

        # Decorative central frame
        margin = 40
        draw.rounded_rectangle(
            [margin, margin, width - margin, height - margin],
            radius=30,
            outline=accent_color,
            width=6,
        )

        # Draw decorative text
        # Since custom ttf might not be in standard path, default bitmap or basic font is used
        try:
            font_title = ImageFont.truetype("arial.ttf", 44)
            font_sub = ImageFont.truetype("arial.ttf", 32)
        except Exception:
            font_title = ImageFont.load_default()
            font_sub = ImageFont.load_default()

        # Text bounding
        bbox_title = draw.textbbox((0, 0), title, font=font_title)
        w_title = bbox_title[2] - bbox_title[0]
        draw.text(((width - w_title) // 2, height // 2 - 50), title, fill=accent_color, font=font_title)

        bbox_sub = draw.textbbox((0, 0), subtitle, font=font_sub)
        w_sub = bbox_sub[2] - bbox_sub[0]
        draw.text(((width - w_sub) // 2, height // 2 + 30), subtitle, fill="#5B3A4A", font=font_sub)

        img.save(file_path, "PNG")


if __name__ == "__main__":
    generate_demo_images()
