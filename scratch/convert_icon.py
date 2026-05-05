from PIL import Image
import os

png_path = r'C:\Users\Piculiar\.gemini\antigravity\brain\39352c22-db27-4852-97bd-649e3e3d773f\cadmation_new_logo_icon_1777922146079.png'
ico_path = r'h:\CADMation\backend\resources\app_icon.ico'

if os.path.exists(png_path):
    img = Image.open(png_path)
    # Resize and create icon with multiple sizes for Windows
    icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(ico_path, format='ICO', sizes=icon_sizes)
    print(f"Successfully converted {png_path} to {ico_path}")
else:
    print(f"Error: {png_path} not found")
