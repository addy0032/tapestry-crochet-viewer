# Crochet Companion

**Crochet Companion** is a feature-rich, high-performance desktop application built with Python and PySide6. It is designed specifically for tapestry crochet, cross-stitch, and pixel-pattern crafters to view charts, track stitch-by-stitch progress, manage color palettes, and keep notes without losing their place.

---

## Features

### 1. Interactive Pattern Canvas & Rulers
*   **Viewport & Navigation:** Pan around the pattern using middle-click (or spacebar + left drag) and zoom dynamically.
*   **19 Zoom Levels:** Zoom from `6.25%` up to `6400%` (including intermediate steps like `37.5%`). Every zoom level is aligned to crisp integer pixel sizes to prevent sub-pixel blur.
*   **Four-Sided Rulers:** Displays column numbers along the top and row numbers along the left. Toggle the checkable **Right & Bottom Rulers** option in the **View** menu to display rulers on all four sides.
*   **Adjustable Intervals:** Ruler coordinates automatically adjust numbering intervals (1, 2, 5, 10, 20...) depending on the zoom level to prevent overlaps.

### 2. Advanced Progress Tracking
*   **Stitch Marking:** Toggle completion of individual stitches by clicking or dragging your mouse across the grid.
*   **Completion Styles:** Choose how completed stitches look via the dropdown in the toolbar:
    *   `Darkened`: Overlays completed cells with a semi-transparent black layer.
    *   `Semi-Transparent`: Blends completed cells with a reduced-opacity transparency.
    *   `Crossed Out`: Draws a crossed "X" over completed cells.
    *   `Horizontal Line`: Draws a clean horizontal strike-through line across completed cells.
*   **Customizable Marking Color:** Click the **Line Color...** button in the toolbar to change the color of the crossed-out or horizontal lines (defaults to Red).
*   **Row/Column Completion:** Click row indexes on the left/right rulers to toggle the entire row as done. Click column indexes on the top/bottom rulers to do the same for columns. Or select a row and press `Shift+R`.
*   **Progress Reset:** Instantly mark all stitches as uncompleted using the **Reset All Progress...** option in the **Edit** menu (includes safety verification).

### 3. Palette Management & Stitch Counts
*   **Compact List:** Shows color swatches, details (Symbol, Name, Hex code), and total stitch counts (e.g. `12400 sts`) side-by-side in the panel.
*   **Global Recolor:** Select any color in your palette and click **Replace Color...** to select a new shade. All matching cells in the grid, the count details, and the minimap preview will update immediately.
*   **Palette Renaming:** Select a color and click **Rename Selected...** to customize its name (e.g. "Main Background") and symbol (e.g. "C1").

### 4. Crochet Direction & Auto-Cursor
*   **Traversals:** Use `Space` to advance your active cursor stitch and `Shift+Space` to step backward.
*   **Order Modes:** Supports physical crochet flows:
    *   `L2R`: Traverses rows strictly left-to-right.
    *   `R2L`: Traverses rows strictly right-to-left.
    *   `Snake`: Alternates row direction (e.g. odd rows left-to-right, even rows right-to-left).
*   **Reverse Direction:** A checkable option to start rows from the opposite end of the pattern.

### 5. Automated Project Management
*   **Companion JSON Files:** Opening a raw PNG, JPG, or BMP file automatically initializes a project and saves it next to the image as `image_name.json`.
*   **Non-Intrusive Saving:** Manually pressing `Ctrl+S` (or clicking Save) directly overwrites the current project file and updates the status bar without opening file-picker prompts. Use **Save Project As...** (`Ctrl+Shift+S`) to save to a new location.
*   **Global Metadata Mapping:** Project files are mapped in `.crochet_companion_metadata.json` under the user's home directory (e.g. `C:\Users\<Username>\.crochet_companion_metadata.json` on Windows). Opening a raw PNG image in the future automatically links and loads your saved JSON project (restoring bookmarks, progress, notes, and custom colors) instead of creating a blank project.

### 6. Bookmarks & Notes
*   **Bookmarks:** Bookmark rows to display red indicator dots next to ruler labels and view them in a jump list.
*   **Row Notes:** Enter row-specific text instructions that display whenever the stitch cursor focuses on that row (indicated by green dots on the rulers).

### 7. Exporting & Undo
*   **High-Res Export:** Save your customized pattern chart (including custom colors, progress overlays, symbol texts, and rulers) as a high-resolution PNG file.
*   **Full Undo Stack:** All canvas edits, color renaming, recoloring, resets, and bookmarks are fully undoable/redoable via `Ctrl+Z` / `Ctrl+Y`.

---

## Setup & Installation

### Requirements
*   **Python 3.12+**
*   **PySide6** (Qt6 bindings for Python)
*   **Pillow** (PIL image library)

### Step 1: Install Dependencies
Open your terminal (PowerShell, Command Prompt, or bash) and run:
```bash
pip install PySide6 Pillow
```

### Step 2: Running the Application
Run the main startup script from the project folder:
```bash
python main.py
```

---

## Files Structure
*   `main.py`: Application entry point, QMainWindow, menu setup, shortcuts, and mapping database hooks.
*   `canvas.py`: Interactive grid canvas, zoom, panning, visible cell calculations, ruler rendering, and mouse coordinates.
*   `project.py`: Core project state structure, loading PNG files, saving and loading JSON projects.
*   `palette.py`: Palette list panel, row stats sequence generator, bookmarks manager, and minimap widget.
*   `toolbar.py`: Main toolbar controls, checkboxes, comboboxes, and color pickers.
*   `statusbar.py`: bottom status bar displaying completion stats, zoom levels, active cursor details, and hover coordinates.
*   `utils.py`: `QUndoCommand` wrappers for actions (drawing, renaming, recoloring, bookmarking, writing notes).
