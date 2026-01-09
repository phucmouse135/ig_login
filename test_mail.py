import time
import os
import sys

# Thêm đường dẫn hiện tại vào sys.path để import module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config_utils import get_driver
from mail_handler import get_code_from_mail
from colorama import init, Fore

# Khởi tạo màu terminal
init(autoreset=True)

def test_mail_extraction():
    print(Fore.CYAN + "=== TEST MAIL HANDLING ===")
    
    # 1. Đọc account đầu tiên từ input.txt
    input_file = 'input.txt'
    if not os.path.exists(input_file):
        print(Fore.RED + f"File {input_file} not found!")
        return

    target_email = ""
    target_pass = ""
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                parts = line.split('\t')
                
                # Format: User | Pass | ... | Email | EmailPass | ...
                # Ta cần Email (index 3) và Pass (index 4)
                if len(parts) >= 5:
                    target_email = parts[3]
                    target_pass = parts[4]
                    break # Lấy dòng hợp lệ đầu tiên
                    
    except Exception as e:
        print(Fore.RED + f"Error reading input.txt: {e}")
        return

    if not target_email or not target_pass:
        print(Fore.RED + "No valid account found in input.txt")
        return

    print(Fore.YELLOW + f"Testing with Email: {target_email}")
    print(Fore.YELLOW + f"Testing with Pass : {target_pass}")

    # 2. Khởi tạo Driver
    print(Fore.CYAN + "Launching browser...")
    driver = get_driver(headless=False)
    
    try:
        # 3. Gọi hàm get_code_from_mail
        print(Fore.CYAN + "Calling get_code_from_mail...")
        start_time = time.time()
        
        code = get_code_from_mail(driver, target_email, target_pass)
        
        end_time = time.time()
        duration = end_time - start_time
        
        if code:
            print(Fore.GREEN + f"SUCCESS! Code found: {code}")
        else:
            print(Fore.RED + "FAILED. Code not found (returned None).")
            
        print(f"Time taken: {duration:.2f} seconds")
        
    except Exception as e:
        print(Fore.RED + f"EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        print(Fore.CYAN + "Test finished.")
        input("Press Enter to close browser...")
        driver.quit()

if __name__ == "__main__":
    test_mail_extraction()
