# main.py
import threading
import sys
from concurrent.futures import ThreadPoolExecutor
from config_utils import get_driver
from ig_login import login_instagram_via_cookie
from two_fa_handler import setup_2fa
from colorama import Fore, init

# Khởi tạo màu terminal
init(autoreset=True)

# Khóa luồng để ghi file không bị lỗi dòng
file_lock = threading.Lock()

def process_account(line_data):
    """Xử lý 1 dòng data account"""
    line_data = line_data.strip()
    if not line_data: return

    # Tách data theo tab
    parts = line_data.split('\t')
    
    # Kiểm tra độ dài data (Data mẫu có user, pass, 2 ô trống, email, pass mail... cookie)
    # Lunamaya57 [tab] pass [tab] EMPTY [tab] EMPTY [tab] email...
    if len(parts) < 5:
        print(Fore.RED + f"[SKIP] Dòng lỗi format: {line_data[:20]}...")
        return

    # print(parts)
    username = parts[0]
    email = parts[3]      # Vị trí email (Index 4 dựa trên mẫu bạn gửi)
    email_pass = parts[4] # Vị trí pass email
    
    # Cookie thường ở cuối cùng
    cookie_str = parts[-1]

    print(Fore.CYAN + f"[{username}] Bắt đầu xử lý...")
    driver = None
    
    try:
        # 1. Khởi tạo Browser
        driver = get_driver(headless=True) # Để False để bạn nhìn thấy quy trình, OK rồi thì sửa thành True
        
        # 2. Login Instagram
        if login_instagram_via_cookie(driver, cookie_str):
            
            # 3. Setup 2FA & Lấy Key
            secret_key = setup_2fa(driver, email, email_pass)
            
            # 4. Lưu kết quả
            # Yêu cầu: "2 tab ivb47SD26tw [TAB] [TAB] lunamaya57@iname.com -> paste kết quả vào ở đây"
            # Tức là chèn vào vị trí index 2 (giữa pass IG và email)
            
            # Logic replace: parts[2] đang là rỗng -> gán key vào
            # Nếu input của bạn là: User \t Pass \t \t Email ...
            # Thì parts[2] là khoảng trắng giữa 2 tab
            
            if len(parts) > 2:
                parts[2] = secret_key
            else:
                # Nếu format lạ, chèn đại vào cuối
                parts.append(secret_key)
                
            final_line = "\t".join(parts) + "\n"
            
            with file_lock:
                with open("output.txt", "a", encoding="utf-8") as f:
                    f.write(final_line)
            
            print(Fore.GREEN + f"[{username}] THÀNH CÔNG! Key: {secret_key}")
            
        else:
            # Login thất bại
            result_to_save = "LOGIN_FAILED"
            print(Fore.RED + f"[{username}] Login IG thất bại (Cookie die).")

    except Exception as e:
        # Lỗi Exception chung
        error_str = str(e).replace("\n", " ").replace("\t", " ")
        result_to_save = f"ERROR: {error_str}"
        print(Fore.RED + f"[{username}] Lỗi Exception: {str(e)}")
            
    finally:
        if driver:
            try: driver.quit()
            except: pass
            
        # --- PHẦN GHI FILE OUTPUT ---
        # Kiểm tra nếu result_to_save chưa có giá trị (do exception trước khi gán)
        if not result_to_save:
             result_to_save = "UNKNOWN_ERROR"

        # Đảm bảo list parts có đủ chỗ để gán vào index 2
        while len(parts) <= 2:
            parts.append("")
        
        # Gán kết quả vào vị trí tab thứ 2 (Index 2 là cột thứ 3)
        parts[2] = result_to_save
        
        # Ghép lại thành dòng string
        final_line = "\t".join(parts) + "\n"
        
        # Ghi vào file output.txt (Thread Safe)
        with file_lock:
            try:
                with open("output.txt", "a", encoding="utf-8") as f:
                    f.write(final_line)
            except: pass

def main():
    print("--- TOOL AUTO 2FA INSTAGRAM ---")
    
    try:
        with open("input.txt", "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print("Lỗi: Không tìm thấy file input.txt")
        return

    # SỐ LUỒNG CHẠY ĐỒNG THỜI (Thread)
    # Máy yếu thì để 2-3, máy khỏe để 5-10
    NUM_THREADS = 1 
    
    print(f"Đang chạy {len(lines)} acc với {NUM_THREADS} luồng...")
    
    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        executor.map(process_account, lines)

    print("--- HOÀN TẤT ---")

if __name__ == "__main__":
    main()