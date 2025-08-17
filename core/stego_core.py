from PIL import Image
import base64
import hashlib
import os
from cryptography.fernet import Fernet

# ================================
# Binary Conversion Helpers
# ================================

def _message_to_binary(message):
    return ''.join(format(ord(char), '08b') for char in message)

def _binary_to_message(binary):
    chars = [binary[i:i+8] for i in range(0, len(binary), 8)]
    return ''.join(chr(int(b, 2)) for b in chars)

# ================================
# Password-based Encryption
# ================================

def _derive_key(password):
    hash = hashlib.sha256(password.encode()).digest()
    return base64.urlsafe_b64encode(hash)

def _encrypt_message(message, password):
    key = _derive_key(password)
    fernet = Fernet(key)
    encrypted = fernet.encrypt(message.encode())
    return encrypted.decode()

def _decrypt_message(encrypted_message, password):
    key = _derive_key(password)
    fernet = Fernet(key)
    decrypted = fernet.decrypt(encrypted_message.encode())
    return decrypted.decode()

# ================================
# LSB Steganography Core Logic
# ================================

def hide_message(input_image_path, message, output_image_path, password=None):
    image = Image.open(input_image_path)
    if image.mode != 'RGB':
        image = image.convert('RGB')

    if password:
        try:
            message = _encrypt_message(message, password)
        except Exception as e:
            raise ValueError(f"Encryption failed: {str(e)}")

    binary_message = _message_to_binary(message) + '1111111111111110'  # EOF marker
    data_index = 0
    new_pixels = []

    for pixel in image.getdata():
        r, g, b = pixel
        new_rgb = []

        for color in (r, g, b):
            if data_index < len(binary_message):
                new_color = (color & ~1) | int(binary_message[data_index])
                data_index += 1
            else:
                new_color = color
            new_rgb.append(new_color)

        new_pixels.append(tuple(new_rgb))

    if data_index < len(binary_message):
        raise ValueError("Message is too large to hide in this image.")

    stego_img = Image.new(image.mode, image.size)
    stego_img.putdata(new_pixels)
    stego_img.save(output_image_path)

def extract_message(stego_image_path, password=None):
    image = Image.open(stego_image_path)
    if image.mode != 'RGB':
        image = image.convert('RGB')

    binary_data = ''
    for pixel in image.getdata():
        for color in pixel:
            binary_data += str(color & 1)

    eof_marker = '1111111111111110'
    end_index = binary_data.find(eof_marker)

    if end_index == -1:
        raise ValueError("No hidden message found or image is not stego.")

    binary_message = binary_data[:end_index]
    extracted_message = _binary_to_message(binary_message)

    if password:
        try:
            return _decrypt_message(extracted_message, password)
        except Exception:
            raise ValueError("Incorrect password or corrupted message.")

    return extracted_message

# ================================
# Optional Helper: Capacity Checker
# ================================

def get_max_capacity(image_path):
    """Returns the max number of bits we can hide in an image."""
    image = Image.open(image_path)
    width, height = image.size
    return (width * height * 3) // 8  # bits to bytes

# ================================
# File Hiding with Base64 + LSB
# ================================

def hide_file(input_image_path, file_path, output_image_path):
    image = Image.open(input_image_path)
    if image.mode != 'RGB':
        image = image.convert('RGB')

    with open(file_path, "rb") as f:
        file_data = f.read()

    encoded_data = base64.b64encode(file_data).decode()  # to string
    filename = os.path.basename(file_path)
    message = f"{filename}:::{encoded_data}"

    binary_message = _message_to_binary(message) + '1111111111111110'
    data_index = 0
    new_pixels = []

    for pixel in image.getdata():
        r, g, b = pixel
        new_rgb = []

        for color in (r, g, b):
            if data_index < len(binary_message):
                new_color = (color & ~1) | int(binary_message[data_index])
                data_index += 1
            else:
                new_color = color
            new_rgb.append(new_color)

        new_pixels.append(tuple(new_rgb))

    if data_index < len(binary_message):
        raise ValueError("File is too large to hide in this image.")

    stego_img = Image.new(image.mode, image.size)
    stego_img.putdata(new_pixels)
    stego_img.save(output_image_path)

def extract_file(stego_image_path, output_folder):
    image = Image.open(stego_image_path)
    if image.mode != 'RGB':
        image = image.convert('RGB')

    binary_data = ''
    for pixel in image.getdata():
        for color in pixel:
            binary_data += str(color & 1)

    eof_marker = '1111111111111110'
    end_index = binary_data.find(eof_marker)

    if end_index == -1:
        raise ValueError("No hidden file found or image is not stego.")

    binary_message = binary_data[:end_index]
    extracted = _binary_to_message(binary_message)

    if ":::" not in extracted:
        raise ValueError("Invalid file format in hidden data.")

    filename, b64_data = extracted.split(":::", 1)
    decoded_bytes = base64.b64decode(b64_data)

    output_path = os.path.join(output_folder, filename)
    with open(output_path, "wb") as f:
        f.write(decoded_bytes)

    return output_path


# ================================
# NEW ADDITIONS FOR GUI SUPPORT
# ================================

def get_asset_path(filename):
    """
    Get absolute path to an asset file located in 'assets' folder relative to project root.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "assets", filename)

def handle_dropped_file(file_path):
    """
    Validate a dropped file path for drag-and-drop.
    Returns absolute path if valid image, else None.
    """
    file_path = file_path.strip()
    if os.path.isfile(file_path) and file_path.lower().endswith(('.png', '.bmp')):
        return os.path.abspath(file_path)
    return None

def ensure_test_image():
    """
    Returns path to test image; creates a simple placeholder if it doesn't exist.
    """
    path = get_asset_path("test_image.png")
    if not os.path.exists(path):
        img = Image.new("RGB", (500, 500), color=(255, 255, 255))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img.save(path)
    return path
