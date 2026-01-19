from PIL import Image, ImageDraw

def create_icon():
    # Create a 64x64 blue icon with a "building" or "sync" motif
    img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    
    # Blue background circle
    d.ellipse((4, 4, 60, 60), fill="#3b82f6", outline="#1d4ed8", width=2)
    
    # White "Sync" arrows (simplified as a recycling shape or circle)
    d.arc((15, 15, 49, 49), start=30, end=330, fill="white", width=4)
    d.polygon([(49, 32), (39, 27), (39, 37)], fill="white") # Arrowhead
    
    # Save
    img.save("C:/Users/me/Projects/ProjectManagerApp/assets/app_icon.png")
    img.save("C:/Users/me/Projects/ProjectManagerApp/assets/app_icon.ico")

if __name__ == "__main__":
    create_icon()
