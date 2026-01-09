# ig_login.py
import time
from selenium.webdriver.common.by import By
from config_utils import parse_cookie_string, wait_and_click

def login_instagram_via_cookie(driver, cookie_raw_string):
    """
    Login IG bằng cookie.
    Return: True (Thành công) / False (Thất bại)
    """
    print("   [IG] Đang nạp Cookie...")
    
    # Bước 1: Phải vào trang chủ trước mới add được cookie
    driver.get("https://www.instagram.com/")
    time.sleep(2)
    
    # Bước 2: Parse và Add Cookie
    cookies = parse_cookie_string(cookie_raw_string)
    for c in cookies:
        driver.add_cookie(c)
        
    # Bước 3: Refresh để nhận cookie
    driver.refresh()
    time.sleep(5)
    
    # Bước 4: Xử lý Popup (Save Info / Notifications)
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
    # Nếu vẫn còn ô nhập password -> Login fail
    if len(driver.find_elements(By.CSS_SELECTOR, "input[name='password']")) > 0:
        print("   [IG] Login FAIL (Cookie chết hoặc sai).")
        return False
        
    # Nếu thấy Avatar hoặc Home Icon -> Login Pass
    # Selector SVG aria-label='Home' hoặc 'Trang chủ'
    if len(driver.find_elements(By.CSS_SELECTOR, "svg[aria-label='Home']")) > 0 or \
       len(driver.find_elements(By.CSS_SELECTOR, "svg[aria-label='Trang chủ']")) > 0 or \
       len(driver.find_elements(By.CSS_SELECTOR, "svg[aria-label='Search']")) > 0:
        print("   [IG] Login SUCCESS!")
        return True
        
    # Trường hợp check point (vẫn tính là login được để xử lý tiếp)
    print("   [IG] Cảnh báo: Không ở màn hình Login nhưng chưa thấy Home (Có thể bị Checkpoint).")
    return True