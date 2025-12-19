from PIL import Image

img = Image.open("/home/te/Documents/KinterBooky/src/assets/castle_booky_icon.png")
sizes = [(16, 16),(24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
img.save("/home/te/Documents/KinterBooky/src/assets/castle_booky_icon.ico", sizes=sizes)
