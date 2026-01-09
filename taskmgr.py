import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
from datetime import datetime

# --- Constants ---
DATA_FILE = "tasks.json"
FONT_MAIN = ("Helvetica", 11)
FONT_HEADER = ("Helvetica", 12, "bold")
FONT_STRIKE = ("Helvetica", 11, "overstrike")

class TaskManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Python Task Manager")
        self.root.geometry("500x600")
        self.root.minsize(400, 500)

        # Data initialization
        self.tasks = []
        self.current_filter = "All"  # Options: All, Active, Completed
        self.load_tasks()

        # UI Setup
        self.style = ttk.Style()
        self.style.configure("TButton", font=FONT_MAIN, padding=5)
        self.style.configure("TEntry", font=FONT_MAIN, padding=5)
        
        self.setup_ui()
        self.refresh_task_list()

    def setup_ui(self):
        """Builds the main graphical user interface."""
        
        # 1. Header / Input Section
        input_frame = ttk.Frame(self.root, padding="10")
        input_frame.pack(fill=tk.X)

        self.task_var = tk.StringVar()
        self.task_entry = ttk.Entry(input_frame, textvariable=self.task_var, font=FONT_MAIN)
        self.task_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.task_entry.bind("<Return>", lambda event: self.add_task())

        add_btn = ttk.Button(input_frame, text="Add Task", command=self.add_task)
        add_btn.pack(side=tk.RIGHT)

        # 2. Filter Section
        filter_frame = ttk.Frame(self.root, padding="5")
        filter_frame.pack(fill=tk.X)

        self.filter_var = tk.StringVar(value="All")
        
        # Using Radiobuttons for filters to make it exclusive
        filters = ["All", "Active", "Completed"]
        for f in filters:
            rb = ttk.Radiobutton(
                filter_frame, 
                text=f, 
                variable=self.filter_var, 
                value=f, 
                command=self.apply_filter
            )
            rb.pack(side=tk.LEFT, padx=10)

        # 3. Task List Section (Scrollable)
        # Create a container frame for canvas + scrollbar
        list_container = ttk.Frame(self.root)
        list_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.canvas = tk.Canvas(list_container, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.canvas.yview)
        
        # The frame that will actually hold the task widgets
        self.scrollable_frame = ttk.Frame(self.canvas)

        # Configure the scrollable region
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        # Create window inside canvas
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        # Bind mousewheel for better UX
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 4. Footer / Status
        self.status_var = tk.StringVar()
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w", padding=2)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.update_status()

    def _on_mousewheel(self, event):
        """Handle mousewheel scrolling for the canvas."""
        if self.canvas.winfo_exists():
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def add_task(self):
        """Adds a new task to the list."""
        title = self.task_var.get().strip()
        if not title:
            return

        new_task = {
            "id": datetime.now().isoformat(), # Simple unique ID based on timestamp
            "title": title,
            "completed": False,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        }

        self.tasks.append(new_task)
        self.task_var.set("") # Clear input
        self.save_tasks()
        self.refresh_task_list()
        self.update_status()

    def delete_task(self, task_id):
        """Deletes a task by ID."""
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this task?"):
            self.tasks = [t for t in self.tasks if t['id'] != task_id]
            self.save_tasks()
            self.refresh_task_list()
            self.update_status()

    def toggle_task(self, task_id, var):
        """Toggles the completion status of a task."""
        for task in self.tasks:
            if task['id'] == task_id:
                task['completed'] = bool(var.get())
                break
        
        self.save_tasks()
        # We re-render to update fonts (strikethrough) and filtering logic
        self.refresh_task_list()
        self.update_status()

    def apply_filter(self):
        """Update current filter and refresh list."""
        self.current_filter = self.filter_var.get()
        self.refresh_task_list()

    def refresh_task_list(self):
        """Clears and rebuilds the list of tasks based on data and filter."""
        # Clear existing widgets in scrollable frame
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Filter tasks
        filtered_tasks = []
        for task in self.tasks:
            if self.current_filter == "All":
                filtered_tasks.append(task)
            elif self.current_filter == "Active" and not task['completed']:
                filtered_tasks.append(task)
            elif self.current_filter == "Completed" and task['completed']:
                filtered_tasks.append(task)

        # Sort: Active first, then by creation date
        # (False < True, so uncompleted tasks come first)
        filtered_tasks.sort(key=lambda x: (x['completed'], x['created_at']), reverse=False)

        if not filtered_tasks:
            lbl = ttk.Label(self.scrollable_frame, text="No tasks found.", foreground="gray", padding=20)
            lbl.pack()

        # Build rows
        for task in filtered_tasks:
            self._create_task_row(task)

        # Ensure the frame width matches the canvas width for aesthetics
        self.scrollable_frame.update_idletasks()
        self.canvas.itemconfigure("all", width=self.canvas.winfo_width())

    def _create_task_row(self, task):
        """Creates a single visual row for a task."""
        # Frame for the row
        row_frame = ttk.Frame(self.scrollable_frame)
        row_frame.pack(fill=tk.X, pady=2, padx=5)

        # Checkbox
        is_done = tk.IntVar(value=1 if task['completed'] else 0)
        chk = ttk.Checkbutton(
            row_frame, 
            variable=is_done, 
            command=lambda t=task['id'], v=is_done: self.toggle_task(t, v)
        )
        chk.pack(side=tk.LEFT)

        # Task Text Label
        text_font = FONT_STRIKE if task['completed'] else FONT_MAIN
        text_color = "gray" if task['completed'] else "black"
        
        lbl = tk.Label(
            row_frame, 
            text=task['title'], 
            font=text_font, 
            fg=text_color, 
            bg="white" if not task['completed'] else "#f0f0f0",
            anchor="w",
            wraplength=350, # Wrap text if it gets too long
            justify="left"
        )
        # Add a white background to labels for cleaner look on canvas
        lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Delete Button
        del_btn = tk.Button(
            row_frame, 
            text="×", 
            font=("Arial", 12, "bold"),
            fg="white", 
            bg="#ff5555", 
            activebackground="#ff0000",
            activeforeground="white",
            relief=tk.FLAT,
            width=3,
            command=lambda t=task['id']: self.delete_task(t)
        )
        del_btn.pack(side=tk.RIGHT)
        
        # Separator line
        ttk.Separator(self.scrollable_frame, orient='horizontal').pack(fill=tk.X, padx=5)

    def update_status(self):
        """Updates the status bar counts."""
        total = len(self.tasks)
        completed = sum(1 for t in self.tasks if t['completed'])
        active = total - completed
        self.status_var.set(f"Total: {total} | Active: {active} | Completed: {completed}")

    def load_tasks(self):
        """Loads tasks from JSON file."""
        if not os.path.exists(DATA_FILE):
            self.tasks = []
            return

        try:
            with open(DATA_FILE, 'r') as f:
                self.tasks = json.load(f)
        except (json.JSONDecodeError, IOError):
            self.tasks = []
            messagebox.showerror("Error", "Could not load tasks. Starting with empty list.")

    def save_tasks(self):
        """Saves tasks to JSON file."""
        try:
            with open(DATA_FILE, 'w') as f:
                json.dump(self.tasks, f, indent=4)
        except IOError:
            messagebox.showerror("Error", "Could not save tasks!")

if __name__ == "__main__":
    root = tk.Tk()
    # Attempt to set a native look if available
    try:
        # 'clam', 'alt', 'default', 'classic' are standard. 
        # Windows/MacOS usually have their own native themes implicitly.
        ttk.Style().theme_use('clam') 
    except:
        pass
        
    app = TaskManagerApp(root)
    root.mainloop()