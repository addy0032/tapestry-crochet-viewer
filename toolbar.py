from PySide6.QtWidgets import (QToolBar, QComboBox, QPushButton, QColorDialog, 
                             QCheckBox, QLabel, QWidget, QHBoxLayout, QSizePolicy)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QColor, QPixmap

class CrochetToolbar(QToolBar):
    # Signals for actions that are handled by the main window
    openClicked = Signal()
    saveClicked = Signal()
    exportClicked = Signal()
    undoClicked = Signal()
    redoClicked = Signal()
    zoomFitClicked = Signal()
    toggleSidebarClicked = Signal()
    
    # Grid settings signals
    gridToggled = Signal(bool)
    gridThicknessChanged = Signal(str)
    gridColorChanged = Signal(QColor)
    
    # View toggles signals
    symbolsToggled = Signal(bool)
    rowHighlightToggled = Signal(bool)
    colHighlightToggled = Signal(bool)
    
    # Navigation signals
    prevStitchClicked = Signal()
    nextStitchClicked = Signal()
    prevRowClicked = Signal()
    nextRowClicked = Signal()
    autoCursorToggled = Signal(bool)
    
    # Crochet direction & progress signals
    directionModeChanged = Signal(str)
    reverseDirectionToggled = Signal(bool)
    completionStyleChanged = Signal(str)
    progressLineColorChanged = Signal(QColor)

    def __init__(self, parent=None):
        super().__init__("Main Toolbar", parent)
        self.setMovable(False)
        self.setAllowedAreas(Qt.TopToolBarArea)
        self.setStyleSheet("""
            QToolBar {
                background-color: #1a1a1a;
                border-bottom: 1px solid #2d2d2d;
                spacing: 6px;
                padding: 4px;
            }
            QToolBar QLabel {
                color: #aaaaaa;
                font-size: 9pt;
                font-weight: bold;
                margin-left: 4px;
                margin-right: 2px;
            }
            QPushButton, QComboBox, QCheckBox {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 9pt;
            }
            QPushButton:hover, QComboBox:hover {
                background-color: #3d3d3d;
                border-color: #00adb5;
            }
            QPushButton:pressed {
                background-color: #00adb5;
                color: #121212;
            }
            QComboBox::drop-down {
                border: none;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border: 1px solid #555;
                border-radius: 3px;
                background-color: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                background-color: #00adb5;
                border-color: #00adb5;
            }
        """)
        
        self.init_ui()

    def init_ui(self):
        # 1. File Section
        self.btn_open = QPushButton("Open")
        self.btn_open.setToolTip("Open Image (Ctrl+O)")
        self.btn_open.clicked.connect(self.openClicked.emit)
        self.addWidget(self.btn_open)
        
        self.btn_save = QPushButton("Save")
        self.btn_save.setToolTip("Save Project (Ctrl+S)")
        self.btn_save.clicked.connect(self.saveClicked.emit)
        self.addWidget(self.btn_save)
        
        self.btn_export = QPushButton("Export PNG")
        self.btn_export.setToolTip("Export Canvas Pattern as PNG")
        self.btn_export.clicked.connect(self.exportClicked.emit)
        self.addWidget(self.btn_export)
        
        self.addSeparator()
        
        # 2. Undo / Redo Section
        self.btn_undo = QPushButton("Undo")
        self.btn_undo.setToolTip("Undo Last Action (Ctrl+Z)")
        self.btn_undo.clicked.connect(self.undoClicked.emit)
        self.addWidget(self.btn_undo)
        
        self.btn_redo = QPushButton("Redo")
        self.btn_redo.setToolTip("Redo Last Action (Ctrl+Y)")
        self.btn_redo.clicked.connect(self.redoClicked.emit)
        self.addWidget(self.btn_redo)
        
        self.addSeparator()
        
        # 3. Zoom Section
        self.addWidget(QLabel("Zoom:"))
        self.zoom_combo = QComboBox()
        self.zoom_combo.addItems(["6.25%", "12.5%", "25%", "50%", "75%", "100%", "150%", "200%", "300%", "400%", "600%", "800%", "1200%", "1600%", "2400%", "3200%", "4800%", "6400%"])
        self.zoom_combo.setCurrentIndex(5)  # default 100%
        self.zoom_combo.setFixedWidth(80)
        self.addWidget(self.zoom_combo)
        
        self.btn_fit = QPushButton("Fit")
        self.btn_fit.setToolTip("Fit Pattern to Screen (0)")
        self.btn_fit.clicked.connect(self.zoomFitClicked.emit)
        self.addWidget(self.btn_fit)
        
        self.addSeparator()
        
        # 4. View Toggles Section
        self.addWidget(QLabel("Show:"))
        self.chk_grid = QCheckBox("Grid")
        self.chk_grid.setToolTip("Toggle Grid lines (G)")
        self.chk_grid.setChecked(True)
        self.chk_grid.toggled.connect(self.gridToggled.emit)
        self.addWidget(self.chk_grid)
        
        self.chk_symbols = QCheckBox("Symbols")
        self.chk_symbols.setToolTip("Toggle Stitch Symbols (T)")
        self.chk_symbols.setChecked(False)
        self.chk_symbols.toggled.connect(self.symbolsToggled.emit)
        self.addWidget(self.chk_symbols)
        
        self.chk_row_highlight = QCheckBox("Row Highlight")
        self.chk_row_highlight.setToolTip("Toggle Current Row Highlight (R)")
        self.chk_row_highlight.setChecked(True)
        self.chk_row_highlight.toggled.connect(self.rowHighlightToggled.emit)
        self.addWidget(self.chk_row_highlight)
        
        self.chk_col_highlight = QCheckBox("Col Highlight")
        self.chk_col_highlight.setToolTip("Toggle Current Column Highlight")
        self.chk_col_highlight.setChecked(False)
        self.chk_col_highlight.toggled.connect(self.colHighlightToggled.emit)
        self.addWidget(self.chk_col_highlight)
        
        self.addSeparator()
        
        # 5. Cursor Navigation
        self.addWidget(QLabel("Stitch Cursor:"))
        
        self.btn_prev_row = QPushButton("Row -")
        self.btn_prev_row.setToolTip("Move Cursor to Previous Row")
        self.btn_prev_row.clicked.connect(self.prevRowClicked.emit)
        self.addWidget(self.btn_prev_row)
        
        self.btn_prev_stitch = QPushButton("<")
        self.btn_prev_stitch.setToolTip("Move to Previous Stitch (Shift+Space)")
        self.btn_prev_stitch.clicked.connect(self.prevStitchClicked.emit)
        self.addWidget(self.btn_prev_stitch)
        
        self.btn_next_stitch = QPushButton(">")
        self.btn_next_stitch.setToolTip("Move to Next Stitch (Space)")
        self.btn_next_stitch.clicked.connect(self.nextStitchClicked.emit)
        self.addWidget(self.btn_next_stitch)
        
        self.btn_next_row = QPushButton("Row +")
        self.btn_next_row.setToolTip("Move Cursor to Next Row")
        self.btn_next_row.clicked.connect(self.nextRowClicked.emit)
        self.addWidget(self.btn_next_row)
        
        self.addSeparator()
        
        # 6. Crochet settings
        self.addWidget(QLabel("Crochet Order:"))
        self.dir_combo = QComboBox()
        self.dir_combo.addItems(["L2R", "R2L", "Snake"])
        self.dir_combo.setCurrentIndex(2) # Default Snake
        self.dir_combo.currentTextChanged.connect(self.directionModeChanged.emit)
        self.addWidget(self.dir_combo)
        
        self.chk_reverse = QCheckBox("Reverse")
        self.chk_reverse.setToolTip("Reverse movement flow")
        self.chk_reverse.setChecked(False)
        self.chk_reverse.toggled.connect(self.reverseDirectionToggled.emit)
        self.addWidget(self.chk_reverse)
        
        self.addSeparator()
        
        # 7. Style preferences
        self.addWidget(QLabel("Progress Style:"))
        self.style_combo = QComboBox()
        self.style_combo.addItems(["Darkened", "Semi-Transparent", "Crossed Out", "Horizontal Line"])
        self.style_combo.currentTextChanged.connect(self.on_style_changed)
        self.addWidget(self.style_combo)
        
        self.btn_progress_line_color = QPushButton("Line Color...")
        self.btn_progress_line_color.setToolTip("Change the color of the cross or horizontal progress line")
        self.btn_progress_line_color.clicked.connect(self.open_progress_line_color_dialog)
        self.addWidget(self.btn_progress_line_color)
        
        # Show default red color preview on button
        pixmap = QPixmap(10, 10)
        pixmap.fill(QColor("#ff0000"))
        self.btn_progress_line_color.setIcon(QIcon(pixmap))
        
        self.addSeparator()
        
        # 8. Grid Details
        self.addWidget(QLabel("Grid Thickness:"))
        self.thickness_combo = QComboBox()
        self.thickness_combo.addItems(["Thin", "Medium", "Thick"])
        self.thickness_combo.currentTextChanged.connect(self.gridThicknessChanged.emit)
        self.addWidget(self.thickness_combo)
        
        self.btn_grid_color = QPushButton("Color...")
        self.btn_grid_color.setToolTip("Change Grid Color")
        self.btn_grid_color.clicked.connect(self.open_grid_color_dialog)
        self.addWidget(self.btn_grid_color)
        
        # Add Spacer to push collapsible panel button to the far right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.addWidget(spacer)
        
        # 9. Sidebar toggle button
        self.btn_sidebar = QPushButton("Toggle Sidebar")
        self.btn_sidebar.setToolTip("Collapse/Expand Palette & Notes Sidebar")
        self.btn_sidebar.clicked.connect(self.toggleSidebarClicked.emit)
        self.addWidget(self.btn_sidebar)

    def on_style_changed(self, text):
        # Convert to key code
        style_key = text.lower().replace(" ", "_").replace("-", "_")
        self.completionStyleChanged.emit(style_key)

    def open_grid_color_dialog(self):
        # Open standard dialog
        color = QColorDialog.getColor(QColor("#444444"), self, "Select Grid Color")
        if color.isValid():
            self.gridColorChanged.emit(color)
            
            # Show color preview on the button border or icon
            pixmap = QPixmap(10, 10)
            pixmap.fill(color)
            self.btn_grid_color.setIcon(QIcon(pixmap))

    def open_progress_line_color_dialog(self):
        color = QColorDialog.getColor(QColor(self.parent().project.progress_line_color if self.parent() and self.parent().project else "#ff0000"), self, "Select Progress Line Color")
        if color.isValid():
            self.progressLineColorChanged.emit(color)
            pixmap = QPixmap(10, 10)
            pixmap.fill(color)
            self.btn_progress_line_color.setIcon(QIcon(pixmap))

    def update_zoom_ui(self, factor):
        """Updates the zoom combobox based on canvas factor changes."""
        val = factor * 100.0
        if val == int(val):
            pct_str = f"{int(val)}%"
        else:
            pct_str = f"{val:.2f}%".rstrip('0').rstrip('.') + "%"
        idx = self.zoom_combo.findText(pct_str)
        if idx >= 0:
            # Block signals temporarily to prevent loop
            self.zoom_combo.blockSignals(True)
            self.zoom_combo.setCurrentIndex(idx)
            self.zoom_combo.blockSignals(False)
