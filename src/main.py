import argparse       # For command-line argument parsing
import os
import random         # For random jittering
import threading      # To run the jiggler in a background thread
import time           # For sleep and timestamps
import tkinter as tk  # GUI library
from tkinter import ttk, messagebox  # Modern widgets and dialogs
import ctypes         # For calling Windows API functions
from ctypes import wintypes
import sys

# --- Win32 setup (no external deps) ---
user32 = ctypes.WinDLL("user32", use_last_error=True)  # Load user32.dll (Windows GUI functions)

# Define a POINT struct for Windows API
class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]  # x and y coordinates

LPPOINT = ctypes.POINTER(POINT)  # Pointer type to pass to API functions

# Bind Windows API functions
GetCursorPos = user32.GetCursorPos
GetCursorPos.argtypes = [LPPOINT]   # Takes a pointer to POINT
GetCursorPos.restype = wintypes.BOOL

SetCursorPos = user32.SetCursorPos
SetCursorPos.argtypes = [wintypes.INT, wintypes.INT]  # x, y coordinates
SetCursorPos.restype = wintypes.BOOL

# --- Helper functions to get/set mouse position ---
def get_cursor_pos():
    """Return current mouse cursor position as (x, y)."""
    p = POINT()
    if not GetCursorPos(ctypes.byref(p)):
        raise ctypes.WinError(ctypes.get_last_error())
    return p.x, p.y

def set_cursor_pos(x, y):
    """Set mouse cursor position to (x, y)."""
    if not SetCursorPos(int(x), int(y)):
        raise ctypes.WinError(ctypes.get_last_error())

