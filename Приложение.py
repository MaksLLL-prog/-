import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import datetime
import time
import threading
import json
import os
import random
from PIL import Image, ImageTk  # Для работы с изображениями


try:
    from plyer import notification
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False
    print("plyer не установлен. Уведомления будут отображаться через messagebox.")


class Task:
    def __init__(self, description, due_date, completed=False):
        self.description = description
        self.due_date = due_date
        self.completed = completed

    def __str__(self):
        return f"{self.description} (Срок: {self.due_date.strftime('%Y-%m-%d')})"

    def to_dict(self):
        return {
            "description": self.description,
            "due_date": self.due_date.strftime("%Y-%m-%d"),
            "completed": self.completed
        }

    @classmethod
    def from_dict(cls, data):
        return cls(data["description"], datetime.datetime.strptime(data["due_date"], "%Y-%m-%d").date(),
                   data["completed"])


class Habit:
    def __init__(self, description, frequency, goal="", completed_dates=None):
        self.description = description
        self.frequency = frequency  # "daily", "weekly", "monthly"
        self.goal = goal
        self.completed_dates = completed_dates or {}

    def __str__(self):
        return f"{self.description} ({self.frequency})"

    def to_dict(self):
        return {
            "description": self.description,
            "frequency": self.frequency,
            "goal": self.goal,
            "completed_dates": self.completed_dates
        }

    @classmethod
    def from_dict(cls, data):
        return cls(data["description"], data["frequency"], data["goal"], data["completed_dates"])


class UserProfile:
    def __init__(self, name="Новый пользователь", level=1, experience=0, quests_completed=0, avatar_path=None, birth_year=None):
        self.name = name
        self.level = level
        self.experience = experience
        self.quests_completed = quests_completed
        self.avatar_path = avatar_path  # Путь к файлу аватарки
        self.birth_year = birth_year

    def to_dict(self):
        return {
            "name": self.name,
            "level": self.level,
            "experience": self.experience,
            "quests_completed": self.quests_completed,
            "avatar_path": self.avatar_path,
            "birth_year": self.birth_year
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data.get("name", "Новый пользователь"),
            level=data.get("level", 1),
            experience=data.get("experience", 0),
            quests_completed=data.get("quests_completed", 0),
            avatar_path=data.get("avatar_path"),
            birth_year=data.get("birth_year")
        )


