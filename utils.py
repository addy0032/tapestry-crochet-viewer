from PySide6.QtGui import QUndoCommand
import json

def get_contrast_color(rgb_color):
    """
    Returns black (#000000) or white (#ffffff) depending on the luminance of the rgb_color.
    rgb_color: tuple of (r, g, b) where elements are 0-255.
    """
    r, g, b = rgb_color
    # Standard relative luminance formula
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    return "#000000" if luminance > 0.5 else "#ffffff"

class ToggleStitchCommand(QUndoCommand):
    """
    Undo/Redo command for toggling stitch completion state.
    Supports single or batch changes (e.g. row/col clicks, dragging).
    """
    def __init__(self, project, stitches, make_completed, callback):
        super().__init__()
        self.project = project
        # Keep copy of stitches as a list of tuples
        self.stitches = list(stitches)
        self.make_completed = make_completed
        self.callback = callback
        
        # We need to save the previous states of these specific stitches to restore on undo.
        # This handles cases where we might drag-paint over already completed stitches.
        self.previous_states = {}
        for s in self.stitches:
            self.previous_states[s] = s in self.project.completed_stitches

    def redo(self):
        for s in self.stitches:
            if self.make_completed:
                self.project.completed_stitches.add(s)
            else:
                self.project.completed_stitches.discard(s)
        self.project.dirty = True
        if self.callback:
            self.callback()

    def undo(self):
        for s in self.stitches:
            was_completed = self.previous_states[s]
            if was_completed:
                self.project.completed_stitches.add(s)
            else:
                self.project.completed_stitches.discard(s)
        self.project.dirty = True
        if self.callback:
            self.callback()

class RenameColorCommand(QUndoCommand):
    """
    Undo/Redo command for renaming a color or changing its symbol.
    """
    def __init__(self, project, hex_color, old_name, old_symbol, new_name, new_symbol, callback):
        super().__init__()
        self.project = project
        self.hex_color = hex_color
        self.old_name = old_name
        self.old_symbol = old_symbol
        self.new_name = new_name
        self.new_symbol = new_symbol
        self.callback = callback

    def redo(self):
        if self.hex_color in self.project.color_palette:
            self.project.color_palette[self.hex_color]['name'] = self.new_name
            self.project.color_palette[self.hex_color]['symbol'] = self.new_symbol
            self.project.dirty = True
            if self.callback:
                self.callback()

    def undo(self):
        if self.hex_color in self.project.color_palette:
            self.project.color_palette[self.hex_color]['name'] = self.old_name
            self.project.color_palette[self.hex_color]['symbol'] = self.old_symbol
            self.project.dirty = True
            if self.callback:
                self.callback()

class ToggleBookmarkCommand(QUndoCommand):
    """
    Undo/Redo command for toggling a row bookmark.
    """
    def __init__(self, project, row, callback):
        super().__init__()
        self.project = project
        self.row = row
        self.callback = callback
        self.was_bookmarked = row in self.project.bookmarks

    def redo(self):
        if self.was_bookmarked:
            self.project.bookmarks.discard(self.row)
        else:
            self.project.bookmarks.add(self.row)
        self.project.dirty = True
        if self.callback:
            self.callback()

    def undo(self):
        # Do the opposite
        if self.was_bookmarked:
            self.project.bookmarks.add(self.row)
        else:
            self.project.bookmarks.discard(self.row)
        self.project.dirty = True
        if self.callback:
            self.callback()

class UpdateNoteCommand(QUndoCommand):
    """
    Undo/Redo command for adding or updating a row note.
    """
    def __init__(self, project, row, old_note, new_note, callback):
        super().__init__()
        self.project = project
        self.row = row
        self.old_note = old_note
        self.new_note = new_note
        self.callback = callback

    def redo(self):
        if self.new_note:
            self.project.notes[self.row] = self.new_note
        else:
            self.project.notes.pop(self.row, None)
        self.project.dirty = True
        if self.callback:
            self.callback()

    def undo(self):
        if self.old_note:
            self.project.notes[self.row] = self.old_note
        else:
            self.project.notes.pop(self.row, None)
        self.project.dirty = True
        if self.callback:
            self.callback()

