import os
import json
from PIL import Image

class Project:
    def __init__(self):
        self.filepath = None  # Path to the .json project file (if saved)
        self.image_path = None
        self.width = 0
        self.height = 0
        self.pixels = []  # 2D list of (R, G, B) tuples. row 0 is bottom row of pattern.
        
        # Color palette: hex string -> {'rgb': (r,g,b), 'name': name, 'symbol': symbol, 'count': count}
        self.color_palette = {}
        
        # Completed stitches: set of (row, col) tuples
        self.completed_stitches = set()
        
        # Row bookmarks and notes
        self.bookmarks = set()
        self.notes = {}  # row (int) -> note (str)
        
        # UI state
        self.zoom_factor = 1.0
        self.pan_offset = [0.0, 0.0]
        self.current_cursor = [0, 0]  # [row, col]
        
        # Preferences
        self.completion_style = 'darkened'  # darkened, transparent, crossed_out
        self.grid_thickness = 'thin'       # thin, medium, thick
        self.grid_color = '#444444'
        self.grid_enabled = True
        self.symbols_enabled = False
        self.row_highlight_enabled = True
        self.col_highlight_enabled = False
        self.direction_mode = 'Snake'       # L2R, R2L, Snake
        self.reverse_direction = False
        self.progress_line_color = '#ff0000'
        self.ruler_four_sides_enabled = False
        
        self.dirty = False

    def load_image(self, img_path):
        """
        Loads an image file, reads pixels (row 0 is bottom), and builds the default palette.
        """
        if not os.path.exists(img_path):
            raise FileNotFoundError(f"Image file not found: {img_path}")
            
        img = Image.open(img_path).convert('RGB')
        self.image_path = os.path.abspath(img_path)
        self.width, self.height = img.size
        
        # Read pixels starting from bottom row (y = height - 1) up to top row (y = 0)
        self.pixels = []
        self.pixel_hexes = []
        color_counts = {}
        for y in range(self.height - 1, -1, -1):
            row_pixels = []
            row_hexes = []
            for x in range(self.width):
                rgb = img.getpixel((x, y))
                row_pixels.append(rgb)
                
                # Count colors for the palette
                hex_color = "#{:02x}{:02x}{:02x}".format(*rgb)
                row_hexes.append(hex_color)
                color_counts[hex_color] = color_counts.get(hex_color, 0) + 1
            self.pixels.append(row_pixels)
            self.pixel_hexes.append(row_hexes)
            
        # Build palette
        # Sort colors by count descending
        sorted_colors = sorted(color_counts.items(), key=lambda item: item[1], reverse=True)
        self.color_palette = {}
        for idx, (hex_val, count) in enumerate(sorted_colors, 1):
            r = int(hex_val[1:3], 16)
            g = int(hex_val[3:5], 16)
            b = int(hex_val[5:7], 16)
            
            # Simple default symbols: C1, C2, etc.
            self.color_palette[hex_val] = {
                'rgb': (r, g, b),
                'name': f"Color {idx}",
                'symbol': f"C{idx}",
                'count': count
            }
            
        self.completed_stitches = set()
        self.bookmarks = set()
        self.notes = {}
        self.current_cursor = [0, 0]
        self.zoom_factor = 1.0
        self.pan_offset = [0.0, 0.0]
        self.dirty = False

    def save_project(self, filepath):
        """
        Saves the project data to a JSON file.
        """
        # Save relative image path if possible, or absolute path
        image_path_to_save = self.image_path
        if filepath:
            try:
                # Store as relative path if on same drive
                image_path_to_save = os.path.relpath(self.image_path, os.path.dirname(filepath))
            except ValueError:
                image_path_to_save = self.image_path

        data = {
            'image_path': image_path_to_save,
            'completed': list(list(s) for s in self.completed_stitches),
            'color_names': {h: {'name': v['name'], 'symbol': v['symbol']} for h, v in self.color_palette.items()},
            'color_palette': self.color_palette,
            'pixel_hexes': self.pixel_hexes,
            'zoom_factor': self.zoom_factor,
            'pan_offset': list(self.pan_offset),
            'bookmarks': list(self.bookmarks),
            'notes': {str(k): v for k, v in self.notes.items()},
            'current_cursor': list(self.current_cursor),
            'completion_style': self.completion_style,
            'grid_thickness': self.grid_thickness,
            'grid_color': self.grid_color,
            'grid_enabled': self.grid_enabled,
            'symbols_enabled': self.symbols_enabled,
            'row_highlight_enabled': self.row_highlight_enabled,
            'col_highlight_enabled': self.col_highlight_enabled,
            'direction_mode': self.direction_mode,
            'reverse_direction': self.reverse_direction,
            'progress_line_color': self.progress_line_color,
            'ruler_four_sides_enabled': self.ruler_four_sides_enabled
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
            
        self.filepath = filepath
        self.dirty = False

    def load_project(self, filepath):
        """
        Loads the project data from a JSON file and reloads the image.
        """
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        # Resolve image path relative to the project directory if necessary
        saved_img_path = data['image_path']
        if not os.path.isabs(saved_img_path):
            proj_dir = os.path.dirname(filepath)
            resolved_img_path = os.path.abspath(os.path.join(proj_dir, saved_img_path))
        else:
            resolved_img_path = saved_img_path
            
        # Load image (this fills pixels, size, and default color_palette)
        self.load_image(resolved_img_path)
        
        # Override with saved pixel colors if they exist (color replacements)
        if 'pixel_hexes' in data:
            self.pixel_hexes = data['pixel_hexes']
            self.pixels = []
            for row in self.pixel_hexes:
                row_pixels = []
                for h in row:
                    r = int(h[1:3], 16)
                    g = int(h[3:5], 16)
                    b = int(h[5:7], 16)
                    row_pixels.append((r, g, b))
                self.pixels.append(row_pixels)

        # Restore color names/symbols/palette from JSON if they exist
        if 'color_palette' in data:
            # Reconstruct color_palette keys and values (ensure RGB is tuple, not list from JSON)
            self.color_palette = {}
            for h, info in data['color_palette'].items():
                self.color_palette[h] = {
                    'rgb': tuple(info['rgb']),
                    'name': info['name'],
                    'symbol': info['symbol'],
                    'count': info['count']
                }
        else:
            # Backward compatibility check:
            saved_colors = data.get('color_names', {})
            for hex_val, info in saved_colors.items():
                if hex_val in self.color_palette:
                    self.color_palette[hex_val]['name'] = info.get('name', self.color_palette[hex_val]['name'])
                    self.color_palette[hex_val]['symbol'] = info.get('symbol', self.color_palette[hex_val]['symbol'])

        # Override with saved data
        self.completed_stitches = {tuple(s) for s in data.get('completed', [])}
                
        self.zoom_factor = data.get('zoom_factor', 1.0)
        self.pan_offset = data.get('pan_offset', [0.0, 0.0])
        self.current_cursor = data.get('current_cursor', [0, 0])
        self.bookmarks = set(data.get('bookmarks', []))
        
        # Notes keys are saved as strings in JSON; convert back to int rows
        saved_notes = data.get('notes', {})
        self.notes = {int(k): v for k, v in saved_notes.items()}
        
        self.completion_style = data.get('completion_style', 'darkened')
        self.grid_thickness = data.get('grid_thickness', 'thin')
        self.grid_color = data.get('grid_color', '#444444')
        self.grid_enabled = data.get('grid_enabled', True)
        self.symbols_enabled = data.get('symbols_enabled', False)
        self.row_highlight_enabled = data.get('row_highlight_enabled', True)
        self.col_highlight_enabled = data.get('col_highlight_enabled', False)
        self.direction_mode = data.get('direction_mode', 'Snake')
        self.reverse_direction = data.get('reverse_direction', False)
        self.progress_line_color = data.get('progress_line_color', '#ff0000')
        self.ruler_four_sides_enabled = data.get('ruler_four_sides_enabled', False)
        
        self.filepath = filepath
        self.dirty = False
