from __future__ import annotations
import tkinter as tk
from tkinter import ttk, font
from tkinter.scrolledtext import ScrolledText as TkScrolledText
from theme import BG, SURFACE, TEXT, MUTED, ACCENT, SIDEBAR, BORDER

def rounded(canvas, x1, y1, x2, y2, radius=12, **kwargs):
    r = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
    points = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(points, smooth=True, splinesteps=20, **kwargs)

class Button(tk.Canvas):

    def __init__(self, parent, text='', command=None, style='', width=None, height=38, **kwargs):
        self.text = text
        self.command = command
        self.accent = 'Accent' in style
        self.danger = 'Danger' in style
        self._disabled = False
        self._pressed = False
        self._hover = False
        self._focused = False
        self._font = font.Font(family='Segoe UI', size=10, weight='bold' if self.accent else 'normal')
        background = kwargs.pop('bg', None) or ttk.Style(parent).lookup(parent.cget('style') if isinstance(parent, ttk.Frame) else 'TFrame', 'background') or BG
        super().__init__(parent, width=width or self._font.measure(text) + 30, height=height, bg=background, highlightthickness=0, bd=0, takefocus=1, cursor='hand2', **kwargs)
        self.bind('<Configure>', lambda event: self.paint())
        self.bind('<Enter>', lambda event: self._feedback(hover=True))
        self.bind('<Leave>', lambda event: self._feedback(hover=False))
        self.bind('<ButtonPress-1>', self.press)
        self.bind('<ButtonRelease-1>', self.release)
        self.bind('<FocusIn>', lambda event: self._feedback(focused=True))
        self.bind('<FocusOut>', lambda event: self._feedback(focused=False))
        self.bind('<space>', self.keyboard_invoke)
        self.bind('<Return>', self.keyboard_invoke)
        self.paint()

    def _feedback(self, hover=None, focused=None):
        if hover is not None:
            self._hover = hover
        if focused is not None:
            self._focused = focused
        self.paint()

    def press(self, event):
        if not self._disabled:
            self.focus_set()
            self._pressed = True
            self.paint()

    def release(self, event):
        pressed = self._pressed
        self._pressed = False
        self.paint()
        if pressed and 0 <= event.x < self.winfo_width() and (0 <= event.y < self.winfo_height()):
            self.invoke()

    def invoke(self):
        if not self._disabled and self.command:
            return self.command()

    def keyboard_invoke(self, event=None):
        self.invoke()
        return 'break'

    def state(self, states=None):
        if states is None:
            return ('disabled',) if self._disabled else ()
        if 'disabled' in states:
            self._disabled = True
        if '!disabled' in states:
            self._disabled = False
        self.configure(cursor='arrow' if self._disabled else 'hand2')
        self.paint()

    def paint(self):
        self.delete('all')
        w = max(self.winfo_width(), int(self.cget('width')))
        h = int(self.cget('height'))
        color = ACCENT if self.accent else '#E9EBEF'
        fg = SURFACE if self.accent else '#B52D27' if self.danger else TEXT
        if self._disabled:
            (color, fg) = ('#EBEDF0', '#90949B')
        elif self._pressed and self._hover:
            color = '#0057B6' if self.accent else '#D2D6DE'
        elif self._hover:
            color = '#0075EF' if self.accent else '#DEE2E9'
        rounded(self, 2, 2, w - 2, h - 2, 10, fill=color, outline=ACCENT if self._focused else color, width=2)
        self.create_text(w / 2, h / 2, text=self.text, fill=fg, font=self._font)

class NavigationButton(Button):

    def __init__(self, parent, text, command, icon='grid', badge='', **kwargs):
        self.selected = False
        self.icon = icon
        self.badge = badge
        super().__init__(parent, text=text, command=command, width=186, height=44, bg=SIDEBAR, **kwargs)

    def paint(self):
        self.delete('all')
        w = max(self.winfo_width(), int(self.cget('width')))
        if self.selected or self._hover or self._pressed:
            rounded(self, 2, 2, w - 2, 42, 11, fill='#D4DFED' if self._pressed else '#FFFFFF' if self.selected else '#E0E3E9', outline='')
        color = ACCENT if self.selected else MUTED
        if self.icon == 'grid':
            for x in (17, 26):
                for y in (15, 24):
                    self.create_rectangle(x, y, x + 6, y + 6, fill=color, outline='')
        elif self.icon == 'history':
            self.create_oval(17, 14, 33, 30, outline=color, width=2)
            self.create_line(25, 17, 25, 22, 29, 24, fill=color, width=2)
        elif self.icon == 'chart':
            for (x, y) in [(18, 23), (24, 17), (30, 12)]:
                self.create_rectangle(x, y, x + 3, 30, fill=color, outline='')
        else:
            self.create_rectangle(17, 14, 32, 30, outline=color, width=2)
            self.create_line(21, 14, 21, 30, fill=color, width=2)
        self.create_text(44, 22, text=self.text, anchor='w', fill=TEXT, font=('Segoe UI', 10, 'bold' if self.selected else 'normal'))
        if self.badge:
            self.create_text(w - 18, 22, text=self.badge, anchor='e', fill=MUTED, font=('Segoe UI', 9))

    def set_selected(self, value):
        self.selected = value
        self.paint()

class StatCard(tk.Canvas):

    def __init__(self, parent, label, caption, color=TEXT, command=None):
        super().__init__(parent, height=116, bg=BG, highlightthickness=0, bd=0, takefocus=bool(command), cursor='hand2' if command else 'arrow')
        (self.label, self.caption, self.color, self.value) = (label, caption, color, 0)
        self.command = command
        self.bind('<Configure>', lambda event: self.paint())
        self.bind('<ButtonRelease-1>', self.release)
        self.bind('<Return>', lambda event: self.command() if self.command else None)
        self.bind('<ButtonPress-1>', lambda event: self.paint(pressed=True))

    def release(self, event):
        self.paint()
        if self.command and 0 <= event.x < self.winfo_width() and (0 <= event.y < self.winfo_height()):
            self.command()

    def set(self, value):
        self.value = value
        self.paint()

    def paint(self, pressed=False):
        self.delete('all')
        w = max(140, self.winfo_width())
        rounded(self, 1, 1, w - 2, 114, 16, fill='#EDF2F8' if pressed else SURFACE, outline=BORDER)
        self.create_text(18, 23, text=self.label, anchor='w', fill=MUTED, font=('Segoe UI', 9))
        self.create_text(17, 59, text=str(self.value), anchor='w', fill=self.color, font=('Segoe UI', 27, 'bold'))
        self.create_text(18, 94, text=self.caption, anchor='w', fill=MUTED, font=('Segoe UI', 9))

class ScrolledText(TkScrolledText):

    def __init__(self, parent, **kwargs):
        kwargs.setdefault('bg', SURFACE)
        kwargs.setdefault('fg', TEXT)
        kwargs.setdefault('selectbackground', '#DDEBFC')
        kwargs.setdefault('selectforeground', TEXT)
        kwargs.setdefault('highlightthickness', 0)
        kwargs.setdefault('spacing1', 2)
        kwargs.setdefault('spacing3', 4)
        super().__init__(parent, **kwargs)
        self.frame.configure(bg=kwargs['bg'])
        self.vbar.destroy()
        self.vbar = ttk.Scrollbar(self.frame, command=self.yview, orient='vertical')
        self.vbar.pack(side='right', fill='y')
        self.configure(yscrollcommand=self.vbar.set)
