from PySide6.QtWidgets import QWidget, QColorDialog
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QCursor, QFontMetrics
from collections import defaultdict
import math
from utils import ToggleStitchCommand, get_contrast_color

class Canvas(QWidget):
    # Signals for updating UI panels
    cursorChanged = Signal(int, int)          # row, col
    hoverChanged = Signal(int, int, str)       # row, col, color_hex
    zoomChanged = Signal(float)               # zoom_factor
    progressChanged = Signal()                # triggered on drawing / row / col fill
    
    # Zoom levels and cell sizes in pixels
    ZOOM_LEVELS = [0.0625, 0.125, 0.25, 0.375, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0, 64.0]
    CELL_SIZES = {
        0.0625: 1,
        0.125: 2,
        0.25: 4,
        0.375: 6,
        0.5: 8,
        0.75: 12,
        1.0: 16,
        1.5: 24,
        2.0: 32,
        3.0: 48,
        4.0: 64,
        6.0: 96,
        8.0: 128,
        12.0: 192,
        16.0: 256,
        24.0: 384,
        32.0: 512,
        48.0: 768,
        64.0: 1024
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        
        self.project = None
        self.undo_stack = None
        
        self.zoom_index = 2  # default to 1.0 (16px)
        
        # Margins for the rulers (will update dynamically)
        self.margin_left = 50
        self.margin_top = 30
        
        # Mouse interaction states
        self.dragging = False
        self.drawing = False
        self.drawing_mode = None  # 'paint' or 'erase'
        self.stroke_original_states = {}  # (r, c) -> was_completed (bool)
        
        self.space_pressed = False
        self.panned_during_space = False
        self.last_mouse_pos = QPointF()
        
        # Hover state
        self.hover_row = -1
        self.hover_col = -1

    def set_project(self, project, undo_stack):
        self.project = project
        self.undo_stack = undo_stack
        
        # Sync canvas zoom index with project
        if self.project.zoom_factor in self.ZOOM_LEVELS:
            self.zoom_index = self.ZOOM_LEVELS.index(self.project.zoom_factor)
        else:
            self.zoom_index = 2
            self.project.zoom_factor = 1.0
            
        self.update_margins()
        self.update()
        self.progressChanged.emit()
        self.cursorChanged.emit(self.project.current_cursor[0], self.project.current_cursor[1])

    def get_cell_size(self):
        zoom = self.ZOOM_LEVELS[self.zoom_index]
        return self.CELL_SIZES[zoom]

    def update_margins(self):
        if not self.project:
            return
        # Dynamically set left margin based on height coordinate width
        font_metrics = QFontMetrics(self.font())
        max_num_width = font_metrics.horizontalAdvance(str(self.project.height))
        self.margin_left = max(50, max_num_width + 15)
        self.margin_top = 30

    def update_view(self):
        """Callback for undo/redo commands to refresh the view."""
        self.update()
        self.progressChanged.emit()
        self.cursorChanged.emit(self.project.current_cursor[0], self.project.current_cursor[1])

    # --- Zoom / Pan Helpers ---
    def set_zoom_index(self, index, center_point=None):
        if not self.project:
            return
        index = max(0, min(len(self.ZOOM_LEVELS) - 1, index))
        if index == self.zoom_index:
            return
            
        old_cell_size = self.get_cell_size()
        self.zoom_index = index
        new_cell_size = self.get_cell_size()
        
        self.project.zoom_factor = self.ZOOM_LEVELS[self.zoom_index]
        self.zoomChanged.emit(self.project.zoom_factor)
        
        # Center zoom on the center_point (widget coords)
        if center_point is None:
            center_point = QPointF(self.width() / 2.0, self.height() / 2.0)
            
        # Grid coord under center_point before zoom
        gx = (center_point.x() - self.margin_left - self.project.pan_offset[0]) / old_cell_size
        gy = (center_point.y() - self.margin_top - self.project.pan_offset[1]) / old_cell_size
        
        # Adjust pan so the same grid coord stays under center_point
        self.project.pan_offset[0] = center_point.x() - self.margin_left - gx * new_cell_size
        self.project.pan_offset[1] = center_point.y() - self.margin_top - gy * new_cell_size
        
        self.project.dirty = True
        self.update()

    def zoom_fit(self):
        if not self.project:
            return
        # Calculate fit zoom level
        avail_w = self.width() - self.margin_left - 20
        avail_h = self.height() - self.margin_top - 20
        
        if avail_w <= 0 or avail_h <= 0:
            return
            
        fit_w_cell = avail_w / self.project.width
        fit_h_cell = avail_h / self.project.height
        fit_cell_size = min(fit_w_cell, fit_h_cell)
        
        # Find closest zoom level that fits
        best_idx = 0
        for idx, z in enumerate(self.ZOOM_LEVELS):
            if self.CELL_SIZES[z] <= fit_cell_size:
                best_idx = idx
                
        self.zoom_index = best_idx
        self.project.zoom_factor = self.ZOOM_LEVELS[best_idx]
        self.zoomChanged.emit(self.project.zoom_factor)
        
        # Center the pattern
        new_cell_size = self.get_cell_size()
        pat_w = self.project.width * new_cell_size
        pat_h = self.project.height * new_cell_size
        
        self.project.pan_offset[0] = (avail_w - pat_w) / 2.0
        self.project.pan_offset[1] = (avail_h - pat_h) / 2.0
        
        self.project.dirty = True
        self.update()

    def get_ruler_step(self, cell_size):
        for step in [1, 2, 5, 10, 20, 50, 100, 200, 500]:
            if cell_size * step >= 40:
                return step
        return 1000

    # --- Mouse Coordinates ---
    def widget_to_grid(self, pos):
        """Converts widget pixel position to (row, col) grid coordinates."""
        if not self.project:
            return -1, -1
        cell_size = self.get_cell_size()
        
        gx = (pos.x() - self.margin_left - self.project.pan_offset[0]) / cell_size
        # y is bottom-up: row 0 is bottom, row H-1 is top
        gy_grid = pos.y() - self.margin_top - self.project.pan_offset[1]
        gr_flipped = gy_grid / cell_size
        
        col = math.floor(gx)
        row = self.project.height - 1 - math.floor(gr_flipped)
        
        return row, col

    # --- Navigation & Auto-Cursor Movements ---
    def move_cursor_to(self, row, col):
        if not self.project:
            return
        row = max(0, min(self.project.height - 1, row))
        col = max(0, min(self.project.width - 1, col))
        self.project.current_cursor = [row, col]
        self.cursorChanged.emit(row, col)
        self.update()

    def get_row_direction(self, r):
        """Returns 1 for Left-to-Right, -1 for Right-to-Left."""
        if self.project.direction_mode == 'L2R':
            return 1
        elif self.project.direction_mode == 'R2L':
            return -1
        else:  # Snake Mode (row 0 is bottom row, which starts L2R)
            # Even rows: L2R (1), Odd rows: R2L (-1)
            # (If reverse_direction is toggled, it flips)
            base_dir = 1 if (r % 2 == 0) else -1
            return base_dir

    def advance_cursor(self, step=1):
        """
        Advances the cursor by step stitches in the crochet order.
        step can be 1 (next) or -1 (previous).
        """
        if not self.project:
            return
            
        r, c = self.project.current_cursor
        W = self.project.width
        H = self.project.height
        
        # Direction factor (1 for forward, -1 for backward in crochet path)
        flow_dir = 1 if not self.project.reverse_direction else -1
        effective_step = step * flow_dir
        
        # Calculate next stitch
        dir_factor = self.get_row_direction(r)
        step_delta = effective_step * dir_factor
        
        new_c = c + step_delta
        
        if 0 <= new_c < W:
            self.move_cursor_to(r, new_c)
        else:
            # End of row reached: move to next row
            # If step_delta is positive (moving right in L2R, or left in R2L)
            # We reached the end of the row. Move to next row: r + 1 (or r - 1 if moving backward)
            row_step = 1 if step > 0 else -1
            new_r = r + row_step
            
            if 0 <= new_r < H:
                # Determine starting column for the new row based on its direction
                new_dir = self.get_row_direction(new_r)
                # If moving forward, we start at the beginning of new row's path.
                # If moving backward, we start at the end of new row's path.
                is_forward_movement = (step > 0)
                
                # Starting column:
                if new_dir == 1: # new row is L2R
                    new_c = 0 if is_forward_movement else W - 1
                else: # new row is R2L
                    new_c = W - 1 if is_forward_movement else 0
                    
                self.move_cursor_to(new_r, new_c)
            else:
                # Wrap around to start/end of pattern
                if step > 0:
                    # Wrap to bottom row start
                    start_dir = self.get_row_direction(0)
                    start_c = 0 if start_dir == 1 else W - 1
                    self.move_cursor_to(0, start_c)
                else:
                    # Wrap to top row end
                    end_dir = self.get_row_direction(H - 1)
                    end_c = W - 1 if end_dir == 1 else 0
                    self.move_cursor_to(H - 1, end_c)

    # --- Mouse Events ---
    def mousePressEvent(self, event):
        if not self.project:
            return
            
        pos = event.position()
        
        # Check if click is on Left Ruler (Row Completion Toggle)
        if pos.x() < self.margin_left and pos.y() >= self.margin_top:
            row, _ = self.widget_to_grid(pos)
            if 0 <= row < self.project.height:
                # Get all stitches in row
                stitches = {(row, c) for c in range(self.project.width)}
                # If all are completed, we erase. Otherwise, we paint.
                all_completed = all(s in self.project.completed_stitches for s in stitches)
                cmd = ToggleStitchCommand(self.project, stitches, not all_completed, self.update_view)
                self.undo_stack.push(cmd)
            return

        # Check if click is on Top Ruler (Column Completion Toggle)
        if pos.y() < self.margin_top and pos.x() >= self.margin_left:
            _, col = self.widget_to_grid(pos)
            if 0 <= col < self.project.width:
                # Get all stitches in column
                stitches = {(r, col) for r in range(self.project.height)}
                all_completed = all(s in self.project.completed_stitches for s in stitches)
                cmd = ToggleStitchCommand(self.project, stitches, not all_completed, self.update_view)
                self.undo_stack.push(cmd)
            return
            
        # Panning activation
        if event.button() == Qt.MiddleButton or self.space_pressed:
            self.dragging = True
            self.last_mouse_pos = pos
            self.setCursor(QCursor(Qt.ClosedHandCursor))
            self.panned_during_space = True
            return

        # Painting / Erasing stitches
        if event.button() == Qt.LeftButton or event.button() == Qt.RightButton:
            row, col = self.widget_to_grid(pos)
            if 0 <= row < self.project.height and 0 <= col < self.project.width:
                self.drawing = True
                self.stroke_original_states = {}
                
                # Left button paints completed; Right button paints erased
                if event.button() == Qt.LeftButton:
                    self.drawing_mode = 'paint'
                else:
                    self.drawing_mode = 'erase'
                
                # Apply to first clicked stitch
                s = (row, col)
                self.stroke_original_states[s] = s in self.project.completed_stitches
                if self.drawing_mode == 'paint':
                    self.project.completed_stitches.add(s)
                else:
                    self.project.completed_stitches.discard(s)
                    
                self.move_cursor_to(row, col)
                self.update()

    def mouseMoveEvent(self, event):
        if not self.project:
            return
            
        pos = event.position()
        
        # Handle hover tracking for status bar
        hover_r, hover_c = self.widget_to_grid(pos)
        if 0 <= hover_r < self.project.height and 0 <= hover_c < self.project.width:
            if hover_r != self.hover_row or hover_c != self.hover_col:
                self.hover_row = hover_r
                self.hover_col = hover_c
                hex_color = self.project.pixel_hexes[hover_r][hover_c]
                self.hoverChanged.emit(hover_r, hover_c, hex_color)
        else:
            if self.hover_row != -1 or self.hover_col != -1:
                self.hover_row = -1
                self.hover_col = -1
                self.hoverChanged.emit(-1, -1, "")

        # Panning drag
        if self.dragging:
            delta = pos - self.last_mouse_pos
            self.project.pan_offset[0] += delta.x()
            self.project.pan_offset[1] += delta.y()
            self.last_mouse_pos = pos
            self.project.dirty = True
            self.update()
            return

        # Drawing drag
        if self.drawing:
            row, col = self.widget_to_grid(pos)
            if 0 <= row < self.project.height and 0 <= col < self.project.width:
                s = (row, col)
                if s not in self.stroke_original_states:
                    self.stroke_original_states[s] = s in self.project.completed_stitches
                    
                if self.drawing_mode == 'paint':
                    self.project.completed_stitches.add(s)
                else:
                    self.project.completed_stitches.discard(s)
                    
                # Update current cursor to match drag lead
                if self.project.current_cursor != [row, col]:
                    self.project.current_cursor = [row, col]
                    self.cursorChanged.emit(row, col)
                self.update()

    def mouseReleaseEvent(self, event):
        if self.dragging:
            self.dragging = False
            if self.space_pressed:
                self.setCursor(QCursor(Qt.OpenHandCursor))
            else:
                self.setCursor(QCursor(Qt.ArrowCursor))
            return
            
        if self.drawing:
            self.drawing = False
            # Push the drag stroke onto the Undo stack
            if self.stroke_original_states:
                cmd = ToggleStitchCommand(
                    self.project,
                    self.stroke_original_states.keys(),
                    self.drawing_mode == 'paint',
                    self.update_view
                )
                self.undo_stack.push(cmd)
            self.drawing_mode = None
            self.progressChanged.emit()

    def wheelEvent(self, event):
        if not self.project:
            return
        # Zoom centered on mouse pointer
        steps = event.angleDelta().y() / 120.0
        self.set_zoom_index(self.zoom_index + int(steps), event.position())

    # --- Keyboard Pan State ---
    def set_space_pressed(self, pressed):
        if not self.project:
            return
        self.space_pressed = pressed
        if pressed:
            self.panned_during_space = False
            self.setCursor(QCursor(Qt.OpenHandCursor))
        else:
            self.setCursor(QCursor(Qt.ArrowCursor))
            # If released without panning, advance cursor (Space = Next Stitch)
            if not self.panned_during_space:
                self.advance_cursor(1)

    # --- Drawing Logic ---
    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.fillRect(self.rect(), QColor("#121212"))
            
            if not self.project:
                # Draw help text
                painter.setPen(QColor("#888888"))
                painter.setFont(QFont("Outfit", 13))
                painter.drawText(self.rect(), Qt.AlignCenter, "Open a pattern image (PNG, JPG, BMP) to begin.")
                return

            cell_size = self.get_cell_size()
            W = self.project.width
            H = self.project.height
            
            margin_right = 50 if self.project.ruler_four_sides_enabled else 0
            margin_bottom = 25 if self.project.ruler_four_sides_enabled else 0

            # Calculate visible grid range
            visible_rows = []
            for r in range(H):
                y = self.margin_top + self.project.pan_offset[1] + (H - 1 - r) * cell_size
                if y + cell_size >= self.margin_top and y <= self.height() - margin_bottom:
                    visible_rows.append((r, y))
                    
            visible_cols = []
            for c in range(W):
                x = self.margin_left + self.project.pan_offset[0] + c * cell_size
                if x + cell_size >= self.margin_left and x <= self.width() - margin_right:
                    visible_cols.append((c, x))

            # --- Draw Grid Cells (Batched by Color) ---
            # Clip painting to grid area to prevent drawing over rulers
            painter.save()
            try:
                painter.setClipRect(QRectF(self.margin_left, self.margin_top, 
                                           self.width() - self.margin_left - margin_right, 
                                           self.height() - self.margin_top - margin_bottom))
                
                cells_by_color = defaultdict(list)
                completed_rects_darken = []
                completed_rects_trans = defaultdict(list)
                completed_cells_cross = []
                completed_cells_horiz = []
                
                for r, y in visible_rows:
                    for c, x in visible_cols:
                        hex_color = self.project.pixel_hexes[r][c]
                        rect = QRectF(x, y, cell_size, cell_size)
                        
                        # Check completion state
                        is_completed = (r, c) in self.project.completed_stitches
                        
                        if is_completed:
                            if self.project.completion_style == 'darkened':
                                # Draw base color, overlay darkened later
                                cells_by_color[hex_color].append(rect)
                                completed_rects_darken.append(rect)
                            elif self.project.completion_style == 'transparent':
                                # Batch transparent color rects separately
                                completed_rects_trans[hex_color].append(rect)
                            elif self.project.completion_style == 'crossed_out':
                                cells_by_color[hex_color].append(rect)
                                completed_cells_cross.append(rect)
                            elif self.project.completion_style == 'horizontal_line':
                                cells_by_color[hex_color].append(rect)
                                completed_cells_horiz.append(rect)
                        else:
                            cells_by_color[hex_color].append(rect)
                            
                # 1. Fill base grid cells
                for hex_color, rects in cells_by_color.items():
                    brush = QBrush(QColor(hex_color))
                    for rect in rects:
                        painter.fillRect(rect, brush)
                    
                # 2. Fill transparent grid cells
                for hex_color, rects in completed_rects_trans.items():
                    color = QColor(hex_color)
                    color.setAlpha(60)  # semi-transparent
                    brush = QBrush(color)
                    for rect in rects:
                        painter.fillRect(rect, brush)
                    
                # 3. Apply Darkened overlays
                if completed_rects_darken:
                    brush = QBrush(QColor(0, 0, 0, 130))
                    for rect in completed_rects_darken:
                        painter.fillRect(rect, brush)
                    
                # 4. Apply Cross-outs and Horizontal Lines
                line_color_val = QColor(self.project.progress_line_color if hasattr(self.project, 'progress_line_color') else "#ff0000")
                line_thickness = 2 if cell_size >= 16 else 1
                
                if completed_cells_cross and cell_size >= 6:
                    painter.setPen(QPen(line_color_val, line_thickness, Qt.SolidLine))
                    for rect in completed_cells_cross:
                        painter.drawLine(rect.topLeft(), rect.bottomRight())
                        painter.drawLine(rect.topRight(), rect.bottomLeft())
                        
                if completed_cells_horiz and cell_size >= 6:
                    painter.setPen(QPen(line_color_val, line_thickness, Qt.SolidLine))
                    for rect in completed_cells_horiz:
                        y_mid = rect.y() + rect.height() / 2.0
                        painter.drawLine(rect.left(), y_mid, rect.right(), y_mid)

                # --- Draw Grid Lines ---
                if self.project.grid_enabled and cell_size >= 6:
                    thickness = 1
                    if self.project.grid_thickness == 'medium':
                        thickness = 2
                    elif self.project.grid_thickness == 'thick':
                        thickness = 3
                        
                    pen = QPen(QColor(self.project.grid_color), thickness, Qt.SolidLine)
                    painter.setPen(pen)
                    
                    # Vertical lines
                    for c, x in visible_cols:
                        painter.drawLine(QPointF(x, self.margin_top), QPointF(x, self.height()))
                    # Draw right-most line if last column is visible
                    if W > 0:
                        last_x = self.margin_left + self.project.pan_offset[0] + W * cell_size
                        if last_x >= self.margin_left and last_x <= self.width():
                            painter.drawLine(QPointF(last_x, self.margin_top), QPointF(last_x, self.height()))
                            
                    # Horizontal lines
                    for r, y in visible_rows:
                        painter.drawLine(QPointF(self.margin_left, y), QPointF(self.width(), y))
                    # Draw bottom-most line of row 0 if visible
                    if H > 0:
                        bottom_y = self.margin_top + self.project.pan_offset[1] + H * cell_size
                        if bottom_y >= self.margin_top and bottom_y <= self.height():
                            painter.drawLine(QPointF(self.margin_left, bottom_y), QPointF(self.width(), bottom_y))

                # --- Draw Symbols Mode ---
                if self.project.symbols_enabled and cell_size >= 22:
                    painter.setFont(QFont("Consolas", int(cell_size * 0.35)))
                    
                    for r, y in visible_rows:
                        for c, x in visible_cols:
                            hex_color = self.project.pixel_hexes[r][c]
                            color_info = self.project.color_palette.get(hex_color)
                            if color_info:
                                symbol = color_info['symbol']
                                rgb = color_info['rgb']
                                
                                # Adjust text opacity if completed & transparent
                                is_completed = (r, c) in self.project.completed_stitches
                                from utils import get_contrast_color
                                text_hex = get_contrast_color(rgb)
                                text_color = QColor(text_hex)
                                if is_completed:
                                    text_color.setAlpha(100)
                                    
                                painter.setPen(text_color)
                                rect = QRectF(x, y, cell_size, cell_size)
                                painter.drawText(rect, Qt.AlignCenter, symbol)

                # --- Draw Row / Column Highlights ---
                curr_row, curr_col = self.project.current_cursor
                
                # Row Highlights
                if self.project.row_highlight_enabled:
                    # Find y position of current row
                    y_curr = self.margin_top + self.project.pan_offset[1] + (H - 1 - curr_row) * cell_size
                    if y_curr + cell_size >= self.margin_top and y_curr <= self.height():
                        painter.fillRect(QRectF(self.margin_left, y_curr, self.width() - self.margin_left, cell_size), 
                                         QColor(255, 255, 0, 50))
                                         
                # Column Highlights
                if self.project.col_highlight_enabled:
                    x_curr = self.margin_left + self.project.pan_offset[0] + curr_col * cell_size
                    if x_curr + cell_size >= self.margin_left and x_curr <= self.width():
                        painter.fillRect(QRectF(x_curr, self.margin_top, cell_size, self.height() - self.margin_top), 
                                         QColor(255, 255, 0, 50))

                # --- Draw Current Stitch Cursor ---
                y_cursor = self.margin_top + self.project.pan_offset[1] + (H - 1 - curr_row) * cell_size
                x_cursor = self.margin_left + self.project.pan_offset[0] + curr_col * cell_size
                if (y_cursor + cell_size >= self.margin_top and y_cursor <= self.height() and
                    x_cursor + cell_size >= self.margin_left and x_cursor <= self.width()):
                    painter.setPen(QPen(QColor("#00ff00"), 3, Qt.SolidLine))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRect(QRectF(x_cursor, y_cursor, cell_size, cell_size))
            finally:
                painter.restore()  # Remove clip rect

            # --- Draw Rulers ---
            painter.setFont(QFont("Outfit", 9))
            
            # Top Ruler
            painter.fillRect(QRectF(self.margin_left, 0, self.width() - self.margin_left - margin_right, self.margin_top), QColor("#1f1f1f"))
            painter.setPen(QPen(QColor("#3a3a3a"), 1))
            painter.drawLine(QPointF(self.margin_left, self.margin_top - 1), QPointF(self.width() - margin_right, self.margin_top - 1))
            
            painter.setPen(QColor("#aaaaaa"))
            top_step = self.get_ruler_step(cell_size)
            for c, x in visible_cols:
                if c % top_step == 0:
                    # Draw tick
                    painter.drawLine(QPointF(x, self.margin_top - 6), QPointF(x, self.margin_top - 1))
                    # Draw text
                    rect_text = QRectF(x - cell_size * 2, 2, cell_size * 4, self.margin_top - 10)
                    painter.drawText(rect_text, Qt.AlignCenter, str(c))

            # Left Ruler
            painter.fillRect(QRectF(0, self.margin_top, self.margin_left, self.height() - self.margin_top - margin_bottom), QColor("#1f1f1f"))
            painter.setPen(QPen(QColor("#3a3a3a"), 1))
            painter.drawLine(QPointF(self.margin_left - 1, self.margin_top), QPointF(self.margin_left - 1, self.height() - margin_bottom))
            
            left_step = self.get_ruler_step(cell_size)
            for r, y in visible_rows:
                if r % left_step == 0:
                    # Draw tick
                    painter.setPen(QColor("#aaaaaa"))
                    painter.drawLine(QPointF(self.margin_left - 6, y), QPointF(self.margin_left - 1, y))
                    
                    # Draw Row Number text
                    rect_text = QRectF(5, y - 6, self.margin_left - 15, 12)
                    painter.drawText(rect_text, Qt.AlignRight | Qt.AlignVCenter, str(r + 1))
                    
                # Draw Bookmarks & Notes cues next to row labels
                has_bookmark = r in self.project.bookmarks
                has_note = r in self.project.notes
                
                if has_bookmark or has_note:
                    dot_y = y + cell_size / 2.0
                    if has_bookmark and has_note:
                        # Draw a split cue or two small dots
                        painter.setPen(Qt.NoPen)
                        painter.setBrush(QColor("#ff3b30"))  # Red dot for bookmark
                        painter.drawEllipse(QPointF(self.margin_left - 12, dot_y), 3.5, 3.5)
                        painter.setBrush(QColor("#34c759"))  # Green dot for note
                        painter.drawEllipse(QPointF(self.margin_left - 20, dot_y), 3.5, 3.5)
                    elif has_bookmark:
                        painter.setPen(Qt.NoPen)
                        painter.setBrush(QColor("#ff3b30"))
                        painter.drawEllipse(QPointF(self.margin_left - 12, dot_y), 4, 4)
                    elif has_note:
                        painter.setPen(Qt.NoPen)
                        painter.setBrush(QColor("#34c759"))
                        painter.drawEllipse(QPointF(self.margin_left - 12, dot_y), 4, 4)
                        
            # Bottom Ruler (if enabled)
            if margin_bottom > 0:
                painter.fillRect(QRectF(self.margin_left, self.height() - margin_bottom, self.width() - self.margin_left - margin_right, margin_bottom), QColor("#1f1f1f"))
                painter.setPen(QPen(QColor("#3a3a3a"), 1))
                painter.drawLine(QPointF(self.margin_left, self.height() - margin_bottom), QPointF(self.width() - margin_right, self.height() - margin_bottom))
                
                painter.setPen(QColor("#aaaaaa"))
                for c, x in visible_cols:
                    if c % top_step == 0:
                        painter.drawLine(QPointF(x, self.height() - margin_bottom), QPointF(x, self.height() - margin_bottom + 5))
                        rect_text = QRectF(x - cell_size * 2, self.height() - margin_bottom + 6, cell_size * 4, margin_bottom - 8)
                        painter.drawText(rect_text, Qt.AlignCenter, str(c))

            # Right Ruler (if enabled)
            if margin_right > 0:
                painter.fillRect(QRectF(self.width() - margin_right, self.margin_top, margin_right, self.height() - self.margin_top - margin_bottom), QColor("#1f1f1f"))
                painter.setPen(QPen(QColor("#3a3a3a"), 1))
                painter.drawLine(QPointF(self.width() - margin_right, self.margin_top), QPointF(self.width() - margin_right, self.height() - margin_bottom))
                
                painter.setPen(QColor("#aaaaaa"))
                for r, y in visible_rows:
                    if r % left_step == 0:
                        painter.drawLine(QPointF(self.width() - margin_right, y), QPointF(self.width() - margin_right + 5, y))
                        rect_text = QRectF(self.width() - margin_right + 8, y - 6, margin_right - 12, 12)
                        painter.drawText(rect_text, Qt.AlignLeft | Qt.AlignVCenter, str(r + 1))

            # Ruler intersection corners
            painter.fillRect(QRectF(0, 0, self.margin_left, self.margin_top), QColor("#181818"))
            painter.setPen(QPen(QColor("#3a3a3a"), 1))
            painter.drawLine(QPointF(self.margin_left - 1, 0), QPointF(self.margin_left - 1, self.margin_top))
            painter.drawLine(QPointF(0, self.margin_top - 1), QPointF(self.margin_left, self.margin_top - 1))

            if margin_right > 0:
                painter.fillRect(QRectF(self.width() - margin_right, 0, margin_right, self.margin_top), QColor("#181818"))
                painter.drawLine(QPointF(self.width() - margin_right, 0), QPointF(self.width() - margin_right, self.margin_top))
                painter.drawLine(QPointF(self.width() - margin_right, self.margin_top - 1), QPointF(self.width(), self.margin_top - 1))

            if margin_bottom > 0:
                painter.fillRect(QRectF(0, self.height() - margin_bottom, self.margin_left, margin_bottom), QColor("#181818"))
                painter.drawLine(QPointF(self.margin_left - 1, self.height() - margin_bottom), QPointF(self.margin_left - 1, self.height()))
                painter.drawLine(QPointF(0, self.height() - margin_bottom), QPointF(self.margin_left, self.height() - margin_bottom))

            if margin_right > 0 and margin_bottom > 0:
                painter.fillRect(QRectF(self.width() - margin_right, self.height() - margin_bottom, margin_right, margin_bottom), QColor("#181818"))
                painter.drawLine(QPointF(self.width() - margin_right, self.height() - margin_bottom), QPointF(self.width() - margin_right, self.height()))
                painter.drawLine(QPointF(self.width() - margin_right, self.height() - margin_bottom), QPointF(self.width(), self.height() - margin_bottom))
        except Exception as e:
            print("Exception in Canvas.paintEvent:", e)
