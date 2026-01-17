# two_fa_handler.py
import time
import re
import pyotp
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from config_utils import wait_and_click, wait_and_send_keys, wait_dom_ready, wait_element

# --- HELPER: Fast Check Text ---
def _body_has_text(driver, text_list):
    try:
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
        return any(t.lower() in body for t in text_list)
    except:
        return False

def _raise_if_change_not_allowed_yet(driver):
    if _body_has_text(driver, ["you can't make this change at the moment"]):
        msg = "Not allowed yet: Instagram blocked change (Unfamiliar device)."
        print("   [2FA] ERROR: " + msg)
        raise RuntimeError(msg)

# --- NEW FUNCTION: VALIDATE MASKED EMAIL ---
def _validate_masked_email(driver, real_email):
    """
    So sánh email bị che trên màn hình (vd: m*******r@g**.ch) 
    với email thực tế trong input (vd: dustinvazquez@usa.com).
    Nếu lệch -> Raise Exception.
    """
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        # Regex tìm chuỗi email bị che. 
        # Pattern: Bắt đầu bằng chữ, chứa *, có @, chứa *, kết thúc bằng chữ.
        # Ví dụ match: m*******r@g**.ch
        match = re.search(r'\b([a-zA-Z0-9][\w\*]*@[\w\*]+\.[a-zA-Z\.]+)\b', body_text)
        
        if not match:
            print("   [2FA] Warning: Could not find masked email text on screen to verify.")
            return # Không tìm thấy text thì cho qua (để an toàn)

        masked_email = match.group(1).lower().strip()
        real_email = real_email.lower().strip()
        
        print(f"   [2FA] Verifying Email: UI='{masked_email}' vs Input='{real_email}'")

        # Phân tách Real Email
        if "@" not in real_email: return 
        real_user, real_domain = real_email.split("@")
        
        # Phân tách Masked Email
        masked_user, masked_domain = masked_email.split("@")

        # 1. Check chữ cái ĐẦU TIÊN (User)
        # masked_user[0] không phải là '*'
        if masked_user[0] != '*' and masked_user[0] != real_user[0]:
            raise Exception(f"WRONG EMAIL HINT: User start '{masked_user[0]}' != '{real_user[0]}'")

        # 2. Check chữ cái CUỐI CÙNG (User - Trước @)
        if masked_user[-1] != '*' and masked_user[-1] != real_user[-1]:
             raise Exception(f"WRONG EMAIL HINT: User end '{masked_user[-1]}' != '{real_user[-1]}'")

        # 3. Check chữ cái ĐẦU TIÊN (Domain - Sau @)
        if masked_domain[0] != '*' and masked_domain[0] != real_domain[0]:
             raise Exception(f"WRONG EMAIL HINT: Domain start '{masked_domain[0]}' != '{real_domain[0]}'")
             
        # 4. Check chữ cái CUỐI CÙNG (Domain)
        # Domain IG thường hiện full hoặc che giữa, lấy ký tự cuối cùng của string
        if masked_domain[-1] != '*' and masked_domain[-1] != real_domain[-1]:
            raise Exception(f"WRONG EMAIL HINT: Domain end '{masked_domain[-1]}' != '{real_domain[-1]}'")
            
        print("   [2FA] Email Hint Validation: MATCHED.")

    except Exception as e:
        if "WRONG EMAIL HINT" in str(e):
            print(f"   [2FA] CRITICAL ERROR: {e}")
            raise e # Ném lỗi để main.py bắt và skip account này
        else:
            print(f"   [2FA] Error validating email hint: {e}")

# --- REACT INPUT HELPER ---
def inject_react_input(driver, code_value):
    js_react_fill = """
    var code = arguments[0];
    var selectors = ["input[name='code']", "input[placeholder='Code']", "input[aria-label='Code']", "input[type='text']", "input[type='number']"];
    var inputEl = null;
    for (var s of selectors) {
        var els = document.querySelectorAll(s);
        for (var i = 0; i < els.length; i++) {
            if (els[i].offsetParent !== null) { inputEl = els[i]; break; }
        }
        if (inputEl) break;
    }
    if (!inputEl) {
        var allInputs = document.querySelectorAll("input");
        for (var i = 0; i < allInputs.length; i++) {
             if (allInputs[i].offsetParent !== null) { inputEl = allInputs[i]; break; }
        }
    }
    if (inputEl) {
        inputEl.focus();
        var lastValue = inputEl.value;
        inputEl.value = code;
        var event = new Event('input', { bubbles: true });
        var tracker = inputEl._valueTracker;
        if (tracker) { tracker.setValue(lastValue); }
        inputEl.dispatchEvent(event);
        return true;
    }
    return false;
    """
    return driver.execute_script(js_react_fill, str(code_value))