class TaskManager:
    def __init__(self, master):
        self.master = master
        master.title("Менеджер задач и привычек")

        self.tasks = []
        self.habits = []
        self.user_profile = UserProfile()  # Создаем профиль пользователя
        self.quests = self.load_quests()
        self.active_quest = None

        self.data_file = "data.json"

        # --- Styling ---
        self.style = ttk.Style()
        self.style.configure("TButton", padding=5, relief="flat", background="#f0f0f0")
        self.style.configure("TLabelFrame.Label", font=('Arial', 12, 'bold'))

        # --- GUI Components ---
        # Notebook for Tabs
        self.notebook = ttk.Notebook(master)
        self.notebook.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        # Task Frame
        self.task_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.task_frame, text="Задачи")
        self.create_task_tab(self.task_frame)

        # Habit Frame
        self.habit_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.habit_frame, text="Привычки")
        self.create_habit_tab(self.habit_frame)

        # User Frame
        self.user_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.user_frame, text="Профиль")
        self.create_user_tab(self.user_frame)

        # --- Bottom Buttons Frame ---
        self.bottom_frame = ttk.Frame(master)
        self.bottom_frame.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

        self.save_button = ttk.Button(self.bottom_frame, text="Сохранить", command=self.save_data)
        self.save_button.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.load_button = ttk.Button(self.bottom_frame, text="Загрузить", command=self.load_data)
        self.load_button.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # --- Configure Weights ---
        master.columnconfigure(0, weight=1)
        self.bottom_frame.columnconfigure(0, weight=1)
        self.bottom_frame.columnconfigure(1, weight=1)

        # Load data and start reminders
        self.load_data()
        self.update_task_list()
        self.update_habit_list()
        self.update_user_profile()
        self.assign_quest()  # Назначаем первый квест
        self.start_reminder_thread()

    def create_task_tab(self, frame):
        self.task_description_label = ttk.Label(frame, text="Описание:")
        self.task_description_label.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.task_description_entry = ttk.Entry(frame, width=40)
        self.task_description_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")

        self.task_due_date_label = ttk.Label(frame, text="Срок (ГГГГ-ММ-ДД):")
        self.task_due_date_label.grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.task_due_date_entry = ttk.Entry(frame, width=15)
        self.task_due_date_entry.grid(row=1, column=1, padx=5, pady=2, sticky="ew")

        self.add_task_button = ttk.Button(frame, text="Добавить задачу", command=self.add_task)
        self.add_task_button.grid(row=2, column=0, columnspan=2, padx=5, pady=5)

        self.task_listbox = tk.Listbox(frame, width=50, height=10)
        self.task_listbox.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        self.task_listbox.bind("<Double-Button-1>", self.complete_task)

        frame.columnconfigure(1, weight=1)  # Entry expands
        frame.rowconfigure(3, weight=1)  # Listbox expands

    def create_habit_tab(self, frame):
        self.habit_description_label = ttk.Label(frame, text="Описание:")
        self.habit_description_label.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.habit_description_entry = ttk.Entry(frame, width=40)
        self.habit_description_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")

        self.habit_frequency_label = ttk.Label(frame, text="Частота:")
        self.habit_frequency_label.grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.habit_frequency_combobox = ttk.Combobox(frame, values=["daily", "weekly", "monthly"], state="readonly")
        self.habit_frequency_combobox.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        self.habit_frequency_combobox.set("daily")

        self.add_habit_button = ttk.Button(frame, text="Добавить привычку", command=self.add_habit)
        self.add_habit_button.grid(row=2, column=0, columnspan=2, padx=5, pady=5)

        self.habit_listbox = tk.Listbox(frame, width=50, height=10)
        self.habit_listbox.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        self.habit_listbox.bind("<Double-Button-1>", self.complete_habit)

        frame.columnconfigure(1, weight=1)  # Entry expands
        frame.rowconfigure(3, weight=1)  # Listbox expands

    def create_user_tab(self, frame):
        # Avatar
        self.avatar_label = ttk.Label(frame, text="Аватар:")
        self.avatar_label.grid(row=0, column=0, padx=5, pady=2, sticky="w")

        self.avatar_image = None
        self.avatar_image_label = ttk.Label(frame)
        self.avatar_image_label.grid(row=1, column=0, columnspan=2, padx=5, pady=2)
        self.load_avatar()

        self.browse_avatar_button = ttk.Button(frame, text="Выбрать аватар", command=self.browse_avatar)
        self.browse_avatar_button.grid(row=2, column=0, columnspan=2, padx=5, pady=5)

        # Name
        self.user_name_label = ttk.Label(frame, text="Имя:")
        self.user_name_label.grid(row=3, column=0, padx=5, pady=2, sticky="w")
        self.user_name_entry = ttk.Entry(frame, width=30)
        self.user_name_entry.grid(row=3, column=1, padx=5, pady=2, sticky="ew")
        self.user_name_entry.bind("<Return>", self.update_user_profile)

        # Birth Year
        self.birth_year_label = ttk.Label(frame, text="Год рождения:")
        self.birth_year_label.grid(row=4, column=0, padx=5, pady=2, sticky="w")
        self.birth_year_entry = ttk.Entry(frame, width=10)
        self.birth_year_entry.grid(row=4, column=1, padx=5, pady=2, sticky="ew")

        # Level, Experience, Quests Completed
        self.level_label = ttk.Label(frame, text="Уровень:")
        self.level_label.grid(row=5, column=0, padx=5, pady=2, sticky="w")
        self.level_value_label = ttk.Label(frame, text=str(self.user_profile.level))
        self.level_value_label.grid(row=5, column=1, padx=5, pady=2, sticky="w")

        self.experience_label = ttk.Label(frame, text="Опыт:")
        self.experience_label.grid(row=6, column=0, padx=5, pady=2, sticky="w")
        self.experience_value_label = ttk.Label(frame, text=str(self.user_profile.experience))
        self.experience_value_label.grid(row=6, column=1, padx=5, pady=2, sticky="w")

        self.quests_completed_label = ttk.Label(frame, text="Квестов выполнено:")
        self.quests_completed_label.grid(row=7, column=0, padx=5, pady=2, sticky="w")
        self.quests_completed_value_label = ttk.Label(frame, text=str(self.user_profile.quests_completed))
        self.quests_completed_value_label.grid(row=7, column=1, padx=5, pady=2, sticky="w")

        self.active_quest_label = ttk.Label(frame, text="Активный квест:")
        self.active_quest_label.grid(row=8, column=0, padx=5, pady=2, sticky="w")
        if self.active_quest:
            self.active_quest_value_label = ttk.Label(frame, text=self.active_quest["description"])
        else:
            self.active_quest_value_label = ttk.Label(frame, text="Нет активного квеста")
        self.active_quest_value_label.grid(row=8, column=1, padx=5, pady=2, sticky="w")

        self.update_profile_button = ttk.Button(frame, text="Сохранить профиль", command=self.update_user_profile)
        self.update_profile_button.grid(row=9, column=0, columnspan=2, padx=5, pady=5)

        frame.columnconfigure(1, weight=1)

    def browse_avatar(self):
        file_path = filedialog.askopenfilename(
            initialdir=os.getcwd(),
            title="Выберите файл аватарки",
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.gif")]
        )
        if file_path:
            self.user_profile.avatar_path = file_path
            self.load_avatar()
            self.save_data()

    def load_avatar(self):
        if self.user_profile.avatar_path:
            try:
                image = Image.open(self.user_profile.avatar_path)
                image = image.resize((100, 100), Image.Resampling.LANCZOS)  # Измените размер по желанию
                self.avatar_image = ImageTk.PhotoImage(image)
                self.avatar_image_label.config(image=self.avatar_image)
            except Exception as e:
                print(f"Ошибка при загрузке аватарки: {e}")
                messagebox.showerror("Ошибка", f"Не удалось загрузить аватарку: {e}")
        else:
            # Устанавливаем пустое изображение, если аватарка отсутствует
            self.avatar_image_label.config(image="")

    def add_task(self):
        description = self.task_description_entry.get()
        due_date_str = self.task_due_date_entry.get()

        try:
            due_date = datetime.datetime.strptime(due_date_str, "%Y-%m-%d").date()
        except ValueError:
            messagebox.showerror("Ошибка", "Неверный формат даты. Используйте ГГГГ-ММ-ДД.")
            return

        if description and due_date:
            task = Task(description, due_date)
            self.tasks.append(task)
            self.update_task_list()
            self.task_description_entry.delete(0, tk.END)
            self.task_due_date_entry.delete(0, tk.END)
            self.save_data()
        else:
            messagebox.showerror("Ошибка", "Пожалуйста, заполните описание и дату.")

    def add_habit(self):
        description = self.habit_description_entry.get()
        frequency = self.habit_frequency_combobox.get()

        if description and frequency:
            habit = Habit(description, frequency)
            self.habits.append(habit)
            self.update_habit_list()
            self.habit_description_entry.delete(0, tk.END)
            self.save_data()
        else:
            messagebox.showerror("Ошибка", "Пожалуйста, заполните описание и частоту.")

    def complete_task(self, event=None):
        try:
            selected_index = self.task_listbox.curselection()[0]
            task = self.tasks[selected_index]
            task.completed = not task.completed
            self.update_task_list()
            self.save_data()

            if task.completed:
                self.award_experience(10)  # Награждаем опытом за выполнение задачи
                self.check_quest_completion()  # Проверяем, завершили ли квест

        except IndexError:
            messagebox.showinfo("Информация", "Выберите задачу для отметки как выполненной/невыполненной.")

    def complete_habit(self, event=None):
        try:
            selected_index = self.habit_listbox.curselection()[0]
            habit = self.habits[selected_index]
            today = datetime.date.today().strftime("%Y-%m-%d")
            if today in habit.completed_dates:
                del habit.completed_dates[today]
            else:
                habit.completed_dates[today] = True
            self.update_habit_list()
            self.save_data()

            self.award_experience(5)  # Награждаем опытом за выполнение привычки
            self.check_quest_completion()  # Проверяем, завершили ли квест

        except IndexError:
            messagebox.showinfo("Информация", "Выберите привычку для отметки выполнения.")

    def update_task_list(self):
        self.task_listbox.delete(0, tk.END)
        for i, task in enumerate(self.tasks):
            status = "[Выполнено]" if task.completed else ""
            self.task_listbox.insert(tk.END, f"{i + 1}. {task} {status}")

    def update_habit_list(self):
        self.habit_listbox.delete(0, tk.END)
        for i, habit in enumerate(self.habits):
            completed_today = datetime.date.today().strftime("%Y-%m-%d") in habit.completed_dates
            status = "[Выполнено сегодня]" if completed_today else ""
            self.habit_listbox.insert(tk.END, f"{i + 1}. {habit} {status}")

    def update_user_profile(self, event=None):
        # Get data from entry fields
        name = self.user_name_entry.get()
        birth_year_str = self.birth_year_entry.get()

        # Validate birth year
        try:
            birth_year = int(birth_year_str) if birth_year_str else None
            if birth_year and (birth_year < 1900 or birth_year > datetime.datetime.now().year):
                messagebox.showerror("Ошибка", "Некорректный год рождения")
                return
        except ValueError:
            messagebox.showerror("Ошибка", "Некорректный год рождения")
            return

        # Update user profile
        self.user_profile.name = name if name else "Новый пользователь"
        self.user_profile.birth_year = birth_year

        # Update GUI labels
        self.level_value_label.config(text=str(self.user_profile.level))
        self.experience_value_label.config(text=str(self.user_profile.experience))
        self.quests_completed_value_label.config(text=str(self.user_profile.quests_completed))

        # Update the name entry field
        self.user_name_entry.delete(0, tk.END)
        self.user_name_entry.insert(0, self.user_profile.name)

        self.save_data()
        messagebox.showinfo("Информация", "Профиль пользователя обновлен!")

    def award_experience(self, amount):
        self.user_profile.experience += amount
        self.check_level_up()
        self.update_user_profile()
        self.save_data()

    def check_level_up(self):
        level_up_threshold = self.user_profile.level * 100
        if self.user_profile.experience >= level_up_threshold:
            self.user_profile.level += 1
            self.user_profile.experience -= level_up_threshold
            messagebox.showinfo("Повышение уровня!", f"Поздравляем! Вы достигли {self.user_profile.level} уровня!")

    def assign_quest(self):
        if self.quests and not self.active_quest:
            self.active_quest = random.choice(self.quests)
            self.update_user_profile()
            messagebox.showinfo("Новый квест!", f"Вам назначен новый квест: {self.active_quest['description']}")

    def check_quest_completion(self):
        if self.active_quest:
            if self.active_quest["type"] == "complete_tasks":
                completed_task_count = sum(1 for task in self.tasks if task.completed)
                if completed_task_count >= self.active_quest["amount"]:
                    self.complete_quest()
            elif self.active_quest["type"] == "complete_habits":
                completed_habit_today = any(
                    habit.completed_dates.get(datetime.date.today().strftime("%Y-%m-%d")) for habit in self.habits)
                if completed_habit_today:
                    self.complete_quest()

    def complete_quest(self):
        messagebox.showinfo("Квест выполнен!",
                            f"Вы выполнили квест: {self.active_quest['description']}! Награда: {self.active_quest['reward']} опыта.")
        self.award_experience(self.active_quest["reward"])
        self.user_profile.quests_completed += 1
        self.active_quest = None
        self.assign_quest()
        self.update_user_profile()

    def load_quests(self):
        return [
            {"type": "complete_tasks", "description": "Выполните 3 задачи", "amount": 3, "reward": 50},
            {"type": "complete_habits", "description": "Отметьте выполнение хотя бы одной привычки сегодня", "amount": 1,
             "reward": 30}
        ]

    def check_reminders(self):
        while True:
            now = datetime.datetime.now()
            for task in self.tasks:
                if not task.completed and task.due_date <= now.date():
                    self.show_notification("Задача!", f"Задача '{task.description}' должна быть выполнена сегодня!")

            # TODO: Добавить логику для напоминаний о привычках (в зависимости от частоты)

            time.sleep(60)

    def show_notification(self, title, message):
        if HAS_PLYER:
            notification.notify(
                title=title,
                message=message,
                timeout=10
            )
        else:
            messagebox.showinfo(title, message)

    def save_data(self):
        try:
            data = {
                "tasks": [task.to_dict() for task in self.tasks],
                "habits": [habit.to_dict() for habit in self.habits],
                "user_profile": self.user_profile.to_dict()
            }
            with open(self.data_file, "w") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка при сохранении данных: {e}")
            messagebox.showerror("Ошибка", f"Не удалось сохранить данные: {e}")

    def load_data(self):
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, "r") as f:
                    data = json.load(f)
                    self.tasks = [Task.from_dict(t) for t in data.get("tasks", [])]
                    self.habits = [Habit.from_dict(h) for h in data.get("habits", [])]
                    user_profile_data = data.get("user_profile")
                    if user_profile_data:
                        self.user_profile = UserProfile.from_dict(user_profile_data)
        except FileNotFoundError:
            print("Файл данных не найден. Начинаем с чистого листа.")
        except json.JSONDecodeError:
            print("Ошибка при загрузке данных: Файл поврежден.")
            messagebox.showerror("Ошибка", "Файл данных поврежден. Начинаем с чистого листа.")
            self.tasks = []
            self.habits = []
            self.user_profile = UserProfile()
        except Exception as e:
            print(f"Неожиданная ошибка при загрузке данных: {e}")
            messagebox.showerror("Ошибка", f"Неожиданная ошибка при загрузке данных: {e}")

    def start_reminder_thread(self):
        reminder_thread = threading.Thread(target=self.check_reminders, daemon=True)
        reminder_thread.start()


root = tk.Tk()
root.geometry("600x500")
root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)

task_manager = TaskManager(root)
root.mainloop()
