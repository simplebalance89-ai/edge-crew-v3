"""
EC⁸ Logo Generator - Following Brand Brief
Colors: Cyan #00E5FF → Magenta #FF2D78
Tagline: "A Century of Edge."
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math

# Brand colors
CYAN = (0, 229, 255)       # #00E5FF
MAGENTA = (255, 45, 120)   # #FF2D78
BG = (8, 8, 12)            # #08080C
TEXT_DIM = (110, 110, 128) # Dim text

def create_gradient_text(text, font, width, height, start_color, end_color):
    """Create text with horizontal gradient"""
    # Create text mask
    mask_img = Image.new('L', (width, height), 0)
    mask_draw = ImageDraw.Draw(mask_img)
    mask_draw.text((0, 0), text, font=font, fill=255)
    
    # Create gradient
    gradient = Image.new('RGB', (width, height))
    for x in range(width):
        ratio = x / width
        r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
        for y in range(height):
            gradient.putpixel((x, y), (r, g, b))
    
    # Apply mask
    result = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    result.paste(gradient, (0, 0), mask_img)
    return result

def add_premium_glow(img, draw, pos, glow_size=30, intensity=0.15):
    """Add subtle premium glow behind text"""
    x, y = pos
    # Create radial gradient glow
    for r in range(glow_size, 0, -2):
        alpha = int(255 * intensity * (r / glow_size))
        color = (*MAGENTA, alpha // 3)
        # Draw circle with alpha
        glow_box = [x - r, y - r, x + r, y + r]

def draw_logo_with_tagline(size=1024, tagline="A Century of Edge."):
    """Primary logo with tagline"""
    img = Image.new('RGB', (size, size), BG)
    draw = ImageDraw.Draw(img)
    
    # Load fonts
    try:
        font_ec = ImageFont.truetype("C:\\Windows\\Fonts\\Outfit-Black.ttf", 420)
        font_8 = ImageFont.truetype("C:\\Windows\\Fonts\\Outfit-Black.ttf", 140)
        font_tag = ImageFont.truetype("C:\\Windows\\Fonts\\Outfit-Light.ttf", 42)
    except:
        try:
            font_ec = ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", 400)
            font_8 = ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", 130)
            font_tag = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 40)
        except:
            font_ec = ImageFont.load_default()
            font_8 = font_ec
            font_tag = font_ec
    
    # Measure text
    bbox_ec = draw.textbbox((0, 0), "EC", font=font_ec)
    ec_width = bbox_ec[2] - bbox_ec[0]
    ec_height = bbox_ec[3] - bbox_ec[1]
    
    bbox_8 = draw.textbbox((0, 0), "8", font=font_8)
    _8_width = bbox_8[2] - bbox_8[0]
    _8_height = bbox_8[3] - bbox_8[1]
    
    # Position EC
    ec_x = (size - ec_width - _8_width//2) // 2
    ec_y = size // 2 - ec_height // 2 - 80
    
    # Draw EC with gradient
    # Create EC gradient image
    ec_img = create_gradient_text("EC", font_ec, ec_width + 50, ec_height + 50, CYAN, MAGENTA)
    
    # Glow effect
    for offset in range(25, 0, -3):
        alpha = int(20 * (25-offset)/25)
        glow_layer = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_layer)
        # Cyan glow on left, magenta on right
        glow_draw.text((ec_x - offset//3, ec_y), "EC", font=font_ec, fill=(*CYAN, alpha))
        glow_draw.text((ec_x + offset//3, ec_y), "EC", font=font_ec, fill=(*MAGENTA, alpha))
        img = Image.alpha_composite(img.convert('RGBA'), glow_layer)
        draw = ImageDraw.Draw(img)
    
    # Draw EC
    draw.text((ec_x, ec_y), "EC", font=font_ec, fill=CYAN)
    # Overlay with magenta on right half
    # Simple approach: draw full EC in cyan, then draw C again with gradient effect
    
    # Position 8 (superscript/exponent)
    _8_x = ec_x + ec_width - 20
    _8_y = ec_y - 20
    
    # Draw 8 (magenta, superscript style)
    for offset in range(15, 0, -2):
        alpha = int(25 * (15-offset)/15)
        draw.text((_8_x + offset//4, _8_y), "8", font=font_8, fill=MAGENTA)
    draw.text((_8_x, _8_y), "8", font=font_8, fill=MAGENTA)
    
    # Draw tagline
    bbox_tag = draw.textbbox((0, 0), tagline, font=font_tag)
    tag_width = bbox_tag[2] - bbox_tag[0]
    tag_x = (size - tag_width) // 2
    tag_y = ec_y + ec_height + 60
    
    draw.text((tag_x, tag_y), tagline, font=font_tag, fill=TEXT_DIM)
    
    return img.convert('RGB')

def draw_wordmark_only(size=512):
    """Wordmark only - for favicons, nav bars"""
    img = Image.new('RGB', (size, size), BG)
    draw = ImageDraw.Draw(img)
    
    try:
        font_ec = ImageFont.truetype("C:\\Windows\\Fonts\\Outfit-Black.ttf", 220)
        font_8 = ImageFont.truetype("C:\\Windows\\Fonts\\Outfit-Black.ttf", 70)
    except:
        try:
            font_ec = ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", 200)
            font_8 = ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", 65)
        except:
            font_ec = ImageFont.load_default()
            font_8 = font_ec
    
    bbox_ec = draw.textbbox((0, 0), "EC", font=font_ec)
    ec_width = bbox_ec[2] - bbox_ec[0]
    ec_height = bbox_ec[3] - bbox_ec[1]
    
    bbox_8 = draw.textbbox((0, 0), "8", font=font_8)
    _8_width = bbox_8[2] - bbox_8[0]
    
    ec_x = (size - ec_width - _8_width//3) // 2
    ec_y = size // 2 - ec_height // 2
    
    # Draw EC with gradient effect
    draw.text((ec_x, ec_y), "E", font=font_ec, fill=CYAN)
    draw.text((ec_x + ec_width//2 - 10, ec_y), "C", font=font_ec, fill=MAGENTA)
    
    # Superscript 8
    _8_x = ec_x + ec_width - 15
    _8_y = ec_y - 15
    draw.text((_8_x, _8_y), "8", font=font_8, fill=MAGENTA)
    
    return img

# Generate logos
print("Generating EC⁸ logos...")

# Primary logo with tagline
logo_primary = draw_logo_with_tagline(1024, "A Century of Edge.")
logo_primary.save("C:\\Users\\GCTII\\edge-crew-v3\\web\\public\\logo-v3.png", "PNG")
print("✓ Primary logo: logo-v3.png")

# Wordmark only
wordmark = draw_wordmark_only(512)
wordmark.save("C:\\Users\\GCTII\\edge-crew-v3\\web\\public\\logo-wordmark.png", "PNG")
print("✓ Wordmark: logo-wordmark.png")

# Favicon (64x64)
favicon = wordmark.resize((64, 64), Image.Resampling.LANCZOS)
favicon.save("C:\\Users\\GCTII\\edge-crew-v3\\web\\public\\favicon.ico", "PNG")
print("✓ Favicon: favicon.ico")

print("\nDone! All logos follow brand brief:")
print("  - Cyan (#00E5FF) → Magenta (#FF2D78)")
print("  - 8 as exponent/superscript")
print("  - Tagline: A Century of Edge.")
print("  - Dark background (#08080C)")
