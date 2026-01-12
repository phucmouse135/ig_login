# ig_login.py
import time
from selenium.webdriver.common.by import By
from config_utils import parse_cookie_string, wait_and_click

def login_instagram_via_cookie(driver, cookie_raw_string):
    """
    Login IG via cookie.
    Return: True (Success) / False (Fail)
    """
    print("   [IG] Loading Cookies...")
    
    # Step 1: Must go to homepage first to add cookies
    driver.get("https://www.instagram.com/")
    time.sleep(2)
    
    # Step 2: Parse and Add Cookies
    cookies = parse_cookie_string(cookie_raw_string)
    for c in cookies:
        driver.add_cookie(c)
        
    # Step 3: Refresh to apply cookies
    driver.refresh()
    time.sleep(5)
    
    # Step 4: Handle Popups (Save Info / Notifications)
    try:
        # Popup "Save Login Info?" -> Click "Not Now"
        btns = driver.find_elements(By.XPATH, "//button[contains(text(), 'Not Now') or contains(text(), 'Lúc khác')]")
        if btns:
            btns[0].click()
            time.sleep(1)
            
        # Popup "Turn on Notifications?" -> Click "Not Now"
        btns_notif = driver.find_elements(By.XPATH, "//button[contains(text(), 'Not Now') or contains(text(), 'Lúc khác')]")
        if btns_notif:
            btns_notif[0].click()
    except:
        pass

    # Bước 5: Validate Login
    # Kiểm tra trạng thái đăng nhập
    # Cập nhật selector input pass dựa trên element: <input name="password" aria-label="Password" type="password" ...>
    has_password_input = (len(driver.find_elements(By.CSS_SELECTOR, "input[name='password']")) > 0 or 
                          len(driver.find_elements(By.CSS_SELECTOR, "input[type='password']")) > 0 or
                          len(driver.find_elements(By.CSS_SELECTOR, "input[aria-label='Password']")) > 0)
    
    # Check thêm trường hợp "Use another profile" (nghĩa là cookie lỗi/hết hạn, nó đá ra màn hình chọn nick)
    has_use_another_profile = len(driver.find_elements(By.XPATH, "//*[contains(text(), 'Use another profile') or contains(text(), 'Chuyển tài khoản khác')]")) > 0

    has_home_icon = (len(driver.find_elements(By.CSS_SELECTOR, "svg[aria-label='Home']")) > 0 or 
                     len(driver.find_elements(By.CSS_SELECTOR, "svg[aria-label='Trang chủ']")) > 0 or 
                     len(driver.find_elements(By.CSS_SELECTOR, "svg[aria-label='Search']")) > 0)

    # Nếu vẫn còn ô nhập password HOẶC nút "Use another profile" VÀ không thấy Home -> Coi như Login Fail
    if (has_password_input or has_use_another_profile) and not has_home_icon:
        print("   [IG] Login FAIL (Cookie dead or incorrect).")
        raise Exception("COOKIE_DIE: Found Login Form")
        
    # Nếu thấy Avatar hoặc Home Icon -> Login Pass
    # Selector SVG aria-label='Home' hoặc 'Trang chủ'
    if len(driver.find_elements(By.CSS_SELECTOR, "svg[aria-label='Home']")) > 0 or \
       len(driver.find_elements(By.CSS_SELECTOR, "svg[aria-label='Trang chủ']")) > 0 or \
       len(driver.find_elements(By.CSS_SELECTOR, "svg[aria-label='Search']")) > 0:
        print("   [IG] Login SUCCESS!")
        return True
        
    # Trường hợp check point (vẫn tính là login được để xử lý tiếp)
    print("   [IG] Warning: Not at Login screen but Home not found (Might be Checkpoint).")
    return True