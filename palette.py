from PySide6.QtWidgets import (QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, 
                             QTreeWidget, QTreeWidgetItem, QLabel, QLineEdit, 
                             QDialog, QDialogButtonBox, QPushButton, QListWidget,
                             QTextEdit, QSplitter, QInputDialog, QMessageBox,
                             QColorDialog)
from PySide6.QtCore import Qt, QSize, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QImage, QPixmap
from utils import RenameColorCommand, ToggleBookmarkCommand, UpdateNoteCommand, ReplaceColorCommand
from collections import Counter

class ColorEditDialog(QDialog):
    def __init__(self, color_hex, name, symbol, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Color Name & Symbol")
        self.setMinimumWidth(300)
        
        layout = QVBoxLayout(self)
        
        # Color Preview
        preview_layout = QHBoxLayout()
        color_preview = QWidget()
        color_preview.setFixedSize(40, 25)
        color_preview.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #555; border-radius: 3px;")
        preview_layout.addWidget(color_preview)
        preview_layout.addWidget(QLabel(f"Color: {color_hex}"))
        preview_layout.addStretch()
        layout.addLayout(preview_layout)
        
        # Name Input
        self.name_edit = QLineEdit(name)
        layout.addWidget(QLabel("Full Color Name:"))
        layout.addWidget(self.name_edit)
        
        # Symbol Input
        self.symbol_edit = QLineEdit(symbol)
        self.symbol_edit.setMaxLength(4)  # keep symbol short for grid rendering
        layout.addWidget(QLabel("Symbol Abbreviation (Max 4 chars):"))
        layout.addWidget(self.symbol_edit)
        
        # OK / Cancel
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        return self.name_edit.text().strip(), self.symbol_edit.text().strip()


class MinimapWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = None
        self.project = None
        self.cached_image = None
        self.dragging = False
        
        # Stylistic properties
        self.setMinimumHeight(150)
        self.setMaximumHeight(220)
        self.setStyleSheet("background-color: #181818; border: 1px solid #333; border-radius: 4px;")

    def set_canvas_and_project(self, canvas, project):
        self.canvas = canvas
        self.project = project
        self.cached_image = None
        if project:
            self.build_cached_image()
        self.update()

    def build_cached_image(self):
        # Create a QImage representation of the pattern
        W = self.project.width
        H = self.project.height
        self.cached_image = QImage(W, H, QImage.Format_RGB32)
        for r in range(H):
            for c in range(W):
                # Map row 0 (bottom row) to image bottom (y = H - 1)
                y_img = H - 1 - r
                rgb = self.project.pixels[r][c]
                self.cached_image.setPixel(c, y_img, QColor(*rgb).rgb())

    def get_scaled_rect(self):
        # Get aspect ratio-fit rect of the pattern inside this widget
        if not self.project:
            return QRectF()
            
        w_avail = self.width() - 8
        h_avail = self.height() - 8
        if w_avail <= 0 or h_avail <= 0:
            return QRectF()
            
        pat_w = self.project.width
        pat_h = self.project.height
        
        scale = min(w_avail / pat_w, h_avail / pat_h)
        w_scaled = pat_w * scale
        h_scaled = pat_h * scale
        
        x = (self.width() - w_scaled) / 2.0
        y = (self.height() - h_scaled) / 2.0
        
        return QRectF(x, y, w_scaled, h_scaled)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#181818"))
        
        if not self.project or not self.cached_image or not self.canvas:
            return
            
        rect_scaled = self.get_scaled_rect()
        if rect_scaled.width() <= 0 or rect_scaled.height() <= 0:
            return
            
        # Draw the cached pattern image
        painter.drawImage(rect_scaled, self.cached_image)
        
        # Calculate viewport bounds in grid coordinates
        cell_size = self.canvas.get_cell_size()
        W_view = self.canvas.width() - self.canvas.margin_left
        H_view = self.canvas.height() - self.canvas.margin_top
        
        pan_x = self.project.pan_offset[0]
        pan_y = self.project.pan_offset[1]
        
        col_left = -pan_x / cell_size
        col_right = (W_view - pan_x) / cell_size
        
        # Row 0 is at bottom, so lower y on screen means higher row index
        row_bottom = self.project.height - 1 - (self.canvas.height() - self.canvas.margin_top - pan_y) / cell_size
        row_top = self.project.height - 1 - (-pan_y) / cell_size
        
        # Clamp to pattern size
        col_left = max(0.0, min(self.project.width, col_left))
        col_right = max(0.0, min(self.project.width, col_right))
        row_bottom = max(0.0, min(self.project.height, row_bottom))
        row_top = max(0.0, min(self.project.height, row_top))
        
        # Map grid coords to minimap pixels
        scale_x = rect_scaled.width() / self.project.width
        scale_y = rect_scaled.height() / self.project.height
        
        vx = rect_scaled.x() + col_left * scale_x
        # row_top is the top row, so on minimap (where 0 is top) it's near the top
        vy = rect_scaled.y() + (self.project.height - row_top) * scale_y
        vw = (col_right - col_left) * scale_x
        vh = (row_top - row_bottom) * scale_y
        
        # Draw viewport box
        painter.setPen(QPen(QColor("#00f0ff"), 1.5, Qt.SolidLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRectF(vx, vy, vw, vh))

    def handle_mouse(self, pos):
        if not self.project or not self.canvas:
            return
            
        rect_scaled = self.get_scaled_rect()
        if rect_scaled.width() <= 0 or rect_scaled.height() <= 0:
            return
            
        # Check coordinates inside scaled pattern rect
        mx = pos.x() - rect_scaled.x()
        my = pos.y() - rect_scaled.y()
        
        # Convert to grid column & row
        scale_x = rect_scaled.width() / self.project.width
        scale_y = rect_scaled.height() / self.project.height
        
        c = mx / scale_x
        # y on minimap starts from top, so row index starts from H - 1 - y
        r = self.project.height - (my / scale_y)
        
        c = max(0.0, min(self.project.width - 1.0, c))
        r = max(0.0, min(self.project.height - 1.0, r))
        
        # Center canvas viewport on (r, c)
        cell_size = self.canvas.get_cell_size()
        W_view = self.canvas.width() - self.canvas.margin_left
        H_view = self.canvas.height() - self.canvas.margin_top
        
        center_x = self.canvas.margin_left + W_view / 2.0
        center_y = self.canvas.margin_top + H_view / 2.0
        
        self.project.pan_offset[0] = center_x - self.canvas.margin_left - c * cell_size
        self.project.pan_offset[1] = center_y - self.canvas.margin_top - (self.project.height - 1 - r) * cell_size
        
        self.project.dirty = True
        self.canvas.update()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.handle_mouse(event.position())

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.handle_mouse(event.position())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False


class PalettePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = None
        self.project = None
        self.undo_stack = None
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Tab Widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # 1. Colors Tab
        self.color_tab = QWidget()
        self.setup_color_tab()
        self.tabs.addTab(self.color_tab, "Palette")
        
        # 2. Row Stats Tab
        self.stats_tab = QWidget()
        self.setup_stats_tab()
        self.tabs.addTab(self.stats_tab, "Row Stats")
        
        # 3. Bookmarks & Notes Tab
        self.bookmarks_tab = QWidget()
        self.setup_bookmarks_tab()
        self.tabs.addTab(self.bookmarks_tab, "Bookmarks")
        
        # Minimap Section (Permanent at the bottom)
        minimap_box = QVBoxLayout()
        minimap_box.addWidget(QLabel("Minimap Overview:"))
        self.minimap = MinimapWidget()
        minimap_box.addWidget(self.minimap)
        layout.addLayout(minimap_box)

    def set_canvas_and_project(self, canvas, project, undo_stack):
        self.canvas = canvas
        self.project = project
        self.undo_stack = undo_stack
        
        self.minimap.set_canvas_and_project(canvas, project)
        
        self.refresh_palette()
        self.refresh_stats()
        self.refresh_bookmarks()

    # --- PALETTE TAB SETUP ---
    def setup_color_tab(self):
        tab_layout = QVBoxLayout(self.color_tab)
        tab_layout.setContentsMargins(2, 2, 2, 2)
        
        self.color_tree = QTreeWidget()
        self.color_tree.setHeaderLabels(["Color Details", "Stitches"])
        self.color_tree.setColumnCount(2)
        self.color_tree.setColumnWidth(0, 220)
        self.color_tree.doubleClicked.connect(self.edit_color_item)
        
        tab_layout.addWidget(self.color_tree)
        
        # Edit and Replace buttons
        btn_layout = QHBoxLayout()
        self.btn_edit_color = QPushButton("Rename Selected...")
        self.btn_edit_color.clicked.connect(self.edit_selected_color)
        btn_layout.addWidget(self.btn_edit_color)
        
        self.btn_replace_color = QPushButton("Replace Color...")
        self.btn_replace_color.setToolTip("Replace all pixels of this color with another color")
        self.btn_replace_color.clicked.connect(self.replace_selected_color)
        btn_layout.addWidget(self.btn_replace_color)
        
        tab_layout.addLayout(btn_layout)
        
        # Add and Delete buttons
        btn_layout_add_del = QHBoxLayout()
        self.btn_add_color = QPushButton("Add Color...")
        self.btn_add_color.setToolTip("Add a new color to the palette")
        self.btn_add_color.clicked.connect(self.add_new_color)
        btn_layout_add_del.addWidget(self.btn_add_color)
        
        self.btn_delete_color = QPushButton("Delete Color...")
        self.btn_delete_color.setToolTip("Remove a color from the palette (painted pixels turn to White empty stitches)")
        self.btn_delete_color.clicked.connect(self.delete_selected_color)
        btn_layout_add_del.addWidget(self.btn_delete_color)
        
        tab_layout.addLayout(btn_layout_add_del)

    def refresh_palette(self):
        self.color_tree.clear()
        if not self.project:
            return
            
        for hex_val, info in self.project.color_palette.items():
            item = QTreeWidgetItem(self.color_tree)
            
            # Colored Square in Col 0 (icon)
            pixmap = QPixmap(16, 16)
            pixmap.fill(QColor(hex_val))
            item.setIcon(0, pixmap)
            
            # Details in Col 0 (text)
            details = f"{info['symbol']} - {info['name']} ({hex_val})"
            item.setText(0, details)
            
            # Count in Col 1
            item.setText(1, f"{info['count']} sts")
            
            # Keep hex value stored in user role for retrieval
            item.setData(0, Qt.UserRole, hex_val)

    def edit_selected_color(self):
        selected = self.color_tree.currentItem()
        if selected:
            self.open_color_dialog(selected)

    def replace_selected_color(self):
        selected = self.color_tree.currentItem()
        if not selected:
            QMessageBox.warning(self, "Selection Error", "Please select a color in the palette to replace.")
            return
            
        old_hex = selected.data(0, Qt.UserRole)
        # Open color picker
        color = QColorDialog.getColor(QColor(old_hex), self, f"Select Replacement Color")
        if color.isValid():
            new_hex = color.name()
            new_rgb = (color.red(), color.green(), color.blue())
            
            # Confirm replacement
            reply = QMessageBox.question(
                self, "Confirm Replace Color",
                f"Are you sure you want to replace all occurrences of {old_hex} with {new_hex}?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                cmd = ReplaceColorCommand(
                    self.project,
                    old_hex,
                    new_hex,
                    new_rgb,
                    self.on_color_replaced
                )
                self.undo_stack.push(cmd)

    def on_color_replaced(self):
        self.refresh_palette()
        if self.canvas:
            # Rebuild minimap image since pixels changed!
            self.minimap.build_cached_image()
            self.canvas.update()
            self.minimap.update()
        self.refresh_stats()

    def selected_hex_color(self):
        item = self.color_tree.currentItem()
        if item:
            return item.data(0, Qt.UserRole)
        return None

    def add_new_color(self):
        if not self.project:
            return
            
        color = QColorDialog.getColor(Qt.white, self, "Select New Color to Add")
        if color.isValid():
            hex_color = color.name()
            if hex_color in self.project.color_palette:
                QMessageBox.warning(self, "Duplicate Color", "This color is already in the palette.")
                return
                
            # Find first unused symbol
            used_symbols = {info['symbol'] for info in self.project.color_palette.values()}
            symbol = None
            for sym in ["1","2","3","4","5","6","7","8","9","A","B","C","D","E","F","G","H","I","J","K","L","M","N","O","P","Q","R","S","T","U","V","W","X","Y","Z"]:
                if sym not in used_symbols:
                    symbol = sym
                    break
            if not symbol:
                symbol = "+"
                
            name = f"Color {len(self.project.color_palette) + 1}"
            
            from utils import AddColorCommand
            cmd = AddColorCommand(self.project, hex_color, name, symbol, self.on_color_added)
            self.undo_stack.push(cmd)

    def on_color_added(self):
        self.refresh_palette()
        self.refresh_stats()
        if self.canvas:
            self.canvas.update()

    def delete_selected_color(self):
        selected = self.color_tree.currentItem()
        if not selected:
            QMessageBox.warning(self, "Selection Error", "Please select a color in the palette to delete.")
            return
            
        hex_color = selected.data(0, Qt.UserRole)
        affected_count = self.project.color_palette[hex_color]['count']
        
        if affected_count > 0:
            reply = QMessageBox.question(
                self, "Confirm Delete Color",
                f"This color is used by {affected_count} stitches. Removing it will mark them as empty stitches (White). Do you want to proceed?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        else:
            reply = QMessageBox.question(
                self, "Confirm Delete Color",
                f"Are you sure you want to remove the unused color {hex_color} from the palette?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
                
        from utils import RemoveColorCommand
        cmd = RemoveColorCommand(self.project, hex_color, self.on_color_removed)
        self.undo_stack.push(cmd)

    def on_color_removed(self):
        self.refresh_palette()
        self.refresh_stats()
        if self.canvas:
            self.minimap.build_cached_image()
            self.canvas.update()
            self.minimap.update()

    def edit_color_item(self, model_index):
        item = self.color_tree.itemFromIndex(model_index)
        if item:
            self.open_color_dialog(item)

    def open_color_dialog(self, item):
        hex_color = item.data(0, Qt.UserRole)
        info = self.project.color_palette[hex_color]
        
        dlg = ColorEditDialog(hex_color, info['name'], info['symbol'], self)
        if dlg.exec() == QDialog.Accepted:
            new_name, new_symbol = dlg.get_values()
            if not new_name or not new_symbol:
                QMessageBox.warning(self, "Validation Error", "Name and Symbol cannot be empty.")
                return
                
            # Create rename color command on Undo stack
            cmd = RenameColorCommand(
                self.project,
                hex_color,
                info['name'],
                info['symbol'],
                new_name,
                new_symbol,
                self.on_color_renamed
            )
            self.undo_stack.push(cmd)

    def on_color_renamed(self):
        self.refresh_palette()
        if self.canvas:
            self.canvas.update()
        self.refresh_stats()  # row stats displays colors with symbols

    # --- ROW STATS TAB SETUP ---
    def setup_stats_tab(self):
        tab_layout = QVBoxLayout(self.stats_tab)
        tab_layout.setContentsMargins(5, 5, 5, 5)
        
        # Row Info Labels
        self.lbl_curr_row = QLabel("Current Row: -")
        self.lbl_curr_row.setStyleSheet("font-weight: bold; font-size: 11pt; color: #00adb5;")
        tab_layout.addWidget(self.lbl_curr_row)
        
        # Completed / Total Row Stitches
        self.lbl_row_progress = QLabel("Row Progress: -")
        tab_layout.addWidget(self.lbl_row_progress)
        
        # Color count lists
        tab_layout.addWidget(QLabel("Color Counts in Current Row:"))
        self.color_counts_list = QListWidget()
        self.color_counts_list.setFixedHeight(120)
        self.color_counts_list.setStyleSheet("background-color: #1a1a1a; border: 1px solid #333;")
        tab_layout.addWidget(self.color_counts_list)
        
        # Color crochet order sequence
        tab_layout.addWidget(QLabel("Stitch Color Sequence (in order of crochet):"))
        self.sequence_text = QTextEdit()
        self.sequence_text.setReadOnly(True)
        self.sequence_text.setStyleSheet("background-color: #1a1a1a; border: 1px solid #333; font-family: Consolas; font-size: 10pt;")
        tab_layout.addWidget(self.sequence_text)

    def refresh_stats(self):
        self.color_counts_list.clear()
        self.sequence_text.clear()
        
        if not self.project or not self.canvas:
            self.lbl_curr_row.setText("Current Row: -")
            self.lbl_row_progress.setText("Row Progress: -")
            return
            
        r, c = self.project.current_cursor
        W = self.project.width
        
        self.lbl_curr_row.setText(f"Current Row: {r + 1}")
        
        # Calculate completed stitches in current row
        row_completed = sum(1 for col in range(W) if (r, col) in self.project.completed_stitches)
        pct = (row_completed / W * 100) if W > 0 else 0
        self.lbl_row_progress.setText(f"Completed: {row_completed} / {W} ({pct:.1f}%) | Remaining: {W - row_completed}")
        
        # Get sequence of pixel hex values in traversal order
        direction = self.canvas.get_row_direction(r)
        if direction == 1:
            cols = list(range(W))
            dir_str = "→ (Left to Right)"
        else:
            cols = list(range(W - 1, -1, -1))
            dir_str = "← (Right to Left)"
            
        self.lbl_curr_row.setText(f"Current Row: {r + 1}  {dir_str}")
        
        row_hexes = [self.project.pixel_hexes[r][col] for col in cols]
        
        # Group color sequences (e.g. BK (4), DB (2)...) with exact column indices
        runs = []
        if cols:
            current_hex = self.project.pixel_hexes[r][cols[0]]
            color_info = self.project.color_palette.get(current_hex)
            current_sym = color_info['symbol'] if color_info else "?"
            current_cols = [cols[0]]
            
            for col in cols[1:]:
                h = self.project.pixel_hexes[r][col]
                if h == current_hex:
                    current_cols.append(col)
                else:
                    runs.append({
                        'hex': current_hex,
                        'symbol': current_sym,
                        'cols': current_cols
                    })
                    current_hex = h
                    color_info = self.project.color_palette.get(current_hex)
                    current_sym = color_info['symbol'] if color_info else "?"
                    current_cols = [col]
            # Add final group
            runs.append({
                'hex': current_hex,
                'symbol': current_sym,
                'cols': current_cols
            })
            
        # Build HTML checklist
        html_lines = []
        for run in runs:
            hex_val = run['hex']
            sym = run['symbol']
            run_cols = run['cols']
            total = len(run_cols)
            completed = sum(1 for col in run_cols if (r, col) in self.project.completed_stitches)
            is_completed = (completed == total)
            
            # Use html representation with swatch, checkbox, and status
            if is_completed:
                line = f"<span style='color: #666666; text-decoration: line-through;'>☑ <font color='{hex_val}'>■</font> {sym} ({total})</span>"
            else:
                prog_str = f"{completed}/{total}" if completed > 0 else f"{total}"
                line = f"<span style='color: #ffffff;'>☐ <font color='{hex_val}'>■</font> {sym} ({prog_str})</span>"
            html_lines.append(line)
            
        self.sequence_text.setHtml("<br>".join(html_lines))
        
        # Calculate color counts for row
        row_counts = Counter(row_hexes)
        for hex_val, count in row_counts.items():
            color_info = self.project.color_palette.get(hex_val)
            name = color_info['name'] if color_info else "Unknown"
            symbol = color_info['symbol'] if color_info else "?"
            
            # Create list item with color swatch icon
            pixmap = QPixmap(12, 12)
            pixmap.fill(QColor(hex_val))
            
            from PySide6.QtGui import QIcon
            icon = QIcon(pixmap)
            
            from PySide6.QtWidgets import QListWidgetItem
            item = QListWidgetItem(f"{name} ({symbol}): {count} stitches")
            item.setIcon(icon)
            self.color_counts_list.addItem(item)

    # --- BOOKMARKS & NOTES TAB SETUP ---
    def setup_bookmarks_tab(self):
        tab_layout = QVBoxLayout(self.bookmarks_tab)
        tab_layout.setContentsMargins(5, 5, 5, 5)
        
        # Row bookmark buttons
        btn_layout = QHBoxLayout()
        self.btn_toggle_bookmark = QPushButton("Toggle Bookmark")
        self.btn_toggle_bookmark.clicked.connect(self.toggle_row_bookmark)
        btn_layout.addWidget(self.btn_toggle_bookmark)
        tab_layout.addLayout(btn_layout)
        
        # Search / Go To row & col buttons
        search_layout = QHBoxLayout()
        self.btn_go_row = QPushButton("Go to Row...")
        self.btn_go_row.clicked.connect(self.go_to_row_prompt)
        self.btn_go_col = QPushButton("Go to Column...")
        self.btn_go_col.clicked.connect(self.go_to_col_prompt)
        search_layout.addWidget(self.btn_go_row)
        search_layout.addWidget(self.btn_go_col)
        tab_layout.addLayout(search_layout)
        
        tab_layout.addWidget(QLabel("Bookmarked Rows (Click to jump):"))
        self.bookmarks_list = QListWidget()
        self.bookmarks_list.setStyleSheet("background-color: #1a1a1a; border: 1px solid #333;")
        self.bookmarks_list.itemClicked.connect(self.jump_to_bookmark)
        tab_layout.addWidget(self.bookmarks_list)
        
        tab_layout.addWidget(QLabel("Row Note (attached to cursor row):"))
        self.note_edit = QTextEdit()
        self.note_edit.setStyleSheet("background-color: #1a1a1a; border: 1px solid #333;")
        self.note_edit.placeholderText = "Type row instructions here... Saved on Focus Out"
        self.note_edit.focusOutEvent = self.save_row_note_focus_out
        tab_layout.addWidget(self.note_edit)
        
        self.btn_save_note = QPushButton("Save Note")
        self.btn_save_note.clicked.connect(self.save_row_note)
        tab_layout.addWidget(self.btn_save_note)

    def refresh_bookmarks(self):
        self.bookmarks_list.clear()
        if not self.project:
            self.note_edit.clear()
            return
            
        # Populate bookmarks
        for row in sorted(self.project.bookmarks):
            self.bookmarks_list.addItem(f"Row {row + 1}")
            
        # Populate note for current row
        r, _ = self.project.current_cursor
        note = self.project.notes.get(r, "")
        self.note_edit.setText(note)

    def toggle_row_bookmark(self):
        if not self.project:
            return
        r, _ = self.project.current_cursor
        cmd = ToggleBookmarkCommand(self.project, r, self.on_bookmark_toggled)
        self.undo_stack.push(cmd)

    def on_bookmark_toggled(self):
        self.refresh_bookmarks()
        if self.canvas:
            self.canvas.update()

    def jump_to_bookmark(self, item):
        if not self.project or not self.canvas:
            return
        row_str = item.text().replace("Row ", "")
        row = int(row_str) - 1
        
        # Move cursor to that row
        self.canvas.move_cursor_to(row, 0)
        self.canvas.zoom_fit() # or center viewport
        
        # Center viewport on this row
        cell_size = self.canvas.get_cell_size()
        H_view = self.canvas.height() - self.canvas.margin_top
        center_y = self.canvas.margin_top + H_view / 2.0
        
        self.project.pan_offset[1] = center_y - self.canvas.margin_top - (self.project.height - 1 - row) * cell_size
        self.canvas.update()
        self.minimap.update()

    def save_row_note(self):
        if not self.project:
            return
        r, _ = self.project.current_cursor
        old_note = self.project.notes.get(r, "")
        new_note = self.note_edit.toPlainText().strip()
        
        if old_note != new_note:
            cmd = UpdateNoteCommand(self.project, r, old_note, new_note, self.on_note_updated)
            self.undo_stack.push(cmd)

    def save_row_note_focus_out(self, event):
        # Call base focus out
        QTextEdit.focusOutEvent(self.note_edit, event)
        self.save_row_note()

    def on_note_updated(self):
        self.refresh_bookmarks()
        if self.canvas:
            self.canvas.update()

    def go_to_row_prompt(self):
        if not self.project or not self.canvas:
            return
        row, ok = QInputDialog.getInt(
            self, "Go to Row", f"Enter Row (1 - {self.project.height}):",
            self.project.current_cursor[0] + 1, 1, self.project.height
        )
        if ok:
            row_idx = row - 1
            self.canvas.move_cursor_to(row_idx, self.project.current_cursor[1])
            self.center_canvas_on_cursor(row_idx, self.project.current_cursor[1])

    def go_to_col_prompt(self):
        if not self.project or not self.canvas:
            return
        col, ok = QInputDialog.getInt(
            self, "Go to Column", f"Enter Column (1 - {self.project.width}):",
            self.project.current_cursor[1] + 1, 1, self.project.width
        )
        if ok:
            col_idx = col - 1
            self.canvas.move_cursor_to(self.project.current_cursor[0], col_idx)
            self.center_canvas_on_cursor(self.project.current_cursor[0], col_idx)

    def center_canvas_on_cursor(self, r, c):
        cell_size = self.canvas.get_cell_size()
        W_view = self.canvas.width() - self.canvas.margin_left
        H_view = self.canvas.height() - self.canvas.margin_top
        
        center_x = self.canvas.margin_left + W_view / 2.0
        center_y = self.canvas.margin_top + H_view / 2.0
        
        self.project.pan_offset[0] = center_x - self.canvas.margin_left - c * cell_size
        self.project.pan_offset[1] = center_y - self.canvas.margin_top - (self.project.height - 1 - r) * cell_size
        self.canvas.update()
        self.minimap.update()
