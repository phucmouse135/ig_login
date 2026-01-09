# two_fa_handler.py
import time
import re
import pyotp
from selenium.webdriver.common.by import By
from config_utils import wait_and_click, wait_and_send_keys
from mail_handler import get_code_from_mail

def _raise_if_change_not_allowed_yet(driver):
    """
    Detect Instagram restriction popup:
    'You can't make this change at the moment'
    """
    try:
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
    except Exception:
        return

    if "you can't make this change at the moment" in body:
        msg = (
            "Not allowed yet: Instagram blocked this change because this device looks unfamiliar. "
            "Use this device/account for a while and try again later."
        )
        print("   [2FA] ERROR: " + msg)
        raise RuntimeError(msg)
def setup_2fa(driver, email, email_pass):
    """
    Thực hiện quy trình bật 2FA -> Lấy Key -> Confirm -> Trả về Key.
    """
    print("   [2FA] Đang truy cập trang cài đặt 2FA...")
    driver.get("https://accountscenter.instagram.com/password_and_security/two_factor/")
    time.sleep(5) # Chờ load framework React
    _raise_if_change_not_allowed_yet(driver)
    

    # BƯỚC 1: CHỌN TÀI KHOẢN
    print("   [2FA] Chọn tài khoản...")
    
    clicked = False
    
    if not clicked:
        clicked = wait_and_click(driver, By.XPATH, "//span[contains(text(), 'Instagram')]")
        
    if not clicked:
        clicked = wait_and_click(driver, By.XPATH, "//div[contains(text(), 'Instagram')]")

    if not clicked:
        # Tìm thẻ SVG (icon) nằm trong list
        clicked = wait_and_click(driver, By.CSS_SELECTOR, "div[role='dialog'] svg")

    if not clicked:
        # Fallback cuối cùng: Click vào bất kỳ div nào có vẻ là item trong list
        print("   [2FA] Thử click fallback...")
        driver.execute_script("""
            var elements = document.querySelectorAll('div[role="button"], div[class*="x1n2onr6"]');
            for (var i = 0; i < elements.length; i++) {
                if (elements[i].innerText.includes('Instagram')) {
                    elements[i].click();
                    break;
                }
            }
        """)

    time.sleep(5)
    _raise_if_change_not_allowed_yet(driver)

    body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
    
    # Các từ khóa xuất hiện trong ảnh bạn gửi: "check your email", "enter the code"
    keywords = ["check your email", "enter the code", "nhập mã", "security code", "mã bảo mật"]
    
    is_checkpoint = False
    for kw in keywords:
        if kw in body_text:
            is_checkpoint = True
            break
            
    if is_checkpoint:
        print("   [2FA] Phát hiện Checkpoint: Yêu cầu verify Email...")
        
        # 1. Mở tab mới lấy code
        mail_code = get_code_from_mail(driver, email, email_pass)
        
        if not mail_code:
            raise Exception("Không lấy được code mail để qua Checkpoint")
            
        # 2. Nhập code vào ô input
        # Trong ảnh: Input có placeholder="Code", ta tìm theo thẻ input hiển thị
        try:
            # Tìm input type text hoặc number đang hiển thị
            inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='number']")
            entered = False
            for inp in inputs:
                if inp.is_displayed():
                    inp.clear()
                    inp.send_keys(mail_code)
                    entered = True
                    break
            
            if not entered:
                # Fallback JS nếu không send_keys được
                driver.execute_script("document.querySelector('input').value = arguments[0]", mail_code)
                # Cần trigger sự kiện input để nút Continue sáng lên
                driver.execute_script(
                    "document.querySelector('input').dispatchEvent(new Event('input', { bubbles: true }));"
                )
        except Exception as e:
            print(f"   [2FA] Lỗi nhập input: {e}")

        time.sleep(2)
        
        # 3. Nhấn Continue (Nút màu xanh)
        # Tìm nút có chữ Continue hoặc Tiếp
        print("   [2FA] Nhấn Continue...")
        if not wait_and_click(driver, By.XPATH, "//div[@role='button']//span[contains(text(), 'Continue') or contains(text(), 'Tiếp')]"):
            # Fallback: tìm nút submit bất kỳ
            try:
                driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            except:
                pass
                
        time.sleep(8) # Chờ xác thực mã xong
        _raise_if_change_not_allowed_yet(driver)
    # BƯỚC 3: CHỌN AUTHENTICATION APP
    print("   [2FA] Chọn 'Authentication App'...")
    # Tìm text "Authentication app"
    # Xpath tìm thẻ chứa text đó, sau đó click
    try:
        auth_option = driver.find_element(By.XPATH, "//*[contains(text(), 'Authentication app') or contains(text(), 'Ứng dụng xác thực')]")
        auth_option.click()
    except:
        # Nếu không thấy text, có thể nó đã được chọn sẵn, cứ nhấn Next
        pass

    time.sleep(1)
    # Nhấn Continue
    wait_and_click(driver, By.XPATH, "//div[@role='button']//span[contains(text(), 'Continue') or contains(text(), 'Tiếp')]")
    time.sleep(5)
    _raise_if_change_not_allowed_yet(driver)

    # BƯỚC 4: LẤY SECRET KEY
    print("   [2FA] Đang lấy Secret Key...")
    
    # Click nút "Copy key" để đảm bảo key hiển thị (dù mình ko dùng clipboard hệ thống)
    wait_and_click(driver, By.XPATH, "//*[contains(text(), 'Copy key') or contains(text(), 'Sao chép')]")
    
    # Quét toàn bộ text trên màn hình để tìm key bằng Regex
    # Key IG thường là chuỗi in hoa dài, chia nhóm bằng khoảng trắng. VD: PNQY UXXF ...
    full_text = driver.find_element(By.TAG_NAME, "body").text
    
    # Regex tìm chuỗi Base32: 
    # (4 ký tự chữ số) lặp lại ít nhất 4 lần, ngăn cách bởi space
    match = re.search(r'([A-Z2-7]{4}\s){3,}[A-Z2-7]{4}', full_text)
    
    secret_key = ""
    if match:
        secret_key = match.group(0)
    else:
        # Thử tìm trong value của input (nếu IG để key trong input readonly)
        inputs = driver.find_elements(By.TAG_NAME, "input")
        for inp in inputs:
            val = inp.get_attribute("value")
            if val and len(val) > 20 and " " in val: # Key thường > 20 ký tự
                secret_key = val
                break
    
    if not secret_key:
        raise Exception("Không tìm thấy Secret Key trên màn hình")

    print(f"   [2FA] Key tìm thấy: {secret_key}")
    
    # Nhấn Next để sang bước nhập OTP
    wait_and_click(driver, By.XPATH, "//div[@role='button']//span[contains(text(), 'Next') or contains(text(), 'Tiếp')]")
    time.sleep(3)

    # BƯỚC 5: TẠO OTP VÀ CONFIRM
    clean_key = secret_key.replace(" ", "")
    totp = pyotp.TOTP(clean_key)
    otp_code = totp.now()
    
    print(f"   [2FA] OTP Code generated: {otp_code}")
    
    # Nhập OTP
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input[type='text'], input[type='number']", otp_code)
    time.sleep(1)
    
    # Nhấn Next
    wait_and_click(driver, By.XPATH, "//div[@role='button']//span[contains(text(), 'Next') or contains(text(), 'Tiếp')]")
    time.sleep(5)
    
    print("   [2FA] Xác nhận hoàn tất.")
    
    # Nhấn Done (Nếu có)
    wait_and_click(driver, By.XPATH, "//div[@role='button']//span[contains(text(), 'Done') or contains(text(), 'Xong')]")
    
    return secret_key