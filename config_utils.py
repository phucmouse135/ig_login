# config_utils.py
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def get_driver(headless=True):
    options = Options()
    if headless:
        options.add_argument("--headless=new") 
    
    options.add_argument("--disable-notifications")
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu") # Tắt GPU acceleration để nhẹ máy
    options.add_argument("--blink-settings=imagesEnabled=false") # CHẶN LOAD HÌNH ẢNH (Tăng tốc cực mạnh)
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    
    options.page_load_strategy = 'eager'
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.set_page_load_timeout(20)
    return driver

def parse_cookie_string(cookie_str):
    """
    Chuyển chuỗi cookie raw: "datr=abc; ds_user_id=123;..." 
    thành dạng List Dictionary để nạp vào Selenium
    """
    cookies = []
    try:
        # Tách các cặp key=value bằng dấu ;
        pairs = cookie_str.split(';')
        for pair in pairs:
            if '=' in pair:
                key, value = pair.strip().split('=', 1)
                cookies.append({
                    'name': key, 
                    'value': value, 
                    'domain': '.instagram.com', # Quan trọng: set domain để IG nhận
                    'path': '/'
                })
    except Exception as e:
        print(f"Lỗi parse cookie: {e}")
    return cookies

def wait_and_click(driver, by, value, timeout=10):
    try:
        element = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, value)))
        element.click()
        return True
    except:
        return False

def wait_and_send_keys(driver, by, value, keys, timeout=10):
    try:
        element = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))
        element.clear()
        element.send_keys(keys)
        return True
    except:
        return False