import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Use customtkinter for modern UI
try:
    import customtkinter as ctk
except ImportError:
    raise SystemExit("Missing dependency: install with 'pip install customtkinter'")

ctk.set_appearance_mode("System")  # Options: "Light", "Dark", "System"
ctk.set_default_color_theme("blue")  # Built-in: blue, green, dark-blue

"""
CustomTkinter based GUI tool to batch rename files sequentially (e.g., series episodes).
Features:
- Select folder
- Enter prefix
- Choose start number & zero padding
- Order by name or modification time
- Reorder manually (multi-select, move block up/down)
- Preview & rename
- Light / Dark / System appearance switching
"""

class FolderRenamerGUI:
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.root.title("Folder Renamer")
        # Start with minimal width, height will auto-fit after first preview build
        self.root.minsize(640, 300)

        # State variables
        self.folder_path = tk.StringVar()
        self.prefix_text = tk.StringVar(value="Episode")
        self.start_number = tk.IntVar(value=1)
        self.padding = tk.IntVar(value=2)
        self.order_mode = tk.StringVar(value="name")
        self.appearance_mode = tk.StringVar(value="System")

        # Data containers
        self.file_list = []
        self.accent_color = '#2563eb'
        self._max_tree_rows = 10  # fixed visible row count (height); DO NOT limit total files
        self._auto_resize_window = True
        self._scroll_hover = False
        self._scroll_hide_job = None

        self._build_ui()
        # Style tree after widgets exist
        self._style_treeview()
        # Initial auto-size
        self.root.after(50, self._auto_fit_height)

    # --- Color helpers and styling additions ---
    def _get_theme_palette(self):
        dark = (ctk.get_appearance_mode() == 'Dark')
        if dark:
            return {
                'bg': '#1d232a',
                'panel': '#242b33',
                'header_bg': '#242b33',
                'header_fg': '#9caec1',
                'row_even': '#2a323c',
                'row_odd': '#252d36',
                'row_fg': '#e3e7eb',
                'sel_bg': '#2563eb',
                'sel_fg': '#ffffff',
                'border': '#2f3943'
            }
        else:
            return {
                'bg': '#ffffff',
                'panel': '#f5f7f9',
                'header_bg': '#eef1f4',
                'header_fg': '#334155',
                'row_even': '#ffffff',
                'row_odd': '#f2f5f7',
                'row_fg': '#1f2933',
                'sel_bg': '#2563eb',
                'sel_fg': '#ffffff',
                'border': '#d5dbe1'
            }

    def _style_treeview(self):
        palette = self._get_theme_palette()
        style = ttk.Style(self.tree)
        # Pick a base theme first to ensure elements exist
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure('Flat.Treeview',
                        background=palette['panel'],
                        fieldbackground=palette['panel'],
                        foreground=palette['row_fg'],
                        borderwidth=0,
                        relief='flat',
                        rowheight=26,
                        font=('Segoe UI', 10))
        style.configure('Flat.Treeview.Heading',
                        background=palette['header_bg'],
                        foreground=palette['header_fg'],
                        relief='flat',
                        borderwidth=0,
                        font=('Segoe UI Semibold', 10))
        style.map('Flat.Treeview',
                  background=[('selected', palette['sel_bg'])],
                  foreground=[('selected', palette['sel_fg'])])
        # Remove border separators (clam uses bordercolor option)
        style.layout('Flat.Treeview', style.layout('Treeview'))
        # Apply style to existing tree
        if hasattr(self, 'tree'):
            self.tree.configure(style='Flat.Treeview')
            # Re-run tag colors if data present
            if self.file_list:
                self._refresh_tree_from_file_list()
        # Restyle custom scrollbar
        if hasattr(self, 'scroll_track'):
            self.scroll_track.configure(fg_color=palette['panel'])
            self.scroll_thumb.configure(fg_color=self.accent_color)
            self._update_scroll_visibility()

    # --- Modern hidden scrollbar logic ---
    def _init_custom_scrollbar(self, container):
        palette = self._get_theme_palette()
        # width/height must be set via constructor or configure() in customtkinter, not via place()
        self.scroll_track = ctk.CTkFrame(container, corner_radius=3, fg_color=palette['panel'], width=6)
        # Provide an initial height for thumb; will be updated dynamically
        self.scroll_thumb = ctk.CTkFrame(self.scroll_track, corner_radius=3, fg_color=self.accent_color, width=6, height=24)
        # Initially hidden; shown on hover/scroll if needed
        self._scrollbar_shown = False
        self._thumb_placed = False

    def _show_scrollbar(self):
        if not hasattr(self, 'scroll_track'):
            return
        if self._needs_vertical_scroll():
            if not self._scrollbar_shown:
                # Width already set; do not pass width/height to place()
                self.scroll_track.place(relx=1.0, rely=0.0, relheight=1.0, x=-2)
                self._scrollbar_shown = True
            self._update_scroll_thumb()

    def _hide_scrollbar(self, force=False):
        if not hasattr(self, 'scroll_track'):
            return
        if force or (not self._scroll_hover and not self._is_scrolling_active()):
            if self._scrollbar_shown:
                self.scroll_track.place_forget()
                self._scrollbar_shown = False
                self._thumb_visible = False

    def _schedule_hide_scrollbar(self):
        if self._scroll_hide_job:
            self.root.after_cancel(self._scroll_hide_job)
        self._scroll_hide_job = self.root.after(1000, self._hide_scrollbar)

    def _needs_vertical_scroll(self):
        if not hasattr(self, 'tree'):
            return False
        first, last = self.tree.yview()
        return not (first <= 0.0001 and last >= 0.9999)

    def _is_scrolling_active(self):
        # Placeholder for possible future smooth scrolling state
        return False

    def _on_tree_scroll(self, first, last):
        # Update thumb from fractional positions
        self._update_scroll_thumb(first=float(first), last=float(last))
        # Autohide logic
        self._show_scrollbar()
        self._schedule_hide_scrollbar()

    def _update_scroll_thumb(self, first=None, last=None):
        if not hasattr(self, 'scroll_track'):
            return
        if first is None or last is None:
            fv = self.tree.yview()
            if not fv:
                return
            first, last = fv
        if not self._needs_vertical_scroll():
            self._hide_scrollbar(force=True)
            return
        if not self._scrollbar_shown:
            return
        track_h = self.scroll_track.winfo_height() or 1
        frac = max(0.02, last - first)
        thumb_h = int(track_h * frac)
        if thumb_h < 22:
            thumb_h = 22
        y = int(track_h * first)
        max_y = track_h - thumb_h
        if y > max_y:
            y = max_y
        # Configure thumb size (height) and place (position). Avoid width/height in place().
        self.scroll_thumb.configure(height=thumb_h)
        if not self._thumb_placed:
            # Place once; then only adjust y position.
            self.scroll_thumb.place(relx=0.0, x=0, y=y, relwidth=1.0)
            self._thumb_placed = True
        else:
            self.scroll_thumb.place_configure(y=y)

    def _update_scroll_visibility(self):
        if self._needs_vertical_scroll():
            # Show only if hovered / active
            if self._scroll_hover:
                self._show_scrollbar()
        else:
            self._hide_scrollbar(force=True)

    def _bind_mousewheel(self):
        # Windows & Mac / Linux support
        self.tree.bind_all('<MouseWheel>', self._on_mousewheel)
        self.tree.bind_all('<Button-4>', self._on_mousewheel)
        self.tree.bind_all('<Button-5>', self._on_mousewheel)

    def _unbind_mousewheel(self):
        self.tree.unbind_all('<MouseWheel>')
        self.tree.unbind_all('<Button-4>')
        self.tree.unbind_all('<Button-5>')

    def _on_mousewheel(self, event):
        if event.num == 4:  # Linux scroll up
            delta = -1
        elif event.num == 5:  # Linux scroll down
            delta = 1
        else:  # Windows / Mac delta
            delta = -1 * int(event.delta / 120)
        if delta != 0:
            self.tree.yview_scroll(delta, 'units')
            self._on_tree_scroll(*self.tree.yview())

    def _auto_fit_height(self):
        if not self._auto_resize_window:
            return
        self.root.update_idletasks()
        if not self.file_list:
            desired = self.root.winfo_reqheight()
        else:
            desired = self.root.winfo_reqheight()
        # Only grow/shrink vertically up to a practical max (rows already capped)
        cur_w = self.root.winfo_width() or self.root.winfo_reqwidth()
        self.root.geometry(f"{cur_w}x{desired}")

    # ------------------------------------------------------------ UI BUILD
    def _build_ui(self):
        outer = ctk.CTkFrame(self.root, corner_radius=12)
        outer.pack(fill='both', expand=True, padx=14, pady=14)

        # SETTINGS SECTION --------------------------------------------------
        settings = ctk.CTkFrame(outer)
        settings.pack(fill='x', padx=8, pady=(8,10))

        # Row 0: Folder selection
        ctk.CTkLabel(settings, text="Folder:").grid(row=0, column=0, sticky='w', padx=4, pady=6)
        self.ent_folder = ctk.CTkEntry(settings, textvariable=self.folder_path, width=420)
        self.ent_folder.grid(row=0, column=1, sticky='w', pady=6)
        ctk.CTkButton(settings, text="Browse", width=90, command=self.browse_folder).grid(row=0, column=2, padx=6, pady=6)

        # Row 1: Prefix / Start / Digits / Order
        ctk.CTkLabel(settings, text="Prefix:").grid(row=1, column=0, sticky='w', padx=4)
        ctk.CTkEntry(settings, textvariable=self.prefix_text, width=180).grid(row=1, column=1, sticky='w', padx=(0,12))

        num_frame = ctk.CTkFrame(settings, fg_color="transparent")
        num_frame.grid(row=1, column=2, sticky='e', padx=4)
        ctk.CTkLabel(num_frame, text="Start").pack(side='left', padx=(0,4))
        # Hover spin entries (with hidden + / - buttons appearing on hover)
        self.start_spin = self._make_hover_spin(num_frame, self.start_number, width=50, minimum=0)
        ctk.CTkLabel(num_frame, text="Digits").pack(side='left', padx=(10,4))
        self.pad_spin = self._make_hover_spin(num_frame, self.padding, width=40, minimum=1)
        # Enable mouse-wheel increment for numeric fields (entries have no arrows by design)
        self._bind_number_wheel(self.start_spin, self.start_number, minimum=0)
        self._bind_number_wheel(self.pad_spin, self.padding, minimum=1)

        # Row 2: Order + Appearance
        order_frame = ctk.CTkFrame(settings, fg_color="transparent")
        order_frame.grid(row=2, column=0, columnspan=3, sticky='w', pady=(4,2), padx=2)
        ctk.CTkLabel(order_frame, text="Order:").pack(side='left')
        self.rb_name = ctk.CTkRadioButton(order_frame, text="Name", variable=self.order_mode, value='name', command=self.refresh_preview)
        self.rb_mtime = ctk.CTkRadioButton(order_frame, text="Modified", variable=self.order_mode, value='mtime', command=self.refresh_preview)
        self.rb_name.pack(side='left', padx=4)
        self.rb_mtime.pack(side='left', padx=4)

        ctk.CTkLabel(order_frame, text="Appearance:").pack(side='left', padx=(20,4))
        self.appearance_menu = ctk.CTkOptionMenu(order_frame,
                                                 values=["Light", "Dark", "System"],
                                                 variable=self.appearance_mode,
                                                 command=self._change_appearance)
        self.appearance_menu.pack(side='left')

        # PREVIEW SECTION ---------------------------------------------------
        preview_frame = ctk.CTkFrame(outer, corner_radius=10)
        preview_frame.pack(fill='both', expand=True, padx=8, pady=(0,8))

        ctk.CTkLabel(preview_frame, text="Preview (original → new)", anchor='w', font=ctk.CTkFont(size=13, weight='bold')).pack(fill='x', padx=10, pady=(10,4))

        tree_container = ctk.CTkFrame(preview_frame, fg_color='transparent')
        tree_container.pack(fill='both', expand=True, padx=10, pady=(0,10))

        # Treeview (ttk) for two-column mapping
        columns = ("old", "new")
        self.tree = ttk.Treeview(tree_container, columns=columns, show='headings', height=8, selectmode='extended', style='Flat.Treeview')
        self.tree.heading('old', text='Original Filename')
        self.tree.heading('new', text='New Filename')
        self.tree.column('old', width=340, anchor='w')
        self.tree.column('new', width=340, anchor='w')

        # Hidden modern scrollbar replacement (vertical only) & mousewheel scrolling
        self.tree.configure(yscrollcommand=self._on_tree_scroll)
        self.tree.grid(row=0, column=0, sticky='nsew')
        tree_container.rowconfigure(0, weight=1)
        tree_container.columnconfigure(0, weight=1)
        self._init_custom_scrollbar(tree_container)
        self.tree.bind('<Enter>', lambda e: (setattr(self, '_scroll_hover', True), self._bind_mousewheel(), self._show_scrollbar()))
        self.tree.bind('<Leave>', lambda e: (setattr(self, '_scroll_hover', False), self._unbind_mousewheel(), self._schedule_hide_scrollbar()))
        self.tree.bind('<Configure>', lambda e: self._update_scroll_thumb())

        # Reorder buttons
        reorder_frame = ctk.CTkFrame(preview_frame, fg_color='transparent')
        reorder_frame.pack(fill='x', padx=10, pady=(0,10))
        ctk.CTkButton(reorder_frame, text="Move Up", width=110, command=self.move_up).pack(side='left')
        ctk.CTkButton(reorder_frame, text="Move Down", width=110, command=self.move_down).pack(side='left', padx=8)
        ctk.CTkButton(reorder_frame, text="Refresh Preview", command=self.refresh_preview).pack(side='left', padx=(16,0))
        ctk.CTkButton(reorder_frame, text="Rename", fg_color='#16a34a', hover_color='#15803d', command=self.rename_files).pack(side='right')

        # FOOTER ------------------------------------------------------------
        footer = ctk.CTkLabel(outer, text="Tip: Multi-select rows with Shift/Ctrl, then use Move Up/Down.", anchor='w', font=ctk.CTkFont(size=11))
        footer.pack(fill='x', padx=12, pady=(0,4))

    # ------------------------------------------------------------ APPEARANCE
    def _change_appearance(self, mode: str):
        ctk.set_appearance_mode(mode)
        self._style_treeview()  # restyle tree
        self._refresh_tree_from_file_list() if self.file_list else None

    def _current_row_colors(self):
        # Updated to use theme palette
        palette = self._get_theme_palette()
        return palette['row_even'], palette['row_odd'], palette['row_fg']

    # ------------------------------------------------------------ FILE LIST
    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_path.set(folder)
            self.refresh_preview()

    def _list_files(self):
        folder = self.folder_path.get()
        if not folder or not os.path.isdir(folder):
            return []
        files = []
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            if os.path.isfile(path):
                files.append(path)
        if self.order_mode.get() == 'mtime':
            files.sort(key=lambda p: os.path.getmtime(p))
        else:
            files.sort(key=lambda p: os.path.basename(p).lower())
        return files

    # ------------------------------------------------------------ PREVIEW
    def refresh_preview(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        files = self._list_files()
        # removed slicing so all files are included; scrolling will handle >10
        if not files:
            self.file_list = []
            self.tree.configure(height=1)
            self._update_scroll_visibility()
            self._auto_fit_height()
            return
        self.file_list = files.copy()
        start = self.start_number.get()
        pad = self.padding.get()
        prefix = self.prefix_text.get().strip()
        even_color, odd_color, fg = self._current_row_colors()
        for idx, filepath in enumerate(self.file_list):
            base = os.path.basename(filepath)
            ext = os.path.splitext(base)[1]
            counter = str(start + idx).zfill(pad)
            new_name = f"{prefix} {counter}{ext}" if prefix else f"{counter}{ext}"
            tag = 'even' if idx % 2 == 0 else 'odd'
            self.tree.insert('', 'end', values=(base, new_name), tags=(tag,))
        self.tree.tag_configure('even', background=even_color, foreground=fg)
        self.tree.tag_configure('odd', background=odd_color, foreground=fg)
        # Adjust displayed rows & window height
        display_rows = min(len(self.file_list), self._max_tree_rows)
        self.tree.configure(height=max(1, display_rows))
        self._update_scroll_visibility()
        self._auto_fit_height()

    # ------------------------------------------------------------ REORDER
    def move_up(self):
        selection = self.tree.selection()
        if not selection:
            return
        indices = sorted(self.tree.index(it) for it in selection)
        if indices[0] == 0:
            return
        block = [self.file_list[i] for i in indices]
        for i in reversed(indices):
            del self.file_list[i]
        insert_at = indices[0] - 1
        self.file_list[insert_at:insert_at] = block
        new_range = list(range(insert_at, insert_at + len(block)))
        self._refresh_tree_from_file_list(select_indices=new_range, focus_index=insert_at)
        self._flash_rows(new_range)

    def move_down(self):
        selection = self.tree.selection()
        if not selection:
            return
        indices = sorted(self.tree.index(it) for it in selection)
        if indices[-1] == len(self.file_list) - 1:
            return
        block = [self.file_list[i] for i in indices]
        for i in reversed(indices):
            del self.file_list[i]
        insert_at = indices[-1] - (len(block) - 1) + 1
        if insert_at > len(self.file_list):
            insert_at = len(self.file_list)
        self.file_list[insert_at:insert_at] = block
        new_range = list(range(insert_at, insert_at + len(block)))
        self._refresh_tree_from_file_list(select_indices=new_range, focus_index=new_range[-1])
        self._flash_rows(new_range)

    def _refresh_tree_from_file_list(self, select_indices=None, focus_index=None):
        # Preserve preview numbering after manual reordering
        self.tree.delete(*self.tree.get_children())
        start = self.start_number.get()
        pad = self.padding.get()
        prefix = self.prefix_text.get().strip()
        even_color, odd_color, fg = self._current_row_colors()
        for idx, filepath in enumerate(self.file_list):
            base = os.path.basename(filepath)
            ext = os.path.splitext(base)[1]
            counter = str(start + idx).zfill(pad)
            new_name = f"{prefix} {counter}{ext}" if prefix else f"{counter}{ext}"
            tag = 'even' if idx % 2 == 0 else 'odd'
            self.tree.insert('', 'end', values=(base, new_name), tags=(tag,))
        self.tree.tag_configure('even', background=even_color, foreground=fg)
        self.tree.tag_configure('odd', background=odd_color, foreground=fg)
        display_rows = min(len(self.file_list), self._max_tree_rows)
        self.tree.configure(height=max(1, display_rows))
        if select_indices is not None:
            children = self.tree.get_children()
            self.tree.selection_set([children[i] for i in select_indices if 0 <= i < len(children)])
            if focus_index is not None and 0 <= focus_index < len(children):
                self.tree.see(children[focus_index])
        self._update_scroll_visibility()
        self._auto_fit_height()

    def _flash_rows(self, indices):
        colors = ['#3b82f6', '#60a5fa', '#93c5fd', '#60a5fa', '#3b82f6']
        children = self.tree.get_children()
        targets = [children[i] for i in indices if 0 <= i < len(children)]
        even_color, odd_color, fg = self._current_row_colors()  # unpack 3 values
        def step(n=0):
            if n >= len(colors):
                for i, item in enumerate(children):
                    base_tag = 'even' if i % 2 == 0 else 'odd'
                    self.tree.item(item, tags=(base_tag,))
                # Restore both background and foreground
                self.tree.tag_configure('even', background=even_color, foreground=fg)
                self.tree.tag_configure('odd', background=odd_color, foreground=fg)
                return
            col = colors[n]
            tag_name = f'flash{n}'
            self.tree.tag_configure(tag_name, background=col, foreground='white')
            for t in targets:
                self.tree.item(t, tags=(tag_name,))
            self.root.after(110, lambda: step(n+1))
        step()

    # ------------------------------------------------------------ RENAME
    def rename_files(self):
        folder = self.folder_path.get()
        if not folder:
            messagebox.showerror("Error", "Select a folder.")
            return
        items = self.tree.get_children()
        if not items:
            messagebox.showinfo("Info", "Nothing to rename.")
            return
        operations = []
        for idx, item in enumerate(items):
            old_path = self.file_list[idx]
            old_name = os.path.basename(old_path)
            new_name = self.tree.item(item, 'values')[1]
            if old_name == new_name:
                continue
            new_path = os.path.join(folder, new_name)
            operations.append((old_path, new_path))
        conflicts = [dst for _, dst in operations if os.path.exists(dst)]
        if conflicts:
            messagebox.showerror("Conflict", f"Target exists: {os.path.basename(conflicts[0])}\nAborting.")
            return
        try:
            for old_path, new_path in operations:
                os.rename(old_path, new_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed: {e}")
            return
        messagebox.showinfo("Done", f"Renamed {len(operations)} files.")
        self.refresh_preview()

    def _bind_number_wheel(self, entry, var: tk.IntVar, minimum=0, maximum=None):
        def on_wheel(event):
            # Determine scroll direction
            if event.num == 4 or getattr(event, 'delta', 0) > 0:  # up
                delta = 1
            elif event.num == 5 or getattr(event, 'delta', 0) < 0:  # down
                delta = -1
            else:
                delta = 0
            try:
                value = int(var.get())
            except Exception:
                value = minimum if minimum is not None else 0
            value += delta
            if minimum is not None and value < minimum:
                value = minimum
            if maximum is not None and value > maximum:
                value = maximum
            var.set(value)
            # Auto refresh preview when changing numbering inputs
            self.refresh_preview()
            return 'break'
        # Bind platform-specific events to the entry (not globally)
        entry.bind('<MouseWheel>', on_wheel, add='+')      # Windows / macOS
        entry.bind('<Button-4>', on_wheel, add='+')        # Linux scroll up
        entry.bind('<Button-5>', on_wheel, add='+')        # Linux scroll down

    def _make_hover_spin(self, parent, var: tk.IntVar, width=60, minimum=0, maximum=None):
        # Create a borderless frame to mimic a single input box
        container = ctk.CTkFrame(parent, fg_color='transparent', corner_radius=0)
        container.pack(side='left', padx=0, pady=0)
        # Use grid for tight alignment
        entry = ctk.CTkEntry(container, textvariable=var, width=width, height=28, border_width=0)
        entry.grid(row=0, column=0, sticky='nsew', padx=(0,0), pady=0)
        # Arrow button frame (vertical)
        btn_frame = ctk.CTkFrame(container, width=16, height=28, fg_color='transparent', corner_radius=0)
        btn_frame.grid(row=0, column=1, sticky='ns', padx=(0,0), pady=0)
        btn_frame.grid_propagate(False)
        # Fixed 8pt font for arrows
        font_small = ctk.CTkFont(size=8, weight='bold')
        # Arrow buttons (fixed size, do not resize on hover)
        arrow_up = ctk.CTkButton(btn_frame, text='▲', width=16, height=12, corner_radius=0,
                                 fg_color='transparent', hover_color=self.accent_color,
                                 font=font_small, command=lambda: self._adjust_spin_value(var, 1, minimum, maximum), border_width=0)
        arrow_down = ctk.CTkButton(btn_frame, text='▼', width=16, height=12, corner_radius=0,
                                   fg_color='transparent', hover_color=self.accent_color,
                                   font=font_small, command=lambda: self._adjust_spin_value(var, -1, minimum, maximum), border_width=0)
        arrow_up.pack(fill='x', padx=0, pady=(1,0))
        arrow_down.pack(fill='x', padx=0, pady=(0,1))
        # Hide arrows until hover
        arrow_up.pack_forget()
        arrow_down.pack_forget()
        state = {'visible': False, 'hide_job': None}
        def show(_=None):
            if state['hide_job']:
                self.root.after_cancel(state['hide_job'])
                state['hide_job'] = None
            if not state['visible']:
                arrow_up.pack(fill='x', padx=0, pady=(1,0))
                arrow_down.pack(fill='x', padx=0, pady=(0,1))
                state['visible'] = True
        def schedule_hide():
            if state['hide_job']:
                self.root.after_cancel(state['hide_job'])
            def do_hide():
                arrow_up.pack_forget()
                arrow_down.pack_forget()
                state['visible'] = False
            state['hide_job'] = self.root.after(350, do_hide)
        def on_leave(_=None):
            schedule_hide()
        for w in (container, entry, btn_frame, arrow_up, arrow_down):
            w.bind('<Enter>', show)
            w.bind('<Leave>', on_leave)
        # Make entry expand to fill container
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        return entry

    def _adjust_spin_value(self, var: tk.IntVar, delta: int, minimum=None, maximum=None):
        try:
            value = int(var.get())
        except Exception:
            value = minimum if minimum is not None else 0
        value += delta
        if minimum is not None and value < minimum:
            value = minimum
        if maximum is not None and value > maximum:
            value = maximum
        var.set(value)
        self.refresh_preview()

# ------------------------------------------------------------ ENTRY POINT

def main():
    root = ctk.CTk()
    FolderRenamerGUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()
