# ig_login.py
import time
from selenium.webdriver.common.by import By
from config_utils import parse_cookie_string, wait_dom_ready, wait_element

def login_instagram_via_cookie(driver, cookie_raw_string):
    """
    Login IG via cookie.
    Return: True (Success) / False (Fail)
    """
    print("   [IG] Loading Cookies...")
    
    # Step 1: Must go to homepage first to add cookies
    # Dùng load strategy 'eager' từ config_utils sẽ giúp bước này nhanh hơn
    driver.get("https://www.instagram.com/")
    
    # Không cần wait quá lâu ở đây, chỉ cần đảm bảo browser nhận domain
    try:
        wait_dom_ready(driver, timeout=5)
    except: pass
    
    # Step 2: Parse and Add Cookies
    cookies = parse_cookie_string(cookie_raw_string)
    if not cookies:
        print("   [IG] Error: No cookies parsed.")
        # Logic cũ có thể raise lỗi ở đoạn sau nếu không login được
    
    for c in cookies:
        try:
            driver.add_cookie(c)
        except Exception:
            pass # Ignore cookie errors
        
    # Step 3: Refresh to apply cookies
    driver.refresh()
    
    # --- FAST DETECTION LOOP ---
    # Thay vì sleep cứng hoặc check tuần tự chậm, ta check song song các dấu hiệu
    # Timeout tổng là 10s (đủ cho mạng chậm)
    end_time = time.time() + 10
    
    # Cached Selectors
    SEL_PASS = "input[name='password'], input[type='password'], input[aria-label='Password']"
    SEL_ERROR = "//*[contains(text(), 'Use another profile') or contains(text(), 'Chuyển tài khoản khác')]"
    SEL_HOME  = "svg[aria-label='Home'], svg[aria-label='Trang chủ'], svg[aria-label='Search'], svg[aria-label='Tìm kiếm']"
    
    while time.time() < end_time:
        # 1. Check Success (Ưu tiên check cái này trước vì đa số là success)
        if len(driver.find_elements(By.CSS_SELECTOR, SEL_HOME)) > 0:
            break
            
        # 2. Check Fail (Login form hiện ra)
        if len(driver.find_elements(By.CSS_SELECTOR, SEL_PASS)) > 0:
            break
            
        # 3. Check Fail (Màn hình chọn tài khoản - cookie die)
        if len(driver.find_elements(By.XPATH, SEL_ERROR)) > 0:
            break
            
        time.sleep(0.1) # Poll nhanh (0.1s)

    # Step 4: Handle Popups (Save Info / Notifications) - TỐI ƯU TỐC ĐỘ
    # Chỉ xử lý popup nếu không phải màn hình Login (đỡ mất thời gian nếu cookie đã die)
    has_password_check = len(driver.find_elements(By.CSS_SELECTOR, SEL_PASS)) > 0
    
    if not has_password_check:
        try:
            # Dùng find_elements để check tồn tại trước -> Không bị delay timeout nếu không có popup
            popups = driver.find_elements(By.XPATH, "//button[contains(text(), 'Not Now') or contains(text(), 'Lúc khác')]")
            if popups:
                for btn in popups:
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(0.5) # Chờ animation một chút nếu có click
        except:
            pass

    # Bước 5: Validate Login (GIỮ NGUYÊN LOGIC CŨ CỦA BẠN)
    has_password_input = (len(driver.find_elements(By.CSS_SELECTOR, SEL_PASS)) > 0)
    
    has_use_another_profile = len(driver.find_elements(By.XPATH, SEL_ERROR)) > 0

    has_home_icon = (len(driver.find_elements(By.CSS_SELECTOR, SEL_HOME)) > 0)

    # Nếu vẫn còn ô nhập password HOẶC nút "Use another profile" VÀ không thấy Home -> Coi như Login Fail
    if (has_password_input or has_use_another_profile) and not has_home_icon:
        print("   [IG] Login FAIL (Cookie dead or incorrect).")
        raise Exception("COOKIE_DIE: Found Login Form")
        
    # Nếu thấy Avatar hoặc Home Icon -> Login Pass
    if has_home_icon:
        print("   [IG] Login SUCCESS!")
        return True
        
    # Trường hợp check point (vẫn tính là login được để xử lý tiếp ở bước sau)
    print("   [IG] Warning: Not at Login screen but Home not found (Might be Checkpoint).")
    return True