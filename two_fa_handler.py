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
def setup_2fa(driver, email, email_pass, target_username=None):
    """
    Thực hiện quy trình bật 2FA -> Lấy Key -> Confirm -> Trả về Key.
    """
    print(f"   [2FA] Đang truy cập trang cài đặt 2FA (Target: {target_username})...")
    driver.get("https://accountscenter.instagram.com/password_and_security/two_factor/")
    time.sleep(5) # Chờ load framework React
    _raise_if_change_not_allowed_yet(driver)
    

    # BƯỚC 1: CHỌN TÀI KHOẢN
    print("   [2FA] Chọn tài khoản...")
    time.sleep(3) # Chờ danh sách tài khoản load
    
    clicked = False
    try:
        # LOGIC SELECT ACCOUNT UPDATED
        # Tìm danh sách các nút (account items)
        # Thông thường là div[role='button'] hoặc a[role='link']
        
        # 1. Tìm tất cả candidate elements
        candidates = driver.find_elements(By.XPATH, "//div[@role='button'] | //a[@role='link']")
        
        instagram_candidates = []
        
        # 2. Lọc danh sách candidate
        for el in candidates:
            try:
                txt = el.text.lower()
                # Chỉ xử lý nếu có chữ Instagram (bỏ qua Facebook)
                if "instagram" in txt:
                    instagram_candidates.append(el)
            except: pass
            
        print(f"   [2FA] Tìm thấy {len(instagram_candidates)} tài khoản Instagram.")
        
        target_el = None
        
        if instagram_candidates:
            # Nếu chỉ có 1 -> Chọn luôn
            if len(instagram_candidates) == 1:
                target_el = instagram_candidates[0]
                print("   [2FA] Chỉ có 1 tài khoản Instagram. Chọn luôn.")
            elif target_username:
                # Nếu có nhiều, tìm cái nào chứa username
                norm_target = target_username.strip().lower()
                print(f"   [2FA] Đang tìm tài khoản khớp user '{norm_target}'...")
                
                for cand in instagram_candidates:
                    if norm_target in cand.text.lower():
                        target_el = cand
                        print("   [2FA] => Đã tìm thấy khớp Username!")
                        break
                
                # Nếu không tìm thấy khớp user -> fallback cái đầu tiên
                if not target_el:
                    print("   [2FA] Không thấy khớp Username. Fallback chọn cái đầu tiên.")
                    target_el = instagram_candidates[0]
            else:
                # Không có target username -> chọn cái đầu
                target_el = instagram_candidates[0]
        
        # 3. Click
        if target_el:
            try:
                # Scroll to view
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_el)
                time.sleep(1)
                target_el.click()
                clicked = True
            except:
                 driver.execute_script("arguments[0].click();", target_el)
                 clicked = True
        
        # Fallback cũ nếu logic trên fail hoàn toàn
        if not clicked:
            print("   [2FA] Fallback JS Selection cu...")
            driver.execute_script("""
                var elements = document.querySelectorAll('div[role="button"], a[role="link"]');
                for (var i = 0; i < elements.length; i++) {
                    if (elements[i].innerText.includes('Instagram')) {
                        elements[i].click();
                        break; 
                    }
                }
            """)
            
    except Exception as e:
        print(f"   [2FA] Lỗi khi chọn tài khoản: {e}")

    # Đợi manual check thay vì WebDriverWait
    print("   [2FA] Đang đợi màn hình tiếp theo load...")
    found_step = False
    for _ in range(20): # Đợi khoảng 20s
        src = driver.page_source.lower()
        if "check your email" in src or "authentication app" in src or "is on" in src:
            found_step = True
            break
        time.sleep(1)
        
    if not found_step:
        print("   [2FA] Cảnh báo: Hết thời gian chờ màn hình tiếp theo.")
    
    _raise_if_change_not_allowed_yet(driver)

    # Cập nhật context màn hình hiện tại
    try:
        # Check kỹ các thẻ Header H2, H1 trong modal (Thường popup IG dùng h2 hoặc div role=heading)
        headers = driver.find_elements(By.TAG_NAME, "h2")
        for h in headers:
            txt = h.text.lower()
            if "authentication is on" in txt or "đang bật" in txt:
                 print("   [2FA] Phát hiện popup: Two-factor authentication is on.")
                 raise Exception("ALREADY_2FA_ON")
    except Exception as e:
        if str(e) == "ALREADY_2FA_ON": raise e

    body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
    
    # --- KIỂM TRA SỚM: ĐÃ BẬT 2FA CHƯA? ---
    # User Request: check text "Two-factor authentication is on"
    if "two-factor authentication is on" in body_text or "is on" in body_text or "đang bật" in body_text:
         print("   [2FA] Phát hiện: 2FA ĐÃ ĐƯỢC BẬT TỪ TRƯỚC. Dừng lại.")
         raise Exception("ALREADY_2FA_ON")

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
    # Clean Key triệt để: Xóa mọi khoảng trắng, tab, xuống dòng
    clean_key = "".join(secret_key.split())
    # print(f"   [2FA] Clean Key: {clean_key}") # Debug nếu cần
    
    # Tạo OTP (Lưu ý: System Time máy tính phải chuẩn)
    totp = pyotp.TOTP(clean_key, interval=30)
    otp_code = totp.now()
    
    print(f"   [2FA] OTP Code generated: {otp_code}")
    print("   [2FA] Lưu ý: Nếu OTP sai, hãy đồng bộ lại giờ hệ thống (Time Sync)!")
    
    # Nhập OTP
    wait_and_send_keys(driver, By.CSS_SELECTOR, "input[type='text'], input[type='number']", otp_code)
    time.sleep(2)
    
    # Nhấn Next (Cập nhật XPath mới dựa trên HTML user cung cấp)
    # HTML: ... <span><span>Next</span></span> ...
    print("   [2FA] Nhấn Next để xác nhận OTP...")
    xpath_next_otp = "//span[text()='Next' or text()='Tiếp']"
    clicked_next = False
    
    try:
        # Tìm element Next
        els = driver.find_elements(By.XPATH, xpath_next_otp)
        for el in els:
            if el.is_displayed():
                el.click()
                clicked_next = True
                break
    except: pass
    
    # Fallback nếu cách trên không được
    if not clicked_next:
         wait_and_click(driver, By.XPATH, "//div[@role='button']//span[contains(text(), 'Next') or contains(text(), 'Tiếp')]")
         
    time.sleep(5)
    
    print("   [2FA] Xác nhận hoàn tất.")
    
    # Nhấn Done (Cập nhật XPath mới cho Done)
    # HTML: ... <span><span>Done</span></span> ...
    print("   [2FA] Nhấn Done...")
    xpath_done = "//span[text()='Done' or text()='Xong']"
    clicked_done = False
    
    try:
        els = driver.find_elements(By.XPATH, xpath_done)
        for el in els:
            if el.is_displayed():
                el.click()
                clicked_done = True
                break
    except: pass

    # Fallback Done
    if not clicked_done:
        wait_and_click(driver, By.XPATH, "//div[@role='button']//span[contains(text(), 'Done') or contains(text(), 'Xong')]")
    
    time.sleep(3)
    return secret_key