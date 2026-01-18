# two_fa_handler.py
import time
import re
import pyotp
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys # Cần import Keys
from selenium.webdriver.common.action_chains import ActionChains
from config_utils import wait_and_click, wait_dom_ready, wait_element

# --- IMPORT MAIL HANDLER ---
try:
    from mail_handler import get_code_from_mail
except ImportError:
    print("   [ERROR] Không tìm thấy file mail_handler.py!")

# ==========================================
# 1. JS SENSOR
# ==========================================
def get_page_state(driver):
    js_sensor = """
    function checkState() {
        var body = document.body.innerText.toLowerCase();
        if (body.includes("you can't make this change") || body.includes("change at the moment")) return 'RESTRICTED';
        if (body.includes("suspended") || body.includes("đình chỉ")) return 'SUSPENDED';
        if (body.includes("sorry, this page isn't available")) return 'BROKEN';

        // Check 2FA ON
        if (body.includes("authentication is on") || body.includes("xác thực 2 yếu tố đang bật")) {
             var h2s = document.querySelectorAll('h2, span');
             for(var h of h2s) {
                 if(h.innerText.toLowerCase().includes("is on") || h.innerText.toLowerCase().includes("đang bật")) {
                     if(h.offsetHeight > 0) return 'ALREADY_ON';
                 }
             }
        }
        // Check Select App
        if (body.includes("authentication app") || body.includes("ứng dụng xác thực") || body.includes("help protect your account")) {
             var lbls = document.querySelectorAll("span, div, h2");
             for (var i=0; i<lbls.length; i++) {
                 var txt = lbls[i].innerText.toLowerCase();
                 if ((txt.includes("authentication app") || txt.includes("ứng dụng xác thực")) && lbls[i].offsetParent !== null) {
                     return 'SELECT_APP';
                 }
             }
        }
        // Check Checkpoint
        var inputs = document.querySelectorAll("input[name='code'], input[placeholder*='Code']");
        var hasInput = false;
        for (var i=0; i<inputs.length; i++) {
            if (inputs[i].offsetParent !== null) { hasInput = true; break; }
        }
        if (hasInput) {
            if (body.includes("email") || body.includes("sms") || body.includes("sent to") || body.includes("mã")) return 'CHECKPOINT';
        }
        if (body.includes("check your email") || body.includes("enter the code")) return 'CHECKPOINT';

        return 'UNKNOWN';
    }
    return checkState();
    """
    try: return driver.execute_script(js_sensor)
    except: return 'UNKNOWN'

# --- HELPERS ---
def _validate_masked_email(driver, real_email):
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        match = re.search(r'\b([a-zA-Z0-9][\w\*]*@[\w\*]+\.[a-zA-Z\.]+)\b', body_text)
        if not match: return 
        masked, real = match.group(1).lower().strip(), real_email.lower().strip()
        if "@" not in real: return 
        r_u, r_d = real.split("@"); m_u, m_d = masked.split("@")
        if m_u[0] != '*' and m_u[0] != r_u[0]: raise Exception(f"WRONG EMAIL HINT: {masked}")
        print(f"   [2FA] Hint OK: {masked}")
    except Exception as e:
        if "WRONG EMAIL HINT" in str(e): raise e 

# --- INPUT HELPER MỚI (CỰC MẠNH) ---
def _robust_fill_input(driver, text_value):
    """
    Thử mọi cách để điền text vào ô Input cho đến khi giá trị dính vào.
    """
    # 1. Tìm ô Input
    input_el = wait_element(driver, By.CSS_SELECTOR, "input[maxlength='6'], input[placeholder*='Code'], input[aria-label*='Code']", timeout=5)
    if not input_el: return False
    
    val = str(text_value)
    
    # 2. Thử Cách 1: React JS Inject (Nhanh nhất)
    driver.execute_script("""
        var input = arguments[0];
        var val = arguments[1];
        input.focus();
        var lastValue = input.value;
        input.value = val;
        var event = new Event('input', { bubbles: true });
        var tracker = input._valueTracker;
        if (tracker) { tracker.setValue(lastValue); }
        input.dispatchEvent(event);
        input.dispatchEvent(new Event('change', { bubbles: true })); // Thêm event change
    """, input_el, val)
    
    time.sleep(0.2)
    
    # Check lại
    if input_el.get_attribute("value").replace(" ", "") == val:
        return True
        
    print("   [2FA] JS Inject failed, trying ActionChains...")
    
    # 3. Thử Cách 2: ActionChains (Giả lập bàn phím)
    try:
        input_el.click()
        time.sleep(0.1)
        # Xóa cũ (Ctrl+A -> Delete)
        input_el.send_keys(Keys.CONTROL + "a")
        input_el.send_keys(Keys.DELETE)
        time.sleep(0.1)
        # Gõ từng số
        ActionChains(driver).send_keys(val).perform()
    except: pass
    
    time.sleep(0.2)
    if input_el.get_attribute("value").replace(" ", "") == val:
        return True

    print("   [2FA] ActionChains failed, trying SendKeys...")

    # 4. Thử Cách 3: SendKeys (Cổ điển)
    try:
        input_el.clear()
        input_el.send_keys(val)
    except: pass
    
    return input_el.get_attribute("value").replace(" ", "") == val


