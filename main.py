import json
import os
import csv
import uuid
from datetime import datetime, timedelta
from enum import IntEnum

from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import StringProperty, BooleanProperty, NumericProperty
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock

from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton, MDFlatButton, MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.filemanager import MDFileManager
from kivymd.uix.label import MDLabel
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.textfield import MDTextField
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.selectioncontrol import MDCheckbox
from kivy.uix.spinner import Spinner
from kivy.uix.modalview import ModalView

try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False


class TaskPriority(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2


class RecurrenceType(IntEnum):
    NONE = 0
    DAILY = 1
    WEEKLY = 2
    MONTHLY = 3


class TaskModel:
    def __init__(self, title, category="Общие", priority=TaskPriority.MEDIUM,
                 due_date=None, description="", recurrence=RecurrenceType.NONE,
                 recurrence_interval=1, is_completed=False, was_notified=False,
                 created_date=None, task_id=None):
        if not title or not title.strip():
            raise ValueError("Название не может быть пустым")
        self.id = task_id or str(uuid.uuid4())
        self.title = title.strip()
        self.category = category.strip() or "Общие"
        self.description = description.strip()
        self.priority = priority
        self.due_date = due_date or datetime.now() + timedelta(hours=1)
        self.is_completed = is_completed
        self.was_notified = was_notified
        self.created_date = created_date or datetime.now()
        self.recurrence = recurrence
        self.recurrence_interval = max(1, recurrence_interval)

    def to_dict(self):
        return {
            "id": self.id, "title": self.title, "category": self.category,
            "description": self.description, "priority": int(self.priority),
            "due_date": self.due_date.isoformat(), "is_completed": self.is_completed,
            "was_notified": self.was_notified,
            "created_date": self.created_date.isoformat(),
            "recurrence": int(self.recurrence),
            "recurrence_interval": self.recurrence_interval
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            title=d["title"], category=d.get("category", "Общие"),
            priority=TaskPriority(d["priority"]),
            due_date=datetime.fromisoformat(d["due_date"]),
            description=d.get("description", ""),
            recurrence=RecurrenceType(d["recurrence"]),
            recurrence_interval=d.get("recurrence_interval", 1),
            is_completed=d.get("is_completed", False),
            was_notified=d.get("was_notified", False),
            created_date=datetime.fromisoformat(d["created_date"]),
            task_id=d["id"]
        )

    def next_due_date(self):
        if self.recurrence == RecurrenceType.DAILY:
            return self.due_date + timedelta(days=self.recurrence_interval)
        elif self.recurrence == RecurrenceType.WEEKLY:
            return self.due_date + timedelta(weeks=self.recurrence_interval)
        elif self.recurrence == RecurrenceType.MONTHLY:
            m = self.due_date.month + self.recurrence_interval
            y = self.due_date.year + (m - 1) // 12
            m = (m - 1) % 12 + 1
            d = min(self.due_date.day, [31, 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28,
                                        31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
            return self.due_date.replace(year=y, month=m, day=d)
        else:
            return self.due_date


class TaskRepository:
    def __init__(self, path="tasks.json"):
        self.path = path
        self.tasks = []
        self.load()

    def load(self):
        if not os.path.exists(self.path):
            self._seed()
            self.save()
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                self.tasks = [TaskModel.from_dict(d) for d in json.load(f)]
        except:
            self.tasks = []
            self._seed()
            self.save()

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump([t.to_dict() for t in self.tasks], f, indent=2, ensure_ascii=False)

    def _seed(self):
        now = datetime.now()
        self.tasks = [
            TaskModel("Изучить SOLID", "Учеба", TaskPriority.HIGH, now + timedelta(hours=2)),
            TaskModel("Купить кофе", "Личное", TaskPriority.LOW, now + timedelta(days=1)),
            TaskModel("Ревью кода", "Работа", TaskPriority.MEDIUM, now + timedelta(minutes=5)),
            TaskModel("Повторить БД", "Учеба", TaskPriority.HIGH, now + timedelta(days=7),
                      recurrence=RecurrenceType.WEEKLY)
        ]

    def all(self):
        return list(self.tasks)

    def add(self, t):
        self.tasks.append(t)
        self.save()

    def update(self, t):
        for i, e in enumerate(self.tasks):
            if e.id == t.id:
                self.tasks[i] = t
                self.save()
                return

    def toggle(self, tid):
        for t in self.tasks:
            if t.id == tid:
                t.is_completed = not t.is_completed
                self.save()
                return

    def delete(self, tid):
        self.tasks = [t for t in self.tasks if t.id != tid]
        self.save()

    def mark_notified(self, tid):
        for t in self.tasks:
            if t.id == tid:
                t.was_notified = True
                self.save()
                return


class TaskService:
    def __init__(self, repo):
        self.repo = repo

    def add_task(self, t):
        self.repo.add(t)

    def update_task(self, t):
        self.repo.update(t)

    def toggle_completion(self, tid):
        t = next((x for x in self.repo.all() if x.id == tid), None)
        if not t:
            return
        was = t.is_completed
        self.repo.toggle(tid)

    def delete_task(self, tid):
        self.repo.delete(tid)

    def mark_notified(self, tid):
        self.repo.mark_notified(tid)

    def all_tasks(self):
        return self.repo.all()

    def categories(self):
        return sorted({t.category for t in self.all_tasks()})


class TaskCard(MDCard):
    task_id = StringProperty()
    title = StringProperty()
    category = StringProperty()
    due_date_str = StringProperty()
    is_completed = BooleanProperty(False)
    priority = NumericProperty(0)
    recurrence = NumericProperty(0)

    def __init__(self, task, toggle_cb, delete_cb, edit_cb, **kw):
        super().__init__(**kw)
        self.task_id = task.id
        self.title = task.title
        self.category = task.category
        self.is_completed = task.is_completed
        self.priority = int(task.priority)
        self.recurrence = int(task.recurrence)
        self.due_date_str = self._fmt(task.due_date)
        self.toggle_cb = toggle_cb
        self.delete_cb = delete_cb
        self.edit_cb = edit_cb

        self.size_hint = (1, None)
        self.height = dp(68)
        self.padding = 0
        self.radius = [dp(16), dp(16), dp(16), dp(16)]
        self.elevation = 3
        self.orientation = "vertical"
        self.md_bg_color = (0.98, 0.98, 1.0, 1)

        bar = MDBoxLayout(size_hint_y=None, height=dp(5),
                          md_bg_color=self._pri_color())
        self.add_widget(bar)

        row = MDBoxLayout(orientation="horizontal", spacing=dp(8),
                          padding=[dp(8), dp(4), dp(4), dp(4)])

        chk = MDCheckbox(active=task.is_completed, size_hint=(None, None),
                         size=(dp(28), dp(28)))
        chk.bind(active=lambda i, v: self.toggle_cb(self.task_id))
        row.add_widget(chk)

        txt_block = MDBoxLayout(orientation="vertical", spacing=dp(2), size_hint_x=1)
        ttl = MDLabel(
            text=self.title,
            font_style="Subtitle1",
            theme_text_color="Custom",
            text_color=(0.5, 0.5, 0.5, 1) if task.is_completed else (0.15, 0.15, 0.15, 1),
            size_hint_x=1, shorten=True, shorten_from="right",
            font_size="14sp"
        )
        meta = f"[{self.category}] - {self.due_date_str}"
        meta_lbl = MDLabel(text=meta, font_style="Caption",
                           theme_text_color="Custom",
                           text_color=(0.5, 0.5, 0.5, 1) if not (task.due_date < datetime.now() and not task.is_completed) else (0.9, 0.2, 0.2, 1),
                           size_hint_x=1, shorten=True,
                           font_size="11sp")
        txt_block.add_widget(ttl)
        txt_block.add_widget(meta_lbl)
        row.add_widget(txt_block)

        if task.recurrence != RecurrenceType.NONE:
            rep_text = {RecurrenceType.DAILY: "Д", RecurrenceType.WEEKLY: "Н", RecurrenceType.MONTHLY: "М"}.get(task.recurrence, "R")
            row.add_widget(MDLabel(text=rep_text,
                                   font_style="Caption", size_hint=(None, None),
                                   size=(dp(20), dp(20)), font_size="12sp", halign="center"))

        edit_btn = MDIconButton(
            icon="pencil",
            on_release=lambda x=None: self.edit_cb(self.task_id),
            size_hint=(None, None),
            size=(dp(36), dp(36)),
            icon_size=dp(20),
            md_bg_color=(0, 0, 0, 0)
        )
        del_btn = MDIconButton(
            icon="delete",
            on_release=lambda x=None: self.delete_cb(self.task_id),
            size_hint=(None, None),
            size=(dp(36), dp(36)),
            icon_size=dp(20),
            md_bg_color=(0, 0, 0, 0)
        )
        row.add_widget(edit_btn)
        row.add_widget(del_btn)
        self.add_widget(row)

    def _pri_color(self):
        return [(0.2, 0.8, 0.3, 1), (1.0, 0.7, 0.1, 1), (0.95, 0.25, 0.25, 1)][self.priority]

    def _fmt(self, dt):
        now = datetime.now()
        if dt < now:
            return f"Просрочено: {dt.strftime('%d.%m.%Y %H:%M')}"
        diff = dt - now
        if diff.days == 0:
            return f"Сегодня, {dt.strftime('%H:%M')}"
        if diff.days == 1:
            return f"Завтра, {dt.strftime('%H:%M')}"
        return dt.strftime("%d.%m.%Y %H:%M")


class PlannerScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.srv = None
        self.sel_pri = 1
        self.menus = {}
        self.fm = None
        self.export_mode = False

        self.task_list = MDBoxLayout(orientation="vertical", spacing=dp(6),
                                     padding=[dp(8)], size_hint_y=None)
        self.task_list.bind(minimum_height=self.task_list.setter("height"))
        self.scroll = ScrollView()
        self.scroll.add_widget(self.task_list)

        self.build_ui()

    def build_ui(self):
        root = MDBoxLayout(orientation="vertical")
        self.md_bg_color = (0.94, 0.96, 0.98, 1)

        toolbar = MDTopAppBar(
            title="Планировщик задач",
            right_action_items=[["plus", lambda x: self.open_add()]],
            elevation=4,
            md_bg_color=(0.25, 0.45, 0.85, 1),
            specific_text_color=(1, 1, 1, 1)
        )
        root.add_widget(toolbar)

        filt = MDBoxLayout(orientation="vertical", size_hint_y=None,
                           height=dp(130), padding=[dp(8), dp(6)], spacing=dp(6),
                           md_bg_color=(1, 1, 1, 1))
        self.search = MDTextField(
            hint_text="Поиск...",
            mode="fill",
            size_hint_x=1,
            font_size="14sp",
            fill_color_normal=(0.95, 0.95, 0.95, 1),
            radius=[dp(12), dp(12), dp(12), dp(12)],
            size_hint_y=None,
            height=dp(44)
        )
        self.search.bind(text=lambda i, v: self.refresh())
        filt.add_widget(self.search)

        row = MDBoxLayout(orientation="horizontal", spacing=dp(6),
                          size_hint_y=None, height=dp(38))
        btn_style = {
            "size_hint_x": 1,
            "font_size": "12sp",
            "md_bg_color": (0.93, 0.95, 0.98, 1),
            "text_color": (0.2, 0.2, 0.2, 1),
            "line_color": (0, 0, 0, 0)
        }
        self.status_btn = MDRaisedButton(
            text="Все", on_release=self.open_status_menu,
            **btn_style
        )
        self.cat_btn = MDRaisedButton(
            text="Категории", on_release=self.open_cat_menu,
            **btn_style
        )
        self.sort_btn = MDRaisedButton(
            text="Сорт.", on_release=self.open_sort_menu,
            **btn_style
        )
        row.add_widget(self.status_btn)
        row.add_widget(self.cat_btn)
        row.add_widget(self.sort_btn)
        filt.add_widget(row)

        self.progress = MDLabel(
            text="Прогресс: 0/0 (0%)",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=(0.4, 0.4, 0.4, 1),
            size_hint_y=None,
            height=dp(20),
            font_size="11sp"
        )
        filt.add_widget(self.progress)

        sep = MDBoxLayout(size_hint_y=None, height=dp(1), md_bg_color=(0.9, 0.9, 0.9, 1))
        filt.add_widget(sep)
        root.add_widget(filt)

        root.add_widget(self.scroll)

        bottom = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                             height=dp(48), padding=[dp(6), dp(4)], spacing=dp(6),
                             md_bg_color=(0.98, 0.98, 1.0, 1))
        bottom.add_widget(MDRaisedButton(
            text="CSV", on_release=lambda x=None: self.export_csv(),
            md_bg_color=(0.25, 0.55, 1.0, 1),
            font_size="12sp", size_hint_x=1,
            text_color=(1, 1, 1, 1)
        ))
        bottom.add_widget(MDRaisedButton(
            text="Импорт", on_release=lambda x=None: self.import_csv(),
            md_bg_color=(0.6, 0.3, 0.9, 1),
            font_size="12sp", size_hint_x=1,
            text_color=(1, 1, 1, 1)
        ))
        bottom.add_widget(MDRaisedButton(
            text="Очистить", on_release=lambda x=None: self.clear_all(),
            md_bg_color=(0.95, 0.35, 0.35, 1),
            font_size="12sp", size_hint_x=1,
            text_color=(1, 1, 1, 1)
        ))
        root.add_widget(bottom)
        self.add_widget(root)

    def set_service(self, srv):
        self.srv = srv
        self.refresh()

    def refresh(self):
        self.task_list.clear_widgets()
        if not self.srv:
            return
        tasks = self.srv.all_tasks()
        q = self.search.text.lower()
        st = self.status_btn.text
        ct = self.cat_btn.text
        so = self.sort_btn.text

        flt = tasks
        if q:
            flt = [t for t in flt if q in t.title.lower() or q in t.description.lower()]
        if st == "Активные":
            flt = [t for t in flt if not t.is_completed]
        elif st == "Выполненные":
            flt = [t for t in flt if t.is_completed]
        if ct != "Категории":
            flt = [t for t in flt if t.category == ct]

        if so == "Приоритет":
            flt.sort(key=lambda t: (-int(t.priority), t.due_date))
        elif so == "Дата":
            flt.sort(key=lambda t: (t.is_completed, t.due_date))
        elif so == "Создание":
            flt.sort(key=lambda t: t.created_date, reverse=True)
        else:
            flt.sort(key=lambda t: (t.is_completed, -int(t.priority), t.due_date))

        total = len(tasks)
        comp = sum(1 for t in tasks if t.is_completed)
        perc = int(comp / total * 100) if total else 0
        self.progress.text = f"Прогресс: {comp}/{total} ({perc}%)"

        for t in flt:
            card = TaskCard(t, self.toggle, self.confirm_del, self.open_edit)
            self.task_list.add_widget(card)

    def open_status_menu(self, caller):
        items = [
            {"text": "Все", "viewclass": "OneLineListItem",
             "on_release": lambda x="Все": self._set_status(x)},
            {"text": "Активные", "viewclass": "OneLineListItem",
             "on_release": lambda x="Активные": self._set_status(x)},
            {"text": "Выполненные", "viewclass": "OneLineListItem",
             "on_release": lambda x="Выполненные": self._set_status(x)},
        ]
        self.menus["status"] = MDDropdownMenu(caller=caller, items=items, width_mult=3)
        self.menus["status"].open()

    def _set_status(self, s):
        self.status_btn.text = s
        self.menus["status"].dismiss()
        self.refresh()

    def open_cat_menu(self, caller):
        cats = self.srv.categories()
        items = [{"text": "Категории", "viewclass": "OneLineListItem",
                  "on_release": lambda x="Категории": self._set_cat(x)}]
        for c in cats:
            items.append({"text": c, "viewclass": "OneLineListItem",
                          "on_release": lambda x=c: self._set_cat(x)})
        self.menus["cat"] = MDDropdownMenu(caller=caller, items=items, width_mult=3)
        self.menus["cat"].open()

    def _set_cat(self, c):
        self.cat_btn.text = c
        self.menus["cat"].dismiss()
        self.refresh()

    def open_sort_menu(self, caller):
        items = [
            {"text": "Невыполненные", "viewclass": "OneLineListItem",
             "on_release": lambda x="Невыполненные": self._set_sort(x)},
            {"text": "Приоритет", "viewclass": "OneLineListItem",
             "on_release": lambda x="Приоритет": self._set_sort(x)},
            {"text": "Дата", "viewclass": "OneLineListItem",
             "on_release": lambda x="Дата": self._set_sort(x)},
            {"text": "Создание", "viewclass": "OneLineListItem",
             "on_release": lambda x="Создание": self._set_sort(x)},
        ]
        self.menus["sort"] = MDDropdownMenu(caller=caller, items=items, width_mult=3)
        self.menus["sort"].open()

    def _set_sort(self, s):
        self.sort_btn.text = s
        self.menus["sort"].dismiss()
        self.refresh()

    def open_add(self):
        self._form(is_edit=False)

    def open_edit(self, tid):
        t = next((x for x in self.srv.all_tasks() if x.id == tid), None)
        if t:
            self._form(is_edit=True, task=t)

    def _show_date_picker(self, target_btn):
        modal = ModalView(size_hint=(0.9, 0.6), auto_dismiss=True)
        modal.md_bg_color = (0.15, 0.15, 0.15, 1)

        layout = MDBoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        layout.md_bg_color = (0.15, 0.15, 0.15, 1)

        title = MDLabel(
            text="Выберите дату",
            halign="center",
            font_style="H6",
            size_hint_y=None,
            height=dp(40),
            theme_text_color="Custom",
            text_color=(1, 1, 1, 1)
        )
        layout.add_widget(title)

        current = self.sel_date if hasattr(self, 'sel_date') else datetime.now().date()
        day_spinner = Spinner(
            text=str(current.day),
            values=[str(i) for i in range(1, 32)],
            size_hint=(0.3, None), height=dp(40)
        )
        month_spinner = Spinner(
            text=str(current.month),
            values=[str(i) for i in range(1, 13)],
            size_hint=(0.3, None), height=dp(40)
        )
        year_spinner = Spinner(
            text=str(current.year),
            values=[str(i) for i in range(current.year-10, current.year+11)],
            size_hint=(0.3, None), height=dp(40)
        )
        spinner_box = MDBoxLayout(orientation="horizontal", spacing=dp(8), adaptive_height=True)
        spinner_box.add_widget(day_spinner)
        spinner_box.add_widget(month_spinner)
        spinner_box.add_widget(year_spinner)
        layout.add_widget(spinner_box)

        def update_max_days(*args):
            try:
                y = int(year_spinner.text)
                m = int(month_spinner.text)
                if m == 2:
                    max_d = 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28
                elif m in [4,6,9,11]:
                    max_d = 30
                else:
                    max_d = 31
                day_spinner.values = [str(i) for i in range(1, max_d+1)]
                if int(day_spinner.text) > max_d:
                    day_spinner.text = str(max_d)
            except:
                pass

        month_spinner.bind(text=update_max_days)
        year_spinner.bind(text=update_max_days)
        update_max_days()

        btn_box = MDBoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(48), padding=[0, dp(8), 0, 0])
        cancel_btn = MDFlatButton(
            text="ОТМЕНА",
            on_release=lambda x: modal.dismiss(),
            theme_text_color="Custom",
            text_color=(1, 1, 1, 1)
        )
        ok_btn = MDRaisedButton(
            text="ВЫБРАТЬ",
            on_release=lambda x: self._on_date_selected(
                int(day_spinner.text), int(month_spinner.text), int(year_spinner.text), target_btn, modal
            )
        )
        btn_box.add_widget(cancel_btn)
        btn_box.add_widget(ok_btn)
        layout.add_widget(btn_box)

        modal.add_widget(layout)
        modal.open()

    def _on_date_selected(self, day, month, year, target_btn, modal):
        try:
            new_date = datetime(year, month, day).date()
            self.sel_date = new_date
            target_btn.text = f"Дата: {new_date.strftime('%d.%m.%Y')}"
        except:
            snack = Snackbar()
            snack.text = "Некорректная дата"
            snack.open()
        modal.dismiss()

    def _show_time_picker(self, target_btn):
        modal = ModalView(size_hint=(0.8, 0.5), auto_dismiss=True)
        modal.md_bg_color = (0.15, 0.15, 0.15, 1)

        layout = MDBoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        layout.md_bg_color = (0.15, 0.15, 0.15, 1)

        title = MDLabel(
            text="Выберите время",
            halign="center",
            font_style="H6",
            size_hint_y=None,
            height=dp(40),
            theme_text_color="Custom",
            text_color=(1, 1, 1, 1)
        )
        layout.add_widget(title)

        current = self.sel_time if hasattr(self, 'sel_time') else datetime.now().time()
        hour_spinner = Spinner(
            text=str(current.hour).zfill(2),
            values=[f"{i:02d}" for i in range(24)],
            size_hint=(0.4, None), height=dp(40)
        )
        minute_spinner = Spinner(
            text=str(current.minute).zfill(2),
            values=[f"{i:02d}" for i in range(0, 60, 5)],
            size_hint=(0.4, None), height=dp(40)
        )
        time_box = MDBoxLayout(orientation="horizontal", spacing=dp(8), adaptive_height=True, pos_hint={'center_x':0.5})
        time_box.add_widget(hour_spinner)
        time_box.add_widget(minute_spinner)
        layout.add_widget(time_box)

        btn_box = MDBoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(48), padding=[0, dp(8), 0, 0])
        cancel_btn = MDFlatButton(
            text="ОТМЕНА",
            on_release=lambda x: modal.dismiss(),
            theme_text_color="Custom",
            text_color=(1, 1, 1, 1)
        )
        ok_btn = MDRaisedButton(
            text="ВЫБРАТЬ",
            on_release=lambda x: self._on_time_selected(
                int(hour_spinner.text), int(minute_spinner.text), target_btn, modal
            )
        )
        btn_box.add_widget(cancel_btn)
        btn_box.add_widget(ok_btn)
        layout.add_widget(btn_box)

        modal.add_widget(layout)
        modal.open()

    def _on_time_selected(self, hour, minute, target_btn, modal):
        self.sel_time = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0).time()
        target_btn.text = f"Время: {self.sel_time.strftime('%H:%M')}"
        modal.dismiss()

    def _form(self, is_edit, task=None):
        content_box = MDBoxLayout(
            orientation="vertical",
            spacing=dp(8),
            padding=dp(8),
            adaptive_height=True
        )

        tf = MDTextField(
            hint_text="Название задачи",
            text=task.title if task else "",
            font_size="14sp",
            mode="fill",
            fill_color_normal=(0.95, 0.95, 0.95, 1),
            radius=[dp(10), dp(10), dp(10), dp(10)],
            size_hint_y=None,
            height=dp(48)
        )
        df = MDTextField(
            hint_text="Описание",
            text=task.description if task else "",
            multiline=True,
            font_size="14sp",
            mode="fill",
            fill_color_normal=(0.95, 0.95, 0.95, 1),
            radius=[dp(10), dp(10), dp(10), dp(10)],
            size_hint_y=None,
            height=dp(80)
        )
        cf = MDTextField(
            hint_text="Категория",
            text=task.category if task else "Общие",
            font_size="14sp",
            mode="fill",
            fill_color_normal=(0.95, 0.95, 0.95, 1),
            radius=[dp(10), dp(10), dp(10), dp(10)],
            size_hint_y=None,
            height=dp(48)
        )
        content_box.add_widget(tf)
        content_box.add_widget(df)
        content_box.add_widget(cf)

        pb = MDBoxLayout(orientation="horizontal", spacing=dp(4),
                         size_hint_y=None, height=dp(38))
        btns = []
        for i, (txt, val) in enumerate([("Низкий", 0), ("Средний", 1), ("Высокий", 2)]):
            btn = MDRaisedButton(
                text=txt,
                font_size="12sp",
                size_hint_x=1,
                md_bg_color=(0.25, 0.45, 0.85, 1) if i == (int(task.priority) if task else 1) else (0.93, 0.95, 0.98, 1),
                text_color=(1, 1, 1, 1) if i == (int(task.priority) if task else 1) else (0.2, 0.2, 0.2, 1),
                on_release=lambda x=None, v=val: self._set_pri(v, btns)
            )
            btns.append(btn)
            pb.add_widget(btn)
        content_box.add_widget(pb)

        dt_box = MDBoxLayout(orientation="horizontal", spacing=dp(4),
                             size_hint_y=None, height=dp(38))
        self.sel_date = task.due_date.date() if task else datetime.now().date()
        self.sel_time = task.due_date.time() if task else datetime.now().time()
        dbtn = MDRaisedButton(
            text=f"Дата: {self.sel_date.strftime('%d.%m.%Y')}",
            font_size="12sp",
            size_hint_x=1,
            md_bg_color=(0.93, 0.95, 0.98, 1),
            text_color=(0.2, 0.2, 0.2, 1)
        )
        tbtn = MDRaisedButton(
            text=f"Время: {self.sel_time.strftime('%H:%M')}",
            font_size="12sp",
            size_hint_x=1,
            md_bg_color=(0.93, 0.95, 0.98, 1),
            text_color=(0.2, 0.2, 0.2, 1)
        )
        dbtn.on_release = lambda x=None: self._show_date_picker(dbtn)
        tbtn.on_release = lambda x=None: self._show_time_picker(tbtn)
        dt_box.add_widget(dbtn)
        dt_box.add_widget(tbtn)
        content_box.add_widget(dt_box)

        rbox = MDBoxLayout(orientation="horizontal", spacing=dp(4),
                           size_hint_y=None, height=dp(40))
        self.chk_rec = MDCheckbox(
            active=task.recurrence != RecurrenceType.NONE if task else False,
            size_hint=(None, None),
            size=(dp(28), dp(28))
        )
        typ = {RecurrenceType.DAILY: "Ежедн",
               RecurrenceType.WEEKLY: "Еженед",
               RecurrenceType.MONTHLY: "Ежемес"}
        cur = typ.get(task.recurrence, "Еженед") if task else "Еженед"
        rbtn = MDRaisedButton(
            text=cur,
            font_size="11sp",
            size_hint_x=0.4,
            md_bg_color=(0.93, 0.95, 0.98, 1),
            text_color=(0.2, 0.2, 0.2, 1),
            on_release=lambda x=None: self._rec_menu(rbtn)
        )
        intf = MDTextField(
            text=str(task.recurrence_interval if task else 1),
            hint_text="Интервал",
            input_filter="int",
            font_size="11sp",
            mode="fill",
            fill_color_normal=(0.95, 0.95, 0.95, 1),
            radius=[dp(10), dp(10), dp(10), dp(10)],
            size_hint_x=0.3,
            width=dp(50),
            height=dp(36)
        )
        rbox.add_widget(self.chk_rec)
        rbox.add_widget(rbtn)
        rbox.add_widget(intf)
        content_box.add_widget(rbox)

        scroll = ScrollView(size_hint_y=None, height=dp(450))
        scroll.add_widget(content_box)

        dlg = MDDialog(
            title="Редактирование" if is_edit else "Новая задача",
            type="custom",
            content_cls=scroll,
            radius=[dp(20), dp(20), dp(20), dp(20)],
            buttons=[
                MDFlatButton(
                    text="ОТМЕНА",
                    on_release=lambda x=None: dlg.dismiss(),
                    font_size="12sp"
                ),
                MDRaisedButton(
                    text="СОХРАНИТЬ",
                    md_bg_color=(0.25, 0.45, 0.85, 1),
                    text_color=(1, 1, 1, 1),
                    on_release=lambda x=None: self._save(
                        is_edit, task, tf.text, df.text, cf.text,
                        rbtn.text, self.chk_rec.active, intf.text, dlg
                    ),
                    font_size="12sp"
                )
            ]
        )
        dlg.open()

    def _set_pri(self, val, btns):
        for i, b in enumerate(btns):
            b.md_bg_color = (0.25, 0.45, 0.85, 1) if i == val else (0.93, 0.95, 0.98, 1)
            b.text_color = (1, 1, 1, 1) if i == val else (0.2, 0.2, 0.2, 1)
        self.sel_pri = val

    def _rec_menu(self, caller):
        items = [
            {"text": t, "viewclass": "OneLineListItem",
             "on_release": lambda x=t: (
                 setattr(caller, 'text', x),
                 self.menus["rec"].dismiss()
             )}
            for t in ["Ежедневно", "Еженедельно", "Ежемесячно"]
        ]
        self.menus["rec"] = MDDropdownMenu(caller=caller, items=items, width_mult=2)
        self.menus["rec"].open()

    def _save(self, is_edit, task, title, desc, cat, rec_txt, rec_act, int_str, dlg):
        if not title.strip():
            snack = Snackbar()
            snack.text = "Введите название"
            snack.open()
            return
        pri = TaskPriority(self.sel_pri)
        try:
            interval = int(int_str) if int_str else 1
        except ValueError:
            interval = 1
        rec = RecurrenceType.NONE
        if rec_act:
            mp = {"Ежедн": RecurrenceType.DAILY,
                  "Еженед": RecurrenceType.WEEKLY,
                  "Ежемес": RecurrenceType.MONTHLY}
            rec = mp.get(rec_txt, RecurrenceType.WEEKLY)
        dt = datetime.combine(self.sel_date, self.sel_time)

        if is_edit and task:
            task.title = title.strip()
            task.description = desc.strip()
            task.category = cat.strip() or "Общие"
            task.priority = pri
            task.due_date = dt
            task.recurrence = rec
            task.recurrence_interval = interval
            self.srv.update_task(task)
        else:
            self.srv.add_task(TaskModel(title, cat, pri, dt, desc, rec, interval))
        dlg.dismiss()
        self.refresh()

    def toggle(self, tid):
        self.srv.toggle_completion(tid)
        self.refresh()

    def confirm_del(self, tid):
        t = next((x for x in self.srv.all_tasks() if x.id == tid), None)
        if not t:
            return
        dlg = MDDialog(
            title="Удалить?",
            text=f"'{t.title}'?",
            radius=[dp(20), dp(20), dp(20), dp(20)],
            buttons=[
                MDFlatButton(text="Нет", on_release=lambda x=None: dlg.dismiss()),
                MDRaisedButton(text="Да", on_release=lambda x=None: self._del(tid, dlg))
            ]
        )
        dlg.open()

    def _del(self, tid, dlg):
        self.srv.delete_task(tid)
        dlg.dismiss()
        self.refresh()

    def export_csv(self, *a):
        if not self.fm:
            self.fm = MDFileManager(
                exit_manager=lambda x=None: self.fm.close(),
                select_path=self._sel_path
            )
        self.export_mode = True
        self.fm.show(os.path.expanduser("~"))

    def import_csv(self, *a):
        if not self.fm:
            self.fm = MDFileManager(
                exit_manager=lambda x=None: self.fm.close(),
                select_path=self._sel_path
            )
        self.export_mode = False
        self.fm.show(os.path.expanduser("~"))

    def _sel_path(self, path):
        if self.export_mode:
            self._do_export(path)
        else:
            self._do_import(path)
        self.fm.close()

    def _do_export(self, dir_path):
        try:
            fp = os.path.join(dir_path, "tasks_export.csv")
            with open(fp, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Id", "Title", "Category", "Priority", "DueDate",
                            "IsCompleted", "Description", "Recurrence", "RecurrenceInterval"])
                for t in self.srv.all_tasks():
                    w.writerow([t.id, t.title, t.category, int(t.priority),
                                t.due_date.isoformat(), t.is_completed,
                                t.description, int(t.recurrence), t.recurrence_interval])
            snack = Snackbar()
            snack.text = f"Экспорт: {fp}"
            snack.open()
        except Exception as e:
            snack = Snackbar()
            snack.text = f"Ошибка: {e}"
            snack.open()

    def _do_import(self, fp):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                r = csv.DictReader(f)
                cnt = 0
                for row in r:
                    try:
                        t = TaskModel(
                            title=row["Title"],
                            category=row.get("Category", "Общие"),
                            priority=TaskPriority(int(row["Priority"])),
                            due_date=datetime.fromisoformat(row["DueDate"]),
                            description=row.get("Description", ""),
                            recurrence=RecurrenceType(int(row["Recurrence"])),
                            recurrence_interval=int(row.get("RecurrenceInterval", 1)),
                            is_completed=row.get("IsCompleted", "False").lower() == "true",
                            task_id=row["Id"]
                        )
                        self.srv.add_task(t)
                        cnt += 1
                    except:
                        pass
            snack = Snackbar()
            snack.text = f"Импортировано: {cnt}"
            snack.open()
            self.refresh()
        except Exception as e:
            snack = Snackbar()
            snack.text = f"Ошибка: {e}"
            snack.open()

    def clear_all(self, *a):
        all_tasks = self.srv.all_tasks()
        if not all_tasks:
            snack = Snackbar()
            snack.text = "Нет задач для удаления"
            snack.open()
            return
        dlg = MDDialog(
            title="Очистить всё?",
            text=f"Вы действительно хотите удалить ВСЕ задачи ({len(all_tasks)} шт.)?",
            radius=[dp(20), dp(20), dp(20), dp(20)],
            buttons=[
                MDFlatButton(text="Нет", on_release=lambda x=None: dlg.dismiss()),
                MDRaisedButton(text="Да, удалить всё", on_release=lambda x=None: self._clear_all(dlg))
            ]
        )
        dlg.open()

    def _clear_all(self, dlg):
        for t in self.srv.all_tasks():
            self.srv.delete_task(t.id)
        dlg.dismiss()
        self.refresh()
        snack = Snackbar()
        snack.text = "Все задачи удалены"
        snack.open()


class TaskPlannerApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.theme_style = "Light"

        Window.size = (360, 640)

        data_file = os.path.join(self.user_data_dir, "tasks.json")
        repo = TaskRepository(data_file)
        self.srv = TaskService(repo)

        self.screen = PlannerScreen()
        self.screen.set_service(self.srv)

        Clock.schedule_interval(self._notify, 30)
        return self.screen

    def _notify(self, dt):
        now = datetime.now()
        for t in self.srv.all_tasks():
            if not t.is_completed and not t.was_notified \
                    and abs((t.due_date - now).total_seconds()) <= 300:
                if PLYER_AVAILABLE:
                    try:
                        notification.notify(
                            title="Дедлайн",
                            message=t.title,
                            timeout=5
                        )
                    except:
                        pass
                self.srv.mark_notified(t.id)


if __name__ == "__main__":
    TaskPlannerApp().run()