import sys
import os
import json
import time
import ctypes
import ctypes.wintypes as wintypes
import webview  # pywebview for the settings UI
import win32gui

from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtGui import QIcon, QPainter, QPen, QColor
from PyQt6.QtCore import Qt, QCoreApplication

# Fix for QtWebEngineWidgets context error
QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

CONFIG_FILENAME = 'crosshair_config.json'


def get_app_folder():
  
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(__file__)


class Overlay(QMainWindow):
    def __init__(self):
        super().__init__()
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowTransparentForInput |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Default settings placeholders
        self.line_thickness = 1
        self.line_color = QColor(255, 0, 0, 255)
        self.show_lines = True
        self.vert_length_ratio = 0.0
        self.horiz_length_ratio = 0.0

    def paintEvent(self, event):
        if not self.show_lines:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.line_color, self.line_thickness, Qt.PenStyle.SolidLine)
        painter.setPen(pen)

        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        v_off = int(self.vert_length_ratio * h)
        h_off = int(self.horiz_length_ratio * w)

        painter.drawLine(cx, v_off, cx, h - v_off)
        painter.drawLine(h_off, cy, w - h_off, cy)


class Api:
    def __init__(self, overlay):
        self.overlay = overlay
        app_folder = get_app_folder()
        os.makedirs(app_folder, exist_ok=True)
        self.config_path = os.path.join(app_folder, CONFIG_FILENAME)
        self.config = self.load_config()
        self.apply_settings()

    def load_config(self):
        defaults = {
            'thickness': 1,
            'vert_offset': 0.0,
            'horiz_offset': 0.0,
            'r': 89, 'g': 247, 'b': 255,
            'alpha': 255,
            'show': True,
            'hex_color': '#59f7ff'
        }
        if not os.path.exists(self.config_path):
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(defaults, f, indent=4)
            return defaults.copy()
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
        except Exception:
            loaded = {}
        return {**defaults, **loaded}

    def get_config(self):
        cfg = self.config.copy()
        cfg['alpha_percent'] = int((cfg.get('alpha', 255) / 255) * 100)
        return cfg

    def apply_settings(self):
        self.overlay.line_thickness = max(1, int(self.config.get('thickness', 1)))
        self.overlay.vert_length_ratio = float(self.config.get('vert_offset', 0.0))
        self.overlay.horiz_length_ratio = float(self.config.get('horiz_offset', 0.0))
        r = int(self.config.get('r', 255))
        g = int(self.config.get('g', 0))
        b = int(self.config.get('b', 0))
        a = int(self.config.get('alpha', 255))
        self.overlay.line_color = QColor(r, g, b, a)
        self.overlay.show_lines = bool(self.config.get('show', True))
        self.overlay.update()

    def save_config(self, new_cfg):
        if 'alpha_percent' in new_cfg:
            a_pct = new_cfg.pop('alpha_percent')
            new_cfg['alpha'] = min(255, max(0, round((a_pct / 100) * 255)))
        self.config.update(new_cfg)
        self.apply_settings()
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4)
        return self.config


# Set Windows title bar color via DWM API

def set_window_caption_color(hwnd, bg_color, text_color=0x00FFFFFF):
    """
    bg_color DWORD: 0x00BBGGRR, text_color DWORD default white
    """
    DWMWA_CAPTION_COLOR = 35
    DWMWA_TEXT_COLOR = 36
    dwm = ctypes.WinDLL('dwmapi')
    bg = wintypes.DWORD(bg_color)
    dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), ctypes.c_uint(DWMWA_CAPTION_COLOR), ctypes.byref(bg), ctypes.sizeof(bg))
    fg = wintypes.DWORD(text_color)
    dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), ctypes.c_uint(DWMWA_TEXT_COLOR), ctypes.byref(fg), ctypes.sizeof(fg))


def find_hwnd_by_title_substring(substr, timeout=0.8, interval=0.0):
    """Polls EnumWindows for a matching title substring until timeout."""
    end = time.time() + timeout
    while time.time() < end:
        hwnds = []
        def cb(hwnd, _):
            title = win32gui.GetWindowText(hwnd)
            if substr.lower() in title.lower():
                hwnds.append(hwnd)
        win32gui.EnumWindows(cb, None)
        if hwnds:
            return hwnds[0]
        time.sleep(interval)
    return None

HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crosshair</title>
    <style>
        :root {
            --bg-color: #121212;
            --surface-color: #1e1e1e;
            --accent-color: #4CAF50;
            --text-color: #e0e0e0;
            --text-bright: #ffffff;
            --border-color: #333;
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body { 
            font-family: 'Segoe UI', Arial, sans-serif; 
            padding: 15px; 
            background-color: var(--bg-color);
            color: var(--text-color);
            overflow: hidden;
            user-select: none;
            max-width: 100%;
            max-height: 100%;
            resize: none;
        }
        
        h2 {
            color: var(--text-bright);
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border-color);
            font-size: 18px;
            margin-bottom: 15px;
        }
        
        .control-group { 
            margin: 12px 0;
        }
        
        label { 
            display: block; 
            margin-bottom: 5px;
            font-size: 14px;
            color: var(--text-bright);
        }
        
        input[type=range] { 
            width: 100%; 
            height: 6px;
            -webkit-appearance: none;
            background: var(--border-color);
            border-radius: 4px;
            outline: none;
            margin: 8px 0;
        }
        
        input[type=range]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 16px;
            height: 16px;
            background: var(--accent-color);
            border-radius: 50%;
            cursor: pointer;
            transition: transform 0.1s;
        }
        
        input[type=range]::-webkit-slider-thumb:hover {
            transform: scale(1.1);
        }
        
        input[type=number] { 
            width: 60px; 
            background: var(--surface-color);
            border: 1px solid var(--border-color);
            color: var(--text-bright);
            padding: 6px;
            border-radius: 4px;
            font-size: 14px;
            text-align: center;
            /* Remove spinner buttons from number inputs */
            -moz-appearance: textfield;
        }
        
        /* Chrome, Safari, Edge, Opera - remove spinner buttons */
        input[type=number]::-webkit-inner-spin-button, 
        input[type=number]::-webkit-outer-spin-button { 
            -webkit-appearance: none;
            margin: 0;
        }
        
        input[type=number]:focus {
            outline: 1px solid var(--accent-color);
            border-color: var(--accent-color);
        }
        
        #color-preview { 
            width: 100%; 
            height: 50px; 
            margin: 15px 0; 
            border: 1px solid var(--border-color); 
            border-radius: 6px;
            background: var(--bg-color);
            box-shadow: inset 0 0 10px rgba(0,0,0,0.3);
        }
        
        .color-section { 
            border: 1px solid var(--border-color); 
            padding: 15px; 
            margin: 20px 0;
            border-radius: 8px;
            background-color: var(--surface-color);
        }
        
        .section-title {
            margin-top: 0;
            font-size: 16px;
            color: var(--text-bright);
            margin-bottom: 10px;
        }
        
        .checkbox-container {
            display: flex;
            align-items: center;
            margin-top: 20px;
            background-color: var(--surface-color);
            padding: 10px 15px;
            border-radius: 6px;
            border: 1px solid var(--border-color);
        }
        
        .checkbox-container input[type="checkbox"] {
            margin-right: 10px;
            transform: scale(1.2);
            accent-color: var(--accent-color);
            cursor: pointer;
        }
        
        .checkbox-container label {
            margin-bottom: 0;
            cursor: pointer;
        }
        
        .rgb-controls {
            display: grid;
            grid-template-columns: 1fr 60px;
            gap: 10px;
            align-items: center;
        }
        
        .rgb-slider {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        /* Color coding for RGB sliders */
        #r, #r_num {
            accent-color: #f44336; /* Red */
        }
        
        #g, #g_num {
            accent-color: #4CAF50; /* Green */
        }
        
        #b, #b_num {
            accent-color: #2196F3; /* Blue */
        }
        
        /* Slider coloring */
        #r::-webkit-slider-thumb {
            background: #f44336;
        }
        
        #g::-webkit-slider-thumb {
            background: #4CAF50;
        }
        
        #b::-webkit-slider-thumb {
            background: #2196F3;
        }
        
        #alpha_percent::-webkit-slider-thumb {
            background: #9e9e9e;
        }
        
        /* Animations */
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        .color-section, .checkbox-container {
            animation: fadeIn 0.3s ease-in-out;
        }
    </style>
