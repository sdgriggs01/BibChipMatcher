#!/usr/bin/env python3
"""Graphical sibling to the CLI for the Bib chip matcher."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Optional

from cli import build_parser, run_pipeline
from utils.bib_chip_matcher_utils import extract_team_names_from_sheets, parse_google_sheet_id
from utils.gui_support import build_cli_args, build_settings_payload, read_settings_cache, write_settings_cache
from utils.version import __version__

PROJECT_URL = 'https://github.com/sdgriggs01/BibChipMatcher'


def resource_path(relative: str) -> Path:
    """Resolve a bundled resource path for both source and frozen (PyInstaller) runs."""
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    return base / relative


class BibChipMatcherGUI(tk.Tk):
    """Simple Tkinter GUI that mirrors the CLI options."""

    def __init__(self) -> None:
        super().__init__()
        self.title('Bib Chip Matcher')
        self.geometry('720x520')
        self.minsize(680, 480)

        self._build_menu()
        self._build_ui()
        self.sheet_id_var.trace_add('write', self._on_sheet_id_change)
        self._restore_saved_settings()

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label='User Guide', command=self._show_user_guide)
        help_menu.add_separator()
        help_menu.add_command(label='About', command=self._show_about)
        menubar.add_cascade(label='Help', menu=help_menu)
        self.config(menu=menubar)

    def _show_user_guide(self) -> None:
        guide_path = resource_path('docs/userGuide.md')
        try:
            text = guide_path.read_text(encoding='utf-8')
        except OSError as exc:
            messagebox.showerror('User Guide', f'Unable to open the user guide: {exc}')
            return

        window = tk.Toplevel(self)
        window.title('Bib Chip Matcher - User Guide')
        window.geometry('720x600')
        text_widget = scrolledtext.ScrolledText(window, wrap='word', font=('Segoe UI', 10))
        text_widget.pack(fill='both', expand=True, padx=8, pady=8)
        text_widget.insert('1.0', text)
        text_widget.configure(state='disabled')

    def _show_about(self) -> None:
        messagebox.showinfo(
            'About Bib Chip Matcher',
            f'Bib Chip Matcher {__version__}\n\n'
            "Assigns timing chips to cross-country athletes from a team roster "
            "spreadsheet and generates HyTek entries.\n\n"
            f'{PROJECT_URL}',
        )

    def _build_ui(self) -> None:
        container = ttk.Frame(self, padding=16)
        container.pack(fill='both', expand=True)

        ttk.Label(container, text='Bib Chip Matcher', font=('Segoe UI', 16, 'bold')).pack(anchor='w')
        ttk.Label(container, text='Fill in the same options as the command-line interface.', foreground='#555').pack(anchor='w', pady=(0, 12))

        self.entries: dict[str, ttk.Entry] = {}
        self.sheet_id_var = tk.StringVar(value='')
        self.var_measure = tk.StringVar(value='M')
        self.team_vars: dict[str, tk.BooleanVar] = {}
        self.team_list_frame: Optional[ttk.Frame] = None
        self.team_options: list[str] = []
        self.spinner_var = tk.StringVar(value='')
        self.spinner_label: Optional[ttk.Label] = None
        self._sheet_id_refresh_job: Optional[str] = None
        self.spinner_frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.spinner_index = 0
        self.spinner_job: Optional[str] = None
        self.busy = False
        self._pending_selected_teams: list[str] = []

        basic_fields = [
            ('sheet-id', 'Sheet ID or URL', '', 'entry'),
        ]

        advanced_fields = [
            ('chip-map', 'Chip map file', 'input/chipLabel_chipID_map.txt', 'file'),
            ('sheet-gid', 'Sheet GID (optional)', '', 'entry'),
            ('output-dir', 'Output directory', 'output', 'dir'),
            ('output-prefix', 'Output prefix (optional)', '', 'entry'),
        ]

        notebook = ttk.Notebook(container)
        notebook.pack(fill='both', expand=True)

        basic_tab = ttk.Frame(notebook, padding=10)
        advanced_tab = ttk.Frame(notebook, padding=10)
        notebook.add(basic_tab, text='Basic')
        notebook.add(advanced_tab, text='Advanced')

        for name, label_text, default, kind in basic_fields:
            if name == 'sheet-id':
                row = ttk.Frame(basic_tab)
                row.pack(fill='x', pady=4)
                ttk.Label(row, text=label_text, width=24, anchor='w').pack(side='left')
                entry = ttk.Entry(row, textvariable=self.sheet_id_var)
                entry.insert(0, default)
                entry.pack(side='left', fill='x', expand=True)
                self.entries[name] = entry
            else:
                self._add_field_row(basic_tab, name, label_text, default, kind)

        event_row = ttk.Frame(basic_tab)
        event_row.pack(fill='x', pady=4)
        ttk.Label(event_row, text='Event code', width=18, anchor='w').pack(side='left')
        self.event_code_var = tk.StringVar(value='5000')
        event_code_combo = ttk.Combobox(event_row, textvariable=self.event_code_var, values=['3000', '5000'], state='readonly', width=20)
        event_code_combo.pack(side='left', fill='x')

        self.team_frame = ttk.LabelFrame(basic_tab, text='Teams', padding=10)
        self.team_frame.pack(fill='x', pady=4)
        team_controls = ttk.Frame(self.team_frame)
        team_controls.pack(fill='x')
        ttk.Button(team_controls, text='Clear all', command=self._clear_team_selections).pack(side='left')
        ttk.Label(team_controls, text='Select the teams to include.').pack(side='left', padx=(8, 0))
        self.spinner_label = ttk.Label(team_controls, textvariable=self.spinner_var)
        self.spinner_label.pack(side='left', padx=(8, 0))

        self.team_canvas = tk.Canvas(self.team_frame, height=170, highlightthickness=0)
        self.team_scrollbar = ttk.Scrollbar(self.team_frame, orient='vertical', command=self.team_canvas.yview)
        self.team_canvas.configure(yscrollcommand=self.team_scrollbar.set)
        self.team_scrollbar.pack(side='right', fill='y')
        self.team_canvas.pack(fill='both', expand=True, pady=(8, 0))
        self.team_list_frame = ttk.Frame(self.team_canvas)
        self.team_canvas_window = self.team_canvas.create_window((0, 0), window=self.team_list_frame, anchor='nw')
        self.team_canvas.bind('<Configure>', self._on_team_canvas_configure)
        self.team_list_frame.bind('<Configure>', self._on_team_frame_configure)
        self.team_canvas.bind_all('<MouseWheel>', self._on_team_mouse_wheel)
        self.team_canvas.bind_all('<Shift-MouseWheel>', self._on_team_mouse_wheel)

        for name, label_text, default, kind in advanced_fields:
            self._add_field_row(advanced_tab, name, label_text, default, kind)

        measure_row = ttk.Frame(advanced_tab)
        measure_row.pack(fill='x', pady=4)
        ttk.Label(measure_row, text='Event measure', width=24, anchor='w').pack(side='left')
        ttk.Combobox(measure_row, textvariable=self.var_measure, values=['M', 'E'], state='readonly', width=20).pack(side='left', fill='x')

        button_row = ttk.Frame(container)
        button_row.pack(fill='x', pady=(16, 0))
        ttk.Button(button_row, text='Run', command=self._run).pack(side='right')

    def _app_data_dir(self) -> Path:
        return Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming')) / 'BibChipMatcher'

    def _cache_settings(self) -> None:
        cache_path = self._app_data_dir() / 'settings.json'
        settings = build_settings_payload(
            sheet_id=self.entries['sheet-id'].get(),
            chip_map=self.entries['chip-map'].get(),
            sheet_gid=self.entries['sheet-gid'].get(),
            output_dir=self.entries['output-dir'].get(),
            output_prefix=self.entries['output-prefix'].get(),
            event_code=self.event_code_var.get(),
            event_measure=self.var_measure.get(),
            selected_teams=self._selected_team_names(),
        )
        write_settings_cache(cache_path, settings)

    def _restore_saved_settings(self) -> None:
        cache_path = self._app_data_dir() / 'settings.json'
        settings = read_settings_cache(cache_path)
        if not settings:
            return

        if 'sheet-id' in settings and settings['sheet-id']:
            self.sheet_id_var.set(settings['sheet-id'])
        if 'chip-map' in settings:
            self.entries['chip-map'].delete(0, tk.END)
            self.entries['chip-map'].insert(0, settings['chip-map'])
        if 'sheet-gid' in settings:
            self.entries['sheet-gid'].delete(0, tk.END)
            self.entries['sheet-gid'].insert(0, settings['sheet-gid'])
        if 'output-dir' in settings:
            self.entries['output-dir'].delete(0, tk.END)
            self.entries['output-dir'].insert(0, settings['output-dir'])
        if 'output-prefix' in settings:
            self.entries['output-prefix'].delete(0, tk.END)
            self.entries['output-prefix'].insert(0, settings['output-prefix'])
        if 'event-code' in settings and settings['event-code']:
            self.event_code_var.set(settings['event-code'])
        if 'event-measure' in settings and settings['event-measure']:
            self.var_measure.set(settings['event-measure'])
        if 'selected-teams' in settings and isinstance(settings['selected-teams'], list):
            self._pending_selected_teams = [team for team in settings['selected-teams'] if isinstance(team, str)]

    def _set_busy(self, busy: bool, message: str = '') -> None:
        self.busy = busy
        if busy:
            self.spinner_index = 0
            self._start_spinner(message)
        else:
            self._stop_spinner()
            self.spinner_var.set('')
            if self.spinner_label is not None:
                self.spinner_label.configure(text='')
        self.update_idletasks()

    def _start_spinner(self, message: str) -> None:
        if self.spinner_job is not None:
            self.after_cancel(self.spinner_job)
        self._update_spinner_message(message)
        self.spinner_job = self.after(80, self._tick_spinner, message)

    def _tick_spinner(self, message: str) -> None:
        if not self.busy:
            return
        self.spinner_var.set(self.spinner_frames[self.spinner_index])
        self.spinner_index = (self.spinner_index + 1) % len(self.spinner_frames)
        self._update_spinner_message(message)
        self.spinner_job = self.after(80, self._tick_spinner, message)

    def _stop_spinner(self) -> None:
        if self.spinner_job is not None:
            self.after_cancel(self.spinner_job)
            self.spinner_job = None

    def _update_spinner_message(self, message: str) -> None:
        if self.spinner_label is not None:
            self.spinner_label.configure(text=f"{self.spinner_var.get()} {message}".strip())

    def _load_saved_sheet_teams(self) -> None:
        sheet_id = self.entries['sheet-id'].get().strip()
        if sheet_id:
            self._refresh_team_list()

    def _on_sheet_id_change(self, *_args: object) -> None:
        if self._sheet_id_refresh_job is not None:
            self.after_cancel(self._sheet_id_refresh_job)
        self._sheet_id_refresh_job = self.after(500, self._refresh_team_list)

    def _refresh_team_list(self) -> None:
        sheet_id = self.entries['sheet-id'].get().strip()
        if not sheet_id:
            self._clear_team_options()
            return

        self._set_busy(True, 'Loading teams...')
        self._disable_controls(True)
        thread = threading.Thread(target=self._load_team_options_worker, args=(sheet_id,), daemon=True)
        thread.start()

    def _load_team_options(self) -> None:
        self._cache_settings()
        self._refresh_team_list()

    def _clear_team_options(self) -> None:
        if self.team_list_frame is None:
            return
        for widget in self.team_list_frame.winfo_children():
            widget.destroy()
        self.team_options = []
        self.team_vars = {}
        self.team_canvas.configure(scrollregion=(0, 0, 0, 0))
        self._disable_controls(False)

    def _load_team_options_worker(self, sheet_id: str) -> None:
        sheet_gid = self.entries['sheet-gid'].get().strip() if 'sheet-gid' in self.entries else ''
        try:
            from utils.bib_chip_matcher_utils import download_google_sheet_xlsx

            sheets = download_google_sheet_xlsx(parse_google_sheet_id(sheet_id), sheet_gid or None)
            team_options = extract_team_names_from_sheets(sheets)
        except Exception as exc:  # pragma: no cover - GUI feedback path
            self.after(0, self._handle_team_load_error, str(exc))
            return

        self.after(0, self._handle_team_load_result, team_options)

    def _handle_team_load_error(self, message: str) -> None:
        self._set_busy(False)
        self._disable_controls(False)
        messagebox.showerror('Unable to load teams', message)

    def _handle_team_load_result(self, team_options: list[str]) -> None:
        self._set_busy(False)
        self._disable_controls(False)
        self.team_options = team_options
        if not self.team_options:
            messagebox.showwarning('No teams found', 'No team names were found in the selected sheet.')
            return
        self._render_team_options()

    def _on_team_canvas_configure(self, event: tk.Event) -> None:
        width = max(event.width, 1)
        self.team_canvas.itemconfig(self.team_canvas_window, width=width)
        self.team_canvas.configure(scrollregion=self.team_canvas.bbox('all'))

    def _on_team_frame_configure(self, event: tk.Event) -> None:
        self.team_canvas.configure(scrollregion=self.team_canvas.bbox('all'))
        self.team_canvas.itemconfig(self.team_canvas_window, width=max(event.width, 1))

    def _on_team_mouse_wheel(self, event: tk.Event) -> None:
        if self.team_canvas.winfo_exists():
            self.team_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

    def _render_team_options(self) -> None:
        for widget in self.team_list_frame.winfo_children():
            widget.destroy()
        self.team_vars = {}
        for team_name in self.team_options:
            var = tk.BooleanVar(value=False)
            self.team_vars[team_name] = var
            row = ttk.Frame(self.team_list_frame)
            row.pack(fill='x', anchor='w', pady=1)
            ttk.Checkbutton(row, text=team_name, variable=var).pack(side='left')
        if self._pending_selected_teams:
            for team_name in self._pending_selected_teams:
                if team_name in self.team_vars:
                    self.team_vars[team_name].set(True)
            self._pending_selected_teams = []
        self.team_list_frame.update_idletasks()
        self.team_canvas.configure(scrollregion=self.team_canvas.bbox('all'))
        self.team_canvas.itemconfig(self.team_canvas_window, width=max(self.team_canvas.winfo_width(), 1))

    def _clear_team_selections(self) -> None:
        for var in self.team_vars.values():
            var.set(False)

    def _selected_team_names(self) -> list[str]:
        return [team for team, var in self.team_vars.items() if var.get()]

    def _disable_controls(self, disabled: bool) -> None:
        for child in self.winfo_children():
            if isinstance(child, ttk.Frame):
                self._set_widget_state(child, not disabled)
        self.update_idletasks()

    def _set_widget_state(self, widget: tk.Widget, enabled: bool) -> None:
        try:
            if isinstance(widget, ttk.Button):
                widget.state(["!disabled"] if enabled else ["disabled"])
            elif isinstance(widget, ttk.Entry):
                widget.state(["!disabled"] if enabled else ["disabled"])
            elif isinstance(widget, ttk.Combobox):
                widget.state(["!disabled"] if enabled else ["disabled"])
            elif isinstance(widget, ttk.Checkbutton):
                widget.state(["!disabled"] if enabled else ["disabled"])
            elif isinstance(widget, ttk.Frame):
                for child in widget.winfo_children():
                    self._set_widget_state(child, enabled)
            elif isinstance(widget, tk.Canvas):
                for child in widget.winfo_children():
                    self._set_widget_state(child, enabled)
        except Exception:
            pass

    def _add_field_row(self, parent: ttk.Frame, name: str, label_text: str, default: str, kind: str) -> None:
        row = ttk.Frame(parent)
        row.pack(fill='x', pady=4)
        ttk.Label(row, text=label_text, width=24, anchor='w').pack(side='left')
        if kind == 'entry':
            entry = ttk.Entry(row)
            entry.insert(0, default)
            entry.pack(side='left', fill='x', expand=True)
            self.entries[name] = entry
        elif kind == 'file':
            frame = ttk.Frame(row)
            frame.pack(side='left', fill='x', expand=True)
            entry = ttk.Entry(frame)
            entry.insert(0, default)
            entry.pack(side='left', fill='x', expand=True)
            self.entries[name] = entry
            ttk.Button(frame, text='Browse', command=lambda n=name, e=entry: self._browse_file(n, e)).pack(side='left', padx=(6, 0))
        elif kind == 'dir':
            frame = ttk.Frame(row)
            frame.pack(side='left', fill='x', expand=True)
            entry = ttk.Entry(frame)
            entry.insert(0, default)
            entry.pack(side='left', fill='x', expand=True)
            self.entries[name] = entry
            ttk.Button(frame, text='Browse', command=lambda n=name, e=entry: self._browse_directory(n, e)).pack(side='left', padx=(6, 0))

    def _browse_file(self, field_name: str, entry: ttk.Entry) -> None:
        path = filedialog.askopenfilename(title=f'Select {field_name}')
        if path:
            entry.delete(0, tk.END)
            entry.insert(0, path)

    def _browse_directory(self, field_name: str, entry: ttk.Entry) -> None:
        path = filedialog.askdirectory(title=f'Select {field_name}')
        if path:
            entry.delete(0, tk.END)
            entry.insert(0, path)

    def _collect_args(self) -> Optional[argparse.Namespace]:
        parser = build_parser()
        selected_teams = self._selected_team_names()
        if not selected_teams:
            messagebox.showerror('Missing teams', 'Select at least one team from the Teams box.')
            return None

        args = build_cli_args(
            chip_map=self.entries['chip-map'].get().strip(),
            sheet_id=self.entries['sheet-id'].get().strip(),
            sheet_gid=self.entries['sheet-gid'].get().strip(),
            teams=','.join(selected_teams),
            output_dir=self.entries['output-dir'].get().strip(),
            output_prefix=self.entries['output-prefix'].get().strip(),
            event_code=self.event_code_var.get().strip(),
            event_measure=self.var_measure.get().strip(),
        )
        try:
            return parser.parse_args(args)
        except SystemExit:
            return None

    def _run(self) -> None:
        self._cache_settings()
        args = self._collect_args()
        if args is None:
            return
        self._set_busy(True, 'Running...')
        self._disable_controls(True)
        thread = threading.Thread(target=self._run_worker, args=(args,), daemon=True)
        thread.start()

    def _run_worker(self, args: argparse.Namespace) -> None:
        try:
            result = run_pipeline(args)
        except Exception as exc:  # pragma: no cover - GUI feedback path
            self.after(0, self._handle_run_error, str(exc))
            return
        self.after(0, self._handle_run_result, result)

    def _handle_run_error(self, message: str) -> None:
        self._set_busy(False)
        self._disable_controls(False)
        messagebox.showerror('Error', message)

    def _handle_run_result(self, result: int) -> None:
        self._set_busy(False)
        self._disable_controls(False)
        if result == 0:
            messagebox.showinfo('Success', 'Processing completed successfully.')
        else:
            messagebox.showwarning('Processing failed', 'The pipeline did not complete successfully.')


def main() -> None:
    app = BibChipMatcherGUI()
    app.mainloop()


if __name__ == '__main__':
    main()
