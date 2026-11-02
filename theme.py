from tkinter import ttk
BG = '#F5F5F7'
SURFACE = '#FFFFFF'
SIDEBAR = '#ECEEF1'
TEXT = '#1D1D1F'
MUTED = '#62656B'
ACCENT = '#0068D9'
GREEN = '#247447'
BORDER = '#DFE1E6'

def apply_theme(root):
    root.configure(bg=BG)
    root.option_add('*TCombobox*Listbox.background', SURFACE)
    root.option_add('*TCombobox*Listbox.foreground', TEXT)
    root.option_add('*TCombobox*Listbox.selectBackground', '#DDEBFC')
    root.option_add('*TCombobox*Listbox.selectForeground', TEXT)
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', font=('Segoe UI', 10), background=BG, foreground=TEXT)
    for (name, color) in [('TFrame', BG), ('Card.TFrame', SURFACE), ('Dialog.TFrame', SURFACE), ('Sidebar.TFrame', SIDEBAR)]:
        style.configure(name, background=color)
    style.configure('TLabel', background=BG, foreground=TEXT)
    style.configure('Title.TLabel', font=('Segoe UI', 25, 'bold'), background=BG)
    style.configure('Section.TLabel', font=('Segoe UI', 12, 'bold'))
    style.configure('Muted.TLabel', foreground=MUTED, font=('Segoe UI', 9))
    style.configure('Card.TLabel', background=SURFACE)
    style.configure('CardTitle.TLabel', background=SURFACE, font=('Segoe UI', 12, 'bold'))
    style.configure('Field.TLabel', background=SURFACE, foreground=MUTED, font=('Segoe UI', 9))
    style.configure('DialogTitle.TLabel', background=SURFACE, font=('Segoe UI', 18, 'bold'))
    style.configure('Sidebar.TLabel', background=SIDEBAR, foreground=MUTED, font=('Segoe UI', 9))
    style.configure('Brand.TLabel', background=SIDEBAR, font=('Segoe UI', 18, 'bold'))
    style.configure('TEntry', fieldbackground=SURFACE, foreground=TEXT, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, padding=(10, 8), insertcolor=TEXT)
    style.map('TEntry', bordercolor=[('focus', ACCENT), ('invalid', '#C5342D')], lightcolor=[('focus', ACCENT)], darkcolor=[('focus', ACCENT)])
    style.configure('TCombobox', fieldbackground=SURFACE, background=SURFACE, foreground=TEXT, bordercolor=BORDER, arrowcolor=MUTED, padding=(8, 8), arrowsize=13)
    style.map('TCombobox', fieldbackground=[('readonly', SURFACE)], foreground=[('readonly', TEXT)], selectbackground=[('readonly', SURFACE)], selectforeground=[('readonly', TEXT)], bordercolor=[('focus', ACCENT)])
    style.configure('TCheckbutton', background=BG, foreground=TEXT, padding=4)
    style.configure('Dialog.TCheckbutton', background=SURFACE)
    style.map('TCheckbutton', background=[('active', BG)])
    style.configure('Treeview', rowheight=42, font=('Segoe UI', 10), background=SURFACE, fieldbackground=SURFACE, foreground=TEXT, borderwidth=0, relief='flat')
    style.configure('Treeview.Heading', font=('Segoe UI', 9, 'bold'), background='#F0F1F4', foreground=MUTED, padding=(10, 12), relief='flat', borderwidth=0)
    style.map('Treeview', background=[('selected', '#DFECFD')], foreground=[('selected', '#163C69')])
    style.map('Treeview.Heading', background=[('active', '#E5E7EB')])
    style.configure('TScrollbar', background='#C8CBD1', troughcolor=BG, borderwidth=0, arrowcolor=MUTED, arrowsize=11, relief='flat')
    style.map('TScrollbar', background=[('active', '#9DA3AD'), ('pressed', '#818892')])
    style.configure('TPanedwindow', background=BG, sashwidth=12)
    style.configure('Content.TNotebook', background=BG, borderwidth=0, tabmargins=0)
    style.layout('Content.TNotebook.Tab', [])
    return style
