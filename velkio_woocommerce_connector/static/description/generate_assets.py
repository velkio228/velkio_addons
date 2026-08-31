from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent


def font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


GOLD = "#c99327"


def make_banner():
    """Premium dark aesthetic. This PIL fallback approximates the real banner
    (which is composited via HTML/CSS for gradients, glass cards and glow —
    see the project notes) so a from-scratch regen still looks on-brand.
    """
    NAVY = (10, 14, 23)
    img = Image.new("RGB", (1280, 500), NAVY)
    draw = ImageDraw.Draw(img)
    for x in range(1280):
        t = x / 1280
        r = int(10 + (19 - 10) * (1 - abs(t - 0.55) * 1.8) if abs(t - 0.55) < 0.55 else 10)
        draw.line([(x, 0), (x, 500)], fill=(max(10, r), 14, max(23, r + 5)))
    draw.rectangle((0, 0, 1280, 2), fill=GOLD)
    draw.rounded_rectangle((14, 14, 1266, 486), 22, outline=(201, 147, 39, 40), width=1)

    draw.text((80, 50), "PREMIUM ODOO INTEGRATION", fill="#b6975a", font=font(12, True))
    draw.text((78, 78), "Odoo WooCommerce Connector", fill="#fbf9f5", font=font(34, True))
    draw.rectangle((80, 124, 136, 127), fill=GOLD)
    draw.text((80, 136), "for Odoo 19 · Community / Enterprise", fill="#d9ab4e", font=font(16, True))
    draw.text((80, 178), "Products    Customers    Orders    Logs    Dashboard", fill="#c7cbd4", font=font(14, True))
    draw.text((80, 216), "Complete synchronization workflow by Velkio", fill="#8b93a3", font=font(14))

    rounded(draw, (80, 250, 264, 292), 10, GOLD)
    draw.text((100, 262), "Multi Store Ready", fill="#1c1305", font=font(16, True))

    # Odoo <-> WooCommerce connector graphic
    draw.text((80, 342), "TWO-WAY SYNC", fill="#8b93a3", font=font(11, True))
    draw.ellipse((80, 362, 148, 430), outline=GOLD, width=2)
    draw.text((100, 388), "odoo", fill="#f0d9a3", font=font(15, True))
    for lx in range(158, 376, 13):
        draw.line([(lx, 396), (lx + 6, 396)], fill=(255, 255, 255, 60), width=2)
    draw.ellipse((250, 390, 263, 403), fill=GOLD)
    draw.ellipse((200, 390, 213, 403), fill="#37b3ad")
    rounded(draw, (386, 368, 462, 420), 14, "#7f54b3")
    draw.text((404, 384), "Woo", fill="#ffffff", font=font(18, True))

    card_x, card_y = 760, 96
    rounded(draw, (card_x, card_y, card_x + 390, card_y + 272), 16, (22, 28, 42), outline=(70, 76, 92), width=1)
    draw.text((card_x + 24, card_y + 22), "SYNC DASHBOARD", fill="#9199aa", font=font(12, True))
    labels = [("Products", 84, "#e2b657"), ("Customers", 42, "#37b3ad"), ("Orders", 31, "#e08a3c")]
    y = card_y + 60
    for label, value, color in labels:
        draw.rectangle((card_x + 24, y + 14, card_x + 27, y + 38), fill=color)
        draw.text((card_x + 44, y + 16), label, fill="#c7cbd4", font=font(14, True))
        draw.text((card_x + 300, y + 12), str(value), fill=color, font=font(22, True))
        y += 60

    # Velkio brand badge, top-right — a clean cutout of the supplied logo artwork
    # (static/description/velkio_logo.png), not a redrawn placeholder.
    logo_path = ROOT / "velkio_logo.png"
    if logo_path.exists():
        logo = Image.open(logo_path).convert("RGBA")
        logo_w = 190
        logo_h = int(logo.height * (logo_w / logo.width))
        logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
        img.paste(logo, (1280 - logo_w - 26, 24), logo)
    img.save(ROOT / "banner.png", "PNG")


def make_icon():
    """Crop the Velkio mark (velkio_mark.png) down to just the gold "V" glyph
    on its navy field — the same fixed crop used to produce the current
    icon.png/img.png, kept here so the app icon stays in sync if regenerated.
    """
    mark_path = ROOT / "velkio_mark.png"
    if mark_path.exists():
        mark = Image.open(mark_path).convert("RGBA")
        cx, cy, side = 467, 433, 430
        box = (cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2)
        crop = mark.crop(box)
        bg = Image.new("RGBA", crop.size, (10, 9, 20, 255))
        bg.paste(crop, (0, 0), crop)
        icon = bg.resize((512, 512), Image.LANCZOS)
    else:
        icon = Image.new("RGBA", (512, 512), GOLD)
        draw = ImageDraw.Draw(icon)
        rounded(draw, (70, 82, 442, 430), 48, "#0a0914")
        draw.text((186, 170), "V", fill=GOLD, font=font(180, True))
    icon.save(ROOT / "icon.png", "PNG")
    icon.save(ROOT / "img.png", "PNG")


if __name__ == "__main__":
    make_banner()
    make_icon()
