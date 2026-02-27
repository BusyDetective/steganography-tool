# 🖼️ Steganography Tool (Python GUI)

A Python-based **Image Steganography Tool** with a modern Tkinter GUI that allows secure embedding and extraction of secret messages or files inside images using the Least Significant Bit (LSB) technique.

This project demonstrates practical implementation of data hiding techniques combined with optional encryption for enhanced confidentiality.

---

## 🔐 Key Features

- Hide and extract **text messages** inside images
- Hide and extract **files** within image data
- LSB-based steganography implementation
- Password-based encryption support
- Modern dark-themed Tkinter GUI
- Drag-and-drop image support
- Cross-platform compatibility (Windows / Linux / macOS)

---

## 🛠️ Tech Stack

**Language:** Python  
**GUI Framework:** Tkinter  
**Steganography Method:** LSB (Least Significant Bit) Encoding  
**Encryption:** AES-based password protection  
**Image Processing:** PIL (Pillow)

---

## 🧠 How It Works

1. Select an image (PNG/BMP recommended for lossless encoding)
2. Enter secret message or select file to embed
3. (Optional) Apply password-based encryption
4. Tool modifies pixel LSB values to encode hidden data
5. Encoded image is saved without visible distortion

For extraction:

1. Load encoded image
2. Enter password (if encrypted)
3. Tool reads pixel LSB values
4. Decodes and reconstructs original message/file

Core logic is implemented inside:
core/stego_core.py
GUI logic is handled in:
gui/gui.py
---

## 📂 Project Structure
<pre> stego_project/
├── assets/ # Icons & images for GUI
├── core/ # Steganography logic
│ └── stego_core.py
├── gui/ # GUI code (Tkinter based)
│ └── gui.py
├── main.py # Entry point
├── requirements.txt # Python dependencies
└── README.md # Project documentation </pre>


---

## 🚀 Installation
### 1. Clone the repository:
   git clone https://github.com/YOUR_USERNAME/steganography-tool.git
   cd stego_project

### 2. Install dependencies:
   pip install -r requirements.txt

### 3. Create and activate a virtual environment:
- python -m venv venv
- source venv/bin/activate      # or venv\Scripts\activate on Windows 

### 4. Run the tool:
   python main.py

## ⚠ Important Notes

- PNG or BMP images are recommended for best results (lossless formats).
- Avoid using compressed formats like JPG for sensitive data embedding.
- This tool is developed for educational and demonstration purposes.

---

## 📜 License

This project is licensed under the MIT License – feel free to use and modify.


### 👤 Author
- Kaivan Shah
- Cybersecurity | Penetration Testing
- Email: kaivanshah1810@gmail.com 
- GitHub: https://github.com/BusyDetective
- Linkedin: linkedin.com/in/kaivan-shah-144489312