def click_continue_robust(driver):
    js_click = """
    var keywords = ["Next", "Tiếp", "Continue", "Submit", "Xác nhận"];
    var btns = document.querySelectorAll("button, div[role='button']");
    for (var b of btns) {
        var txt = b.innerText.trim();
        var match = false;
        for(var k of keywords) { if(txt.includes(k)) { match = true; break; } }
        if (match && b.offsetParent !== null) { b.click(); return true; }
    }
    var sub = document.querySelector('button[type="submit"]');
    if(sub && sub.offsetParent !== null) { sub.click(); return true; }
    return false;
    """
    return driver.execute_script(js_click)

# ==========================================
# 2. MAIN LOGIC
# ==========================================

def setup_2fa(driver, email, email_pass, target_username=None):
    print(f"   [2FA] Accessing settings...")
    driver.get("https://accountscenter.instagram.com/password_and_security/two_factor/")
    wait_dom_ready(driver, timeout=5)

    # STEP 1: SELECT ACCOUNT
    print("   [2FA] Selecting account...")
    wait_element(driver, By.XPATH, "//div[@role='button'] | //a[@role='link']", timeout=5)
    driver.execute_script("""
        var els = document.querySelectorAll('div[role="button"], a[role="link"]');
        for (var i=0; i<els.length; i++) {
            if (els[i].innerText.toLowerCase().includes('instagram')) { els[i].click(); break; }
        }
    """)
    time.sleep(1)

    # STEP 2: SCAN STATE
    print("   [2FA] Scanning State...")
    state = "UNKNOWN"
    end_time = time.time() + 15
    while time.time() < end_time:
        state = get_page_state(driver)
        if state == 'SELECT_APP': 
            print("   [2FA] Detected 'Select App' -> Skipping Checkpoint.")
            break 
        if state == 'CHECKPOINT': break
        if state == 'ALREADY_ON': break
        if state == 'RESTRICTED': break
        time.sleep(0.5)

    print(f"   [2FA] Detected State: {state}")

    if state == 'RESTRICTED': raise RuntimeError("RESTRICTED_DEVICE")
    if state == 'SUSPENDED': raise RuntimeError("ACCOUNT_SUSPENDED")
    if state == 'ALREADY_ON': raise Exception("ALREADY_2FA_ON")

    # HANDLE CHECKPOINT
    if state == 'CHECKPOINT':
        print("   [2FA] Handling Checkpoint (Mail)...")
        time.sleep(1)
        if get_page_state(driver) == 'SELECT_APP':
             print("   [2FA] Auto-redirected to Select App -> Skip Mail.")
        else:
            _validate_masked_email(driver, email)
            print(f"   [2FA] Calling mail_handler for {email}...")
            mail_code = get_code_from_mail(driver, email, email_pass)
            
            if not mail_code:
                 if get_page_state(driver) == 'SELECT_APP':
                    print("   [2FA] Mail failed but page moved to Select App -> Ignore.")
                 else:
                    raise Exception("CHECKPOINT_FAIL: No code found in mail.")
            else:
                print(f"   [2FA] Inputting Checkpoint Code: {mail_code}")
                # Dùng hàm Robust Input
                if not _robust_fill_input(driver, mail_code):
                    print("   [2FA] Warning: Failed to fill Checkpoint code.")
                
                time.sleep(0.5)
                click_continue_robust(driver)

                # Validate
                print("   [2FA] Validating Email Code...")
                chk_valid = False
                cp_end = time.time() + 10
                while time.time() < cp_end:
                    err = driver.execute_script("return document.body.innerText.toLowerCase().includes('code isn\\'t right') || document.body.innerText.toLowerCase().includes('mã không đúng');")
                    if err: raise Exception("WRONG EMAIL CODE")
                    
                    st = get_page_state(driver)
                    if st == 'SELECT_APP': chk_valid = True; break
                    if st == 'ALREADY_ON': raise Exception("ALREADY_2FA_ON")
                    time.sleep(0.5)
                
                if not chk_valid: raise Exception("TIMEOUT: Checkpoint stuck.")

    # STEP 3: SELECT APP
    print("   [2FA] Selecting 'Authentication App'...")
    driver.execute_script("""
        var els = document.querySelectorAll("span, div");
        for (var i=0; i<els.length; i++) {
             if ((els[i].innerText.includes("Authentication app") || els[i].innerText.includes("Ứng dụng xác thực")) && els[i].offsetParent !== null) {
                 els[i].click(); break;
             }
        }
    """)
    time.sleep(0.5)

    print("   [2FA] Clicking Next/Continue...")
    if not click_continue_robust(driver):
        try:
             btn = wait_element(driver, By.XPATH, "//button[contains(.,'Continue')] | //div[@role='button'][contains(.,'Next')] | //button[@type='submit']", timeout=3)
             if btn: btn.click()
        except: pass

    time.sleep(1)
    if get_page_state(driver) == 'ALREADY_ON': raise Exception("ALREADY_2FA_ON")

    # STEP 4: GET KEY
    print("   [2FA] Waiting for Key screen...")
    try:
        wait_element(driver, By.XPATH, "//*[contains(text(), 'Copy key') or contains(text(), 'Sao chép')]", timeout=8)
    except:
        if get_page_state(driver) == 'ALREADY_ON': raise Exception("ALREADY_2FA_ON")
    
    secret_key = ""
    key_wait_end = time.time() + 20
    
    while time.time() < key_wait_end:
        driver.execute_script("""
            var els = document.querySelectorAll("span, div[role='button']");
            for(var e of els) {
                if(e.innerText.includes("Copy key") || e.innerText.includes("Sao chép")) { e.click(); break; }
            }
        """)
        time.sleep(1.5) 
        
        try:
            full_text = driver.find_element(By.TAG_NAME, "body").text
            match = re.search(r'([A-Z2-7]{4}\s){3,}[A-Z2-7]{4}', full_text)
            if match:
                found_key = match.group(0).strip()
                if len(found_key) > 16:
                    secret_key = found_key
                    print(f"   [2FA] Key Detected: {secret_key[:5]}...")
                    break
        except: pass
        
        if not secret_key:
            inputs = driver.find_elements(By.TAG_NAME, "input")
            for inp in inputs:
                val = inp.get_attribute("value")
                if val and len(val) > 16 and (" " in val or len(val) == 32): 
                    secret_key = val
                    print(f"   [2FA] Key Detected (Input): {secret_key[:5]}...")
                    break
            if secret_key: break
            
        print("   [2FA] Key loading...")
    
    if not secret_key: raise Exception("Secret Key not found (Timeout).")
    print(f"   [2FA] Final Key: {secret_key}")

    # =========================================================
    # STEP 5: CONFIRM OTP (FIXED INPUT)
    # =========================================================
    
    # 1. Click Next từ màn hình Copy Key
    print("   [2FA] Clicking Next to Input OTP...")
    click_continue_robust(driver)
    
    # 2. Tính toán OTP
    clean_key = "".join(secret_key.split())
    totp = pyotp.TOTP(clean_key, interval=30)
    otp_code = totp.now()
    
    # 3. Chờ ô Input xuất hiện
    print(f"   [2FA] Waiting for OTP Input (Code: {otp_code})...")
    
    # 4. ĐIỀN OTP BẰNG HÀM ROBUST
    is_filled = False
    fill_end = time.time() + 10 # Thử trong 10s
    while time.time() < fill_end:
        # Thử điền
        if _robust_fill_input(driver, otp_code):
            is_filled = True
            break
        print("   [2FA] Retrying input fill...")
        time.sleep(1)
        
    if not is_filled:
        raise Exception("FAIL: Could not fill OTP into input box.")
    
    print(f"   [2FA] Input Filled. Confirming...")
    
    # 5. Confirm
    time.sleep(0.5)
    click_continue_robust(driver)
    
    print("   [2FA] Waiting for completion...")
    end_confirm = time.time() + 15
    success = False
    
    while time.time() < end_confirm:
        res = driver.execute_script("""
            var body = document.body.innerText.toLowerCase();
            if (body.includes("code isn't right") || body.includes("mã không đúng")) return 'WRONG_OTP';
            
            var doneBtns = document.querySelectorAll("span");
            for(var b of doneBtns) {
                if((b.innerText === 'Done' || b.innerText === 'Xong') && b.offsetParent !== null) {
                    b.click(); return 'SUCCESS';
                }
            }
            return 'WAIT';
        """)
        
        if res == 'WRONG_OTP': raise Exception("WRONG OTP CODE")
        if res == 'SUCCESS': success = True; print("   [2FA] => SUCCESS."); break
        time.sleep(0.2)

    if not success: raise Exception("TIMEOUT: Done button not found.")
    time.sleep(1)
    return secret_key