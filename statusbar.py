from PySide6.QtWidgets import QStatusBar, QLabel, QFrame
from PySide6.QtCore import Qt

class CrochetStatusBar(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QStatusBar {
                background-color: #151515;
                color: #aaaaaa;
                border-top: 1px solid #2d2d2d;
            }
            QStatusBar::item {
                border: none;
            }
            QLabel {
                font-family: "Outfit", sans-serif;
                font-size: 9pt;
                padding: 2px 5px;
            }
            .status-val {
                color: #ffffff;
                font-weight: bold;
            }
            .status-accent {
                color: #00adb5;
                font-weight: bold;
            }
        """)
        
        self.project = None
        self.init_ui()

    def init_ui(self):
        # 1. Overall Progress Label
        self.lbl_progress = QLabel("Progress: <span class='status-val'>0 / 0 (0.0%)</span>")
        self.addWidget(self.lbl_progress)
        
        self.add_separator()
        
        # 2. Zoom Level Label
        self.lbl_zoom = QLabel("Zoom: <span class='status-accent'>100%</span>")
        self.addWidget(self.lbl_zoom)
        
        self.add_separator()
        
        # 3. Current Cursor Stitch
        self.lbl_cursor = QLabel("Cursor: <span class='status-val'>Row - Col -</span> | Color: <span class='status-val'>-</span>")
        self.addWidget(self.lbl_cursor)
        
        self.add_separator()
        
        # 4. Hover Stitch (Far right / temporary)
        self.lbl_hover = QLabel("Hover: <span class='status-val'>Row - Col -</span> | Color: <span class='status-val'>-</span>")
        self.addPermanentWidget(self.lbl_hover)

    def add_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #2d2d2d; max-width: 1px; margin: 4px 2px;")
        self.addWidget(line)

    def set_project(self, project):
        self.project = project
        self.update_progress()
        self.update_cursor(0, 0)
        self.update_hover(-1, -1, "")

    def update_progress(self):
        if not self.project:
            self.lbl_progress.setText("Progress: <span class='status-val'>0 / 0 (0.0%)</span>")
            return
            
        total = self.project.width * self.project.height
        completed = len(self.project.completed_stitches)
        pct = (completed / total * 100.0) if total > 0 else 0
        
        self.lbl_progress.setText(
            f"Progress: <span class='status-accent'>{completed}</span> / <span class='status-val'>{total}</span> "
            f"(<span class='status-accent'>{pct:.1f}%</span>)"
        )

    def update_zoom(self, factor):
        self.lbl_zoom.setText(f"Zoom: <span class='status-accent'>{int(factor * 100)}%</span>")

    def update_cursor(self, row, col):
        if not self.project:
            self.lbl_cursor.setText("Cursor: <span class='status-val'>Row - Col -</span> | Color: <span class='status-val'>-</span>")
            return
            
        hex_val = self.project.pixel_hexes[row][col]
        color_info = self.project.color_palette.get(hex_val)
        color_name = color_info['name'] if color_info else "Unknown"
        symbol = color_info['symbol'] if color_info else "?"
        
        self.lbl_cursor.setText(
            f"Cursor: Row <span class='status-val'>{row + 1}</span> Col <span class='status-val'>{col + 1}</span> | "
            f"Color: <span class='status-val'>{color_name} ({symbol}) {hex_val}</span>"
        )

    def update_hover(self, row, col, hex_val):
        if not self.project or row == -1 or col == -1:
            self.lbl_hover.setText("Hover: <span class='status-val'>Row - Col -</span> | Color: <span class='status-val'>-</span>")
            return
            
        color_info = self.project.color_palette.get(hex_val)
        color_name = color_info['name'] if color_info else "Unknown"
        symbol = color_info['symbol'] if color_info else "?"
        
        self.lbl_hover.setText(
            f"Hover: Row <span class='status-val'>{row + 1}</span> Col <span class='status-val'>{col + 1}</span> | "
            f"Color: <span class='status-val'>{color_name} ({symbol}) {hex_val}</span>"
        )