class ReplaceColorCommand(QUndoCommand):
    """
    Undo/Redo command to replace all pixels of a particular color with another color.
    """
    def __init__(self, project, old_hex, new_hex, new_rgb, callback):
        super().__init__()
        self.project = project
        self.old_hex = old_hex
        self.new_hex = new_hex
        self.new_rgb = new_rgb
        self.callback = callback
        
        # Save previous states to restore on undo
        self.previous_pixel_hexes = [row[:] for row in project.pixel_hexes]
        self.previous_pixels = [row[:] for row in project.pixels]
        self.previous_color_palette = json.loads(json.dumps(project.color_palette))

    def redo(self):
        H = self.project.height
        W = self.project.width
        for r in range(H):
            for c in range(W):
                if self.project.pixel_hexes[r][c] == self.old_hex:
                    self.project.pixel_hexes[r][c] = self.new_hex
                    self.project.pixels[r][c] = self.new_rgb
        
        self.rebuild_palette()
        self.project.dirty = True
        if self.callback:
            self.callback()

    def undo(self):
        self.project.pixel_hexes = [row[:] for row in self.previous_pixel_hexes]
        self.project.pixels = [row[:] for row in self.previous_pixels]
        self.project.color_palette = json.loads(json.dumps(self.previous_color_palette))
        self.project.dirty = True
        if self.callback:
            self.callback()

    def rebuild_palette(self):
        color_counts = {}
        H = self.project.height
        W = self.project.width
        for r in range(H):
            for c in range(W):
                h = self.project.pixel_hexes[r][c]
                color_counts[h] = color_counts.get(h, 0) + 1
                
        if self.old_hex in self.project.color_palette:
            old_info = self.project.color_palette[self.old_hex]
            if self.new_hex not in self.project.color_palette:
                self.project.color_palette[self.new_hex] = {
                    'rgb': self.new_rgb,
                    'name': old_info['name'],
                    'symbol': old_info['symbol'],
                    'count': 0
                }
        
        for h in list(self.project.color_palette.keys()):
            if h in color_counts:
                self.project.color_palette[h]['count'] = color_counts[h]
            else:
                self.project.color_palette.pop(h, None)

class PaintStitchCommand(QUndoCommand):
    """
    Undo/Redo command for changing the color of specific stitches.
    Supports single or batch changes (e.g. click, dragging).
    """
    def __init__(self, project, stitch_color_map, callback):
        """
        stitch_color_map: dict of (r, c) -> new_hex_color
        """
        super().__init__()
        self.project = project
        self.stitch_color_map = stitch_color_map
        self.callback = callback
        
        # Save previous states: (r, c) -> (old_hex, old_rgb)
        self.previous_states = {}
        for (r, c), new_hex in stitch_color_map.items():
            old_hex = self.project.pixel_hexes[r][c]
            old_rgb = self.project.pixels[r][c]
            self.previous_states[(r, c)] = (old_hex, old_rgb)

    def redo(self):
        for (r, c), new_hex in self.stitch_color_map.items():
            old_hex = self.project.pixel_hexes[r][c]
            if old_hex == new_hex:
                continue
                
            # Update pixel colors
            self.project.pixel_hexes[r][c] = new_hex
            r_val = int(new_hex[1:3], 16)
            g_val = int(new_hex[3:5], 16)
            b_val = int(new_hex[5:7], 16)
            self.project.pixels[r][c] = (r_val, g_val, b_val)
            
            # Update counts in color_palette
            if old_hex in self.project.color_palette:
                self.project.color_palette[old_hex]['count'] = max(0, self.project.color_palette[old_hex]['count'] - 1)
            if new_hex in self.project.color_palette:
                self.project.color_palette[new_hex]['count'] += 1
                
        self.project.dirty = True
        if self.callback:
            self.callback()

    def undo(self):
        for (r, c), (old_hex, old_rgb) in self.previous_states.items():
            new_hex = self.project.pixel_hexes[r][c]
            if new_hex == old_hex:
                continue
                
            # Restore pixel colors
            self.project.pixel_hexes[r][c] = old_hex
            self.project.pixels[r][c] = old_rgb
            
            # Restore counts in color_palette
            if new_hex in self.project.color_palette:
                self.project.color_palette[new_hex]['count'] = max(0, self.project.color_palette[new_hex]['count'] - 1)
            if old_hex in self.project.color_palette:
                self.project.color_palette[old_hex]['count'] += 1
                
        self.project.dirty = True
        if self.callback:
            self.callback()

