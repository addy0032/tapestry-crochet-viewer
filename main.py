import sys
import os
import json
from PySide6.QtWidgets import (QApplication, QMainWindow, QFileDialog, QMessageBox, 
                             QProgressDialog, QSplitter, QWidget, QVBoxLayout, 
                             QMenu)
from PySide6.QtCore import Qt, QTimer, QSettings, QCoreApplication, QRect, QPoint
from PySide6.QtGui import QAction, QIcon, QPainter, QColor, QFont, QPen, QBrush, QImage, QUndoStack, QPixmap

from project import Project
from canvas import Canvas
from palette import PalettePanel
from toolbar import CrochetToolbar
from statusbar import CrochetStatusBar
from utils import ToggleStitchCommand

# Metadata helper database for linking PNG files to JSON projects
def get_companion_metadata_path():
    return os.path.join(os.path.expanduser("~"), ".crochet_companion_metadata.json")

def get_companion_project_path(image_path):
    path = get_companion_metadata_path()
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                mappings = json.load(f)
                return mappings.get(os.path.abspath(image_path))
        except Exception:
            pass
    return None

def save_companion_project_mapping(image_path, project_path):
    path = get_companion_metadata_path()
    mappings = {}
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                mappings = json.load(f)
        except Exception:
            pass
    mappings[os.path.abspath(image_path)] = os.path.abspath(project_path)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(mappings, f, indent=4)
    except Exception as e:
        print("Error saving companion metadata mapping:", e)

class CrochetMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Crochet Companion")
        self.resize(1280, 800)
        
        # Initialize Settings and Undo Stack
        self.settings = QSettings("Antigravity", "CrochetCompanion")
        self.undo_stack = QUndoStack(self)
        
        # Initialize empty project
        self.project = None
        
        # Setup UI components
        self.init_ui()
        self.setup_menu()
        self.setup_shortcuts()
        self.setup_autosave()
        self.update_recent_menu()
        
        # Disable controls initially
        self.set_controls_enabled(False)

    def init_ui(self):
        # 1. Toolbar
        self.toolbar = CrochetToolbar(self)
        self.addToolBar(self.toolbar)
        
        # Connect toolbar signals
        self.toolbar.openClicked.connect(self.open_image_dialog)
        self.toolbar.saveClicked.connect(self.save_project)
        self.toolbar.exportClicked.connect(self.export_png_dialog)
        self.toolbar.undoClicked.connect(self.undo_stack.undo)
        self.toolbar.redoClicked.connect(self.undo_stack.redo)
        self.toolbar.zoomFitClicked.connect(self.zoom_fit)
        self.toolbar.toggleSidebarClicked.connect(self.toggle_sidebar)
        self.toolbar.toolModeChanged.connect(self.on_tool_mode_changed)
        
        self.toolbar.gridToggled.connect(self.on_grid_toggled)
        self.toolbar.gridThicknessChanged.connect(self.on_grid_thickness_changed)
        self.toolbar.gridColorChanged.connect(self.on_grid_color_changed)
        self.toolbar.symbolsToggled.connect(self.on_symbols_toggled)
        self.toolbar.rowHighlightToggled.connect(self.on_row_highlight_toggled)
        self.toolbar.colHighlightToggled.connect(self.on_col_highlight_toggled)
        
        self.toolbar.prevStitchClicked.connect(self.on_prev_stitch)
        self.toolbar.nextStitchClicked.connect(self.on_next_stitch)
        self.toolbar.prevRowClicked.connect(self.on_prev_row)
        self.toolbar.nextRowClicked.connect(self.on_next_row)
        self.toolbar.directionModeChanged.connect(self.on_direction_mode_changed)
        self.toolbar.reverseDirectionToggled.connect(self.on_reverse_direction_toggled)
        self.toolbar.completionStyleChanged.connect(self.on_completion_style_changed)
        self.toolbar.progressLineColorChanged.connect(self.on_progress_line_color_changed)
        
        # Toolbar zoom preset changes
        self.toolbar.zoom_combo.currentTextChanged.connect(self.on_zoom_combo_changed)
        
        # 2. Central Splitter (Collapsible sidebar + Canvas)
        self.splitter = QSplitter(Qt.Horizontal, self)
        
        self.palette_panel = PalettePanel(self.splitter)
        self.canvas = Canvas(self.splitter)
        
        self.splitter.addWidget(self.palette_panel)
        self.splitter.addWidget(self.canvas)
        self.splitter.setSizes([340, 940])  # default ratio
        self.setCentralWidget(self.splitter)
        
        # Connect canvas signals
        self.canvas.cursorChanged.connect(self.on_canvas_cursor_changed)
        self.canvas.hoverChanged.connect(self.on_canvas_hover_changed)
        self.canvas.zoomChanged.connect(self.on_canvas_zoom_changed)
        self.canvas.progressChanged.connect(self.on_canvas_progress_changed)
        self.canvas.paletteChanged.connect(self.on_canvas_palette_changed)
        self.canvas.active_paint_color_callback = self.get_active_paint_color
        
        # Connect Undo Stack changes to refresh Undo/Redo buttons
        self.undo_stack.canUndoChanged.connect(self.toolbar.btn_undo.setEnabled)
        self.undo_stack.canRedoChanged.connect(self.toolbar.btn_redo.setEnabled)
        self.toolbar.btn_undo.setEnabled(False)
        self.toolbar.btn_redo.setEnabled(False)

        # 3. Status Bar
        self.statusbar = CrochetStatusBar(self)
        self.setStatusBar(self.statusbar)

    def setup_menu(self):
        menubar = self.menuBar()
        
        # File Menu
        self.file_menu = menubar.addMenu("&File")
        
        open_action = QAction("&Open Image...", self, shortcut="Ctrl+O", triggered=self.open_image_dialog)
        self.file_menu.addAction(open_action)
        
        load_proj_action = QAction("&Load Project...", self, shortcut="Ctrl+L", triggered=self.load_project_dialog)
        self.file_menu.addAction(load_proj_action)
        
        self.save_action = QAction("&Save Project", self, shortcut="Ctrl+S", triggered=self.save_project)
        self.file_menu.addAction(self.save_action)
        
        self.save_as_action = QAction("Save Project &As...", self, shortcut="Ctrl+Shift+S", triggered=self.save_project_as)
        self.file_menu.addAction(self.save_as_action)
        
        self.export_action = QAction("&Export PNG...", self, triggered=self.export_png_dialog)
        self.file_menu.addAction(self.export_action)
        
        # Recent Files submenu
        self.recent_menu = QMenu("Recent Files", self)
        self.file_menu.addMenu(self.recent_menu)
        
        self.file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self, triggered=self.close)
        self.file_menu.addAction(exit_action)
        
        # Edit Menu
        self.edit_menu = menubar.addMenu("&Edit")
        self.undo_action = QAction("&Undo", self, shortcut="Ctrl+Z", triggered=self.undo_stack.undo)
        self.redo_action = QAction("&Redo", self, shortcut="Ctrl+Y", triggered=self.undo_stack.redo)
        self.edit_menu.addAction(self.undo_action)
        self.edit_menu.addAction(self.redo_action)
        
        self.edit_menu.addSeparator()
        
        from PySide6.QtWidgets import QInputDialog
        self.go_row_action = QAction("Go to Row...", self, shortcut="Ctrl+G", triggered=self.go_to_row)
        self.go_col_action = QAction("Go to Column...", self, shortcut="Ctrl+Shift+G", triggered=self.go_to_column)
        self.edit_menu.addAction(self.go_row_action)
        self.edit_menu.addAction(self.go_col_action)
        
        # View Menu
        self.view_menu = menubar.addMenu("&View")
        self.ruler_four_sides_action = QAction("Right & Bottom Rulers", self, checkable=True, triggered=self.on_ruler_four_sides_toggled)
        self.view_menu.addAction(self.ruler_four_sides_action)
        
        self.edit_menu.addSeparator()
        
        self.toggle_row_action = QAction("Toggle Row Done", self, shortcut="Shift+R", triggered=self.toggle_current_row_done)
        self.reset_progress_action = QAction("Reset All Progress...", self, triggered=self.reset_all_progress)
        self.edit_menu.addAction(self.toggle_row_action)
        self.edit_menu.addAction(self.reset_progress_action)

    def setup_shortcuts(self):
        # Keyboard shortcuts not handled directly by canvas key events
        
        # Grid Toggle: G
        action_grid = QAction(self)
        action_grid.setShortcut("G")
        action_grid.triggered.connect(lambda: self.toolbar.chk_grid.toggle())
        self.addAction(action_grid)
        
        # Symbols Toggle: T
        action_sym = QAction(self)
        action_sym.setShortcut("T")
        action_sym.triggered.connect(lambda: self.toolbar.chk_symbols.toggle())
        self.addAction(action_sym)
        
        # Row Highlight Toggle: R
        action_row_h = QAction(self)
        action_row_h.setShortcut("R")
        action_row_h.triggered.connect(lambda: self.toolbar.chk_row_highlight.toggle())
        self.addAction(action_row_h)
        
        # Zoom In: *
        action_zoom_in = QAction(self)
        action_zoom_in.setShortcut("*")
        action_zoom_in.triggered.connect(self.zoom_in)
        self.addAction(action_zoom_in)
        
        # Zoom Out: -
        action_zoom_out = QAction(self)
        action_zoom_out.setShortcut("-")
        action_zoom_out.triggered.connect(self.zoom_out)
        self.addAction(action_zoom_out)
        
        # Fit Window: 0
        action_fit = QAction(self)
        action_fit.setShortcut("0")
        action_fit.triggered.connect(self.zoom_fit)
        self.addAction(action_fit)
        
        # Fullscreen: F
        action_fullscreen = QAction(self)
        action_fullscreen.setShortcut("F")
        action_fullscreen.triggered.connect(self.toggle_fullscreen)
        self.addAction(action_fullscreen)

    def setup_autosave(self):
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(30000)  # 30 seconds
        self.autosave_timer.timeout.connect(self.perform_autosave)
        self.autosave_timer.start()

    def set_controls_enabled(self, enabled):
        self.palette_panel.setEnabled(enabled)
        self.canvas.setEnabled(enabled)
        self.toolbar.btn_save.setEnabled(enabled)
        self.toolbar.btn_export.setEnabled(enabled)
        self.toolbar.zoom_combo.setEnabled(enabled)
        self.toolbar.btn_fit.setEnabled(enabled)
        self.toolbar.chk_grid.setEnabled(enabled)
        self.toolbar.chk_symbols.setEnabled(enabled)
        self.toolbar.chk_row_highlight.setEnabled(enabled)
        self.toolbar.chk_col_highlight.setEnabled(enabled)
        self.toolbar.btn_prev_row.setEnabled(enabled)
        self.toolbar.btn_prev_stitch.setEnabled(enabled)
        self.toolbar.btn_next_stitch.setEnabled(enabled)
        self.toolbar.btn_next_row.setEnabled(enabled)
        self.toolbar.dir_combo.setEnabled(enabled)
        self.toolbar.chk_reverse.setEnabled(enabled)
        self.toolbar.style_combo.setEnabled(enabled)
        self.toolbar.thickness_combo.setEnabled(enabled)
        self.toolbar.btn_grid_color.setEnabled(enabled)
        
        self.save_action.setEnabled(enabled)
        self.save_as_action.setEnabled(enabled)
        self.export_action.setEnabled(enabled)
        self.go_row_action.setEnabled(enabled)
        self.go_col_action.setEnabled(enabled)
        self.ruler_four_sides_action.setEnabled(enabled)
        self.toggle_row_action.setEnabled(enabled)
        self.reset_progress_action.setEnabled(enabled)
        self.toolbar.btn_progress_line_color.setEnabled(enabled)

    # --- File Operations ---
    def open_image_dialog(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open Crochet Chart Image", "", 
            "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        if filepath:
            self.load_image(filepath)

    def load_image(self, filepath):
        filepath = os.path.abspath(filepath)
        
        # 1. Check if there is an existing JSON project mapped for this image
        mapped_json = get_companion_project_path(filepath)
        if mapped_json and os.path.exists(mapped_json):
            self.load_project(mapped_json)
            self.statusBar().showMessage("Restored existing project data for this image.", 3000)
            return

        # 2. Check if a JSON file exists next to the image on disk
        default_json = os.path.splitext(filepath)[0] + ".json"
        if os.path.exists(default_json):
            self.load_project(default_json)
            save_companion_project_mapping(filepath, default_json)
            self.statusBar().showMessage("Restored companion project from disk.", 3000)
            return

        # 3. Create a fresh project for the image
        self.undo_stack.clear()
        self.project = Project()
        try:
            self.project.load_image(filepath)
            
            # Auto-assign JSON filepath and save it immediately
            self.project.filepath = default_json
            self.project.save_project(default_json)
            save_companion_project_mapping(filepath, default_json)
            
            # Setup Canvas & Sidebar Panel
            self.canvas.set_project(self.project, self.undo_stack)
            self.palette_panel.set_canvas_and_project(self.canvas, self.project, self.undo_stack)
            self.statusbar.set_project(self.project)
            
            self.set_controls_enabled(True)
            self.ruler_four_sides_action.setChecked(False)
            self.canvas.zoom_fit()
            self.add_recent_file(filepath)
            self.canvas.setFocus()
            self.statusBar().showMessage("Created new project JSON next to image.", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load image:\n{str(e)}")

    def save_project(self):
        if not self.project:
            return
        if self.project.filepath:
            try:
                self.project.save_project(self.project.filepath)
                save_companion_project_mapping(self.project.image_path, self.project.filepath)
                self.statusBar().showMessage(f"Project saved to {os.path.basename(self.project.filepath)}", 2000)
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save project:\n{str(e)}")
        else:
            self.save_project_as()

    def save_project_as(self):
        if not self.project:
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Crochet Companion Project As", "", 
            "Crochet Companion Project (*.json)"
        )
        if filepath:
            try:
                self.project.save_project(filepath)
                save_companion_project_mapping(self.project.image_path, filepath)
                self.add_recent_file(filepath)
                self.statusBar().showMessage(f"Project saved to {os.path.basename(filepath)}", 2000)
                QMessageBox.information(self, "Success", f"Project saved successfully to:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save project:\n{str(e)}")

    def load_project_dialog(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Crochet Companion Project", "", 
            "Crochet Companion Project (*.json)"
        )
        if filepath:
            self.load_project(filepath)

    def load_project(self, filepath):
        self.undo_stack.clear()
        self.project = Project()
        try:
            self.project.load_project(filepath)
            
            # Sync Canvas, Toolbar, and Sidebar
            self.canvas.set_project(self.project, self.undo_stack)
            
            # Restore view coordinates
            self.canvas.zoom_index = self.canvas.ZOOM_LEVELS.index(self.project.zoom_factor)
            
            # Sync toolbar checks
            self.toolbar.chk_grid.setChecked(self.project.grid_enabled)
            self.toolbar.chk_symbols.setChecked(self.project.symbols_enabled)
            self.toolbar.chk_row_highlight.setChecked(self.project.row_highlight_enabled)
            self.toolbar.chk_col_highlight.setChecked(self.project.col_highlight_enabled)
            self.toolbar.chk_reverse.setChecked(self.project.reverse_direction)
            self.toolbar.dir_combo.setCurrentText(self.project.direction_mode)
            
            # Style combo setting
            style_name = self.project.completion_style.replace("_", " ").title()
            self.toolbar.style_combo.setCurrentText(style_name)
            
            if hasattr(self.project, 'progress_line_color'):
                color = QColor(self.project.progress_line_color)
                pixmap = QPixmap(10, 10)
                pixmap.fill(color)
                self.toolbar.btn_progress_line_color.setIcon(QIcon(pixmap))
            
            self.toolbar.thickness_combo.setCurrentText(self.project.grid_thickness.title())
            self.toolbar.update_zoom_ui(self.project.zoom_factor)
            
            self.palette_panel.set_canvas_and_project(self.canvas, self.project, self.undo_stack)
            self.statusbar.set_project(self.project)
            self.statusbar.update_zoom(self.project.zoom_factor)
            
            self.set_controls_enabled(True)
            self.ruler_four_sides_action.setChecked(self.project.ruler_four_sides_enabled)
            save_companion_project_mapping(self.project.image_path, filepath)
            
            # Add to recent
            self.add_recent_file(filepath)
            
            self.canvas.update()
            self.canvas.setFocus()
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load project:\n{str(e)}")

    def perform_autosave(self):
        if not self.project or not self.project.dirty:
            return
            
        if self.project.filepath:
            try:
                self.project.save_project(self.project.filepath)
                self.statusBar().showMessage("Project autosaved.", 2000)
            except Exception:
                pass
        elif self.project.image_path:
            # Save companion backup JSON next to image
            try:
                base, _ = os.path.splitext(self.project.image_path)
                backup_path = base + ".companion.json"
                self.project.save_project(backup_path)
                self.statusBar().showMessage("Backup autosaved.", 2000)
            except Exception:
                pass

    # --- Export PNG with Progress ---
    def export_png_dialog(self):
        if not self.project:
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Chart as PNG", "", 
            "PNG Image (*.png)"
        )
        if filepath:
            self.export_png(filepath)

    def export_png(self, filepath):
        W = self.project.width
        H = self.project.height
        cell_size = 20  # fixed cell size for clean high-res export
        margin_left = 60
        margin_top = 40
        
        img_w = margin_left + W * cell_size + 20
        img_h = margin_top + H * cell_size + 20
        
        # Setup Progress Dialog
        progress = QProgressDialog("Generating Export Image...", "Cancel", 0, H, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(200)
        progress.setValue(0)
        
        # Initialize Canvas Image
        export_img = QImage(img_w, img_h, QImage.Format_RGB32)
        painter = QPainter(export_img)
        painter.fillRect(QRect(0, 0, img_w, img_h), QColor("#121212"))
        
        # Paint grid row by row to support progress updates
        for r in range(H):
            if progress.wasCanceled():
                painter.end()
                return
                
            y = margin_top + (H - 1 - r) * cell_size
            for c in range(W):
                x = margin_left + c * cell_size
                hex_color = self.project.pixel_hexes[r][c]
                rect = QRect(x, y, cell_size, cell_size)
                
                # Draw stitch color
                painter.fillRect(rect, QColor(hex_color))
                
                # Draw completion overlay if applicable
                is_completed = (r, c) in self.project.completed_stitches
                if is_completed:
                    if self.project.completion_style == 'darkened':
                        painter.fillRect(rect, QColor(0, 0, 0, 130))
                    elif self.project.completion_style == 'transparent':
                        painter.fillRect(rect, QColor(20, 20, 20, 180))
                    elif self.project.completion_style == 'crossed_out':
                        line_color = QColor(self.project.progress_line_color if hasattr(self.project, 'progress_line_color') else "#ff0000")
                        painter.setPen(QPen(line_color, 2 if cell_size >= 16 else 1))
                        painter.drawLine(rect.topLeft(), rect.bottomRight())
                        painter.drawLine(rect.topRight(), rect.bottomLeft())
                    elif self.project.completion_style == 'horizontal_line':
                        line_color = QColor(self.project.progress_line_color if hasattr(self.project, 'progress_line_color') else "#ff0000")
                        painter.setPen(QPen(line_color, 2 if cell_size >= 16 else 1))
                        y_mid = rect.y() + rect.height() / 2.0
                        painter.drawLine(rect.left(), y_mid, rect.right(), y_mid)
                
                # Draw symbols if enabled
                if self.project.symbols_enabled:
                    color_info = self.project.color_palette.get(hex_color)
                    if color_info:
                        symbol = color_info['symbol']
                        from utils import get_contrast_color
                        text_color = QColor(get_contrast_color(color_info['rgb']))
                        if is_completed:
                            text_color.setAlpha(100)
                            
                        painter.setFont(QFont("Consolas", int(cell_size * 0.35)))
                        painter.setPen(text_color)
                        painter.drawText(rect, Qt.AlignCenter, symbol)
            
            progress.setValue(r + 1)
            QCoreApplication.processEvents()

        # Draw Grid Lines
        if self.project.grid_enabled:
            thickness = 1
            if self.project.grid_thickness == 'medium':
                thickness = 2
            elif self.project.grid_thickness == 'thick':
                thickness = 3
            painter.setPen(QPen(QColor(self.project.grid_color), thickness))
            
            # Vertical lines
            for c in range(W + 1):
                x = margin_left + c * cell_size
                painter.drawLine(x, margin_top, x, margin_top + H * cell_size)
            # Horizontal lines
            for r in range(H + 1):
                y = margin_top + r * cell_size
                painter.drawLine(margin_left, y, margin_left + W * cell_size, y)
                
        # Draw Rulers
        painter.setFont(QFont("Outfit", 9))
        painter.setPen(QColor("#aaaaaa"))
        
        # Top Ruler
        for c in range(W):
            if c % 10 == 0:
                x = margin_left + c * cell_size
                painter.drawLine(x, margin_top - 5, x, margin_top)
                painter.drawText(QRect(x - 20, 5, 40, margin_top - 10), Qt.AlignCenter, str(c))
                
        # Left Ruler
        for r in range(H):
            if r % 10 == 0:
                y = margin_top + (H - 1 - r) * cell_size
                painter.drawLine(margin_left - 5, y, margin_left, y)
                painter.drawText(QRect(5, y - 6, margin_left - 12, 12), Qt.AlignRight | Qt.AlignVCenter, str(r))
                
        painter.end()
        export_img.save(filepath)
        QMessageBox.information(self, "Success", "Pattern image exported successfully.")

    # --- Recent Files ---
    def add_recent_file(self, filepath):
        recent = self.settings.value("recent_files", [])
        if filepath in recent:
            recent.remove(filepath)
        recent.insert(0, filepath)
        recent = recent[:10]  # keep top 10
        self.settings.setValue("recent_files", recent)
        self.update_recent_menu()

    def update_recent_menu(self):
        self.recent_menu.clear()
        recent = self.settings.value("recent_files", [])
        if not recent:
            no_action = QAction("No Recent Files", self)
            no_action.setEnabled(False)
            self.recent_menu.addAction(no_action)
            return
            
        for path in recent:
            action = QAction(os.path.basename(path), self)
            action.setData(path)
            action.setToolTip(path)
            action.triggered.connect(self.open_recent_file)
            self.recent_menu.addAction(action)

    def open_recent_file(self):
        action = self.sender()
        if action:
            filepath = action.data()
            if os.path.exists(filepath):
                _, ext = os.path.splitext(filepath)
                if ext.lower() == '.json':
                    self.load_project(filepath)
                else:
                    self.load_image(filepath)
            else:
                QMessageBox.warning(self, "File Not Found", f"The file could not be found:\n{filepath}")
                # Remove from recent list
                recent = self.settings.value("recent_files", [])
                if filepath in recent:
                    recent.remove(filepath)
                    self.settings.setValue("recent_files", recent)
                    self.update_recent_menu()

    # --- UI Actions Connection ---
    def toggle_sidebar(self):
        is_visible = self.palette_panel.isVisible()
        self.palette_panel.setVisible(not is_visible)

    def zoom_in(self):
        self.canvas.set_zoom_index(self.canvas.zoom_index + 1)

    def zoom_out(self):
        self.canvas.set_zoom_index(self.canvas.zoom_index - 1)

    def zoom_fit(self):
        self.canvas.zoom_fit()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def go_to_row(self):
        if not self.project:
            return
        from PySide6.QtWidgets import QInputDialog
        row, ok = QInputDialog.getInt(
            self, "Go to Row", f"Enter Row (1 - {self.project.height}):",
            self.project.current_cursor[0] + 1, 1, self.project.height
        )
        if ok:
            row_idx = row - 1
            self.canvas.move_cursor_to(row_idx, self.project.current_cursor[1])
            self.center_canvas_on_cursor()

    def go_to_column(self):
        if not self.project:
            return
        from PySide6.QtWidgets import QInputDialog
        col, ok = QInputDialog.getInt(
            self, "Go to Column", f"Enter Column (1 - {self.project.width}):",
            self.project.current_cursor[1] + 1, 1, self.project.width
        )
        if ok:
            col_idx = col - 1
            self.canvas.move_cursor_to(self.project.current_cursor[0], col_idx)
            self.center_canvas_on_cursor()

    def center_canvas_on_cursor(self):
        if not self.project or not self.canvas:
            return
        r, c = self.project.current_cursor
        cell_size = self.canvas.get_cell_size()
        W_view = self.canvas.width() - self.canvas.margin_left
        H_view = self.canvas.height() - self.canvas.margin_top
        
        center_x = self.canvas.margin_left + W_view / 2.0
        center_y = self.canvas.margin_top + H_view / 2.0
        
        self.project.pan_offset[0] = center_x - self.canvas.margin_left - c * cell_size
        self.project.pan_offset[1] = center_y - self.canvas.margin_top - (self.project.height - 1 - r) * cell_size
        self.canvas.update()
        self.palette_panel.minimap.update()

    def toggle_current_row_done(self):
        if not self.project:
            return
        r = self.project.current_cursor[0]
        stitches = {(r, c) for c in range(self.project.width)}
        all_completed = all(s in self.project.completed_stitches for s in stitches)
        cmd = ToggleStitchCommand(self.project, stitches, not all_completed, self.canvas.update_view)
        self.undo_stack.push(cmd)

    def reset_all_progress(self):
        if not self.project or not self.project.completed_stitches:
            return
        reply = QMessageBox.question(
            self, "Reset All Progress",
            "Are you sure you want to reset all progress? This will mark all stitches as uncompleted.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            cmd = ToggleStitchCommand(
                self.project,
                list(self.project.completed_stitches),
                False,
                self.canvas.update_view
            )
            self.undo_stack.push(cmd)
            self.statusBar().showMessage("All progress reset.", 2000)

    def on_progress_line_color_changed(self, color):
        if self.project:
            self.project.progress_line_color = color.name()
            self.project.dirty = True
            self.canvas.update()

    def on_ruler_four_sides_toggled(self, checked):
        if self.project:
            self.project.ruler_four_sides_enabled = checked
            self.project.dirty = True
            self.canvas.update()

    # toolbar triggers
    def on_zoom_combo_changed(self, text):
        try:
            pct = float(text.replace("%", ""))
            factor = pct / 100.0
            if factor in self.canvas.ZOOM_LEVELS:
                idx = self.canvas.ZOOM_LEVELS.index(factor)
                self.canvas.set_zoom_index(idx)
        except ValueError:
            pass

    def on_grid_toggled(self, checked):
        if self.project:
            self.project.grid_enabled = checked
            self.project.dirty = True
            self.canvas.update()

    def on_grid_thickness_changed(self, text):
        if self.project:
            self.project.grid_thickness = text.lower()
            self.project.dirty = True
            self.canvas.update()

    def on_grid_color_changed(self, color):
        if self.project:
            self.project.grid_color = color.name()
            self.project.dirty = True
            self.canvas.update()

    def on_symbols_toggled(self, checked):
        if self.project:
            self.project.symbols_enabled = checked
            self.project.dirty = True
            self.canvas.update()

    def on_row_highlight_toggled(self, checked):
        if self.project:
            self.project.row_highlight_enabled = checked
            self.project.dirty = True
            self.canvas.update()

    def on_col_highlight_toggled(self, checked):
        if self.project:
            self.project.col_highlight_enabled = checked
            self.project.dirty = True
            self.canvas.update()

    def on_prev_stitch(self):
        self.canvas.advance_cursor(-1)

    def on_next_stitch(self):
        self.canvas.advance_cursor(1)

    def on_prev_row(self):
        if self.project:
            self.canvas.move_cursor_to(self.project.current_cursor[0] - 1, self.project.current_cursor[1])

    def on_next_row(self):
        if self.project:
            self.canvas.move_cursor_to(self.project.current_cursor[0] + 1, self.project.current_cursor[1])

    def on_direction_mode_changed(self, text):
        if self.project:
            self.project.direction_mode = text
            self.project.dirty = True
            self.palette_panel.refresh_stats()
            self.canvas.update()

    def on_reverse_direction_toggled(self, checked):
        if self.project:
            self.project.reverse_direction = checked
            self.project.dirty = True
            self.palette_panel.refresh_stats()
            self.canvas.update()

    def on_completion_style_changed(self, style_key):
        if self.project:
            self.project.completion_style = style_key
            self.project.dirty = True
            self.canvas.update()

    # --- Canvas Signals Connections ---
    def on_canvas_cursor_changed(self, row, col):
        self.statusbar.update_cursor(row, col)
        self.palette_panel.refresh_stats()
        self.palette_panel.refresh_bookmarks()

    def on_canvas_hover_changed(self, row, col, hex_val):
        self.statusbar.update_hover(row, col, hex_val)

    def on_canvas_zoom_changed(self, factor):
        self.statusbar.update_zoom(factor)
        self.toolbar.update_zoom_ui(factor)
        self.palette_panel.minimap.update()

    def on_canvas_progress_changed(self):
        self.statusbar.update_progress()
        self.palette_panel.refresh_stats()
        self.palette_panel.minimap.update()

    def keyPressEvent(self, event):
        focused = self.focusWidget()
        from PySide6.QtWidgets import QLineEdit, QTextEdit
        if isinstance(focused, (QLineEdit, QTextEdit)):
            super().keyPressEvent(event)
            return

        if event.key() == Qt.Key_Space:
            if self.canvas and self.project:
                self.canvas.keyPressEvent(event)
                event.accept()
                return

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        focused = self.focusWidget()
        from PySide6.QtWidgets import QLineEdit, QTextEdit
        if isinstance(focused, (QLineEdit, QTextEdit)):
            super().keyReleaseEvent(event)
            return

        if event.key() == Qt.Key_Space:
            if self.canvas and self.project:
                self.canvas.keyReleaseEvent(event)
                event.accept()
                return

        super().keyReleaseEvent(event)

    def on_tool_mode_changed(self, mode):
        self.canvas.tool_mode = mode
        self.statusBar().showMessage(f"Active Tool: {mode}", 2000)

    def get_active_paint_color(self):
        color = self.palette_panel.selected_hex_color()
        if not color and self.project and self.project.color_palette:
            color = list(self.project.color_palette.keys())[0]
        return color

    def on_canvas_palette_changed(self):
        self.palette_panel.refresh_palette()
        self.palette_panel.refresh_stats()
        self.palette_panel.minimap.build_cached_image()
        self.palette_panel.minimap.update()
        self.canvas.update()

    def closeEvent(self, event):
        if self.project and self.project.dirty:
            reply = QMessageBox.question(
                self, "Unsaved Changes", 
                "You have unsaved changes. Do you want to save before exiting?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            if reply == QMessageBox.Save:
                self.save_project_dialog()
                event.accept()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


# Clean dark-themed CSS stylesheet
DARK_THEME_STYLE = """
QMainWindow {
    background-color: #121212;
}
QMenuBar {
    background-color: #1a1a1a;
    color: #e0e0e0;
    border-bottom: 1px solid #2d2d2d;
}
QMenuBar::item:selected {
    background-color: #00adb5;
    color: #121212;
}
QMenu {
    background-color: #1a1a1a;
    color: #e0e0e0;
    border: 1px solid #2d2d2d;
}
QMenu::item {
    padding: 6px 60px 6px 25px; /* generous padding on the right to prevent shortcut overlap */
    background-color: transparent;
}
QMenu::item:selected {
    background-color: #00adb5;
    color: #121212;
}
QTabWidget::pane {
    border: 1px solid #2d2d2d;
    background-color: #1a1a1a;
}
QTabBar::tab {
    background-color: #252525;
    color: #aaaaaa;
    padding: 6px 12px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    border: 1px solid #2d2d2d;
    border-bottom: none;
}
QTabBar::tab:selected {
    background-color: #1a1a1a;
    color: #00adb5;
    border-color: #2d2d2d;
    font-weight: bold;
}
QTabBar::tab:hover:!selected {
    background-color: #2e2e2e;
    color: #ffffff;
}
QTreeWidget {
    background-color: #1a1a1a;
    color: #e0e0e0;
    border: 1px solid #2d2d2d;
    alternate-background-color: #222222;
}
QHeaderView::section {
    background-color: #2d2d2d;
    color: #e0e0e0;
    padding: 4px;
    border: 1px solid #1a1a1a;
}
QListWidget {
    background-color: #1a1a1a;
    color: #e0e0e0;
    border: 1px solid #2d2d2d;
}
QListWidget::item:hover {
    background-color: #282828;
}
QListWidget::item:selected {
    background-color: #00adb5;
    color: #121212;
}
QTextEdit, QLineEdit {
    background-color: #1a1a1a;
    color: #ffffff;
    border: 1px solid #2d2d2d;
    border-radius: 4px;
    padding: 4px;
}
QTextEdit:focus, QLineEdit:focus {
    border: 1px solid #00adb5;
}
QPushButton {
    background-color: #2d2d2d;
    color: #ffffff;
    border: 1px solid #444444;
    border-radius: 4px;
    padding: 5px 10px;
}
QPushButton:hover {
    background-color: #3d3d3d;
    border-color: #00adb5;
}
QPushButton:pressed {
    background-color: #00adb5;
    color: #121212;
}
QDialog {
    background-color: #1e1e1e;
    color: #ffffff;
}
QLabel {
    color: #e0e0e0;
}
QSplitter::handle {
    background-color: #252525;
}
QSplitter::handle:horizontal {
    width: 6px;
}
"""

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME_STYLE)
    
    # Set Outfit or Inter font if available, fallback to Segoe UI
    font = QFont("Outfit")
    if not font.exactMatch():
        font = QFont("Inter")
    if not font.exactMatch():
        font = QFont("Segoe UI", 9)
    app.setFont(font)
    
    window = CrochetMainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