</head>
<body>
    <div class="control-group">
        <label>Line Thickness (px)</label>
        <div class="rgb-slider">
            <input type="range" id="thickness" min="1" max="20">
            <input type="number" id="thickness_num" min="1" max="20">
        </div>
    </div>

    <div class="control-group">
        <label>Vertical Offset Ratio (0.0-0.5)</label>
        <div class="rgb-slider">
            <input type="range" id="vert_offset" min="0" max="0.5" step="0.01">
            <input type="number" id="vert_offset_num" min="0" max="0.5" step="0.01">
        </div>
    </div>

    <div class="control-group">
        <label>Horizontal Offset Ratio (0.0-0.5)</label>
        <div class="rgb-slider">
            <input type="range" id="horiz_offset" min="0" max="0.5" step="0.01">
            <input type="number" id="horiz_offset_num" min="0" max="0.5" step="0.01">
        </div>
    </div>

    <div class="color-section">
        <h3 class="section-title">Color Settings</h3>
        
        <div id="color-preview"></div>

        <div class="control-group">
            <label>Red</label>
            <div class="rgb-slider">
                <input type="range" id="r" min="0" max="255">
                <input type="number" id="r_num" min="0" max="255">
            </div>
        </div>

        <div class="control-group">
            <label>Green</label>
            <div class="rgb-slider">
                <input type="range" id="g" min="0" max="255">
                <input type="number" id="g_num" min="0" max="255">
            </div>
        </div>

        <div class="control-group">
            <label>Blue</label>
            <div class="rgb-slider">
                <input type="range" id="b" min="0" max="255">
                <input type="number" id="b_num" min="0" max="255">
            </div>
        </div>

        <div class="control-group">
            <label>Opacity (0-100%)</label>
            <div class="rgb-slider">
                <input type="range" id="alpha_percent" min="0" max="100">
                <input type="number" id="alpha_percent_num" min="0" max="100">
            </div>
        </div>
    </div>

    <div class="checkbox-container">
        <input type="checkbox" id="show">
        <label for="show">Show Crosshair</label>
    </div>

    <script>
        window.addEventListener('pywebviewready', async () => {
            loadSettings();
        });

        // Disable resize
        window.addEventListener('resize', function(e) {
            e.preventDefault();
            return false;
        });

        let debounceTimer;
        const controllers = ['thickness', 'vert_offset', 'horiz_offset', 'r', 'g', 'b'];
        let currentHexColor = "#59f7ff";

        function setupControls(id) {
            const slider = document.getElementById(id);
            const number = document.getElementById(id + '_num');
            
            slider.oninput = () => {
                number.value = slider.value;
                updatePreview();
                autoSave();
            };
            
            number.oninput = () => {
                slider.value = number.value;
                updatePreview();
                autoSave();
            };
        }
        
        // Special setup for alpha percentage
        function setupAlphaControls() {
            const slider = document.getElementById('alpha_percent');
            const number = document.getElementById('alpha_percent_num');
            
            slider.oninput = () => {
                number.value = slider.value;
                updatePreview();
                autoSave();
            };
            
            number.oninput = () => {
                slider.value = number.value;
                updatePreview();
                autoSave();
            };
        }
        
        function autoSave() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(save, 100);
        }
        
        function save() {
            const cfg = {};
            controllers.forEach(id => {
                cfg[id] = +document.getElementById(id).value;
            });
            
            // Handle alpha conversion
            const alphaPercent = +document.getElementById('alpha_percent').value;
            cfg['alpha_percent'] = alphaPercent;
            
            cfg.show = document.getElementById('show').checked;
            cfg.hex_color = rgbToHex(
                document.getElementById('r').value,
                document.getElementById('g').value,
                document.getElementById('b').value
            );
            
            window.pywebview.api.save_config(cfg);
            return cfg;
        }
        
        function updatePreview() {
            const r = document.getElementById('r').value;
            const g = document.getElementById('g').value;
            const b = document.getElementById('b').value;
            const aPercent = document.getElementById('alpha_percent').value;
            const a = aPercent / 100;  // Convert to 0-1 range
            document.getElementById('color-preview').style.backgroundColor = `rgba(${r},${g},${b},${a})`;
            currentHexColor = rgbToHex(r, g, b);
        }
        
        function rgbToHex(r, g, b) {
            r = parseInt(r).toString(16).padStart(2, '0');
            g = parseInt(g).toString(16).padStart(2, '0');
            b = parseInt(b).toString(16).padStart(2, '0');
            return "#" + r + g + b;
        }
        
        document.getElementById('show').onchange = autoSave;
        
        async function loadSettings() {
            try {
                const cfg = await window.pywebview.api.get_config();

                // Load standard controls
                controllers.forEach(key => {
                    document.getElementById(key).value = cfg[key];
                    document.getElementById(key + '_num').value = cfg[key];
                    setupControls(key);
                });

                // Load alpha percentage
                const alphaPercent = cfg.alpha_percent !== undefined
                    ? cfg.alpha_percent
                    : Math.round((cfg.alpha / 255) * 100);

                document.getElementById('alpha_percent').value = alphaPercent;
                document.getElementById('alpha_percent_num').value = alphaPercent;
                setupAlphaControls();

                currentHexColor = cfg.hex_color || rgbToHex(cfg.r, cfg.g, cfg.b);
                document.getElementById('show').checked = cfg.show;
                updatePreview();
            } catch (error) {
                console.error("Error loading settings:", error);
            }
        }

        controllers.forEach(setupControls);
        setupAlphaControls();
    </script>
</body>
</html>
'''

# Create a custom webview window class to replace the default one


def main():
    app = QApplication(sys.argv)
    app_folder = get_app_folder()
    icon_path = os.path.join(app_folder, 'icon.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    overlay = Overlay()
    overlay.show()
    api = Api(overlay)

    # Create webview window
    window = webview.create_window(
        'ScreenCrosshair', html=HTML, js_api=api,
        width=400, height=700, resizable=False, min_size=(400,700)
    )

    # Callback: wait for window then set title bar color
    def on_ready():
        hwnd = find_hwnd_by_title_substring('ScreenCrosshair')
        if hwnd:
            set_window_caption_color(hwnd, bg_color=0x000000)
        else:
            print("(timeout).")

    # Start GUI
    if os.path.exists(icon_path):
        webview.start(gui='qt', icon=icon_path, func=on_ready)
    else:
        webview.start(gui='qt', func=on_ready)


if __name__ == '__main__':
    main()