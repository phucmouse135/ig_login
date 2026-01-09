import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import time
from concurrent.futures import ThreadPoolExecutor

# Import các logic có sẵn từ project
from config_utils import get_driver
from ig_login import login_instagram_via_cookie
from two_fa_handler import setup_2fa

class Instagram2FAToolApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Tool Auto 2FA Instagram - Pro GUI")
        self.root.geometry("1000x700")

        # --- Variables ---
        self.file_path = "input.txt" # Default
        self.is_running = False
        self.task_queue = queue.Queue()
        self.executor = None
        self.stop_event = threading.Event()
        self.results_lock = threading.Lock()

        # --- UI Layout ---
        self.setup_top_controls()
        self.setup_tables()
        self.setup_status_bar()

    def setup_top_controls(self):
        frame = ttk.LabelFrame(self.root, text="Cấu hình & Điều khiển", padding=10)
        frame.pack(fill="x", padx=10, pady=5)

        # File Input
        ttk.Label(frame, text="File Input:").grid(row=0, column=0, padx=5, sticky="w")
        self.entry_file = ttk.Entry(frame, width=40)
        self.entry_file.insert(0, self.file_path)
        self.entry_file.grid(row=0, column=1, padx=5)
        ttk.Button(frame, text="Chọn File", command=self.browse_file).grid(row=0, column=2, padx=5)
        ttk.Button(frame, text="Load Data", command=self.load_data).grid(row=0, column=3, padx=5)

        # Threads
        ttk.Label(frame, text="Số luồng:").grid(row=0, column=4, padx=(20, 5))
        self.spin_threads = ttk.Spinbox(frame, from_=1, to=20, width=5)
        self.spin_threads.set(1)
        self.spin_threads.grid(row=0, column=5, padx=5)

        # Control Buttons
        self.btn_start = ttk.Button(frame, text="▶ BẮT ĐẦU", command=self.start_process)
        self.btn_start.grid(row=0, column=6, padx=10)
        
        self.btn_stop = ttk.Button(frame, text="⏹ DỪNG LẠI", command=self.stop_process, state="disabled")
        self.btn_stop.grid(row=0, column=7, padx=5)

    def setup_tables(self):
        # PanedWindow để chia 2 phần (Input và Output)
        paned = ttk.PanedWindow(self.root, orient="vertical")
        paned.pack(fill="both", expand=True, padx=10, pady=5)

        # --- Bảng Input ---
        frame_input = ttk.LabelFrame(paned, text="Danh sách tài khoản (Input)", padding=5)
        paned.add(frame_input, weight=2)

        cols_in = ("ID", "Username", "Password", "Email", "Status")
        self.tree_input = ttk.Treeview(frame_input, columns=cols_in, show="headings", height=10)
        
        # Heading & Column setup
        self.tree_input.heading("ID", text="#")
        self.tree_input.column("ID", width=40, anchor="center")
        self.tree_input.heading("Username", text="Username")
        self.tree_input.column("Username", width=150)
        self.tree_input.heading("Password", text="Password")
        self.tree_input.column("Password", width=100)
        self.tree_input.heading("Email", text="Email")
        self.tree_input.column("Email", width=200)
        self.tree_input.heading("Status", text="Trạng thái")
        self.tree_input.column("Status", width=150)

        scroll_in = ttk.Scrollbar(frame_input, orient="vertical", command=self.tree_input.yview)
        self.tree_input.configure(yscroll=scroll_in.set)
        
        self.tree_input.pack(side="left", fill="both", expand=True)
        scroll_in.pack(side="right", fill="y")

        # --- Bảng Output ---
        frame_output = ttk.LabelFrame(paned, text="Kết quả xử lý (Output)", padding=5)
        paned.add(frame_output, weight=1)

        cols_out = ("Time", "Username", "Result", "Message")
        self.tree_output = ttk.Treeview(frame_output, columns=cols_out, show="headings", height=8)
        
        self.tree_output.heading("Time", text="Giờ")
        self.tree_output.column("Time", width=80)
        self.tree_output.heading("Username", text="Username")
        self.tree_output.column("Username", width=150)
        self.tree_output.heading("Result", text="Kết quả")
        self.tree_output.column("Result", width=250)
        self.tree_output.heading("Message", text="Chi tiết")
        self.tree_output.column("Message", width=300)

        scroll_out = ttk.Scrollbar(frame_output, orient="vertical", command=self.tree_output.yview)
        self.tree_output.configure(yscroll=scroll_out.set)

        self.tree_output.pack(side="left", fill="both", expand=True)
        scroll_out.pack(side="right", fill="y")
        
        # Tag configuration for validation colors
        self.tree_input.tag_configure("pending", background="white")
        self.tree_input.tag_configure("running", background="#fffacd") # Vàng nhạt
        self.tree_input.tag_configure("success", background="#e0ffe0") # Xanh nhạt
        self.tree_input.tag_configure("fail", background="#ffe0e0")    # Đỏ nhạt

    def setup_status_bar(self):
        self.status_var = tk.StringVar(value="Sẵn sàng")
        lbl_status = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w")
        lbl_status.pack(side="bottom", fill="x")

    def browse_file(self):
        f = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if f:
            self.entry_file.delete(0, tk.END)
            self.entry_file.insert(0, f)
            self.load_data()

    def load_data(self):
        # Clear cũ
        for item in self.tree_input.get_children():
            self.tree_input.delete(item)
            
        path = self.entry_file.get()
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            count = 0
            for line in lines:
                line = line.strip()
                if not line: continue
                parts = line.split("\t")
                if len(parts) >= 5:
                    # columns=("ID", "Username", "Password", "Email", "Status")
                    username = parts[0]
                    password = parts[1] # Thường là pass IG
                    email = parts[3]
                    
                    # Store full line data in hidden values or manage externally
                    # IID sẽ là index của row để dễ truy xuất
                    self.tree_input.insert("", "end", iid=str(count), values=(count+1, username, password, email, "Chờ chạy"), tags=("pending",))
                    
                    # Lưu data gốc vào dictionary để thread lấy ra dùng
                    if not hasattr(self, 'data_map'): self.data_map = {}
                    self.data_map[str(count)] = line
                    
                    count += 1
            
            self.status_var.set(f"Đã load {count} dòng.")
        except Exception as e:
            messagebox.showerror("Lỗi load file", str(e))

    def start_process(self):
        if self.is_running: return
        
        # Get pending items
        items = self.tree_input.get_children()
        if not items:
            messagebox.showwarning("Cảnh báo", "Chưa có dữ liệu input!")
            return

        threads_count = int(self.spin_threads.get())
        
        self.is_running = True
        self.stop_event.clear()
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.status_var.set(f"Đang chạy với {threads_count} luồng...")

        # Reset queue
        self.task_queue = queue.Queue()
        for iid in items:
            # Chỉ add những dòng chưa chạy hoặc chạy lỗi muốn chạy lại? 
            # Hiện tại add tất cả dòng có status "Chờ chạy" hoặc muốn chạy lại hết thì tùy logic
            # Ở đây mình sẽ duyệt từ đầu, bỏ qua những cái đã "Success"
            curr_status = self.tree_input.item(iid, "values")[4]
            if "Thành công" not in curr_status: # Chạy cả pending và error
                self.task_queue.put(iid)

        # Start Workers in a separate background thread to manage ThreadPool
        threading.Thread(target=self.run_thread_pool, args=(threads_count,), daemon=True).start()

    def run_thread_pool(self, max_workers):
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            while not self.task_queue.empty() and not self.stop_event.is_set():
                if self.stop_event.is_set(): break
                try:
                    iid = self.task_queue.get_nowait()
                    futures.append(executor.submit(self.process_one_account, iid))
                except queue.Empty:
                    break
            
            # Wait for all submitted tasks
            for f in futures:
                if self.stop_event.is_set(): break
                f.result() # Wait
        
        self.root.after(0, self.on_finish)

    def process_one_account(self, iid):
        if self.stop_event.is_set(): return
        
        line_data = self.data_map.get(iid)
        parts = line_data.split('\t')
        username = parts[0]
        email = parts[3]
        email_pass = parts[4]
        cookie_str = parts[-1]

        # Update running status UI
        self.update_input_status(iid, "Đang chạy...", "running")
        
        driver = None
        result_key = ""
        status_msg = ""
        is_success = False

        try:
            # 1. Init Driver
            driver = get_driver(headless=False)
            
            # 2. Login
            if login_instagram_via_cookie(driver, cookie_str):
                # 3. Setup 2FA
                secret_key = setup_2fa(driver, email, email_pass)
                
                result_key = secret_key
                status_msg = "Thành công"
                is_success = True
            else:
                status_msg = "Login Failed (Cookie Die)"
                result_key = "LOGIN_FAIL"
                
        except Exception as e:
            status_msg = str(e).replace("\n", " ")
            result_key = f"ERROR: {status_msg}"
        finally:
            if driver:
                try: driver.quit()
                except: pass

        # Update Final Status UI
        tag = "success" if is_success else "fail"
        self.update_input_status(iid, status_msg, tag)
        
        # Add to Output
        timestamp = time.strftime("%H:%M:%S")
        self.add_output_row(timestamp, username, result_key, status_msg)

        # Write to File directly (Thread safe Logic)
        self.write_to_output_file(parts, result_key)

    def write_to_output_file(self, parts, result):
        with self.results_lock:
            while len(parts) <= 2: parts.append("")
            parts[2] = result
            final_line = "\t".join(parts) + "\n"
            try:
                with open("output.txt", "a", encoding="utf-8") as f:
                    f.write(final_line)
            except: pass

    def update_input_status(self, iid, status_text, tag):
        # Helper to update Treeview safely from thread
        def _update():
            # Check if item exists (in case cleared)
            if self.tree_input.exists(iid):
                vals = list(self.tree_input.item(iid, "values"))
                vals[4] = status_text
                self.tree_input.item(iid, values=vals, tags=(tag,))
                # Auto scroll to current
                self.tree_input.see(iid)
        self.root.after(0, _update)

    def add_output_row(self, time_str, username, res, msg):
        def _add():
            self.tree_output.insert("", 0, values=(time_str, username, res, msg))
        self.root.after(0, _add)

    def stop_process(self):
        if not self.is_running: return
        if messagebox.askyesno("Xác nhận", "Bạn có muốn dừng tiến trình?"):
            self.stop_event.set()
            # Clear queue
            with self.task_queue.mutex:
                self.task_queue.queue.clear()
            self.status_var.set("Đang dừng... Đợi các luồng hiện tại hoàn tất.")
            # Interface sẽ được reset ở on_finish

    def on_finish(self):
        self.is_running = False
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.status_var.set("Hoàn tất / Đã dừng.")
        messagebox.showinfo("Thông báo", "Quá trình hoàn tất.")

if __name__ == "__main__":
    root = tk.Tk()
    app = Instagram2FAToolApp(root)
    root.mainloop()
