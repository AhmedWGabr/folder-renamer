# Folder Renamer Documentation

## Overview
Folder Renamer is a Python GUI application for batch-renaming files in a selected folder. It provides a modern interface with a live preview, custom scrollbars, and intuitive numeric entry controls.

## Main Features
- **Batch Rename**: Rename all files in a folder with a consistent pattern.
- **Preview Table**: See a live preview of new filenames before applying changes.
- **Custom Controls**: Numeric entry fields for start number and digit count, with mouse wheel and hover arrow support.
- **Modern UI**: Uses CustomTkinter for a clean, modern look.

## How It Works
1. **Select Folder**: Choose the folder containing files to rename.
2. **Set Parameters**: Adjust the starting number and digit count for filenames.
3. **Preview**: The table shows the current and new filenames (up to 10 visible at a time, scrollable for more).
4. **Rename**: Click 'Rename' to apply changes. The app will rename files as previewed.

## Requirements
- Python 3.8 or higher
- customtkinter

Install dependencies:
```
pip install customtkinter
```

## Running the App
```
python folder_renamer.py
```

## Notes
- The preview table always shows 10 rows, but you can scroll to see more files.
- Numeric entry fields have custom up/down arrows that appear on hover and support mouse wheel changes.
- All renaming actions are previewed before being applied.

## License
MIT License
