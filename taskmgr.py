import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import subprocess
import threading
import time
import csv
import io
import re

# --- Constants & Configuration ---
REFRESH_RATE_PROCESSES = 3000  # ms
REFRESH_RATE_PERFORMANCE = 1000  # ms
FONT_MAIN = ("Segoe UI", 10)
FONT_HEADER = ("Segoe UI", 12, "bold")
FONT_BIG = ("Segoe UI", 24, "bold")

class SystemTaskManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Task Manager (Python Native)")
        self.root.geometry("800x600")
        
        # Windows 11-ish styling colors
        self.colors = {
            "bg_sidebar": "#f3f3f3",
            "bg_content": "#ffffff",
            "accent": "#0067c0",
            "text": "#000000",
            "text_light": "#666666"
        }
        
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Configure Treeview colors
        self.style.configure("Treeview", 
                           background="white", 
                           foreground="black", 
                           rowheight=25, 
                           fieldbackground="white",
                           font=FONT_MAIN)
        self.style.map('Treeview', background=[('selected', self.colors['accent'])])
        
        # Layout: Sidebar + Main Content
        self.setup_layout()
        
        # State
        self.current_tab = "Processes"
        self.running = True
        self.processes_data = []
        self.cpu_usage = 0
        self.mem_usage = 0
        self.total_mem = 0
        
        # Start background threads for data fetching
        self.thread_procs = threading.Thread(target=self.loop_fetch_processes, daemon=True)
        self.thread_stats = threading.Thread(target=self.loop_fetch_stats, daemon=True)
        self.thread_procs.start()
        self.thread_stats.start()
        
        # Start UI update loops
        self.root.after(100, self.update_ui_performance)
        self.root.after(100, self.update_ui_processes)

    def setup_layout(self):
        # 1. Sidebar
        sidebar = tk.Frame(self.root, bg=self.colors["bg_sidebar"], width=200)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False) # Don't shrink

        lbl_title = tk.Label(sidebar, text="Task Manager", bg=self.colors["bg_sidebar"], 
                             font=("Segoe UI", 14, "bold"), pady=20)
        lbl_title.pack(anchor="w", padx=15)

        # Navigation Buttons
        self.btn_procs = self.create_nav_btn(sidebar, "Processes", lambda: self.switch_tab("Processes"))
        self.btn_perf = self.create_nav_btn(sidebar, "Performance", lambda: self.switch_tab("Performance"))
        
        self.btn_procs.pack(fill=tk.X, padx=5, pady=2)
        self.btn_perf.pack(fill=tk.X, padx=5, pady=2)

        # Actions Section
        lbl_actions = tk.Label(sidebar, text="Actions", bg=self.colors["bg_sidebar"], 
                               font=("Segoe UI", 10, "bold"), fg=self.colors["text_light"], pady=10)
        lbl_actions.pack(anchor="w", padx=15, pady=(10, 0))

        btn_run = self.create_nav_btn(sidebar, "Run New Task", self.run_task)
        btn_run.pack(fill=tk.X, padx=5, pady=2)

        # 2. Main Content Area
        self.content_area = tk.Frame(self.root, bg=self.colors["bg_content"])
        self.content_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # --- Frame: Processes ---
        self.frame_procs = tk.Frame(self.content_area, bg=self.colors["bg_content"])
        
        # Treeview for processes
        columns = ("name", "pid", "mem")
        self.tree = ttk.Treeview(self.frame_procs, columns=columns, show="headings", selectmode="browse")
        
        self.tree.heading("name", text="Name", anchor="w", command=lambda: self.sort_tree("name", False))
        self.tree.heading("pid", text="PID", anchor="w", command=lambda: self.sort_tree("pid", False))
        self.tree.heading("mem", text="Memory", anchor="e", command=lambda: self.sort_tree("mem", False))
        
        self.tree.column("name", width=300)
        self.tree.column("pid", width=100)
        self.tree.column("mem", width=150, anchor="e")
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.frame_procs, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        # Process Action Buttons
        action_frame = tk.Frame(self.frame_procs, bg=self.colors["bg_content"])
        action_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        btn_kill = ttk.Button(action_frame, text="End Selected Task", command=self.end_task)
        btn_kill.pack(side=tk.RIGHT)

        # --- Frame: Performance ---
        self.frame_perf = tk.Frame(self.content_area, bg=self.colors["bg_content"], padx=20, pady=20)
        
        # CPU Widget
        self.lbl_cpu_title = tk.Label(self.frame_perf, text="CPU", font=FONT_HEADER, bg="white", fg=self.colors["text_light"])
        self.lbl_cpu_title.pack(anchor="w")
        self.lbl_cpu_val = tk.Label(self.frame_perf, text="0%", font=FONT_BIG, bg="white", fg=self.colors["accent"])
        self.lbl_cpu_val.pack(anchor="w")
        self.progress_cpu = ttk.Progressbar(self.frame_perf, orient="horizontal", length=400, mode="determinate")
        self.progress_cpu.pack(fill=tk.X, pady=(5, 20))

        # Memory Widget
        self.lbl_mem_title = tk.Label(self.frame_perf, text="Memory", font=FONT_HEADER, bg="white", fg=self.colors["text_light"])
        self.lbl_mem_title.pack(anchor="w")
        self.lbl_mem_val = tk.Label(self.frame_perf, text="0 / 0 GB", font=FONT_BIG, bg="white", fg="#d3009b") # Magenta for mem
        self.lbl_mem_val.pack(anchor="w")
        self.progress_mem = ttk.Progressbar(self.frame_perf, orient="horizontal", length=400, mode="determinate")
        self.progress_mem.pack(fill=tk.X, pady=(5, 20))

        # Initial View
        self.switch_tab("Processes")

    def create_nav_btn(self, parent, text, command):
        btn = tk.Button(parent, text=text, command=command, 
                        font=("Segoe UI", 11), 
                        bg=self.colors["bg_sidebar"], 
                        fg=self.colors["text"],
                        activebackground="#e5e5e5",
                        relief=tk.FLAT, anchor="w", padx=20)
        return btn

    def run_task(self):
        """Open a dialog to run a new task."""
        target = simpledialog.askstring("Run New Task", "Type the name of a program (e.g., notepad, calc) or a path:", parent=self.root)
        if target:
            try:
                # Use Popen to run non-blocking
                subprocess.Popen(target, shell=True)
            except Exception as e:
                messagebox.showerror("Error", f"Could not start '{target}':\n{e}")

    def switch_tab(self, tab_name):
        self.current_tab = tab_name
        self.frame_procs.pack_forget()
        self.frame_perf.pack_forget()
        
        # Reset button styles
        self.btn_procs.config(bg=self.colors["bg_sidebar"], font=("Segoe UI", 11))
        self.btn_perf.config(bg=self.colors["bg_sidebar"], font=("Segoe UI", 11))

        if tab_name == "Processes":
            self.frame_procs.pack(fill=tk.BOTH, expand=True)
            self.btn_procs.config(bg="#e0e0e0", font=("Segoe UI", 11, "bold"))
        else:
            self.frame_perf.pack(fill=tk.BOTH, expand=True)
            self.btn_perf.config(bg="#e0e0e0", font=("Segoe UI", 11, "bold"))

    # --- Data Fetching (Background Threads) ---
    def loop_fetch_processes(self):
        """Fetches process list using Windows 'tasklist' command."""
        while self.running:
            try:
                # tasklist /fo csv /nh (CSV format, no header)
                # Creation flag 0x08000000 prevents cmd window popup
                output = subprocess.check_output("tasklist /fo csv /nh", shell=True, creationflags=0x08000000).decode("utf-8", errors="ignore")
                
                new_data = []
                # Use csv module to parse correctly handling quotes
                reader = csv.reader(io.StringIO(output))
                for row in reader:
                    if len(row) >= 5:
                        name = row[0]
                        pid = row[1]
                        mem = row[4] # e.g. "14,500 K"
                        
                        # Convert mem to integer for sorting
                        mem_clean = int(re.sub(r"[^0-9]", "", mem))
                        new_data.append((name, pid, mem, mem_clean))
                
                self.processes_data = new_data
                
            except Exception as e:
                print(f"Error fetching processes: {e}")
            
            time.sleep(3) # Update processes every 3 seconds

    def loop_fetch_stats(self):
        """Fetches Global CPU and Memory usage using 'wmic'."""
        while self.running:
            try:
                # CPU Load
                cpu_out = subprocess.check_output("wmic cpu get loadpercentage", shell=True, creationflags=0x08000000).decode()
                # Parse number from output
                cpu_match = re.search(r"\d+", cpu_out)
                if cpu_match:
                    self.cpu_usage = int(cpu_match.group())

                # Memory
                # FreePhysicalMemory, TotalVisibleMemorySize
                mem_out = subprocess.check_output("wmic OS get FreePhysicalMemory,TotalVisibleMemorySize /Value", shell=True, creationflags=0x08000000).decode()
                
                free_match = re.search(r"FreePhysicalMemory=(\d+)", mem_out)
                total_match = re.search(r"TotalVisibleMemorySize=(\d+)", mem_out)
                
                if free_match and total_match:
                    free_kb = int(free_match.group(1))
                    total_kb = int(total_match.group(1))
                    used_kb = total_kb - free_kb
                    
                    self.total_mem = total_kb
                    self.mem_usage = (used_kb / total_kb) * 100
                    
            except Exception as e:
                print(f"Error fetching stats: {e}")
                
            time.sleep(1)

    # --- UI Updaters ---
    def update_ui_processes(self):
        if self.current_tab == "Processes":
            # Simple refresh: Clear and Refill
            # Note: In a production app, you would diff the list to keep selection
            selected_item = self.tree.selection()
            selected_pid = None
            if selected_item:
                selected_pid = self.tree.item(selected_item[0])['values'][1] # Get PID

            # Clear
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Repopulate
            # We use the raw data (processes_data)
            # Default sort by memory (index 3) desc
            data_to_show = sorted(self.processes_data, key=lambda x: x[3], reverse=True)
            
            for p in data_to_show:
                self.tree.insert("", "end", values=(p[0], p[1], p[2]))
                
            # Try to restore selection
            # (This is a simplified restoration, might scroll to top)
        
        self.root.after(REFRESH_RATE_PROCESSES, self.update_ui_processes)

    def update_ui_performance(self):
        if self.current_tab == "Performance":
            # CPU
            self.lbl_cpu_val.config(text=f"{self.cpu_usage}%")
            self.progress_cpu['value'] = self.cpu_usage
            
            # RAM
            total_gb = self.total_mem / (1024*1024)
            used_percent = self.mem_usage
            used_gb = total_gb * (used_percent / 100)
            
            self.lbl_mem_val.config(text=f"{used_gb:.1f} GB / {total_gb:.1f} GB ({int(used_percent)}%)")
            self.progress_mem['value'] = used_percent

        self.root.after(REFRESH_RATE_PERFORMANCE, self.update_ui_performance)

    def sort_tree(self, col, reverse):
        # A simplified sorter could go here
        # Currently, the main loop overwrites this, so it's tricky without pausing updates.
        pass

    def end_task(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a process to end.")
            return
            
        item = self.tree.item(selected[0])
        pid = item['values'][1] # PID is index 1
        name = item['values'][0]

        if messagebox.askyesno("End Task", f"Do you want to force kill {name} (PID: {pid})?"):
            try:
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, creationflags=0x08000000)
                # Force immediate refresh
                self.loop_fetch_processes()
                self.update_ui_processes()
            except Exception as e:
                messagebox.showerror("Error", f"Could not kill process: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = SystemTaskManager(root)
    root.mainloop()