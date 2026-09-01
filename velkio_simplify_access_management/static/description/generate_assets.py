"""
Regenerate the Odoo Apps Store artwork for "Velkio Simplify Access Management".

Outputs (static/description/):
  * banner.png       - 1280x640 static banner (Apps Store card + hero fallback)
  * banner.gif       - 1280x640 animated banner (tab-by-tab restriction preview)
  * icon.png / img.png - 512x512 app icon (Velkio mark on navy)
  * screenshot_list.png - 1280-wide mock-up of the Access Studio list view
  * screenshot_form.png - 1280-wide mock-up of the Access Studio form view

Brand: Velkio navy (#0a0e17 / #0f172a) + gold (#c99327), with the Access Studio
violet (#7c3aed) as the product accent.  Uses the supplied brand art
(velkio_logo.png / velkio_mark.png), never a redrawn placeholder.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent

NAVY = (10, 14, 23)
NAVY_2 = (15, 23, 42)
GOLD = "#c99327"
GOLD_SOFT = "#e8c468"
VIOLET = "#7c3aed"
INK_SOFT = "#c7cbd4"
INK_FAINT = "#8b93a3"

TABS = [
    "Hide Menu", "Model Access", "Field Access", "Domain Access",
    "Button/Tab", "Filter/Group By", "Chatter", "Global",
]


def font(size, bold=False):
    for path in (
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
        f"/usr/share/fonts/truetype/liberation2/LiberationSans-{'Bold' if bold else 'Regular'}.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _bg(w, h):
    img = Image.new("RGB", (w, h), NAVY)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        v = int(10 + 9 * (1 - abs(t - 0.35) * 1.6)) if abs(t - 0.35) < 0.6 else 10
        d.line([(0, y), (w, y)], fill=(max(10, v), 14, max(23, v + 6)))
    d.rectangle((0, 0, w, 3), fill=GOLD)
    d.rounded_rectangle((16, 16, w - 16, h - 16), 22, outline=(201, 147, 39, 60), width=1)
    return img, d


def _paste_logo(img, width, margin=26):
    p = ROOT / "velkio_logo.png"
    if not p.exists():
        return
    logo = Image.open(p).convert("RGBA")
    h = int(logo.height * (width / logo.width))
    logo = logo.resize((width, h), Image.LANCZOS)
    img.paste(logo, (img.width - width - margin, margin), logo)


def _studio_card(d, x, y, w, h, active_tab):
    d.rounded_rectangle((x, y, x + w, y + h), 16, fill=(22, 28, 42), outline=(70, 76, 92), width=1)
    d.rectangle((x, y, x + w, y + 4), fill=VIOLET)
    d.text((x + 22, y + 20), "ACCESS STUDIO", fill=INK_FAINT, font=font(12, True))
    d.text((x + 22, y + 40), "Restriction Rule  -  TEST", fill="#f3f0ff", font=font(17, True))

    # tab pills
    tx, ty = x + 22, y + 82
    small = font(11, True)
    for i, name in enumerate(TABS):
        tw = small.getlength(name) + 18
        if tx + tw > x + w - 22:
            tx, ty = x + 22, ty + 30
        on = i == active_tab
        d.rounded_rectangle((tx, ty, tx + tw, ty + 22), 8,
                            fill=VIOLET if on else (32, 38, 54),
                            outline=(124, 58, 237, 120) if not on else None, width=1)
        d.text((tx + 9, ty + 5), name, fill="#ffffff" if on else INK_SOFT, font=small)
        tx += tw + 8

    # "hidden" rows preview
    ry = ty + 44
    rows = ["Sales / Orders menu", "Delete button", "Cost field", "Group By: Salesperson", "Send Message"]
    for i, label in enumerate(rows):
        hidden = i <= active_tab % len(rows)
        col = "#4b5468" if hidden else INK_SOFT
        d.rounded_rectangle((x + 22, ry, x + w - 22, ry + 26), 7, fill=(28, 34, 48))
        d.text((x + 40, ry + 6), label, fill=col, font=font(13, True))
        # lock / eye-off glyph
        gx = x + w - 44
        if hidden:
            d.rounded_rectangle((gx, ry + 8, gx + 12, ry + 18), 2, outline=GOLD, width=2)
            d.line((gx + 2, ry + 8, gx + 2, ry + 5), fill=GOLD, width=2)
            d.line((gx + 10, ry + 8, gx + 10, ry + 5), fill=GOLD, width=2)
            d.arc((gx + 2, ry + 2, gx + 10, ry + 10), 180, 360, fill=GOLD, width=2)
        else:
            d.ellipse((gx, ry + 9, gx + 12, ry + 15), outline="#37b3ad", width=2)
        ry += 32


def _hero_text(d):
    d.text((80, 78), "PREMIUM ODOO ACCESS CONTROL", fill="#b6975a", font=font(12, True))
    d.text((78, 108), "Simplify Access", fill="#fbf9f5", font=font(40, True))
    d.text((78, 156), "Management", fill="#fbf9f5", font=font(40, True))
    d.rectangle((82, 210, 142, 213), fill=GOLD)
    d.text((82, 226), "for Odoo 17  -  Community & Enterprise", fill=GOLD_SOFT, font=font(16, True))
    d.text((82, 268), "Menus  .  Fields  .  Views  .  Buttons  .  Reports  .  Filters  .  Records",
           fill=INK_SOFT, font=font(13, True))
    d.text((82, 296), "One screen. Every restriction. Per user.", fill=INK_FAINT, font=font(14))

    f = font(15, True)
    txt = "No record rules   -   No XML"
    d.rounded_rectangle((82, 336, 116 + f.getlength(txt), 376), 10, fill=GOLD)
    d.text((100, 348), txt, fill="#1c1305", font=f)


def make_banner_png():
    W, H = 1280, 640
    img, d = _bg(W, H)
    _hero_text(d)
    _studio_card(d, 720, 150, 476, 366, active_tab=1)
    _paste_logo(img, 188)
    img.save(ROOT / "banner.png", "PNG")


def make_banner_gif():
    W, H = 1280, 640
    frames = []
    for i in range(len(TABS)):
        img, d = _bg(W, H)
        _hero_text(d)
        _studio_card(d, 720, 150, 476, 366, active_tab=i)
        _paste_logo(img, 188)
        frames.append(img.convert("P", palette=Image.ADAPTIVE, colors=128))
    frames[0].save(
        ROOT / "banner.gif", save_all=True, append_images=frames[1:],
        duration=750, loop=0, optimize=True,
    )


def make_icon():
    mark = ROOT / "velkio_mark.png"
    if mark.exists():
        m = Image.open(mark).convert("RGBA")
        cx, cy, side = 467, 433, 430
        crop = m.crop((cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2))
        bg = Image.new("RGBA", crop.size, (10, 9, 20, 255))
        bg.paste(crop, (0, 0), crop)
        icon = bg.resize((512, 512), Image.LANCZOS)
    else:
        icon = Image.new("RGBA", (512, 512), NAVY)
        d = ImageDraw.Draw(icon)
        d.rounded_rectangle((70, 82, 442, 430), 48, fill=NAVY_2, outline=GOLD, width=6)
        d.text((196, 150), "V", fill=GOLD, font=font(200, True))
    icon.save(ROOT / "icon.png", "PNG")
    icon.save(ROOT / "img.png", "PNG")


# ===================================================================
#  UI screenshots (mock-ups of the real Access Studio backend, so the
#  Apps Store page always shows the app populated with sample data)
# ===================================================================

S_SURFACE = "#fbfaff"
S_CARD = "#ffffff"
S_BORDER = "#e9e3f7"
S_BORDER2 = "#dbd1f1"
S_V = "#7c3aed"
S_VDEEP = "#5b21b6"
S_VSOFT = "#efe9fd"
S_SUNK = "#f4f1fd"
S_INK = "#1e1b2e"
S_INKSOFT = "#6a6280"
S_INKFAINT = "#9a92ad"
S_GREEN = "#0f9d6b"

TAG_COLORS = [
    ("#ece7fb", "#5b21b6"), ("#e6f4ec", "#0f7a4f"), ("#fdeede", "#9a4a00"),
    ("#e4eefb", "#1b4f8f"), ("#fbe7ef", "#9c1c50"), ("#e6f3f6", "#0a6a78"),
]


def _navbar(d, w):
    d.rectangle((0, 0, w, 46), fill=S_CARD)
    d.line((0, 46, w, 46), fill=S_BORDER)
    d.rounded_rectangle((16, 11, 40, 35), 7, fill=S_V)
    # padlock
    d.rounded_rectangle((22, 22, 34, 31), 2, fill="#ffffff")
    d.arc((23, 15, 33, 26), 180, 360, fill="#ffffff", width=2)
    d.ellipse((26.5, 24.5, 29.5, 27.5), fill=S_V)
    d.text((50, 15), "Access Studio", fill=S_INK, font=font(15, True))


def _new_button(d, x, y):
    d.rounded_rectangle((x, y, x + 56, y + 26), 8, fill=S_V)
    d.text((x + 14, y + 6), "New", fill="#ffffff", font=font(12, True))


def _checkbox(d, x, y, checked, size=14):
    d.rounded_rectangle((x, y, x + size, y + size), 4,
                        fill=S_V if checked else "#ffffff",
                        outline=S_V if checked else S_BORDER2, width=1)
    if checked:
        d.line((x + 3, y + size / 2, x + size / 2 - 1, y + size - 3), fill="#fff", width=2)
        d.line((x + size / 2 - 1, y + size - 3, x + size - 3, y + 3), fill="#fff", width=2)


def _chip(d, x, y, text, f, ci=0):
    bg, fg = TAG_COLORS[ci % len(TAG_COLORS)]
    tw = f.getlength(text)
    d.rounded_rectangle((x, y, x + tw + 20, y + 20), 10, fill=bg)
    d.text((x + 10, y + 4), text, fill=fg, font=f)
    return tw + 20


def _control_panel(d, w, h_bottom):
    d.rectangle((0, 46, w, h_bottom), fill="#faf8ff")
    d.line((0, h_bottom, w, h_bottom), fill=S_BORDER)


def make_screenshot_list():
    W, H = 1280, 556
    img = Image.new("RGB", (W, H), S_SURFACE)
    d = ImageDraw.Draw(img)
    _navbar(d, W)
    _control_panel(d, W, 98)
    _new_button(d, 16, 58)
    d.text((88, 64), "Access Management", fill=S_INK, font=font(15, True))
    # search bar
    d.rounded_rectangle((W - 380, 58, W - 16, 84), 13, fill="#fff", outline=S_BORDER2, width=1)
    d.ellipse((W - 368, 66, W - 358, 76), outline=S_INKFAINT, width=2)
    d.rounded_rectangle((W - 350, 64, W - 322, 78), 6, fill=S_VSOFT)
    d.text((W - 344, 66), "All", fill=S_VDEEP, font=font(11, True))
    d.text((W - 300, 65), "Search...", fill=S_INKFAINT, font=font(12))

    # search panel
    d.line((150, 98, 150, H), fill=S_BORDER)
    d.text((18, 118), "ALL", fill=S_INKSOFT, font=font(10, True))
    for i, lbl in enumerate(("Rules", "Users", "Companies")):
        d.text((18, 148 + i * 26), lbl, fill=S_INKFAINT, font=font(11, True))

    # list card
    cx, cy, cw = 168, 116, W - 168 - 20
    d.rounded_rectangle((cx, cy, cx + cw, H - 18), 14, fill=S_CARD, outline=S_BORDER, width=1)
    cols = [(cx + 18, "NAME"), (cx + 250, "CREATED BY"), (cx + 430, "CREATED ON"),
            (cx + 600, "USERS"), (cx + 860, "ACCESS RULES"), (cx + 1000, "ACTIVE")]
    d.rectangle((cx + 1, cy + 1, cx + cw - 1, cy + 36), fill=S_SUNK)
    for x, t in cols:
        d.text((x, cy + 13), t, fill=S_INKSOFT, font=font(9, True))
    d.line((cx, cy + 37, cx + cw, cy + 37), fill=S_BORDER2)

    rows = [
        ("Sales Team - Read Only", "Mitchell Admin", "09/02/2026", [("Anna Smith", 0), ("John Doe", 1)], "9", True),
        ("Warehouse Operators", "Mitchell Admin", "09/02/2026", [("WH Team", 2)], "14", True),
        ("Accountant - Restricted", "Mitchell Admin", "09/03/2026", [("Karen Lee", 3)], "17", True),
        ("External Consultant", "Mitchell Admin", "09/04/2026", [("Contractor", 4)], "23", True),
        ("POS Cashiers", "Mitchell Admin", "09/05/2026", [("3 users", 5)], "6", True),
        ("Interns - View Only", "Mitchell Admin", "09/06/2026", [("Sam Park", 0)], "4", False),
    ]
    ry = cy + 38
    rh = 62
    for name, by, on, tags, rules, active in rows:
        muted = not active
        col = S_INKFAINT if muted else S_INK
        d.text((cx + 18, ry + 21), name, fill=col, font=font(12, True))
        d.text((cx + 250, ry + 22), by, fill=S_INKFAINT, font=font(11))
        d.text((cx + 430, ry + 22), on, fill=S_INKFAINT, font=font(11))
        tx = cx + 600
        for t, ci in tags:
            tx += _chip(d, tx, ry + 16, t, font(10, True), ci) + 6
        d.text((cx + 890, ry + 22), rules, fill=S_INKFAINT, font=font(11, True))
        # active toggle
        ax = cx + 1000
        d.rounded_rectangle((ax, ry + 18, ax + 30, ry + 34), 8,
                            fill=S_GREEN if active else "#d6d2e0")
        d.ellipse((ax + (16 if active else 2), ry + 20, ax + (28 if active else 14), ry + 32), fill="#fff")
        if ry + rh < H - 19:
            d.line((cx + 12, ry + rh, cx + cw - 12, ry + rh), fill="#f0ecfa")
        ry += rh

    img.save(ROOT / "screenshot_list.png", "PNG")


def make_screenshot_form():
    W, H = 1280, 604
    img = Image.new("RGB", (W, H), S_SURFACE)
    d = ImageDraw.Draw(img)
    _navbar(d, W)
    _control_panel(d, W, 108)
    _new_button(d, 16, 62)
    d.text((84, 56), "Access Management", fill=S_INKFAINT, font=font(10, True))
    d.rectangle((84, 74, 87, 94), fill=S_V)
    d.text((94, 74), "Sales Team - Read Only", fill=S_INK, font=font(15, True))
    # stat pills
    d.rounded_rectangle((W - 360, 60, W - 210, 92), 8, fill="#fff", outline=S_BORDER2, width=1)
    d.rectangle((W - 348, 70, W - 336, 82), fill="#e11d48")
    d.text((W - 320, 69), "Deactivate Rule", fill="#e11d48", font=font(11, True))
    d.rounded_rectangle((W - 200, 60, W - 20, 92), 8, fill="#fff", outline=S_BORDER2, width=1)
    for i in range(3):
        d.line((W - 186, 70 + i * 5, W - 176, 70 + i * 5), fill=S_INKFAINT, width=2)
    d.text((W - 168, 65), "9", fill=S_VDEEP, font=font(15, True))
    d.text((W - 148, 70), "Access Rules", fill=S_INKSOFT, font=font(10, True))

    # sheet
    sx, sy, sw = 24, 122, W - 48
    d.rounded_rectangle((sx, sy, sx + sw, H - 18), 16, fill=S_CARD, outline=S_BORDER, width=1)
    d.rounded_rectangle((sx, sy, sx + sw, sy + 5), 3, fill=S_V)

    lx, rx, fy = sx + 30, sx + sw // 2 + 20, sy + 34
    lbl = font(12, True)
    val = font(12, True)
    # left column
    d.text((lx, fy), "Name", fill=S_INKSOFT, font=lbl)
    d.text((lx + 150, fy), "Sales Team - Read Only", fill=S_INK, font=val)
    d.text((lx, fy + 34), "Read-Only", fill=S_INKSOFT, font=lbl)
    _checkbox(d, lx + 150, fy + 33, True)
    d.text((lx, fy + 68), "Company", fill=S_INKSOFT, font=lbl)
    _chip(d, lx + 150, fy + 64, "My Company", font(10, True), 0)
    # right column
    d.text((rx, fy), "Users", fill=S_INKSOFT, font=lbl)
    tx = rx + 150
    for i, nm in enumerate(("Anna Smith", "John Doe", "Karen Lee")):
        tx += _chip(d, tx, fy - 4, nm, font(10, True), i) + 6
    d.text((rx, fy + 34), "Disable Developer Mode", fill=S_INKSOFT, font=lbl)
    _checkbox(d, rx + 200, fy + 33, True)
    d.text((rx, fy + 68), "Created by", fill=S_INKSOFT, font=lbl)
    d.text((rx + 150, fy + 68), "Mitchell Admin", fill=S_INKFAINT, font=font(12))

    # notebook
    ny = fy + 118
    d.line((sx + 20, ny + 26, sx + sw - 20, ny + 26), fill=S_BORDER)
    tabx = sx + 30
    for i, t in enumerate(TABS):
        f = font(11, True)
        active = i == 1
        d.text((tabx, ny + 6), t, fill=S_VDEEP if active else S_INKSOFT, font=f)
        if active:
            d.rectangle((tabx, ny + 25, tabx + f.getlength(t), ny + 28), fill=S_V)
        tabx += f.getlength(t) + 26

    # mini grid
    gy = ny + 44
    gcols = [(sx + 40, "MODEL"), (sx + 260, "HIDE REPORTS"), (sx + 430, "HIDE CREATE"),
             (sx + 590, "HIDE EDIT"), (sx + 740, "HIDE DELETE"), (sx + 900, "HIDE EXPORT"),
             (sx + 1060, "HIDE DUPLICATE")]
    d.rounded_rectangle((sx + 28, gy, sx + sw - 28, gy + 30), 8, fill=S_SUNK)
    for x, t in gcols:
        d.text((x, gy + 10), t, fill=S_INKSOFT, font=font(8, True))
    grows = [
        ("sale.order", [1], [False, True, True, True, False]),
        ("account.move", [], [True, True, False, True, False]),
        ("stock.picking", [], [False, False, True, False, True]),
    ]
    ry = gy + 34
    for model, tags, checks in grows:
        d.text((sx + 40, ry + 8), model, fill=S_INK, font=font(11, True))
        for j, ck in enumerate(checks):
            _checkbox(d, gcols[j + 1][0] + 20, ry + 5, ck)
        d.line((sx + 34, ry + 30, sx + sw - 34, ry + 30), fill="#f0ecfa")
        ry += 34
    d.text((sx + 40, ry + 8), "Add a line", fill=S_V, font=font(11, True))

    # info alert
    ay = ry + 40
    d.rounded_rectangle((sx + 28, ay, sx + sw - 28, ay + 74), 10, fill="#f2effe", outline="#e0d6fb", width=1)
    d.rectangle((sx + 28, ay, sx + 31, ay + 74), fill=S_V)
    d.ellipse((sx + 44, ay + 14, sx + 60, ay + 30), outline=S_V, width=2)
    d.text((sx + 50, ay + 15), "i", fill=S_V, font=font(12, True))
    d.text((sx + 74, ay + 14), "Model Access - hide reports, actions, whole views and toolbar buttons per model.",
           fill=S_INK, font=font(11, True))
    d.text((sx + 74, ay + 38), "This only hides things on screen. Use the Domain Access tab to block an operation everywhere.",
           fill=S_INKSOFT, font=font(11))

    img.save(ROOT / "screenshot_form.png", "PNG")


if __name__ == "__main__":
    make_banner_png()
    make_banner_gif()
    make_icon()
    make_screenshot_list()
    make_screenshot_form()
    print("done:", ", ".join(p.name for p in sorted(ROOT.glob("*.png")) + sorted(ROOT.glob("*.gif"))))
