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
    
    # --- PROMOTED HELPER ---
    def robust_click(xpath_list, description):
        for xpath in xpath_list:
            try:
                els = driver.find_elements(By.XPATH, xpath)
                for el in els:
                    if el.is_displayed():
                        driver.execute_script("arguments[0].style.border='3px solid red'", el)
                        time.sleep(0.2)
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                        time.sleep(0.5)
                        try: el.click()
                        except: driver.execute_script("arguments[0].click();", el)
                        print(f"   [2FA] Đã click {description}")
                        return True
            except: pass
        return False

    # --- CLICK NEXT (SAU KHI LẤY KEY) ---
    print("   [2FA] Nhấn Next để sang bước nhập OTP...")
    next_step_xpaths = [
        "//span[text()='Next']", "//span[text()='Tiếp']",
        "//div[@role='button']//span[contains(text(), 'Next')]",
        "//div[@role='button']//span[contains(text(), 'Tiếp')]",
        "//button[contains(text(), 'Next')]",
        "//button[contains(text(), 'Tiếp')]",
        "//span[contains(text(), 'Next')]", # Fallback loose
        "//span[contains(text(), 'Tiếp')]"
    ]
    
    if not robust_click(next_step_xpaths, "Next (Step 4)"):
         print("   [2FA] Warning: Không click được Next bằng Robust. Thử fallback wait_and_click cũ...")
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
    
    # --- NHẬP OTP (ROBUST) ---
    print(f"   [2FA] Đang nhập OTP: {otp_code}")
    entered_otp = False
    target_input = None
    
    # 0. CHIẾN THUẬT AUTO-FOCUS + KEYBOARD ACTIONS (Mạnh nhất cho IG Modal)
    try:
        # Danh sách selector tiềm năng (ưu tiên placeholder và maxlength)
        potential_selectors = [
            "input[maxlength='6']", 
            "input[placeholder='Enter code']", 
            "input[placeholder='Code']",
            "input[aria-label='Code']",
            "input[aria-label='Security Code']"
        ]
        
        # 1. Tìm input tốt nhất
        for sel in potential_selectors:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in els:
                    if el.is_displayed():
                        target_input = el
                        print(f"   [2FA] Tìm thấy input bằng selector: {sel}")
                        break
            except: pass
            if target_input: break
            
        # 2. Xử lý User XPath (Dynamic ID handling)
        # XPath User đưa: "//*[@id="mount..."]/div/div/..../div/div" -> đây có thể là wrapper
        if not target_input:
             # Tìm input nằm sâu trong cấu trúc div (fallback)
             # Tìm tất cả input hiển thị trong dialog
             dialog_inputs = driver.find_elements(By.XPATH, "//div[@role='dialog']//input")
             for inp in dialog_inputs:
                 if inp.is_displayed():
                     target_input = inp
                     print("   [2FA] Tìm thấy input trong Dialog.")
                     break

        # 3. Thực hiện Focus & Type
        if target_input:
            # Click vào parent để đảm bảo focus nếu click input bị chặn
            try:
                driver.execute_script("arguments[0].parentElement.click();", target_input)
            except: pass
            
            # Click trực tiếp input
            try:
                target_input.click()
            except: 
                 driver.execute_script("arguments[0].click();", target_input)
            
            time.sleep(0.5)
            
            # Action chains send keys (Global send keys vào active element)
            ActionChains(driver).send_keys(otp_code).perform()
            entered_otp = True
            print("   [2FA] Đã nhập OTP (ActionChains Global trên Target).")
        else:
            print("   [2FA] Không tìm thấy input cụ thể, thử click tọa độ giữa màn hình...")
            # Fallback cực đoan: Click vào body rồi tab hoặc tìm input chung chung
            
    except Exception as e:
        print(f"   [2FA] Lỗi nhập ActionChains: {e}")

    # 1. Fallback nhập trực tiếp (SendKeys) nếu chưa được
    if not entered_otp:
        try:
            # Tìm input có maxlength=6 (Đặc trưng của IG 2FA)
            candidates = driver.find_elements(By.CSS_SELECTOR, "input[maxlength='6']")
            for inp in candidates:
                if inp.is_displayed():
                    target_input = inp
                    print("   [2FA] Tìm thấy input OTP (theo maxlength=6).")
                    break
            
            # Nếu không thấy, tìm input hiển thị đầu tiên trong modal
            if not target_input:
                inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='number']")
                for inp in inputs:
                    if inp.is_displayed():
                        target_input = inp
                        print("   [2FA] Tìm thấy input OTP (theo hiển thị).")
                        break
                        
            if target_input:
                # Click focus
                try: target_input.click()
                except: pass
                time.sleep(0.2)
                
                # Clear & Send Keys (Từng ký tự để kích hoạt event)
                target_input.clear()
                for digit in str(otp_code):
                    target_input.send_keys(digit)
                    time.sleep(0.05) 
                
                entered_otp = True
                print(f"   [2FA] Đã nhập mã {otp_code} (SendKeys).")
        except Exception as e:
            print(f"   [2FA] Lỗi nhập phím thường: {e}")

    # 2. Fallback JS (React Safe)
    # Check lại value
    try:
        val = ""
        # Cố gắng lấy value từ active element nếu target_input fail
        active_el = driver.switch_to.active_element
        if active_el and active_el.tag_name == 'input':
             val = active_el.get_attribute("value")
        elif target_input: 
            val = target_input.get_attribute("value")
        
        # Nếu chưa nhập được hoặc value rỗng -> Dùng JS inject
        if not entered_otp or not val:
            print(f"   [2FA] Input value='{val}' -> Thử nhập bằng JS (React Safe)...")
            
            # Script tìm lại input maxlength 6 nếu target_input mất ref
            js_code = """
                var otp = arguments[0];
                var found = false;
                
                function setNativeValue(element, value) {
                    var lastValue = element.value;
                    element.value = value;
                    var event = new Event('input', { bubbles: true });
                    // Hack for React 15/16
                    var tracker = element._valueTracker;
                    if (tracker) {
                        tracker.setValue(lastValue);
                    }
                    element.dispatchEvent(event);
                }

                // Strategy 0: Active Element
                if (document.activeElement && document.activeElement.tagName === 'INPUT') {
                    setNativeValue(document.activeElement, otp);
                    found = true;
                }

                // Strategy 1: Try maxlength 6 (Most accurate for 2FA)
                if (!found) {
                    var inputs = document.querySelectorAll("input[maxlength='6']");
                    for(var i=0; i<inputs.length; i++) {
                        if(inputs[i].offsetParent !== null) {
                            inputs[i].focus();
                            setNativeValue(inputs[i], otp);
                            found = true;
                            break;
                        }
                    }
                }
                
                // Strategy 2: Fallback generic
                if (!found) {
                    var allInputs = document.querySelectorAll("input[type='text'], input[type='number']");
                     for(var i=0; i<allInputs.length; i++) {
                        if(allInputs[i].offsetParent !== null) {
                            allInputs[i].focus();
                            setNativeValue(allInputs[i], otp);
                            found = true;
                            break;
                        }
                    }
                }
                return found;
            """
            driver.execute_script(js_code, otp_code)
            entered_otp = True
            print("   [2FA] Đã thực thi JS nhập OTP (React Pattern).")
            
    except Exception as e:
        print(f"   [2FA] Lỗi nhập JS: {e}")

    time.sleep(1)

    # --- VERIFY OTP ENTRY BEFORE NEXT ---
    # Kiểm tra chắc chắn đã có OTP trong input chưa
    print("   [2FA] Verify OTP input value...")
    verify_js = """
        var otp = arguments[0];
        var inputs = document.querySelectorAll("input");
        for(var i=0; i<inputs.length; i++) {
            if (inputs[i].value == otp) return true;
        }
        return false;
    """
    is_filled = driver.execute_script(verify_js, otp_code)
    
    if not is_filled:
        print("   [2FA] Warning: OTP chưa được nhập đúng giá trị. Thử lại lần cuối...")
        # Retry logic here if needed (e.g. re-run JS)
        driver.execute_script(js_code, otp_code)
        time.sleep(1)
        is_filled = driver.execute_script(verify_js, otp_code)
        
    if not is_filled:
        raise Exception("NHẬP OTP THẤT BẠI: Input value không khớp code.")
        
    print("   [2FA] Verify Input OK. Proceed to Next.")
    
    # Helper: Hàm click mạnh tay
    def robust_click(xpath_list, description):
        for xpath in xpath_list:
            try:
                els = driver.find_elements(By.XPATH, xpath)
                for el in els:
                    if el.is_displayed():
                        # Highlighting for debug
                        driver.execute_script("arguments[0].style.border='3px solid red'", el)
                        time.sleep(0.2)
                        # Scroll & Click
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                        time.sleep(0.5)
                        try:
                            el.click()
                        except:
                            driver.execute_script("arguments[0].click();", el)
                        print(f"   [2FA] Đã click {description}")
                        return True
            except:
                pass
        return False

    # --- CLICK NEXT (XÁC NHẬN OTP) ---
    print("   [2FA] Nhấn Next để xác nhận OTP...")
    next_xpaths = [
        "//span[text()='Next']", 
        "//span[text()='Tiếp']",
        "//div[@role='button']//span[contains(text(), 'Next')]",
        "//div[@role='button']//span[contains(text(), 'Tiếp')]"
    ]
    
    robust_click(next_xpaths, "Next")
    
    # --- CHỜ MÀN HÌNH 'DONE' (GIAI ĐOẠN QUAN TRỌNG) ---
    print("   [2FA] Đang đợi kết quả xác nhận OTP (Chờ nút Done)...")
    success_confirmed = False
    
    done_xpaths = [
        "//span[text()='Done']", 
        "//span[text()='Xong']",
        "//div[@role='button']//span[contains(text(), 'Done')]",
        "//div[@role='button']//span[contains(text(), 'Xong')]"
    ]

    for i in range(15): # Loop 15 lần (khoảng 15-20s)
        time.sleep(1.5)
        
        # 1. Check lỗi từ Instagram (OTP sai)
        try:
            body_text_check = driver.find_element(By.TAG_NAME, "body").text.lower()
            if "code isn't right" in body_text_check or "mã không đúng" in body_text_check:
                raise Exception("OTP CODE SAI (Instagram từ chối).")
            if "please check the code" in body_text_check:
                raise Exception("OTP CODE SAI (Please check the code).")
        except Exception as e:
            if "OTP CODE SAI" in str(e): raise e

        # 2. Check xem nút Done đã hiện chưa
        found_done = False
        for xpath in done_xpaths:
            if len(driver.find_elements(By.XPATH, xpath)) > 0:
                # Kiểm tra hiển thị
                if any(e.is_displayed() for e in driver.find_elements(By.XPATH, xpath)):
                    found_done = True
                    break
        
        if found_done:
            success_confirmed = True
            print("   [2FA] => Đã thấy nút Done (OTP OK).")
            break
            
        # Nếu chưa thấy Done, có thể nút Next click hụt, nhấn lại Next
        if i % 3 == 0 and i > 0:
             print(f"   [2FA] Chưa thấy Done, thử click Next lại lần {int(i/3)}...")
             robust_click(next_xpaths, "Next (Retry)")

    if not success_confirmed:
        raise Exception("TIMEOUT: Không thấy nút Done sau khi nhập OTP. Có thể OTP sai hoặc mạng lag.")

    # --- CLICK DONE (HOÀN TẤT) ---
    print("   [2FA] Đợi 3s để màn hình 'Done' ổn định...")
    time.sleep(3) # Thêm delay theo yêu cầu user để tránh click trượt khi animation chưa xong
    
    print("   [2FA] Nhấn Done để hoàn tất quy trình...")
    clicked_done = robust_click(done_xpaths, "Done")
    
    if not clicked_done:
        # Fallback JS tìm và click mạnh hơn, có check throw error
        try:
            print("   [2FA] Click Done (Selenium) fail, thử JS...")
            driver.execute_script("""
                var found = false;
                var elements = document.querySelectorAll('span, div[role="button"]');
                for (var i = 0; i < elements.length; i++) {
                    var txt = elements[i].innerText.trim().toLowerCase();
                    if (txt === 'done' || txt === 'xong') {
                        elements[i].click();
                        found = true;
                        break;
                    }
                }
                if (!found) throw "JS could not find Done button";
            """)
            clicked_done = True
            print("   [2FA] Click Done (JS) thành công.")
        except Exception as e:
            print(f"   [2FA] Click Done (JS) thất bại: {e}")
            clicked_done = False
            
    if not clicked_done:
        raise Exception("LỖI CRITICAL: Không nhấn được nút Done cuối cùng. 2FA chưa complete.")
    
    time.sleep(3)
    
    # Check lại lần nữa xem còn ở màn hình done không (Optional)
    # Nếu còn chữ Done -> click fail
    return secret_key