class AddColorCommand(QUndoCommand):
    """
    Undo/Redo command for adding a new color to the palette.
    """
    def __init__(self, project, hex_color, name, symbol, callback):
        super().__init__()
        self.project = project
        self.hex_color = hex_color
        self.name = name
        self.symbol = symbol
        self.callback = callback
        
    def redo(self):
        r = int(self.hex_color[1:3], 16)
        g = int(self.hex_color[3:5], 16)
        b = int(self.hex_color[5:7], 16)
        self.project.color_palette[self.hex_color] = {
            'rgb': (r, g, b),
            'name': self.name,
            'symbol': self.symbol,
            'count': 0
        }
        self.project.dirty = True
        if self.callback:
            self.callback()
            
    def undo(self):
        self.project.color_palette.pop(self.hex_color, None)
        self.project.dirty = True
        if self.callback:
            self.callback()

class RemoveColorCommand(QUndoCommand):
    """
    Undo/Redo command for removing a color from the palette,
    and replacing all matching pixels with White (#ffffff).
    """
    def __init__(self, project, hex_color, callback):
        super().__init__()
        self.project = project
        self.hex_color = hex_color
        self.callback = callback
        
        # Find all coordinates that currently have this color
        self.affected_stitches = []
        H = self.project.height
        W = self.project.width
        for r in range(H):
            for c in range(W):
                if self.project.pixel_hexes[r][c] == self.hex_color:
                    self.affected_stitches.append((r, c))
                    
        # Save original state of white (#ffffff) color in palette
        self.white_added = False
        self.white_previous_info = None
        if "#ffffff" in self.project.color_palette:
            info = self.project.color_palette["#ffffff"]
            self.white_previous_info = {
                'rgb': info['rgb'],
                'name': info['name'],
                'symbol': info['symbol'],
                'count': info['count']
            }
        
        # Save original info of the deleted color
        info = self.project.color_palette[self.hex_color]
        self.deleted_info = {
            'rgb': info['rgb'],
            'name': info['name'],
            'symbol': info['symbol'],
            'count': info['count']
        }

    def redo(self):
        # 1. Update pixels to white (#ffffff)
        for r, c in self.affected_stitches:
            self.project.pixel_hexes[r][c] = "#ffffff"
            self.project.pixels[r][c] = (255, 255, 255)
            
        # 2. Add or update white (#ffffff) in color_palette
        if "#ffffff" in self.project.color_palette:
            self.project.color_palette["#ffffff"]['count'] += len(self.affected_stitches)
        else:
            self.project.color_palette["#ffffff"] = {
                'rgb': (255, 255, 255),
                'name': 'White',
                'symbol': 'W',
                'count': len(self.affected_stitches)
            }
            self.white_added = True
            
        # 3. Remove deleted color from palette
        self.project.color_palette.pop(self.hex_color, None)
        
        self.project.dirty = True
        if self.callback:
            self.callback()

    def undo(self):
        # 1. Restore original pixels color
        for r, c in self.affected_stitches:
            self.project.pixel_hexes[r][c] = self.hex_color
            self.project.pixels[r][c] = self.deleted_info['rgb']
            
        # 2. Restore white (#ffffff) state
        if self.white_added:
            self.project.color_palette.pop("#ffffff", None)
        elif self.white_previous_info:
            self.project.color_palette["#ffffff"] = self.white_previous_info.copy()
            
        # 3. Restore deleted color info
        self.project.color_palette[self.hex_color] = self.deleted_info.copy()
        
        self.project.dirty = True
        if self.callback:
            self.callback()
