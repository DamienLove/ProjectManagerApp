from PIL import Image, ImageDraw, ImageFont
import os

ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

def create_pill_icon(name, color, symbol, text_color="white"):
    """Creates a modern 64x64 icon with a colored background and a symbol."""
    img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    
    # Background circle with slight gradient effect (simulated with border)
    d.ellipse((2, 2, 62, 62), fill=color, outline="white", width=1)
    
    # Draw simple symbols using lines/shapes
    if symbol == "antigravity":
        # Purple planet with ring
        d.ellipse((16, 16, 48, 48), fill=text_color)
        d.arc((8, 25, 56, 39), start=0, end=360, fill=color, width=3)
    elif symbol == "android":
        # Green android-like shape
        d.chord((16, 20, 48, 52), start=180, end=0, fill=text_color) # head
        d.rectangle((16, 38, 48, 55), fill=text_color) # body
    elif symbol == "cog":
        # Gear shape
        d.ellipse((20, 20, 44, 44), outline=text_color, width=6)
        for i in range(8):
            import math
            angle = i * (360/8)
            rad = math.radians(angle)
            x1 = 32 + 18 * math.cos(rad)
            y1 = 32 + 18 * math.sin(rad)
            d.line((32, 32, x1, y1), fill=text_color, width=6)
    elif symbol == "cloud":
        # Cloud shape
        d.ellipse((15, 25, 35, 45), fill=text_color)
        d.ellipse((25, 15, 50, 40), fill=text_color)
        d.ellipse((35, 25, 55, 45), fill=text_color)
        d.rectangle((25, 35, 45, 45), fill=text_color)
    elif symbol == "activate":
        # Rocket/Triangle
        d.polygon([(32, 10), (15, 50), (49, 50)], fill=text_color)
    elif symbol == "apps":
        # 3x3 Grid
        for x in [15, 28, 41]:
            for y in [15, 28, 41]:
                d.rectangle((x, y, x+8, y+8), fill=text_color)
    elif symbol == "export":
        # Folder + Arrow
        d.rectangle((10, 25, 45, 50), outline=text_color, width=3)
        d.polygon([(40, 10), (60, 30), (40, 50)], fill=text_color)
    elif symbol == "quit":
        # Power symbol
        d.arc((15, 15, 49, 49), start=120, end=60, fill=text_color, width=5)
        d.line((32, 10, 32, 30), fill=text_color, width=5)
    
    path = os.path.join(ASSET_DIR, f"{name}.png")
    img.save(path)
    print(f"Created {path}")

def generate_all():
    os.makedirs(ASSET_DIR, exist_ok=True)
    # name, color, symbol
    icons = [
        ("antigravity", "#9333ea", "antigravity"),
        ("android_studio", "#3DDC84", "android"),
        ("config_cog", "#64748b", "cog"),
        ("cloud", "#3b82f6", "cloud"),
        ("activate", "#22c55e", "activate"),
        ("settings", "#475569", "cog"),
        ("apps", "#0ea5e9", "apps"),
        ("export", "#f59e0b", "export"),
        ("quit", "#ef4444", "quit"),
        ("folder", "#fbbf24", "apps")
    ]
    for n, c, s in icons:
        create_pill_icon(n, c, s)

if __name__ == "__main__":
    generate_all()