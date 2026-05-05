import os
from PIL import Image

def convert_png_to_ico(png_path, ico_path):
    if not os.path.exists(png_path):
        print(f"Error: {png_path} not found.")
        return
    
    img = Image.open(png_path)
    # Use standard icon sizes
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(ico_path, format='ICO', sizes=sizes)
    print(f"Successfully converted {png_path} to {ico_path}")

if __name__ == "__main__":
    base_path = r"h:\CADMation\backend\resources"
    convert_png_to_ico(
        os.path.join(base_path, "app_logo.png"),
        os.path.join(base_path, "app_icon.ico")
    )
