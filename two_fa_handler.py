# two_fa_handler.py
import time
import re
import pyotp
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
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
    Execute 2FA setup process: Enable 2FA -> Get Key -> Confirm -> Return Key.
    """
    print(f"   [2FA] Accessing 2FA settings page (Target: {target_username})...")
    driver.get("https://accountscenter.instagram.com/password_and_security/two_factor/")
    time.sleep(5) # Wait React Framework
    _raise_if_change_not_allowed_yet(driver)
    

    # STEP 1: SELECT ACCOUNT
    print("   [2FA] Selecting account...")
    time.sleep(3) # Wait account list
    
    clicked = False
    try:
        # LOGIC SELECT ACCOUNT UPDATED
        # Find account buttons
        # Usually div[role='button'] or a[role='link']
        
        # 1. Find all candidates
        candidates = driver.find_elements(By.XPATH, "//div[@role='button'] | //a[@role='link']")
        
        instagram_candidates = []
        
        # 2. Filter list
        for el in candidates:
            try:
                txt = el.text.lower()
                # Check for Instagram
                if "instagram" in txt:
                    instagram_candidates.append(el)
            except: pass
            
        print(f"   [2FA] Found {len(instagram_candidates)} Instagram accounts.")
        
        target_el = None
        
        if instagram_candidates:
            # If 1 -> Select
            if len(instagram_candidates) == 1:
                target_el = instagram_candidates[0]
                print("   [2FA] Only 1 Instagram account. Selecting.")
            elif target_username:
                # If multiple, find match
                norm_target = target_username.strip().lower()
                print(f"   [2FA] Finding account matching '{norm_target}'...")
                
                for cand in instagram_candidates:
                    if norm_target in cand.text.lower():
                        target_el = cand
                        print("   [2FA] => Match found!")
                        break
                
                # If not found -> fallback
                if not target_el:
                    print("   [2FA] Username match not found. Fallback to first.")
                    target_el = instagram_candidates[0]
            else:
                # No target user -> first
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
        
        # Fallback old
        if not clicked:
            print("   [2FA] Fallback JS Selection old...")
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
        print(f"   [2FA] Error selecting account: {e}")

    # Wait manual check
    print("   [2FA] Waiting for next screen...")
    found_step = False
    
    # Increase wait to 60s
    for _ in range(60): 
        src = driver.page_source.lower()
        if "check your email" in src or "authentication app" in src or "is on" in src:
            found_step = True
            # Wait for UI stability
            time.sleep(3)
            break
        time.sleep(1)
        
    if not found_step:
        print("   [2FA] Warning: Timeout waiting for next screen.")
    
    _raise_if_change_not_allowed_yet(driver)

    # Update current screen context
    try:
        # Check carefully H2, H1 in modal
        # Supplement deep xpath search
        # div > h2 > span
        check_elements = driver.find_elements(By.XPATH, "//*[@id='mount_0_0_2j']//h2//span") # Hard selector
        check_elements += driver.find_elements(By.XPATH, "//h2//span") # Soft selector
        check_elements += driver.find_elements(By.TAG_NAME, "h2")
        
        for el in check_elements:
            try:
                txt = el.text.lower()
                if "authentication is on" in txt or "đang bật" in txt:
                    print(f"   [2FA] Detected text '{txt}' -> 2FA ON.")
                    raise Exception("ALREADY_2FA_ON")
            except: pass # Ignore stale element
            
    except Exception as e:
        if str(e) == "ALREADY_2FA_ON": raise e

    body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
    
    # --- EARLY CHECK: IS 2FA ON? ---
    # User Request: check text "Two-factor authentication is on"
    # Add xpath check
    is_2fa_on_xpath = len(driver.find_elements(By.XPATH, "//*[contains(text(), 'Two-factor authentication is on') or contains(text(), 'Tính năng xác thực 2 yếu tố đang bật')]")) > 0
    
    if is_2fa_on_xpath or "two-factor authentication is on" in body_text or "is on" in body_text or "đang bật" in body_text:
         print("   [2FA] Detected: 2FA ALREADY ON. Stopping.")
         raise Exception("ALREADY_2FA_ON")

    # Keywords from image: "check your email", "enter the code"
    keywords = ["check your email", "enter the code", "nhập mã", "security code", "mã bảo mật"]
    
    is_checkpoint = False
    for kw in keywords:
        if kw in body_text:
            is_checkpoint = True
            break
            
    if is_checkpoint:
        print("   [2FA] Checkpoint Detected: Email verify required...")
        
        # 1. Open new tab to get code
        mail_code = get_code_from_mail(driver, email, email_pass)
        
        if not mail_code:
            raise Exception("Could not get mail code to bypass Checkpoint")
            
        # 2. Input code
        # In image: Placeholder="Code"
        try:
            # Find input
            inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='number']")
            entered = False
            for inp in inputs:
                if inp.is_displayed():
                    inp.clear()
                    inp.send_keys(mail_code)
                    entered = True
                    break
            
            if not entered:
                # Fallback JS
                driver.execute_script("document.querySelector('input').value = arguments[0]", mail_code)
                # Need trigger input event
                driver.execute_script(
                    "document.querySelector('input').dispatchEvent(new Event('input', { bubbles: true }));"
                )
        except Exception as e:
            print(f"   [2FA] Input error: {e}")

        time.sleep(2)
        
        # 3. Click Continue
        print("   [2FA] Clicking Continue...")
        if not wait_and_click(driver, By.XPATH, "//div[@role='button']//span[contains(text(), 'Continue') or contains(text(), 'Tiếp')]"):
            # Fallback
            try:
                driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            except:
                pass
                
        time.sleep(8) 
        _raise_if_change_not_allowed_yet(driver)
    # STEP 3: CHOOSE AUTHENTICATION APP
    print("   [2FA] Selecting 'Authentication App'...")
    # Find text "Authentication app"
    try:
        auth_option = driver.find_element(By.XPATH, "//*[contains(text(), 'Authentication app') or contains(text(), 'Ứng dụng xác thực')]")
        auth_option.click()
    except:
        # Maybe already selected
        pass

    time.sleep(1)
    # Click Continue
    wait_and_click(driver, By.XPATH, "//div[@role='button']//span[contains(text(), 'Continue') or contains(text(), 'Tiếp')]")
    time.sleep(5)
    _raise_if_change_not_allowed_yet(driver)

    # STEP 4: GET SECRET KEY
    print("   [2FA] Getting Secret Key...")
    
    # Click "Copy key"
    wait_and_click(driver, By.XPATH, "//*[contains(text(), 'Copy key') or contains(text(), 'Sao chép')]")
    
    # Scan text on screen
    # Key IG: long uppercase, space separated. Ex: PNQY UXXF ...
    full_text = driver.find_element(By.TAG_NAME, "body").text
    
    # Regex Base32: 
    match = re.search(r'([A-Z2-7]{4}\s){3,}[A-Z2-7]{4}', full_text)
    
    secret_key = ""
    if match:
        secret_key = match.group(0)
    else:
        # Try input value
        inputs = driver.find_elements(By.TAG_NAME, "input")
        for inp in inputs:
            val = inp.get_attribute("value")
            if val and len(val) > 20 and " " in val: # Key usually > 20 chars
                secret_key = val
                break
    
    if not secret_key:
        raise Exception("Secret Key not found on screen")

    print(f"   [2FA] Key found: {secret_key}")
    
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
                        print(f"   [2FA] Clicked {description}")
                        return True
            except: pass
        return False

    # --- CLICK NEXT (AFTER KEY) ---
    print("   [2FA] Clicking Next to enter OTP...")
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
         print("   [2FA] Warning: Next click fail (Robust). Trigger fallback...")
         wait_and_click(driver, By.XPATH, "//div[@role='button']//span[contains(text(), 'Next') or contains(text(), 'Tiếp')]")

    time.sleep(3)

    # STEP 5: GEN OTP AND CONFIRM
    # Clean Key
    clean_key = "".join(secret_key.split())
    # print(f"   [2FA] Clean Key: {clean_key}") # Debug
    
    # Gen OTP (Note: System Time)
    totp = pyotp.TOTP(clean_key, interval=30)
    otp_code = totp.now()
    
    print(f"   [2FA] OTP Code generated: {otp_code}")
    print("   [2FA] Note: If OTP fails, check System Time!")
    
    # --- NHẬP OTP (ROBUST) ---
    print(f"   [2FA] Đang nhập OTP: {otp_code}")
    entered_otp = False
    target_input = None
    
    # 0. STRATEGY AUTO-FOCUS + KEYBOARD ACTIONS (Strongest for IG Modal)
    try:
        # Potential selectors
        potential_selectors = [
            "input[maxlength='6']", 
            "input[placeholder='Enter code']", 
            "input[placeholder='Code']",
            "input[aria-label='Code']",
            "input[aria-label='Security Code']"
        ]
        
        # 1. Find best input
        for sel in potential_selectors:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in els:
                    if el.is_displayed():
                        target_input = el
                        print(f"   [2FA] Found input via selector: {sel}")
                        break
            except: pass
            if target_input: break
            
        # 2. User XPath (Dynamic ID handling)
        if not target_input:
             # Find input deep in div
             dialog_inputs = driver.find_elements(By.XPATH, "//div[@role='dialog']//input")
             for inp in dialog_inputs:
                 if inp.is_displayed():
                     target_input = inp
                     print("   [2FA] Found input in Dialog.")
                     break

        # 3. Focus & Type
        if target_input:
            # Click parent to focus
            try:
                driver.execute_script("arguments[0].parentElement.click();", target_input)
            except: pass
            
            # Click input
            try:
                target_input.click()
            except: 
                 driver.execute_script("arguments[0].click();", target_input)
            
            time.sleep(0.5)
            
            # Action chains send keys
            ActionChains(driver).send_keys(otp_code).perform()
            entered_otp = True
            print("   [2FA] Entered OTP (ActionChains Global).")
        else:
            print("   [2FA] Input not found, trying center click...")
            # Fallback
            
    except Exception as e:
        print(f"   [2FA] ActionChains error: {e}")

    # 1. Fallback Direct Input (SendKeys)
    if not entered_otp:
        try:
            # Find input maxlength=6
            candidates = driver.find_elements(By.CSS_SELECTOR, "input[maxlength='6']")
            for inp in candidates:
                if inp.is_displayed():
                    target_input = inp
                    print("   [2FA] Found OTP input (maxlength=6).")
                    break
            
            # If not found, find first visible input
            if not target_input:
                inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='number']")
                for inp in inputs:
                    if inp.is_displayed():
                        target_input = inp
                        print("   [2FA] Found OTP input (visible).")
                        break
                        
            if target_input:
                # Click focus
                try: target_input.click()
                except: pass
                time.sleep(0.2)
                
                # Clear & Send Keys
                target_input.clear()
                for digit in str(otp_code):
                    target_input.send_keys(digit)
                    time.sleep(0.05) 
                
                entered_otp = True
                print(f"   [2FA] Entered code {otp_code} (SendKeys).")
        except Exception as e:
            print(f"   [2FA] Normal input error: {e}")

    # 2. Fallback JS (React Safe)
    # Check value
    try:
        val = ""
        # Try getting value from active element
        active_el = driver.switch_to.active_element
        if active_el and active_el.tag_name == 'input':
             val = active_el.get_attribute("value")
        elif target_input: 
            val = target_input.get_attribute("value")
        
        # If not entered or empty value -> JS inject
        if not entered_otp or not val:
            print(f"   [2FA] Input value='{val}' -> Try JS Input (React Safe)...")
            
            # Script find input
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
            print("   [2FA] Executed JS OTP Input (React Pattern).")
            
    except Exception as e:
        print(f"   [2FA] JS Input error: {e}")

    time.sleep(1)


    # --- VERIFY OTP ENTRY BEFORE NEXT ---
    # Check OTP in input
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
        print("   [2FA] Warning: OTP value mismatch. Retrying...")
        # Retry logic here if needed (e.g. re-run JS)
        driver.execute_script(js_code, otp_code)
        time.sleep(1)
        is_filled = driver.execute_script(verify_js, otp_code)
        
    if not is_filled:
        raise Exception("OTP ENTRY FAILED: Input value mismatch.")
        
    print("   [2FA] Verify Input OK. Proceed to Next.")
    
    # Helper: Robust click
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
                        print(f"   [2FA] Clicked {description}")
                        return True
            except:
                pass
        return False

    # --- CLICK NEXT (CONFIRM OTP) ---
    print("   [2FA] Clicking Next to confirm OTP...")
    next_xpaths = [
        "//span[text()='Next']", 
        "//span[text()='Tiếp']",
        "//div[@role='button']//span[contains(text(), 'Next')]",
        "//div[@role='button']//span[contains(text(), 'Tiếp')]"
    ]
    
    robust_click(next_xpaths, "Next")
    
    # --- WAIT FOR 'DONE' (IMPORTANT) ---
    print("   [2FA] Waiting for OTP confirmation (Wait Done button)...")
    success_confirmed = False
    
    done_xpaths = [
        "//span[text()='Done']", 
        "//span[text()='Xong']",
        "//div[@role='button']//span[contains(text(), 'Done')]",
        "//div[@role='button']//span[contains(text(), 'Xong')]"
    ]

    for i in range(15): # Loop 15 times (15-20s)
        time.sleep(1.5)
        
        # 1. Check Instagram errors
        try:
            body_text_check = driver.find_element(By.TAG_NAME, "body").text.lower()
            if "code isn't right" in body_text_check or "mã không đúng" in body_text_check:
                raise Exception("WRONG OTP CODE (Instagram rejected).")
            if "please check the code" in body_text_check:
                raise Exception("WRONG OTP CODE (Please check the code).")
        except Exception as e:
            if "WRONG OTP CODE" in str(e): raise e

        # 2. Check Done button
        found_done = False
        for xpath in done_xpaths:
            if len(driver.find_elements(By.XPATH, xpath)) > 0:
                # Check displayed
                if any(e.is_displayed() for e in driver.find_elements(By.XPATH, xpath)):
                    found_done = True
                    break
        
        if found_done:
            success_confirmed = True
            print("   [2FA] => Done button found (OTP OK).")
            break
            
        # If not done, maybe Next click failed, retry Next
        if i % 3 == 0 and i > 0:
             print(f"   [2FA] Done not found, retrying Next {int(i/3)}...")
             robust_click(next_xpaths, "Next (Retry)")

    if not success_confirmed:
        raise Exception("TIMEOUT: Done button not found after OTP. OTP might be wrong or network lag.")

    # --- CLICK DONE (COMPLETE) ---
    print("   [2FA] Waiting 3s for 'Done' screen stability...")
    time.sleep(3) # Delay requested by user to avoid misclick during animation
    
    print("   [2FA] Clicking Done to finish...")
    clicked_done = robust_click(done_xpaths, "Done")
    
    if not clicked_done:
        # Fallback JS
        try:
            print("   [2FA] Click Done (Selenium) fail, trying JS...")
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
            print("   [2FA] Click Done (JS) success.")
        except Exception as e:
            print(f"   [2FA] Click Done (JS) failed: {e}")
            clicked_done = False
            
    if not clicked_done:
        raise Exception("CRITICAL ERROR: Could not click Done. 2FA not completed.")
    
    time.sleep(3)
    
    # Check again
    return secret_key