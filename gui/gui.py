import os
import sys
import threading
import platform
import subprocess
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import base64
import hashlib
from cryptography.fernet import Fernet

# safe import: supports core/stego_core.py or root stego_core.py
try:
    from core.stego_core import hide_message, extract_message, hide_file, extract_file, get_max_capacity, ensure_test_image
except Exception:
    # If your stego_core doesn't have ensure_test_image, fallback to our internal helper below.
    from stego_core import hide_message, extract_message, hide_file, extract_file, get_max_capacity

# ------------------------
# Project / assets paths
# ------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
if not os.path.isdir(ASSETS_DIR):
    ASSETS_DIR = os.path.join(os.getcwd(), "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

# ------------------------
# Theme & Colors
# ------------------------
BG = "#111214"
PANEL = "#1e1e1f"
CARD = "#171718"
FG = "#e6eef6"
MUTED = "#98a0ab"
ACCENT = "#4CAF50"
BTN_BG = "#2b2f33"
BTN_HOVER = "#3a4147"

# ------------------------
# Encryption helpers (optional file encryption)
# ------------------------
def _derive_key(password: str) -> bytes:
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_bytes(data: bytes, password: str) -> bytes:
    if not password:
        return data
    f = Fernet(_derive_key(password))
    return f.encrypt(data)


def decrypt_bytes(data: bytes, password: str) -> bytes:
    if not password:
        return data
    f = Fernet(_derive_key(password))
    return f.decrypt(data)


# ------------------------
# Helpers
# ------------------------
def load_icon(name, size=(20, 20)):
    path = os.path.join(ASSETS_DIR, name)
    if os.path.exists(path):
        try:
            img = Image.open(path).convert("RGBA").resize(size, Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            return None
    return None


def open_with_default_app(path):
    try:
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
    except Exception as e:
        messagebox.showerror("Open error", f"Couldn't open file: {e}")


def threaded(fn):
    """Decorator to run a function in a separate daemon thread."""
    def wrapper(*args, **kwargs):
        t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
        t.start()
        return t
    return wrapper


# If stego_core didn't define ensure_test_image, provide a small helper here
def _ensure_test_image_local():
    candidate = os.path.join(ASSETS_DIR, "test_image.png")
    if os.path.exists(candidate):
        return os.path.abspath(candidate)
    # create placeholder in assets
    try:
        out = os.path.join(ASSETS_DIR, "test_image.png")
        img = Image.new("RGB", (500, 500), color=(240, 240, 240))
        img.save(out)
        return out
    except Exception:
        return None


# Try to use ensure_test_image from stego_core if available
try:
    ensure_test_image  # noqa: F821
except NameError:
    ensure_test_image = _ensure_test_image_local


# Placeholder Entry
class PlaceholderEntry(tk.Entry):
    def __init__(self, master=None, placeholder="", color=MUTED, **kwargs):
        super().__init__(master, **kwargs)
        self.placeholder = placeholder
        self.placeholder_color = color
        self.default_fg = kwargs.get("fg", FG)
        self.put_placeholder()
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)

    def put_placeholder(self):
        self.delete(0, tk.END)
        self.insert(0, self.placeholder)
        self.config(fg=self.placeholder_color)

    def _on_focus_in(self, _):
        if self.get() == self.placeholder and self['fg'] == self.placeholder_color:
            self.delete(0, tk.END)
            self.config(fg=self.default_fg)

    def _on_focus_out(self, _):
        if not self.get():
            self.put_placeholder()


# Tooltip
class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _=None):
        if self.tip:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tip, text=self.text, bg="#222", fg=FG, padx=6, pady=3, font=("Segoe UI", 9))
        label.pack()

    def hide(self, _=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


# ------------------------
# Main GUI
# ------------------------
class StegoGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("StegoTool — Modern")
        self.root.configure(bg=BG)
        self.root.geometry("980x640")
        self.root.minsize(840, 520)
        self.last_dir = os.getcwd()

        # Icons
        self.icon_browse = load_icon("open-folder.png", (20, 20))
        self.icon_extract = load_icon("search.png", (18, 18))
        self.icon_clear = load_icon("broom.png", (18, 18))
        self.icon_detect = load_icon("private-detective.png", (18, 18))

        # Panels
        self.left_panel = tk.Frame(self.root, bg=PANEL, width=360)
        self.left_panel.pack(side="left", fill="y")
        self.right_panel = tk.Frame(self.root, bg=BG)
        self.right_panel.pack(side="right", fill="both", expand=True, padx=4)

        # Image state
        self.current_image_path = ""
        self.img_full = None
        self.thumb = None  # persistent PhotoImage reference so Tk doesn't GC it

        # For drag & drop (optional)
        self._dnd_available = False
        self._try_enable_dnd()

        # Build UI
        self._build_left()
        self._build_right()
        
    # ---------------- DnD (optional) ----------------
    def _try_enable_dnd(self):
        # Try to enable tkinterdnd2 if available. It's optional.
        try:
            from tkinterdnd2 import TkinterDnD, DND_FILES  # type: ignore
            self._dnd_available = True
            # If root is Tk(), this won't change the instance type. We only need bindings.
            # We'll use root.tk.call to register a drop target if possible.
            # Instead of complex re-creation, we'll allow TkinterDnD users to call separate launcher if they want full integration.
        except Exception:
            self._dnd_available = False

    # ---------- LEFT: preview & quick actions ----------
    def _build_left(self):
        header = tk.Label(self.left_panel, text="Preview", bg=PANEL, fg=FG, font=("Segoe UI", 14, "bold"))
        header.pack(anchor="w", padx=16, pady=(12, 6))

        self.preview_card = tk.Frame(self.left_panel, bg=CARD, width=320, height=320)
        self.preview_card.pack(padx=12, pady=6)
        self.preview_card.pack_propagate(False)

        self.thumb_label = tk.Label(self.preview_card, bg=CARD, text="No image loaded", fg=MUTED)
        self.thumb_label.pack(expand=True)
        self.thumb_label.bind("<Button-1>", lambda e: self._open_preview_fullsize())
        self.thumb_label.config(cursor="hand2")

        # If DnD available attempt to bind drop events (tkinterdnd2 required)
        if self._dnd_available:
            try:
                from tkinterdnd2 import DND_FILES  # type: ignore
                self.root.drop_target_register(DND_FILES)
                self.root.dnd_bind('<<Drop>>', self._on_drop)
            except Exception:
                pass

        info_frame = tk.Frame(self.left_panel, bg=PANEL)
        info_frame.pack(fill="x", padx=12, pady=8)

        tk.Label(info_frame, text="Image Path:", bg=PANEL, fg=MUTED).pack(anchor="w")
        self.img_path_var = tk.StringVar()
        self.img_path_label = tk.Label(info_frame, textvariable=self.img_path_var, bg=PANEL, fg=FG, wraplength=320, justify="left")
        self.img_path_label.pack(anchor="w", pady=(0, 6))

        self.capacity_var = tk.StringVar(value="Capacity: —")
        tk.Label(info_frame, textvariable=self.capacity_var, bg=PANEL, fg=MUTED).pack(anchor="w")

        btns = tk.Frame(self.left_panel, bg=PANEL)
        btns.pack(fill="x", padx=12, pady=10)
        b_open = tk.Button(btns, text="Open Image", image=self.icon_browse, compound="left", bg=BTN_BG, fg=FG,
                           relief="flat", command=self._browse_image)
        b_open.pack(side="left", padx=6, ipady=6)
        Tooltip(b_open, "Select image to preview")

        b_clear = tk.Button(btns, text="Clear", image=self.icon_clear, compound="left", bg=BTN_BG, fg=FG,
                            relief="flat", command=self._clear_preview)
        b_clear.pack(side="left", padx=6)
        Tooltip(b_clear, "Clear preview and selections")

        b_detect = tk.Button(btns, text="Capacity", image=self.icon_detect, compound="left", bg=BTN_BG, fg=FG,
                             relief="flat", command=self._show_capacity)
        b_detect.pack(side="left", padx=6)
        Tooltip(b_detect, "Show capacity for selected image")

        # --- Run Test button (uses ensure_test_image and persists PhotoImage refs) ---
        b_test = tk.Button(btns, text="Run Test", bg=ACCENT, fg="white", relief="flat", command=self._run_test)
        b_test.pack(side="left", padx=6)
        b_test.bind("<Enter>", lambda e: e.widget.config(bg=BTN_HOVER))
        b_test.bind("<Leave>", lambda e: e.widget.config(bg=ACCENT))
        Tooltip(b_test, "Run auto test: hide 'Test123' into a default image and verify")

        for w in (b_open, b_clear, b_detect, b_test):
            w.bind("<Enter>", lambda e: e.widget.config(bg=BTN_HOVER))
            w.bind("<Leave>", lambda e: e.widget.config(bg=BTN_BG))

    # ---------- RIGHT: notebook with Text & File tabs (scrollable) ----------
    def _build_right(self):
        title = tk.Label(
            self.right_panel,
            text="🖼️ Steganography Tool",
            bg=BG,
            fg=FG,
            font=("Segoe UI", 20, "bold")
        )
        title.pack(anchor="center", pady=(16, 10))
    
        # Create canvas for scrolling
        self.right_canvas = tk.Canvas(self.right_panel, bg=BG, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self.right_panel, orient="vertical", command=self.right_canvas.yview)
        self.scrollable_frame = tk.Frame(self.right_canvas, bg=BG, padx=12, pady=12)

        # Configure canvas scrollregion
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.right_canvas.configure(scrollregion=self.right_canvas.bbox("all"))
        )

        # scrollable_frame inside the canvas and stretch it
        self.window_id = self.right_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.right_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Make sure the inner frame always matches canvas width
        self.right_canvas.bind(
            "<Configure>",
            lambda e: self.right_canvas.itemconfig(self.window_id, width=e.width)
        )

        self.right_canvas.configure(yscrollcommand=self.scrollbar.set)
    
        # Pack widgets
        self.right_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Bind mousewheel for all OS
        self.right_canvas.bind_all("<Button-4>", self._on_mousewheel)   # Linux scroll up
        self.right_canvas.bind_all("<Button-5>", self._on_mousewheel)   # Linux scroll down
        self.right_canvas.bind_all("<MouseWheel>", self._on_mousewheel) # Windows/Mac
        
        # ---- Modern Notebook ----
        style = ttk.Style()
        style.theme_use("clam")  # modern-ish look
        style.configure(
            "TNotebook",
            background=BG,
            borderwidth=0
        )
        style.configure(
            "TNotebook.Tab",
            font=("Segoe UI", 11, "bold"),
            padding=[12, 6],
            background="#1E1E1E",
            foreground="#FFFFFF"
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#2D2D30")],
            foreground=[("selected", "#00FFCC")]
        )
    
        notebook = ttk.Notebook(self.scrollable_frame)
        notebook.pack(fill="both", expand=True, padx=6, pady=6)

        text_frame = tk.Frame(notebook, bg=BG)
        self._build_text_tab(text_frame)
        notebook.add(text_frame, text="Text Steganography")

        file_frame = tk.Frame(notebook, bg=BG)
        self._build_file_tab(file_frame)
        notebook.add(file_frame, text="File Steganography")
        
    def _on_mousewheel(self, event):
        if event.num == 4:  # Linux scroll up
            self.right_canvas.yview_scroll(-1, "units")
        elif event.num == 5:  # Linux scroll down
            self.right_canvas.yview_scroll(1, "units")
        else:  # Windows/Mac style
            self.right_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ---------- Text tab ----------
    def _build_text_tab(self, parent):
        hide_card = tk.LabelFrame(parent, text="Hide Message", bg=BG, fg=FG, font=("Segoe UI", 11, "bold"), padx=10, pady=8)
        hide_card.pack(fill="x", padx=12, pady=(10, 8))

        tk.Label(hide_card, text="Image (preview or browse):", bg=BG, fg=MUTED).pack(anchor="w")
        self.tx_img_entry = PlaceholderEntry(hide_card, placeholder="(use Preview → Open Image) or browse", width=56, bg=CARD, fg=FG, insertbackground=FG)
        self.tx_img_entry.pack(pady=6)
        b = tk.Button(hide_card, text="Browse", image=self.icon_browse, compound="left", bg=BTN_BG, fg=FG, relief="flat",
                      command=lambda: self._browse_and_put(self.tx_img_entry))
        b.pack(anchor="e")
        b.bind("<Enter>", lambda e: e.widget.config(bg=BTN_HOVER)); b.bind("<Leave>", lambda e: e.widget.config(bg=BTN_BG))

        tk.Label(hide_card, text="Message to hide:", bg=BG, fg=MUTED).pack(anchor="w", pady=(8, 0))
        self.tx_msg = tk.Text(hide_card, height=6, bg=CARD, fg=FG, insertbackground=FG)
        self.tx_msg.pack(fill="x", pady=6)

        tk.Label(hide_card, text="Password (optional):", bg=BG, fg=MUTED).pack(anchor="w")
        self.tx_pwd = PlaceholderEntry(hide_card, placeholder="Password (optional)", width=30, bg=CARD, fg=FG, insertbackground=FG)
        self.tx_pwd.pack(pady=6)

        self.tx_progress = ttk.Progressbar(hide_card, mode="indeterminate")
        self.tx_progress.pack(fill="x", pady=(4, 6))

        btn_frame = tk.Frame(hide_card, bg=BG)
        btn_frame.pack(fill="x", pady=6)
        hide_btn = tk.Button(btn_frame, text="Hide Message", bg=ACCENT, fg="white", relief="flat", command=self._hide_message)
        hide_btn.pack(side="left", padx=6)
        hide_btn.bind("<Enter>", lambda e: e.widget.config(bg=BTN_HOVER)); hide_btn.bind("<Leave>", lambda e: e.widget.config(bg=ACCENT))

        extract_btn = tk.Button(btn_frame, text="Extract (to textbox)", image=self.icon_extract, compound="left",
                                bg=BTN_BG, fg=FG, relief="flat", command=self._extract_message)
        extract_btn.pack(side="left", padx=6)
        extract_btn.bind("<Enter>", lambda e: e.widget.config(bg=BTN_HOVER)); extract_btn.bind("<Leave>", lambda e: e.widget.config(bg=BTN_BG))

        clear_btn = tk.Button(btn_frame, text="Clear", image=self.icon_clear, compound="left", bg=BTN_BG, fg=FG, relief="flat",
                              command=self._clear_text_tab)
        clear_btn.pack(side="right", padx=6)
        clear_btn.bind("<Enter>", lambda e: e.widget.config(bg=BTN_HOVER)); clear_btn.bind("<Leave>", lambda e: e.widget.config(bg=BTN_BG))

    # ---------- File tab ----------
    def _build_file_tab(self, parent):
        hide_card = tk.LabelFrame(parent, text="Hide File", bg=BG, fg=FG, font=("Segoe UI", 11, "bold"), padx=10, pady=8)
        hide_card.pack(fill="x", padx=12, pady=(10, 8))

        tk.Label(hide_card, text="Image (preview or browse):", bg=BG, fg=MUTED).pack(anchor="w")
        self.f_img_entry = PlaceholderEntry(hide_card, placeholder="(use Preview → Open Image) or browse", width=56, bg=CARD, fg=FG, insertbackground=FG)
        self.f_img_entry.pack(pady=6)
        b = tk.Button(hide_card, text="Browse Image", image=self.icon_browse, compound="left", bg=BTN_BG, fg=FG, relief="flat",
                      command=lambda: self._browse_and_put(self.f_img_entry))
        b.pack(anchor="e")
        b.bind("<Enter>", lambda e: e.widget.config(bg=BTN_HOVER)); b.bind("<Leave>", lambda e: e.widget.config(bg=BTN_BG))

        tk.Label(hide_card, text="File to hide:", bg=BG, fg=MUTED).pack(anchor="w", pady=(8, 0))
        self.f_file_entry = PlaceholderEntry(hide_card, placeholder="Select file to hide", width=56, bg=CARD, fg=FG, insertbackground=FG)
        self.f_file_entry.pack(pady=6)
        btn_file = tk.Button(hide_card, text="Browse File", bg=BTN_BG, fg=FG, relief="flat", command=lambda: self._browse_and_put(self.f_file_entry, file=True))
        btn_file.pack(anchor="e", pady=(0, 6))
        btn_file.bind("<Enter>", lambda e: e.widget.config(bg=BTN_HOVER)); btn_file.bind("<Leave>", lambda e: e.widget.config(bg=BTN_BG))

        tk.Label(hide_card, text="Password (optional):", bg=BG, fg=MUTED).pack(anchor="w")
        self.f_pwd = PlaceholderEntry(hide_card, placeholder="Password (optional)", width=30, bg=CARD, fg=FG, insertbackground=FG)
        self.f_pwd.pack(pady=6)

        self.f_progress = ttk.Progressbar(hide_card, mode="indeterminate")
        self.f_progress.pack(fill="x", pady=(4, 6))
      
        btn_frame = tk.Frame(hide_card, bg=BG) 
        btn_frame.pack(fill="x", pady=6)

	# Hide File button
        hide_btn = tk.Button(btn_frame, text="Hide File", bg=ACCENT, fg="white", relief="flat", command=self._hide_file)
        hide_btn.pack(side="left", padx=6)
        hide_btn.bind("<Enter>", lambda e: e.widget.config(bg=BTN_HOVER))
        hide_btn.bind("<Leave>", lambda e: e.widget.config(bg=ACCENT))

	# Clear button
        clear_btn = tk.Button(btn_frame, text="Clear", bg=BTN_BG, fg=FG, relief="flat",
    	    command=lambda: [
        	self.f_img_entry.delete(0, "end"),
        	self.f_file_entry.delete(0, "end"),
        	self.f_pwd.delete(0, "end")
    	    ])
        clear_btn.pack(side="left", padx=6)
        clear_btn.bind("<Enter>", lambda e: e.widget.config(bg=BTN_HOVER))
        clear_btn.bind("<Leave>", lambda e: e.widget.config(bg=BTN_BG))

        # Extract card
        extract_card = tk.LabelFrame(parent, text="Extract File", bg=BG, fg=FG, font=("Segoe UI", 11, "bold"), padx=10, pady=8)
        extract_card.pack(fill="x", padx=12, pady=(8, 12))

        tk.Label(extract_card, text="Image (preview or browse):", bg=BG, fg=MUTED).pack(anchor="w")
        self.x_img_entry = PlaceholderEntry(extract_card, placeholder="(use Preview → Open Image) or browse", width=56, bg=CARD, fg=FG, insertbackground=FG)
        self.x_img_entry.pack(pady=6)
        b2 = tk.Button(extract_card, text="Browse Image", image=self.icon_browse, compound="left", bg=BTN_BG, fg=FG, relief="flat",
                       command=lambda: self._browse_and_put(self.x_img_entry))
        b2.pack(anchor="e")
        b2.bind("<Enter>", lambda e: e.widget.config(bg=BTN_HOVER)); b2.bind("<Leave>", lambda e: e.widget.config(bg=BTN_BG))

        tk.Label(extract_card, text="Password (optional):", bg=BG, fg=MUTED).pack(anchor="w")
        self.x_pwd = PlaceholderEntry(extract_card, placeholder="Password (optional)", width=40, bg=CARD, fg=FG, insertbackground=FG)
        self.x_pwd.pack(fill="x", pady=6)

        self.x_progress = ttk.Progressbar(extract_card, mode="indeterminate")
        self.x_progress.pack(fill="x", pady=(4, 6))

        ex_frame = tk.Frame(extract_card, bg=BG)
        ex_frame.pack(fill="x", pady=6)

	# Extract File button
        extract_btn = tk.Button(ex_frame, text="Extract File", bg=ACCENT, fg="white", relief="flat", command=self._extract_file)
        extract_btn.pack(side="left", padx=6)
        extract_btn.bind("<Enter>", lambda e: e.widget.config(bg=BTN_HOVER))
        extract_btn.bind("<Leave>", lambda e: e.widget.config(bg=ACCENT))

	# Clear button
        clear_extract_btn = tk.Button(ex_frame, text="Clear", bg=BTN_BG, fg=FG, relief="flat",
    	    command=lambda: [
                self.x_img_entry.delete(0, "end"),
                self.x_pwd.delete(0, "end")
            ])
        clear_extract_btn.pack(side="left", padx=6)
        clear_extract_btn.bind("<Enter>", lambda e: e.widget.config(bg=BTN_HOVER))
        clear_extract_btn.bind("<Leave>", lambda e: e.widget.config(bg=BTN_BG))


    # ---------- Preview handlers ----------
    def _browse_image(self):
        path = filedialog.askopenfilename(
    	    initialdir=self.last_dir,
    	    title="Open image",
    	    filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")]
	)
        if path:
    	    self.last_dir = os.path.dirname(path)
    	    self._set_preview(path)

    def _browse_and_put(self, entry_widget, file=False):
    	initial = getattr(self, "last_dir", ASSETS_DIR if os.path.isdir(ASSETS_DIR) else os.getcwd())

    	if file:
            p = filedialog.askopenfilename(
            	initialdir=initial,
            	title="Select file"
            )
    	else:
            p = filedialog.askopenfilename(
            	initialdir=initial,
            	title="Open image",
            	filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")]
            )

    	if p:
            # Store last visited folder
            self.last_dir = os.path.dirname(p)

            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, p)

            if not file:
            	self._set_preview(p)


    def _set_preview(self, path):
        try:
            img = Image.open(path)
            self.current_image_path = path
            self.img_full = img.copy()
            img.thumbnail((320, 320))
            self.thumb = ImageTk.PhotoImage(img)
            self.thumb_label.config(image=self.thumb, text="")
            self.img_path_var.set(path)
            try:
                cap = get_max_capacity(path)
                self.capacity_var.set(f"Capacity: {cap} bytes")
            except Exception:
                self.capacity_var.set("Capacity: —")
        except Exception as e:
            messagebox.showerror("Preview error", f"Unable to preview image: {e}")

    def _open_preview_fullsize(self):
        if not getattr(self, "img_full", None):
            return
        open_with_default_app(self.current_image_path)

    def _clear_preview(self):
        self.current_image_path = ""
        self.img_full = None
        self.thumb = None
        self.img_path_var.set("")
        self.capacity_var.set("Capacity: —")
        self.thumb_label.config(image="", text="No image loaded", fg=MUTED)

    # DnD handler (optional)
    def _on_drop(self, event):
        # event.data may contain a list of filenames — keep it simple
        data = event.data
        if not data:
            return
        # On some platforms data comes in as '{/path/one} {/path/two}'
        paths = []
        for token in data.split():
            token = token.strip("{}")
            if os.path.isfile(token):
                paths.append(token)
        if paths:
            # take first
            self._set_preview(paths[0])

    # ---------- Actions (threaded) ----------
    def _clear_text_tab(self):
        self.tx_msg.delete("1.0", "end")
        self.tx_pwd.put_placeholder()
        self.tx_img_entry.put_placeholder()
        
    def _clear_file_tab(self):
    	self.f_img_entry.put_placeholder()
    	self.f_file_entry.put_placeholder()
    	self.f_pwd.put_placeholder()
    	self.f_output_entry.put_placeholder() if hasattr(self, 'f_output_entry') else None
    	self._clear_preview()

    def _hide_message(self):
        img = self.tx_img_entry.get()
        if img == self.tx_img_entry.placeholder:
            img = getattr(self, "current_image_path", "")
        msg = self.tx_msg.get("1.0", "end").strip()
        pwd = self.tx_pwd.get()
        if not img or not msg:
            messagebox.showerror("Error", "Please select an image and enter a message.")
            return
        out = filedialog.asksaveasfilename(initialdir=ASSETS_DIR, defaultextension=".png", filetypes=[("PNG", "*.png")])
        if not out:
            return
        self.tx_progress.start(10)

        @threaded
        def work():
            try:
                hide_message(img, msg, out, pwd if pwd and pwd != self.tx_pwd.placeholder else None)
                self.root_event(lambda: messagebox.showinfo("Success", f"Saved to {out}"))
                # show stego preview
                self.root_event(lambda: self._set_preview(out))
            except Exception as e:
                self.root_event(lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.root_event(lambda: self.tx_progress.stop())

        work()

    def _extract_message(self):
        img = self.tx_img_entry.get()
        if img == self.tx_img_entry.placeholder:
            img = getattr(self, "current_image_path", "")
        if not img:
            messagebox.showerror("Error", "Please select an image to extract from.")
            return
        pwd = self.tx_pwd.get()
        self.tx_progress.start(10)

        @threaded
        def work():
            try:
                msg = extract_message(img, pwd if pwd and pwd != self.tx_pwd.placeholder else None)
                self.root_event(lambda: self.tx_msg.delete("1.0", "end"))
                self.root_event(lambda: self.tx_msg.insert("1.0", msg))
                self.root_event(lambda: messagebox.showinfo("Success", "Message extracted."))
            except Exception as e:
                self.root_event(lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.root_event(lambda: self.tx_progress.stop())

        work()

    def _hide_file(self):
        img = self.f_img_entry.get()
        if img == self.f_img_entry.placeholder:
            img = getattr(self, "current_image_path", "")
        file_path = self.f_file_entry.get()
        if file_path == self.f_file_entry.placeholder:
            messagebox.showerror("Error", "Select a file to hide.")
            return
        if not img or not file_path:
            messagebox.showerror("Error", "Please select image and file to hide.")
            return
        out = filedialog.asksaveasfilename(initialdir=ASSETS_DIR, defaultextension=".png", filetypes=[("PNG", "*.png")])
        if not out:
            return
        pwd = self.f_pwd.get()
        self.f_progress.start(10)

        @threaded
        def work():
            tmp_enc = None
            try:
                # If password provided, encrypt the file bytes to a temporary file first
                if pwd and pwd != self.f_pwd.placeholder:
                    with open(file_path, "rb") as f:
                        raw = f.read()
                    enc = encrypt_bytes(raw, pwd)
                    fd, tmp_enc = tempfile.mkstemp(suffix=".enc")
                    os.close(fd)
                    with open(tmp_enc, "wb") as f:
                        f.write(enc)
                    hide_file(img, tmp_enc, out)
                else:
                    hide_file(img, file_path, out)
                self.root_event(lambda: messagebox.showinfo("Success", f"File hidden to {out}"))
                # show stego preview
                self.root_event(lambda: self._set_preview(out))
            except Exception as e:
                self.root_event(lambda: messagebox.showerror("Error", str(e)))
            finally:
                if tmp_enc and os.path.exists(tmp_enc):
                    try:
                        os.remove(tmp_enc)
                    except Exception:
                        pass
                self.root_event(lambda: self.f_progress.stop())

        work()

    def _extract_file(self):
        img = self.x_img_entry.get()
        if img == self.x_img_entry.placeholder:
            img = getattr(self, "current_image_path", "")
        if not img:
            messagebox.showerror("Error", "Please select a stego image.")
            return

        # Ask for folder, default to project's assets folder
        outdir = filedialog.askdirectory(initialdir=ASSETS_DIR, title="Select output folder")
        if not outdir:
            outdir = os.path.dirname(img) if img else os.getcwd()

        pwd = self.x_pwd.get()
        self.x_progress.start(10)

        @threaded
        def work():
            try:
                path = extract_file(img, outdir)
                # If password provided, attempt to decrypt the extracted file in-place
                if pwd and pwd != self.x_pwd.placeholder:
                    try:
                        with open(path, "rb") as f:
                            enc = f.read()
                        dec = decrypt_bytes(enc, pwd)
                        with open(path, "wb") as f:
                            f.write(dec)
                    except Exception as e:
                        # If decryption fails, notify user but still leave file
                        self.root_event(lambda: messagebox.showwarning("Decryption failed", f"File extracted but decryption failed: {e}"))
                        self.root_event(lambda: self._open_folder_and_select(path))
                        return

                self.root_event(lambda: messagebox.showinfo("Success", f"Extracted to {path}"))
                # Auto-open the folder containing the extracted file
                self.root_event(lambda: self._open_folder_and_select(path))
            except Exception as e:
                self.root_event(lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.root_event(lambda: self.x_progress.stop())

        work()

    def _open_folder_and_select(self, path):
        folder = os.path.dirname(path)
        try:
            if platform.system() == "Windows":
                subprocess.run(["explorer", "/select,", os.path.normpath(path)], check=False)
            elif platform.system() == "Darwin":
                subprocess.run(["open", "-R", path], check=False)
            else:
                subprocess.run(["xdg-open", folder], check=False)
        except Exception:
            open_with_default_app(folder)

    def _show_capacity(self):
        path = getattr(self, "current_image_path", "") or ""
        if not path:
            messagebox.showinfo("Capacity", "No image selected.")
            return
        try:
            cap = get_max_capacity(path)
            messagebox.showinfo("Capacity", f"Approximate capacity: {cap} bytes")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---------- New method: Run automated test ----------
    def _run_test(self):
        """Auto test:
        - Use bundled assets/test_image.png if present, else create temp placeholder.
        - Hide Test123 into it, save stego PNG to assets/stego_test_output.png, extract and verify.
        - Update preview with produced stego image on success.
        """
        test_message = "Test123"
        img_path = ensure_test_image()
        if not img_path:
            # fallback local
            img_path = _ensure_test_image_local()
            if not img_path:
                messagebox.showerror("Test aborted", "No test image available.")
                return

        # Save stego output to assets folder
        out_path = os.path.join(ASSETS_DIR, "stego_test_output.png")

        # progress
        try:
            self.tx_progress.start(10)
        except Exception:
            pass

        @threaded
        def work():
            try:
                hide_message(img_path, test_message, out_path, None)
                extracted = extract_message(out_path, None)
                if extracted == test_message:
                    self.root_event(lambda: self._set_preview(out_path))
                    self.root_event(lambda: messagebox.showinfo("Auto Test Result", f"Success! Message '{extracted}' correctly hidden and extracted.\nSaved to:\n{out_path}"))
                else:
                    self.root_event(lambda: messagebox.showerror("Auto Test Result", f"Failure: Extracted message '{extracted}' does not match test message."))
            except Exception as e:
                self.root_event(lambda: messagebox.showerror("Auto Test Error", str(e)))
            finally:
                self.root_event(lambda: self.tx_progress.stop() if hasattr(self, "tx_progress") else None)

        work()

    # convenience to safely call GUI updates from threads
    def root_event(self, func):
        self.root.after(0, func)


# ------------------------
# Run
# ------------------------
def launch_gui():
    # If tkinterdnd2 is available and user wants fullscreen drag-drop, they can start specially.
    # We'll just start a normal Tk here; DnD is optional and handled if available.
    root = tk.Tk()
    app = StegoGUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