def setup_2fa(driver, email, email_pass, target_username=None):
    """
    Execute 2FA setup process: Enable 2FA -> Get Key -> Confirm -> Return Key.
    """
    print(f"   [2FA] Accessing 2FA settings page...")
    driver.get("https://accountscenter.instagram.com/password_and_security/two_factor/")
    
    wait_dom_ready(driver, timeout=5)
    _raise_if_change_not_allowed_yet(driver)

    # STEP 1: SELECT ACCOUNT
    print("   [2FA] Selecting account...")
    wait_element(driver, By.XPATH, "//div[@role='button'] | //a[@role='link']", timeout=5)
    
    candidates = driver.find_elements(By.XPATH, "//div[@role='button'] | //a[@role='link']")
    target_el = None
    ig_candidates = [el for el in candidates if "instagram" in el.text.lower()]
    
    if ig_candidates:
        if len(ig_candidates) == 1:
            target_el = ig_candidates[0]
        elif target_username:
            norm_target = target_username.strip().lower()
            for cand in ig_candidates:
                if norm_target in cand.text.lower():
                    target_el = cand; break
            if not target_el: target_el = ig_candidates[0]
        else:
            target_el = ig_candidates[0]

    if target_el:
        try: driver.execute_script("arguments[0].click();", target_el)
        except: target_el.click()
    else:
        driver.execute_script("""
            var elements = document.querySelectorAll('div[role="button"], a[role="link"]');
            for (var i = 0; i < elements.length; i++) {
                if (elements[i].innerText.includes('Instagram')) { elements[i].click(); break; }
            }
        """)

    # STEP 2: WAIT FOR NEXT SCREEN
    print("   [2FA] Waiting for next screen...")
    
    found_next_step = False
    is_checkpoint = False
    
    end_wait = time.time() + 15 
    while time.time() < end_wait:
        src = driver.page_source.lower()
        
        # 1. Success
        if "authentication app" in src or "ứng dụng xác thực" in src:
            found_next_step = True; break

        # 2. Checkpoint
        if "check your email" in src or "enter the code" in src or "mã bảo mật" in src:
            is_checkpoint = True; break

        # 3. Already ON
        try:
            headers = driver.find_elements(By.XPATH, "//div[@role='dialog']//h2 | //div[@role='dialog']//span | //h2 | //span")
            for h in headers:
                if h.is_displayed():
                    txt = h.text.lower()
                    if "authentication is on" in txt or "xác thực 2 yếu tố đang bật" in txt or "two-factor authentication is on" in txt:
                        raise Exception("ALREADY_2FA_ON")
        except Exception as e:
            if "ALREADY_2FA_ON" in str(e): raise e

        if "is on" in src or "đang bật" in src:
             if _body_has_text(driver, ["authentication is on", "tính năng xác thực 2 yếu tố đang bật"]):
                 raise Exception("ALREADY_2FA_ON")

        time.sleep(0.5)

    _raise_if_change_not_allowed_yet(driver)

    # --- HANDLE CHECKPOINT ---
    if is_checkpoint:
        print("   [2FA] Checkpoint Detected: Email verify required...")
        
        # ===> THÊM BƯỚC VALIDATE EMAIL Ở ĐÂY <===
        _validate_masked_email(driver, email)
        # ========================================

        # 1. Get Code
        from mail_handler import get_code_from_mail
        mail_code = get_code_from_mail(driver, email, email_pass)
        
        if not mail_code:
            raise Exception("Could not get mail code to bypass Checkpoint")

        # 2. Input Code
        print(f"   [2FA] Inputting Checkpoint Code: {mail_code}")
        try:
            chk_input = wait_element(driver, By.CSS_SELECTOR, "input[name='code'], input[placeholder='Code']", timeout=2)
            if chk_input: chk_input.click()
        except: pass
        
        inject_react_input(driver, mail_code)
        time.sleep(0.5) 
        
        # 3. Click Continue
        clicked = wait_and_click(driver, By.XPATH, "//div[@role='button']//span[contains(text(), 'Continue') or contains(text(), 'Tiếp')]", timeout=2)
        if not clicked:
             try: driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
             except: pass

        # 4. Wait Result
        cp_end = time.time() + 10
        while time.time() < cp_end:
            if _body_has_text(driver, ["code isn't right", "wrong code", "mã không đúng"]):
                raise Exception("WRONG EMAIL CODE (Instagram rejected).")
            
            if _body_has_text(driver, ["authentication app", "ứng dụng xác thực"]):
                break
            
            # Check 2FA ON again
            try:
                headers = driver.find_elements(By.XPATH, "//div[@role='dialog']//h2 | //h2")
                for h in headers:
                    if h.is_displayed():
                        txt = h.text.lower()
                        if "authentication is on" in txt or "đang bật" in txt:
                             raise Exception("ALREADY_2FA_ON")
            except Exception as e:
                if "ALREADY_2FA_ON" in str(e): raise e

            time.sleep(0.5)
            
        _raise_if_change_not_allowed_yet(driver)


    # STEP 3: CHOOSE AUTHENTICATION APP
    print("   [2FA] Selecting 'Authentication App'...")
    auth_text_xpaths = [
        "//*[contains(text(), 'Authentication app')]",
        "//*[contains(text(), 'Ứng dụng xác thực')]",
        "//input[@value='authentication_app']/.." 
    ]
    for xpath in auth_text_xpaths:
        try:
            els = driver.find_elements(By.XPATH, xpath)
            for el in els:
                if el.is_displayed(): el.click(); break
        except: pass
    time.sleep(0.5)

    # Click Next (Robust)
    print("   [2FA] Clicking Next/Continue...")
    next_btn_xpaths = [
        "//button[contains(text(), 'Next')]",
        "//button[contains(text(), 'Tiếp')]",
        "//button[contains(text(), 'Continue')]",
        "//div[@role='button'][contains(., 'Next')]",
        "//div[@role='button'][contains(., 'Tiếp')]",
        "//div[@role='button'][contains(., 'Continue')]",
        "//button[@type='submit']", 
        "//div[@role='button'][@tabindex='0']"
    ]
    
    clicked_next = False
    for xpath in next_btn_xpaths:
        try:
            btns = driver.find_elements(By.XPATH, xpath)
            for btn in btns:
                if btn.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    time.sleep(0.2)
                    try: btn.click(); clicked_next = True
                    except: 
                        try: driver.execute_script("arguments[0].click();", btn); clicked_next = True
                        except: pass
                    if clicked_next: break
        except: pass
        if clicked_next: break
            
    if not clicked_next:
        print("   [2FA] Warning: Standard Next click failed. Trying blind JS Submit...")
        try: driver.execute_script("document.querySelector('button[type=\"submit\"]').click()"); clicked_next = True
        except: pass

    try: wait_element(driver, By.XPATH, "//*[contains(text(), 'Copy key') or contains(text(), 'Sao chép')]", timeout=5)
    except: 
        if not clicked_next: raise Exception("Cannot click Next/Continue button at Step 3.")
    _raise_if_change_not_allowed_yet(driver)

    # STEP 4: GET SECRET KEY
    print("   [2FA] Getting Secret Key...")
    wait_and_click(driver, By.XPATH, "//*[contains(text(), 'Copy key') or contains(text(), 'Sao chép')]", timeout=2)
    
    full_text = driver.find_element(By.TAG_NAME, "body").text
    match = re.search(r'([A-Z2-7]{4}\s){3,}[A-Z2-7]{4}', full_text)
    secret_key = match.group(0) if match else ""
    
    if not secret_key:
        inputs = driver.find_elements(By.TAG_NAME, "input")
        for inp in inputs:
            val = inp.get_attribute("value")
            if val and len(val) > 16 and " " in val: secret_key = val; break
    
    if not secret_key: raise Exception("Secret Key not found")
    print(f"   [2FA] Key found: {secret_key}")

    # STEP 5: CLICK NEXT & GENERATE OTP
    wait_and_click(driver, By.XPATH, "//div[@role='button']//span[contains(text(), 'Next') or contains(text(), 'Tiếp')]", timeout=3)
    
    clean_key = "".join(secret_key.split())
    totp = pyotp.TOTP(clean_key, interval=30)
    otp_code = totp.now()
    
    wait_element(driver, By.CSS_SELECTOR, "input[maxlength='6'], input[placeholder='Enter code']", timeout=5)

    # STEP 6: ENTER OTP
    print(f"   [2FA] Entering OTP: {otp_code}")
    inject_react_input(driver, otp_code)
    time.sleep(0.5) 
    
    # STEP 7: CONFIRM
    print("   [2FA] Confirming...")
    wait_and_click(driver, By.XPATH, "//div[@role='button']//span[contains(text(), 'Next') or contains(text(), 'Tiếp')]", timeout=2)
    
    print("   [2FA] Waiting for completion...")
    end_confirm = time.time() + 15
    success_confirmed = False
    SEL_DONE = "//span[contains(text(), 'Done')] | //span[contains(text(), 'Xong')]"
    
    while time.time() < end_confirm:
        if _body_has_text(driver, ["code isn't right", "mã không đúng", "check the code"]):
            raise Exception("WRONG OTP CODE (Instagram rejected).")
            
        done_btns = driver.find_elements(By.XPATH, SEL_DONE)
        visible_done = [b for b in done_btns if b.is_displayed()]
        if visible_done:
            visible_done[0].click(); success_confirmed = True; print("   [2FA] => SUCCESS (Done clicked)."); break
        time.sleep(0.2)

    if not success_confirmed: raise Exception("TIMEOUT: Done button not found (OTP might be wrong).")
    time.sleep(1)
    return secret_key