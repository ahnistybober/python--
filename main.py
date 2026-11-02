import csv
import json
import sqlite3
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from adapter import AIAdapter
from database import Database
from manager import PlantCareManager
from models import LIGHTING, PLANT_CLASSES, PLANT_TYPES, PlantCareError, RepottingEvent, WateringEvent, read_date
from theme import BG, GREEN, MUTED, SIDEBAR, SURFACE, TEXT, apply_theme
from widgets import Button, NavigationButton, ScrolledText, StatCard


def show_date(value):
    return value.strftime('%d.%m.%Y')


class App(tk.Tk):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        with open(Path(__file__).with_name('catalog.json'), encoding='utf-8') as stream:
            self.catalog = json.load(stream)
        self.adapter = AIAdapter(manager)
        self.title('FloraCare Manager')
        self.geometry('1440x860')
        self.minsize(1080, 700)
        apply_theme(self)
        self.search = tk.StringVar()
        self.type_filter = tk.StringVar(value='Все типы')
        self.light_filter = tk.StringVar(value='Любой свет')
        self.status_filter = tk.StringVar(value='Все статусы')
        self.summary = tk.StringVar()
        self.details = tk.StringVar(value='Выберите растение в таблице.')
        self.make_menu()
        sidebar = ttk.Frame(self, style='Sidebar.TFrame', padding=(16, 28), width=210)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        mark = tk.Canvas(sidebar, width=38, height=40, bg=SIDEBAR, highlightthickness=0)
        mark.pack(anchor='w', pady=(0, 12))
        mark.create_oval(5, 2, 31, 30, fill=GREEN, outline='')
        mark.create_line(12, 31, 25, 12, fill=SURFACE, width=2)
        ttk.Label(sidebar, text='FloraCare', style='Brand.TLabel').pack(anchor='w')
        ttk.Label(sidebar, text='Уход за домашними\nрастениями', style='Sidebar.TLabel').pack(anchor='w', pady=(5, 28))
        self.nav_buttons = []
        for index, (label, icon) in enumerate([('Мои растения', 'grid'), ('История ухода', 'history'),
                                               ('Аналитика', 'chart'), ('Библиотека', 'book')]):
            button = NavigationButton(sidebar, label, lambda i=index: self.tabs.select(i), icon=icon,
                                      badge=str(len(self.catalog['plants'])) if index == 3 else '')
            button.pack(fill='x', pady=3)
            self.nav_buttons.append(button)
        ttk.Label(sidebar, text='FloraCare Manager\nЛокальное хранение данных', style='Sidebar.TLabel').pack(
            side='bottom', anchor='w', pady=(24, 0))
        Button(sidebar, text='Задание для ИИ', bg=SIDEBAR,
               command=lambda: self.run_action(self.save_ai_task)).pack(side='bottom', fill='x')
        shell = ttk.Frame(self, padding=(26, 24))
        shell.pack(fill='both', expand=True)
        header = ttk.Frame(shell)
        header.pack(fill='x', pady=(0, 20))
        titles = ttk.Frame(header)
        titles.pack(side='left')
        self.page_title = tk.StringVar(value='Мои растения')
        self.page_subtitle = tk.StringVar(value='Коллекция и ближайшие события ухода')
        ttk.Label(titles, textvariable=self.page_title, style='Title.TLabel').pack(anchor='w')
        ttk.Label(titles, textvariable=self.page_subtitle, style='Muted.TLabel').pack(anchor='w', pady=(5, 0))
        Button(header, text='+ Добавить растение', style='Accent.TButton',
               command=lambda: self.run_action(self.add_plant)).pack(side='right', pady=10)
        cards = ttk.Frame(shell)
        cards.pack(fill='x', pady=(0, 22))
        self.stat_cards = []
        for index, (label, caption, color, value) in enumerate([
                ('В коллекции', 'Ваши растения', GREEN, 'Все статусы'),
                ('Пора полить', 'Сегодня и с просрочкой', TEXT, 'Пора полить'),
                ('Срочный полив', 'Нужно больше внимания', '#BD382F', 'Срочный полив'),
                ('Пересадка', 'Проверьте корни и грунт', TEXT, 'Требует пересадки')]):
            cards.columnconfigure(index, weight=1, uniform='stats')
            card = StatCard(cards, label, caption, color, lambda val=value: self.filter_card(val))
            card.grid(row=0, column=index, sticky='ew', padx=(0, 12 if index < 3 else 0))
            self.stat_cards.append(card)
        self.footer = tk.StringVar()
        ttk.Label(shell, textvariable=self.footer, style='Muted.TLabel').pack(side='bottom', anchor='w', pady=(12, 0))
        self.tabs = ttk.Notebook(shell, style='Content.TNotebook')
        self.tabs.pack(fill='both', expand=True)
        plants_page = ttk.Frame(self.tabs)
        history_page = ttk.Frame(self.tabs)
        charts_page = ttk.Frame(self.tabs)
        library_page = ttk.Frame(self.tabs)
        self.tabs.add(plants_page, text='Мои растения')
        self.tabs.add(history_page, text='История ухода')
        self.tabs.add(charts_page, text='Графики')
        self.tabs.add(library_page, text='Библиотека')
        self.tabs.bind('<<NotebookTabChanged>>', self.navigate)
        search_row = ttk.Frame(plants_page)
        search_row.pack(fill='x', pady=(0, 12))
        ttk.Label(search_row, text='Поиск').pack(side='left', padx=(0, 7))
        ttk.Entry(search_row, textvariable=self.search, width=18).pack(side='left', padx=(0, 10))
        for variable, choices, width in [
                (self.type_filter, ('Все типы',) + PLANT_TYPES, 13),
                (self.light_filter, ('Любой свет',) + LIGHTING, 16),
                (self.status_filter, ('Все статусы', 'Пора полить', 'Полив не требуется', 'Требует полива',
                                      'Срочный полив', 'Требует пересадки'), 19)]:
            ttk.Combobox(search_row, textvariable=variable, values=choices, width=width,
                         state='readonly').pack(side='left', padx=(0, 8))
        Button(search_row, text='Сброс', command=self.reset_filters).pack(side='left')
        for variable in (self.search, self.type_filter, self.light_filter, self.status_filter):
            variable.trace_add('write', lambda *args: self.fill_plants())
        actions = ttk.Frame(plants_page)
        actions.pack(fill='x', pady=(0, 12))
        self.plant_actions = []
        for label, action in [('Изменить', self.edit_plant), ('Полив', self.water),
                              ('Пересадка', self.repot), ('Удалить', self.delete_plant)]:
            button = Button(actions, text=label, command=lambda fn=action: self.run_action(fn),
                            style='Danger.TButton' if label == 'Удалить' else '')
            button.pack(side='left', padx=(0, 8))
            self.plant_actions.append(button)
        split = ttk.Panedwindow(plants_page, orient='horizontal')
        split.pack(fill='both', expand=True)
        table = ttk.Frame(split)
        side = ttk.Frame(split, padding=(16, 0, 0, 0), width=260)
        split.add(table, weight=4)
        split.add(side, weight=1)
        columns = [('name', 'Имя', 140), ('species', 'Вид', 160), ('light', 'Свет', 135),
                   ('water', 'Следующий', 95), ('days', 'Дней', 55), ('status', 'Статус', 150)]
        self.plant_tree = self.make_table(table, columns)
        self.plant_tree.tag_configure('urgent', foreground='#a52020')
        self.plant_tree.tag_configure('due', foreground='#886000')
        self.plant_tree.bind('<<TreeviewSelect>>', lambda event: self.show_details())
        self.plant_tree.bind('<Double-1>', lambda event: self.run_action(self.edit_plant))
        ttk.Label(side, text='Требует внимания', style='Section.TLabel').pack(anchor='w')
        self.attention = tk.Listbox(side, height=4, width=27, relief='flat', bg='#FFF5E7', fg='#854D12',
                                    font=('Segoe UI', 9), highlightthickness=0, exportselection=False)
        self.attention.pack(fill='x', pady=(10, 18))
        self.attention.bind('<<ListboxSelect>>', self.choose_attention)
        ttk.Label(side, text='Карточка растения', style='Section.TLabel').pack(anchor='w')
        self.detail_view = ScrolledText(side, width=28, height=12, wrap='word', font=('Segoe UI', 10),
                                        relief='flat', padx=12, pady=12)
        self.detail_view.pack(fill='both', expand=True, pady=10)
        ttk.Label(side, text='Проверяйте влажность грунта перед поливом.', style='Muted.TLabel',
                  wraplength=240).pack(anchor='w', pady=8)
        history_controls = ttk.Frame(history_page)
        history_controls.pack(fill='x', pady=(0, 12))
        self.history_all = tk.BooleanVar(value=True)
        self.history_type = tk.StringVar(value='Все события')
        ttk.Checkbutton(history_controls, text='Все растения', variable=self.history_all,
                        command=self.fill_history).pack(side='left')
        picker = ttk.Combobox(history_controls, textvariable=self.history_type,
                              values=('Все события', 'Полив', 'Пересадка'), state='readonly', width=18)
        picker.pack(side='left', padx=12)
        picker.bind('<<ComboboxSelected>>', lambda event: self.fill_history())
        Button(history_controls, text='Удалить событие', style='Danger.TButton',
               command=lambda: self.run_action(self.delete_event)).pack(side='right')
        self.history_tree = self.make_table(history_page, [('date', 'Дата', 100), ('plant', 'Растение', 170),
                                           ('care', 'Уход', 420), ('notes', 'Заметки', 250)])
        chart_controls = ttk.Frame(charts_page)
        chart_controls.pack(fill='x', pady=(0, 8))
        self.period_start = tk.StringVar(value=show_date(date.today() - timedelta(days=90)))
        self.period_end = tk.StringVar(value=show_date(date.today()))
        for label, variable in [('С', self.period_start), ('По', self.period_end)]:
            ttk.Label(chart_controls, text=label).pack(side='left', padx=(0, 6))
            ttk.Entry(chart_controls, textvariable=variable, width=13).pack(side='left', padx=(0, 12))
        Button(chart_controls, text='Обновить графики',
               command=lambda: self.run_action(self.draw_charts)).pack(side='left')
        self.chart_summary = tk.StringVar()
        ttk.Label(charts_page, textvariable=self.chart_summary, style='Muted.TLabel').pack(anchor='w', pady=4)
        self.figure = Figure(figsize=(10, 6), dpi=100, layout='constrained', facecolor=BG)
        self.canvas = FigureCanvasTkAgg(self.figure, master=charts_page)
        self.toolbar = NavigationToolbar2Tk(self.canvas, charts_page, pack_toolbar=False)
        self.toolbar.pack(side='bottom', fill='x')
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        self.make_library(library_page)
        self.bind('<F5>', lambda event: self.run_action(self.refresh))
        self.refresh()

    def navigate(self, event=None):
        index = self.tabs.index('current')
        titles = [('Мои растения', 'Коллекция и ближайшие события ухода'),
                  ('История ухода', 'Каждый полив и пересадка в одном журнале'),
                  ('Аналитика', 'Как меняется уход за вашей коллекцией'),
                  ('Библиотека растений', 'Найдите растение и добавьте свой экземпляр')]
        self.page_title.set(titles[index][0])
        self.page_subtitle.set(titles[index][1])
        for i, button in enumerate(self.nav_buttons):
            button.set_selected(i == index)

    def reset_filters(self):
        self.search.set('')
        self.type_filter.set('Все типы')
        self.light_filter.set('Любой свет')
        self.status_filter.set('Все статусы')

    def filter_card(self, value):
        self.tabs.select(0)
        self.reset_filters()
        self.status_filter.set(value)

    def make_menu(self):
        menu = tk.Menu(self)
        files = tk.Menu(menu, tearoff=False)
        files.add_command(label='Обновить данные    F5', command=lambda: self.run_action(self.refresh))
        files.add_separator()
        files.add_command(label='Экспорт поливов в CSV', command=lambda: self.run_action(self.export_csv))
        files.add_command(label='Импорт поливов из CSV', command=lambda: self.run_action(self.import_csv))
        files.add_separator()
        files.add_command(label='Выход', command=self.destroy)
        menu.add_cascade(label='Файл', menu=files)
        adapter_menu = tk.Menu(menu, tearoff=False)
        adapter_menu.add_command(label='Сохранить задание для ИИ',
                                 command=lambda: self.run_action(self.save_ai_task))
        adapter_menu.add_command(label='Импортировать ответ JSON',
                                 command=lambda: self.run_action(self.import_ai_answer))
        menu.add_cascade(label='ИИ-адаптер', menu=adapter_menu)
        menu.add_command(label='О программе', command=lambda: messagebox.showinfo('FloraCare',
                         'Учет поливов и пересадок домашних растений.\n\n'
                         + self.catalog['source'] + '\n' + self.catalog['source_url']
                         + '\n' + self.catalog['license_url'] + '\n' + self.catalog['changes'], parent=self))
        self.configure(menu=menu)

    def make_table(self, parent, columns):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show='headings', selectmode='browse')
        for key, label, width in columns:
            tree.heading(key, text=label)
            tree.column(key, width=width, minwidth=70)
        scroll = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
        horizontal = ttk.Scrollbar(frame, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky='nsew')
        scroll.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        return tree

    def make_library(self, page):
        filters = ttk.Frame(page)
        filters.pack(fill='x', pady=(0, 12))
        ttk.Label(filters, text='Найти растение').pack(side='left', padx=(0, 8))
        self.library_query = tk.StringVar()
        self.library_type = tk.StringVar(value='Все группы')
        ttk.Entry(filters, textvariable=self.library_query, width=32).pack(side='left', padx=(0, 14))
        ttk.Combobox(filters, textvariable=self.library_type, values=('Все группы',) + PLANT_TYPES,
                     state='readonly', width=24).pack(side='left')
        self.library_count = tk.StringVar()
        ttk.Label(filters, textvariable=self.library_count, style='Muted.TLabel').pack(side='right')
        split = ttk.Panedwindow(page, orient='horizontal')
        split.pack(fill='both', expand=True)
        table = ttk.Frame(split)
        details = ttk.Frame(split, padding=(18, 0, 0, 0))
        split.add(table, weight=3)
        split.add(details, weight=2)
        self.library_tree = self.make_table(table, [('name', 'Растение', 230), ('type', 'Группа', 140),
                                                   ('light', 'Свет', 150)])
        ttk.Label(details, text='Справочная карточка', style='Section.TLabel').pack(anchor='w')
        self.library_add = Button(details, text='+ В мою коллекцию', style='Accent.TButton',
                                   command=self.add_from_library)
        self.library_add.pack(anchor='w', pady=10)
        self.library_description = ScrolledText(details, wrap='word', width=45, font=('Segoe UI', 10),
                                                relief='flat', padx=12, pady=12)
        self.library_description.pack(fill='both', expand=True)
        self.library_tree.bind('<<TreeviewSelect>>', self.select_library)
        self.library_tree.bind('<Double-1>', lambda event: self.add_from_library())
        for variable in (self.library_query, self.library_type):
            variable.trace_add('write', lambda *args: self.fill_library())
        ttk.Label(page, text='300 карточек · Plantfolio / Luminoid · CC BY-NC-SA 4.0',
                  style='Muted.TLabel').pack(anchor='w', pady=(10, 0))
        self.fill_library()

    def fill_library(self):
        self.library_tree.delete(*self.library_tree.get_children())
        query = self.library_query.get().casefold().replace('ё', 'е').split()
        count = 0
        for index, plant in enumerate(self.catalog['plants']):
            text = (plant['name'] + ' ' + plant['species']).casefold().replace('ё', 'е')
            if not all(word in text for word in query):
                continue
            if self.library_type.get() not in ('Все группы', plant['plant_type']):
                continue
            self.library_tree.insert('', 'end', iid=str(index),
                                     values=(plant['name'], plant['plant_type'], plant['lighting']))
            count += 1
        self.library_count.set(f'Найдено: {count} из {len(self.catalog["plants"])}')
        self.library_add.state(['disabled'])
        self.library_description.configure(state='normal')
        self.library_description.delete('1.0', 'end')
        self.library_description.insert('1.0', 'Выберите растение, чтобы увидеть условия ухода и грунт.\n\n'
                                         'Один вид можно добавить в коллекцию несколько раз.')
        self.library_description.configure(state='disabled')

    def library_text(self, plant):
        return (f'{plant["name"]}\n{plant["species"]}\n\nГруппа: {plant["plant_type"]}\n\n'
                f'СВЕТ\n{plant["lighting"]}\n\nПОЛИВ\nНачальный интервал: {plant["watering_days"]} дн.\n'
                'Проверяйте влажность грунта перед поливом.\n\n'
                f'ГРУНТ\n{plant["soil"]}\nТиповая смесь по группе.\n\n'
                f'ПЕРЕСАДКА\nНачальный интервал: {plant["repotting_days"]} дн.')

    def select_library(self, event=None):
        selected = self.library_tree.selection()
        self.library_add.state(['!disabled'] if selected else ['disabled'])
        if selected:
            plant = self.catalog['plants'][int(selected[0])]
            self.library_description.configure(state='normal')
            self.library_description.delete('1.0', 'end')
            self.library_description.insert('1.0', self.library_text(plant))
            self.library_description.configure(state='disabled')

    def add_from_library(self):
        selected = self.library_tree.selection()
        if selected:
            self.plant_form(preset=self.catalog['plants'][int(selected[0])])

    def run_action(self, action):
        try:
            action()
        except (PlantCareError, sqlite3.Error, OSError, ValueError, csv.Error) as error:
            messagebox.showerror('Ошибка', str(error), parent=self)

    def selected_plant(self):
        selection = self.plant_tree.selection()
        if not selection:
            raise PlantCareError('Сначала выберите растение.')
        return self.manager.find_plant(int(selection[0]))

    def refresh(self):
        self.manager.refresh()
        self.fill_plants()
        self.fill_history()
        self.draw_charts()
        statuses = list(self.manager.statuses.values())
        counts = [len(self.manager.plants), sum(s['days_left'] <= 0 for s in statuses),
                  sum(s['status'] == 'Срочный полив' for s in statuses),
                  sum(s['repot_date'] <= date.today() for s in statuses)]
        for card, count in zip(self.stat_cards, counts):
            card.set(count)
        self.footer.set('Все изменения сохранены на этом компьютере  ·  Обновлено ' + show_date(date.today()))

    def fill_plants(self):
        selected = self.plant_tree.selection()
        self.plant_tree.delete(*self.plant_tree.get_children())
        today = date.today()
        due = 0
        self.attention.delete(0, 'end')
        self.attention_ids = []
        for plant in self.manager.plants:
            status = self.manager.statuses[plant.id]
            needs_care = status['days_left'] <= 0 or status['repot_date'] <= today
            due += needs_care
            if needs_care:
                care = 'полив' if status['days_left'] <= 0 else 'пересадка'
                self.attention.insert('end', f'{plant.name[:20]} · {care}')
                self.attention_ids.append(plant.id)
            if self.search.get().casefold() not in (plant.name + ' ' + plant.species).casefold():
                continue
            kind = next(name for name, cls in PLANT_CLASSES.items() if type(plant) is cls)
            if self.type_filter.get() not in ('Все типы', kind):
                continue
            if self.light_filter.get() not in ('Любой свет', plant.lighting):
                continue
            wanted = self.status_filter.get()
            if wanted == 'Пора полить' and status['days_left'] > 0:
                continue
            if wanted == 'Требует пересадки' and status['repot_date'] > today:
                continue
            if wanted not in ('Все статусы', 'Пора полить', 'Требует пересадки', status['status']):
                continue
            tag = 'urgent' if status['status'] == 'Срочный полив' else 'due' if needs_care else ''
            self.plant_tree.insert('', 'end', iid=str(plant.id), values=(plant.name, plant.species,
                                   plant.lighting, show_date(status['next_date']), status['days_left'], status['status']), tags=(tag,))
        self.summary.set(f'Растений: {len(self.manager.plants)}. Требуют ухода: {due}. * — пора пересадить.')
        if selected and self.plant_tree.exists(selected[0]):
            self.plant_tree.selection_set(selected[0])
        self.show_details()

    def show_details(self):
        selection = self.plant_tree.selection()
        for button in self.plant_actions:
            button.state(['!disabled'] if selection else ['disabled'])
        text = 'Выберите растение в таблице.\n\nДля новой карточки нажмите «Добавить растение» или откройте библиотеку.'
        if selection:
            plant = self.selected_plant()
            status = self.manager.statuses[plant.id]
            text = (f'{plant.name}\n{plant.species}\n\n{status["status"]}\n'
                    f'Следующий полив: {show_date(status["next_date"])}\nИнтервал: {status["interval"]} дн.\n'
                    f'До полива: {status["days_left"]} дн.\n\nПересадка: {show_date(status["repot_date"])}\n\n'
                    f'Грунт\n{plant.soil or "Не указан"}\n\nОсвещение\n{plant.lighting}')
        self.details.set(text)
        self.detail_view.configure(state='normal')
        self.detail_view.delete('1.0', 'end')
        self.detail_view.insert('1.0', text)
        self.detail_view.configure(state='disabled')
        if hasattr(self, 'history_tree'):
            self.fill_history()

    def choose_attention(self, event):
        selection = self.attention.curselection()
        if selection:
            plant_id = str(self.attention_ids[selection[0]])
            self.reset_filters()
            self.plant_tree.selection_set(plant_id)
            self.plant_tree.see(plant_id)
            self.show_details()

    def fill_history(self):
        self.history_tree.delete(*self.history_tree.get_children())
        names = {p.id: p.name for p in self.manager.plants}
        selection = self.plant_tree.selection()
        for event in self.manager.events:
            if not self.history_all.get() and (not selection or event.plant_id != int(selection[0])):
                continue
            if self.history_type.get() == 'Полив' and not isinstance(event, WateringEvent):
                continue
            if self.history_type.get() == 'Пересадка' and isinstance(event, WateringEvent):
                continue
            if isinstance(event, WateringEvent):
                care = f'Полив: {event.water_ml:g} мл'
                if event.fertilizer:
                    care += f'; подкормка: {event.fertilizer}'
            else:
                care = f'Пересадка: {event.pot_liters:g} л; {event.soil}'
            self.history_tree.insert('', 'end', iid=str(event.id),
                                     values=(show_date(event.event_date), names[event.plant_id], care, event.notes))

    def open_form(self, title, fields, initial, on_save, library=False):
        window = tk.Toplevel(self)
        window.title(title)
        window.transient(self)
        window.resizable(False, False)
        window.configure(bg=SURFACE)
        body = ttk.Frame(window, padding=28, style='Dialog.TFrame')
        body.pack(fill='both', expand=True)
        ttk.Label(body, text=title, style='DialogTitle.TLabel').grid(row=0, column=0, sticky='w', pady=(0, 24))
        fields_frame = ttk.Frame(body, style='Card.TFrame')
        fields_frame.grid(row=1, column=0, sticky='nsew')
        columns = 2 if len(fields) > 6 else 1
        row = col = 0
        variables = {}
        for key, label, choices in fields:
            span = columns if key in ('soil', 'notes') else 1
            if span == columns and col:
                row += 1
                col = 0
            cell = ttk.Frame(fields_frame, style='Card.TFrame')
            cell.grid(row=row, column=col, columnspan=span, sticky='ew',
                      padx=(0, 12 if col == 0 and span == 1 and columns == 2 else 0), pady=(0, 13))
            ttk.Label(cell, text=label, style='Field.TLabel').pack(anchor='w', pady=(0, 5))
            variable = tk.StringVar(value=initial.get(key, ''))
            variables[key] = variable
            if choices:
                widget = ttk.Combobox(cell, textvariable=variable, values=choices, state='readonly',
                                      width=22 if columns == 2 else 38)
            else:
                widget = ttk.Entry(cell, textvariable=variable, width=24 if columns == 2 else 40)
            widget.pack(fill='x')
            col += span
            if col >= columns:
                row += 1
                col = 0
        if library:
            lookup = ttk.Frame(body, padding=(28, 0, 0, 0), style='Card.TFrame')
            lookup.grid(row=0, column=1, rowspan=4, sticky='ns')
            ttk.Label(lookup, text='Найдите свое растение', style='CardTitle.TLabel').pack(anchor='w')
            ttk.Label(lookup, text='300 карточек с рекомендациями по уходу', style='Field.TLabel').pack(anchor='w', pady=8)
            query = tk.StringVar()
            ttk.Entry(lookup, textvariable=query, width=38).pack(fill='x', pady=5)
            matches = tk.Listbox(lookup, width=45, height=6, exportselection=False, font=('Segoe UI', 10),
                                 relief='flat', bg=SURFACE, fg=TEXT, highlightthickness=0)
            matches.pack(fill='x')
            description = ScrolledText(lookup, width=43, height=14, font=('Segoe UI', 10),
                                       relief='flat', wrap='word', padx=8, pady=12)
            description.pack(fill='both', expand=True)
            found = []

            def search(*args):
                found.clear()
                matches.delete(0, 'end')
                words = query.get().casefold().replace('ё', 'е').split()
                for item in self.catalog['plants']:
                    text = (item['name'] + ' ' + item['species']).casefold().replace('ё', 'е')
                    if all(word in text for word in words):
                        found.append(item)
                        matches.insert('end', item['name'])
                        if len(found) == 10:
                            break

            def choose(event):
                if matches.curselection():
                    record = found[matches.curselection()[0]]
                    for key, value in record.items():
                        if key in variables:
                            variables[key].set(value)
                    description.configure(state='normal')
                    description.delete('1.0', 'end')
                    description.insert('1.0', self.library_text(record))
                    description.configure(state='disabled')

            query.trace_add('write', search)
            matches.bind('<<ListboxSelect>>', choose)
            search()
        error = tk.StringVar()
        ttk.Label(body, textvariable=error, foreground='#a52020', background=SURFACE, wraplength=470).grid(
            row=2, column=0, sticky='w', pady=(12, 8))
        buttons = ttk.Frame(body, style='Card.TFrame')
        buttons.grid(row=3, column=0, sticky='e', pady=(8, 0))

        def save():
            save_button.state(['disabled'])
            try:
                on_save({key: value.get() for key, value in variables.items()})
            except (PlantCareError, sqlite3.Error, ValueError) as problem:
                error.set(str(problem))
            else:
                self.refresh()
                window.destroy()
            finally:
                if window.winfo_exists():
                    save_button.state(['!disabled'])

        Button(buttons, text='Отмена', command=window.destroy).pack(side='left', padx=5)
        save_button = Button(buttons, text='Сохранить', command=save, style='Accent.TButton')
        save_button.pack(side='left')
        window.bind('<Escape>', lambda event: window.destroy())
        window.update_idletasks()
        window.geometry(f'+{self.winfo_rootx() + 100}+{self.winfo_rooty() + 70}')
        window.grab_set()

    def plant_form(self, plant=None, preset=None):
        fields = [('name', 'Имя растения', None), ('species', 'Вид', None),
                  ('plant_type', 'Тип', PLANT_TYPES), ('lighting', 'Освещение', LIGHTING),
                  ('watering_days', 'Интервал полива, дней', None),
                  ('repotting_days', 'Интервал пересадки, дней', None),
                  ('planted_on', 'Дата посадки', None), ('soil', 'Грунт', None)]
        initial = dict(plant_type=PLANT_TYPES[0], lighting=LIGHTING[1], watering_days=7,
                       repotting_days=365, planted_on=show_date(date.today()))
        if preset:
            initial.update(preset)
        if plant:
            initial.update(vars(plant))
            initial['planted_on'] = show_date(plant.planted_on)
            initial['plant_type'] = next(name for name, cls in PLANT_CLASSES.items() if type(plant) is cls)
        self.open_form('Изменить растение' if plant else 'Добавить растение', fields, initial,
                       lambda values: self.manager.save_plant(values, plant.id if plant else None), library=True)

    def add_plant(self):
        self.plant_form()

    def edit_plant(self):
        self.plant_form(self.selected_plant())

    def delete_plant(self):
        plant = self.selected_plant()
        if messagebox.askyesno('Удаление', f'Удалить {plant.name} и всю историю ухода?', parent=self):
            self.manager.database.delete_plant(plant.id)
            self.refresh()

    def water(self):
        plant = self.selected_plant()
        fields = [('event_date', 'Дата полива', None), ('water_ml', 'Объем воды, мл', None),
                  ('fertilizer', 'Подкормка', None), ('notes', 'Заметки', None)]
        self.open_form('Полив: ' + plant.name, fields, dict(event_date=show_date(date.today()), water_ml=200),
                       lambda values: self.manager.record_event(WateringEvent(plant.id, **values)))

    def repot(self):
        plant = self.selected_plant()
        fields = [('event_date', 'Дата пересадки', None), ('pot_liters', 'Новый горшок, л', None),
                  ('soil', 'Грунт', None), ('notes', 'Заметки', None)]
        self.open_form('Пересадка: ' + plant.name, fields,
                       dict(event_date=show_date(date.today()), pot_liters=2, soil=plant.soil),
                       lambda values: self.manager.record_event(RepottingEvent(plant.id, **values)))

    def delete_event(self):
        selection = self.history_tree.selection()
        if not selection:
            raise PlantCareError('Сначала выберите событие.')
        if messagebox.askyesno('Удаление', 'Удалить выбранное событие?', parent=self):
            self.manager.database.delete_event(int(selection[0]))
            self.refresh()

    def export_csv(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension='.csv', filetypes=[('CSV', '*.csv')])
        if path:
            self.manager.export_csv(path)
            messagebox.showinfo('Экспорт', 'История поливов сохранена.', parent=self)

    def import_csv(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[('CSV', '*.csv')])
        if path:
            count = self.manager.import_csv(path)
            self.refresh()
            messagebox.showinfo('Импорт', f'Добавлено поливов: {count}.', parent=self)

    def save_ai_task(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension='.txt', filetypes=[('Текст', '*.txt')])
        if path:
            self.adapter.save_task(path)
            messagebox.showinfo('ИИ-адаптер', 'Задание сохранено. Передайте его ИИ вместе со своим списком растений.', parent=self)

    def import_ai_answer(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[('JSON', '*.json')])
        if path:
            plants, events = self.adapter.read_file(path)
            text = (f'Добавить растений: {len(plants)}, событий: {len(events)}?\n'
                    'Все растения будут добавлены как новые экземпляры.')
            if messagebox.askyesno('Импорт JSON', text, parent=self):
                self.adapter.import_data(plants, events)
                self.refresh()

    def draw_charts(self):
        start = read_date(self.period_start.get())
        end = read_date(self.period_end.get())
        if start > end:
            raise PlantCareError('Начало периода не может быть позже конца.')
        events = [event for event in self.manager.events if start <= event.event_date <= end]
        self.figure.clear()
        self.toolbar.update()
        water_chart = self.figure.add_subplot(211)
        interval_chart = self.figure.add_subplot(223)
        light_chart = self.figure.add_subplot(224)
        volumes = [0] * 7
        for event in events:
            if isinstance(event, WateringEvent):
                volumes[event.event_date.weekday()] += event.water_ml
        water_chart.bar(('Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'), volumes, color='#68AB8A')
        water_chart.set_title('Объем поливов по дням недели за выбранный период')
        water_chart.set_ylabel('Объем, мл')
        stats = self.manager.statistics(events)
        observed = {key: value['avg_interval_days'] for key, value in stats.items()
                    if value['avg_interval_days'] is not None}
        if observed:
            interval_chart.bar(list(observed), list(observed.values()), color='#9CCCB1')
        else:
            interval_chart.text(0.5, 0.5, 'Недостаточно истории', ha='center', transform=interval_chart.transAxes)
        interval_chart.set_title('Средний фактический интервал')
        interval_chart.set_ylabel('Дни')
        lights = {key: len(value) for key, value in self.manager.lighting.items() if value}
        if lights:
            light_chart.pie(list(lights.values()), labels=list(lights), autopct='%1.0f%%',
                            colors=['#9DD7BA', '#F0D46A', '#BCD3EA'])
        else:
            light_chart.text(0.5, 0.5, 'Нет растений', ha='center', transform=light_chart.transAxes)
        light_chart.set_title('Текущее освещение · весь каталог')
        for axis in (water_chart, interval_chart, light_chart):
            axis.set_facecolor(BG)
            axis.spines['top'].set_visible(False)
            axis.spines['right'].set_visible(False)
            axis.tick_params(labelsize=8, colors=MUTED)
        count = sum(isinstance(event, WateringEvent) for event in events)
        self.chart_summary.set(f'Поливов за период: {count} · Общий объем: {sum(volumes):g} мл')
        self.canvas.draw_idle()


def main():
    database = None
    try:
        database = Database(Path(__file__).with_name('floracare.db'))
        App(PlantCareManager(database)).mainloop()
    except (PlantCareError, sqlite3.Error, OSError) as error:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror('FloraCare', str(error), parent=root)
        root.destroy()
    finally:
        if database:
            database.close()


if __name__ == '__main__':
    main()
