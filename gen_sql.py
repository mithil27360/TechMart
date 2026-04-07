import os
import hashlib

# Configuration
SOURCE_DIR = '/Users/mithils/Downloads/images for items'
UPLOAD_DIR = '/Users/mithils/Desktop/electronic marketplace/static/uploads'

# All Items
original_items = ['iPhone 13', 'MacBook Air', 'Mac Studio Silicon M2']
mobiles = ['iPhone 12', 'iPhone 14 Pro', 'Samsung Galaxy S22', 'OnePlus 11', 'Google Pixel 7']
laptops = ['Lenovo ThinkPad X1 Carbon', 'Asus ROG Strix G15', 'Acer Predator Helios 300', 'MacBook Pro M1', 'MacBook Pro M2']
audio = ['boAt Airdopes 141', 'Noise Buds VS104', 'Realme Buds Air 5', 'Apple AirPods Pro 2', 'boAt Rockerz 450', 'Sony WH-CH720N', 'Apple AirPods Max', 'JBL Flip 6 Bluetooth Speaker', 'boAt Stone 350 Speaker', 'Marshall Emberton Speaker']
watches = ['Apple Watch Series 9', 'Samsung Galaxy Watch 6', 'Noise ColorFit Pro 5']
accessories = ['Anker Power Bank 20000mAh', 'USB-C Hub 7-in-1 Adapter', 'Logitech MX Master 3 Mouse', 'Mechanical Keyboard (RGB)']

all_items = original_items + mobiles + laptops + audio + watches + accessories

def get_hash(path):
    if not os.path.isfile(path): return None
    with open(path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

source_files = sorted(os.listdir(SOURCE_DIR))
upload_files = sorted(os.listdir(UPLOAD_DIR))

source_hashes = {f: get_hash(os.path.join(SOURCE_DIR, f)) for f in source_files}
upload_hashes = {f: get_hash(os.path.join(UPLOAD_DIR, f)) for f in upload_files}

# Build hash to UUID mapping
hash_to_uuid = {h: f for f, h in upload_hashes.items() if h is not None}

# Special mapping for original items (iPhone 13, MacBook Air, Mac Studio)
# These images are likely not in the source dir but were uploaded already.
# I will check if they are in the source dir, but if not, I'll have to find them in uploads.
# Actually, the user's screenshot showed placeholder icons for them. I'll just use them if I can find them.

sql_lines = []
for i, item_name in enumerate(all_items):
    item_id = i + 1
    # Match files by title
    matches = [f for f in source_files if item_name.lower() in f.lower()]
    # Special match for AirPods Pro 2 (to distinguish from Max/boAt)
    if 'AirPods Pro 2' in item_name:
        matches = [f for f in matches if 'Pro 2' in f]
    elif 'iPhone 14' in item_name:
        matches = [f for f in matches if '14' in f]
    elif 'iPhone 12' in item_name:
        matches = [f for f in matches if '12' in f]

    found_any = False
    for j, f in enumerate(matches):
        h = source_hashes.get(f)
        uuid_name = hash_to_uuid.get(h)
        if uuid_name:
            is_primary = 'TRUE' if j == 0 else 'FALSE'
            sql_lines.append(f"({item_id}, '{uuid_name}', {is_primary})")
            found_any = True
    
    # If no image found for original items, use a placeholder or leave empty for now
    # (The original items 1-3 don't have images in the source folder)

print('INSERT INTO items_img (item_id, image_url, is_primary) VALUES')
print(',\n'.join(sql_lines) + ';')