# --- Core Mouse Jiggler logic ---
class MouseJiggler:
    def __init__(self, base_interval=45, interval_jitter=10, pixel_jitter=2, idle_grace=2.0):
        """
        base_interval: seconds between jiggles
        interval_jitter: random +/- seconds to vary interval
        pixel_jitter: max pixels to move cursor
        idle_grace: seconds since last user movement to consider idle
        """
        self.base_interval = float(base_interval)
        self.interval_jitter = float(interval_jitter)
        self.pixel_jitter = int(pixel_jitter)
        self.idle_grace = float(idle_grace)

        self._thread = None
        self._stop = threading.Event()       # Flag to stop thread
        self._last_pos = get_cursor_pos()    # Track last cursor position
        self._last_move_time = time.time()   # Track last time user moved mouse

    def _idle(self):
        """Return True if mouse is idle long enough."""
        x, y = get_cursor_pos()
        if (x, y) != self._last_pos:
            # User moved, reset timer
            self._last_pos = (x, y)
            self._last_move_time = time.time()
            return False
        # True if enough time has passed since last movement
        return (time.time() - self._last_move_time) >= self.idle_grace

    def _sleep_randomized(self):
        """Sleep for base_interval ± interval_jitter seconds."""
        wait = self.base_interval + random.uniform(-self.interval_jitter, self.interval_jitter)
        wait = max(1.0, wait)  # Ensure at least 1 second
        for _ in range(int(wait * 10)):
            if self._stop.is_set():
                return
            time.sleep(0.1)

    def _jiggle_once(self):
        """
        Perform a tiny mouse move (micro-jiggle) and return cursor to original position.
        This avoids cursor drift while keeping PC awake.
        """
        ox, oy = get_cursor_pos()  # original position
        dx = random.randint(-self.pixel_jitter, self.pixel_jitter)
        dy = random.randint(-self.pixel_jitter, self.pixel_jitter)
        if dx == 0 and dy == 0:
            dx = 1  # ensure at least some movement
        try:
            set_cursor_pos(ox + dx, oy + dy)
            time.sleep(0.05)          # short delay
            set_cursor_pos(ox, oy)    # move back
        except Exception:
            pass  # ignore any transient errors

    def _run(self):
        """Thread function: loop, sleep, and jiggle if idle."""
        while not self._stop.is_set():
            self._sleep_randomized()
            if self._stop.is_set():
                break
            if self._idle():          # Only jiggle if user not active
                self._jiggle_once()

    def start(self):
        """Start the jiggler in a background thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the jiggler and wait for thread to exit."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)


def resource_path(relative_path):
    """Get absolute path to resource, works in dev and PyInstaller."""
    try:
        base_path = sys._MEIPASS  # PyInstaller temp folder
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# --- GUI Application ---
class App(tk.Tk):
    def __init__(self):
        super().__init__()

        # --- Set the window icon here ---
        icon_path = resource_path("assets/click_64px.ico")  # compatible size
        self.iconbitmap(icon_path)

        self.title("Tiny Mouse Jiggler")
        self.geometry("300x200")       # bigger window
        self.resizable(False, False)
        self.overrideredirect(False)

        self.jiggler = MouseJiggler()

        # --- Main wrapper frame to center everything ---
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(expand=True)  # expand vertically and horizontally
        main_frame.grid_columnconfigure(0, weight=1)  # center columns

        self.var_running = tk.BooleanVar(value=False)

        # --- Input fields in a sub-frame ---
        input_frame = ttk.Frame(main_frame)
        input_frame.grid(row=0, column=0, pady=(0, 20))  # space below inputs
        for i in range(2):
            input_frame.grid_columnconfigure(i, weight=1)

        ttk.Label(input_frame, text="Interval (sec)").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.ent_interval = ttk.Entry(input_frame, width=10)
        self.ent_interval.insert(0, "45")
        self.ent_interval.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(input_frame, text="Interval jitter ±").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.ent_jitter = ttk.Entry(input_frame, width=10)
        self.ent_jitter.insert(0, "10")
        self.ent_jitter.grid(row=1, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(input_frame, text="Pixel jitter").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.ent_pixels = ttk.Entry(input_frame, width=10)
        self.ent_pixels.insert(0, "2")
        self.ent_pixels.grid(row=2, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(input_frame, text="Idle grace (sec)").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        self.ent_idle = ttk.Entry(input_frame, width=10)
        self.ent_idle.insert(0, "2.0")
        self.ent_idle.grid(row=3, column=1, sticky="w", padx=5, pady=5)

        # --- Buttons at the bottom ---
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=1, column=0)
        self.btn_toggle = ttk.Button(btn_frame, text="Start", command=self.toggle)
        self.btn_toggle.pack(side="left", padx=10)

        self.btn_quit = ttk.Button(btn_frame, text="Quit", command=self.quit_app)
        self.btn_quit.pack(side="left", padx=10)

        # Ensure jiggler stops on window close
        self.protocol("WM_DELETE_WINDOW", self.quit_app)

    def toggle(self):
        """Toggle the jiggler on/off when the button is clicked."""
        running = self.var_running.get()
        if not running:
            try:
                # Update jiggler settings from inputs
                self.jiggler.base_interval = float(self.ent_interval.get())
                self.jiggler.interval_jitter = float(self.ent_jitter.get())
                self.jiggler.pixel_jitter = int(self.ent_pixels.get())
                self.jiggler.idle_grace = float(self.ent_idle.get())
            except ValueError:
                messagebox.showerror("Invalid input", "Please enter valid numbers.")
                return
            self.jiggler.start()
            self.var_running.set(True)
            self.btn_toggle.config(text="Stop")
        else:
            self.jiggler.stop()
            self.var_running.set(False)
            self.btn_toggle.config(text="Start")

    def quit_app(self):
        """Stop the jiggler and close the window."""
        try:
            self.jiggler.stop()
        finally:
            self.destroy()

# --- Command-Line Interface (optional) ---
def main():
    parser = argparse.ArgumentParser(description="Tiny Mouse Jiggler")
    parser.add_argument("--headless", action="store_true", help="Run without GUI")
    parser.add_argument("--interval", type=float, default=45, help="Base interval seconds")
    parser.add_argument("--jitter", type=float, default=10, help="Interval jitter ± seconds")
    parser.add_argument("--pixels", type=int, default=2, help="Max pixel jitter")
    parser.add_argument("--idle-grace", type=float, default=2.0, help="Seconds since last mouse move to count as idle")
    args = parser.parse_args()

    if args.headless:
        # Headless mode: run jiggler without GUI
        jig = MouseJiggler(args.interval, args.jitter, args.pixels, args.idle_grace)
        jig.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            jig.stop()
    else:
        # Start GUI
        App().mainloop()

if __name__ == "__main__":
    main()
