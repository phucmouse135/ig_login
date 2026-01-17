# mail_handler.py
import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException

# --- OPTIMIZED UTILS ---
def wait_element(driver, by, value, timeout=10, poll=0.1):
    """Hàm chờ element xuất hiện và trả về element đó (Poll nhanh hơn)"""
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            el = driver.find_element(by, value)
            if el.is_displayed():
                return el
        except: pass
        time.sleep(poll) # Giảm từ 0.5 xuống 0.1
    return None

def _stop_loading(driver) -> None:
    try:
        driver.execute_script("window.stop();")
    except Exception:
        pass

def _safe_get(driver, url, timeout=20) -> bool:
    try:
        driver.set_page_load_timeout(timeout)
    except Exception:
        pass
    try:
        driver.get(url)
        return True
    except (TimeoutException, WebDriverException):
        _stop_loading(driver)
        return False

def _safe_refresh(driver, timeout=20) -> bool:
    try:
        driver.set_page_load_timeout(timeout)
        driver.refresh()
        return True
    except (TimeoutException, WebDriverException):
        _stop_loading(driver)
        return False

def _wait_dom_ready(driver, timeout=10, poll=0.1) -> bool:
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            if driver.execute_script("return document.readyState") == "complete":
                return True
        except Exception:
            pass
        time.sleep(poll)
    _stop_loading(driver)
    return False

def _find_rows_with_frame_search(driver, verbose=False):
    """Find table rows, try iframe if not found (Optimized Log)"""
    # 1. Try current context
    try:
        rows = driver.find_elements(By.XPATH, "//table[@id='mail-list']//tbody/tr")
        if rows: return rows
    except: pass

    # 2. Try iframe (Chỉ tìm iframe nếu main context không thấy)
    frames = driver.find_elements(By.TAG_NAME, "iframe")
    for frame in frames:
        try:
            driver.switch_to.frame(frame)
            rows = driver.find_elements(By.XPATH, "//table[@id='mail-list']//tbody/tr")
            if rows:
                if verbose: print(f"   [Mail] Found mail list in iframe!")
                return rows
            driver.switch_to.default_content() 
        except:
            driver.switch_to.default_content()
    
    return []

def _wait_for_mail_rows(driver, timeout=12):
    end_time = time.time() + timeout
    while time.time() < end_time:
        rows = _find_rows_with_frame_search(driver, verbose=False)
        if rows:
            return rows
        time.sleep(0.2) # Poll nhanh hơn (Cũ: 0.5)
    return []

def _recover_from_hang(driver, reason=""):
    msg = f" ({reason})" if reason else ""
    print(f"   [Mail] Page stuck{msg}. Recovering...")
    _stop_loading(driver)
    time.sleep(0.5)
    if not _safe_refresh(driver):
        _safe_get(driver, "https://www.mail.com/")
    _wait_dom_ready(driver, timeout=8)

def _ensure_logged_in(driver, email, password) -> bool:
    # Check nhanh xem có rows không trước khi check login form
    if _wait_for_mail_rows(driver, timeout=3):
        try: driver.switch_to.default_content()
        except: pass
        return True

    def _try_login() -> bool:
        try: driver.switch_to.default_content()
        except: pass

        # Tìm nhanh input
        email_inp = wait_element(driver, By.ID, "login-email", timeout=3)
        if not email_inp:
            # Check nút login button để mở form
            login_btn = wait_element(driver, By.ID, "login-button", timeout=2)
            if login_btn:
                driver.execute_script("arguments[0].click();", login_btn)
                time.sleep(0.5)
            email_inp = wait_element(driver, By.ID, "login-email", timeout=3)
        
        pass_inp = wait_element(driver, By.ID, "login-password", timeout=3)
        
        if not email_inp or not pass_inp:
            return False

        try: email_inp.clear()
        except: pass
        email_inp.send_keys(email)

        try: pass_inp.clear()
        except: pass
        pass_inp.send_keys(password)

        try:
            driver.find_element(By.CSS_SELECTOR, ".login-submit").click()
        except:
            pass_inp.send_keys(Keys.ENTER)

        print("   [Mail] Login submitted...")
        _wait_dom_ready(driver, timeout=10)
        return True

    if not _try_login():
        _recover_from_hang(driver, "login form missing")
        if not _try_login():
            return False

    if _wait_for_mail_rows(driver, timeout=8):
        try: driver.switch_to.default_content()
        except: pass
        return True

    return False

def _find_target_mail_row(driver, target_subject, rows=None):
    try:
        if rows is None:
            rows = _find_rows_with_frame_search(driver)
    except Exception:
        return None

    if not rows: return None
    
    # Duyệt ngược từ dưới lên (hoặc trên xuống tùy mail mới nhất ở đâu).
    # Thường mail mới nhất ở trên cùng -> giữ nguyên thứ tự enumerate
    # Tối ưu: Không in log từng dòng để tăng tốc
    
    target_subject_lower = target_subject.lower() if target_subject else ""

    for idx, row in enumerate(rows):
        # Skip header/Ads nhanh bằng tag name
        if row.tag_name == "th": continue

        try:
            # 1. Check Unread class trước (Nhanh hơn lấy text)
            try:
                # Tìm thẻ a có class mail-read-mark
                mark_el = row.find_element(By.CSS_SELECTOR, "a.mail-read-mark")
                cls = mark_el.get_attribute("class") or ""
                if "marked" not in cls: 
                    continue # Đã đọc -> Skip ngay
            except:
                continue

            # 2. Get Text Content (Nhanh hơn .text)
            row_text = row.get_attribute("textContent").lower()
            
            # 3. Check Condition (Instagram + Subject)
            if "instagram" in row_text and (not target_subject_lower or target_subject_lower in row_text):
                print(f"   [Mail] => FOUND TARGET ROW at index {idx}")
                return row

        except Exception:
            continue

    return None

def _click_mail_row(driver, row) -> None:
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'nearest', inline: 'nearest'});", row)
        time.sleep(0.2) # Giảm từ 1s xuống 0.2s
        
        # Ưu tiên click vào Subject (thường là thẻ span.subject hoặc div.subject)
        try:
            target = row.find_element(By.CSS_SELECTOR, "span.subject, div.subject, td.subject")
        except:
            target = row
        
        # JS Click (Nhanh và chính xác nhất)
        try:
            driver.execute_script("arguments[0].click();", target)
        except:
            try: target.click()
            except: pass
        
        time.sleep(0.5) # Chờ load content nhẹ

    except Exception as e:
        print(f"   [Mail] Click warning: {e}")

def extract_instagram_code(text: str) -> str | None:
    if not text: return None
    if text.startswith("DIRECT_CODE:"):
        return text.split(":", 1)[1].strip()
    
    # Regex optimizations (Compiled outside could be faster but this is negligible)
    # 1. HTML Font tag
    m_html = re.search(r'size=["\']6["\'][^>]*>([\d\s]{6,9})</font>', text, re.IGNORECASE)
    if m_html: return m_html.group(1).replace(" ", "").strip()

    # 2. Contextual Keywords (Faster than scanning full text with dots)
    clean_text = re.sub(r'<[^>]+>', ' ', text)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    patterns = [
        r"identity[:\s\W]*([0-9]{6,8})",  
        r"security code[:\s\W]*([0-9]{6,8})",
        r"code\s*(\d{6,8})",
        r"confirm your identity.*?(\d{6,8})"
    ]
    for pat in patterns:
        m = re.search(pat, clean_text, re.IGNORECASE)
        if m: return m.group(1)
        
    return None

def _get_code_from_mail_attempt(driver, email, password):
    # Setup Tab
    original_window = driver.current_window_handle
    driver.execute_script("window.open('');")
    driver.switch_to.window(driver.window_handles[-1])
    
    print(f"   [Mail] Checking: {email}...")
    
    try:
        if not _safe_get(driver, "https://www.mail.com/"):
            _safe_get(driver, "https://www.mail.com/")
        
        # Fast Cookie Consent Handling
        try:
            # Check iframes quickly
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            if len(iframes) > 0:
                for iframe in iframes:
                    # Skip kích thước nhỏ (ads) để tăng tốc
                    if iframe.size['height'] < 100: continue 
                    try:
                        driver.switch_to.frame(iframe)
                        btns = driver.find_elements(By.XPATH, "//button[contains(text(), 'Agree') or contains(text(), 'Accept') or contains(text(), 'Zustimmen')]")
                        if btns:
                            driver.execute_script("arguments[0].click();", btns[0])
                            driver.switch_to.default_content(); break
                        driver.switch_to.default_content()
                    except: driver.switch_to.default_content()
        except: pass

        if not _ensure_logged_in(driver, email, password):
            return None

        print("   [Mail] Scanning Inbox...")
        target_subject = "Authenticate your account"

        # Vòng lặp quét mail
        for i in range(5):
            try:
                driver.switch_to.default_content()
                if i > 0: # Chỉ refresh từ lần 2
                    if not _safe_refresh(driver):
                        _recover_from_hang(driver)
                
                rows = _wait_for_mail_rows(driver, timeout=8) # Giảm timeout
                if not rows:
                    if i == 0: _recover_from_hang(driver) # Chỉ recover nếu lần đầu fail
                    continue

                target_row = _find_target_mail_row(driver, target_subject, rows=rows)

                if not target_row:
                    print(f"   [Mail] Scan {i+1}: Mail not found yet.")
                    continue

                _click_mail_row(driver, target_row)
                
                # --- RECURSIVE SEARCH OPTIMIZED ---
                def _attempt_extract_in_current_frame(drv):
                    # Ưu tiên tìm trong ID #email_content trước (thường chứa nội dung chính)
                    try:
                        div = drv.find_element(By.ID, "email_content")
                        code = extract_instagram_code(div.get_attribute("innerHTML"))
                        if code: return code
                    except: pass
                    
                    # Fallback body
                    try:
                        body_html = drv.find_element(By.TAG_NAME, "body").get_attribute("innerHTML")
                        return extract_instagram_code(body_html)
                    except: pass
                    return None

                def _recursive_search_code(drv, depth=0):
                    # Check current
                    code = _attempt_extract_in_current_frame(drv)
                    if code: return code
                    
                    # Check children (Limit depth 3 is enough)
                    if depth < 3: 
                        frames = drv.find_elements(By.TAG_NAME, "iframe")
                        for f in frames:
                            try:
                                drv.switch_to.frame(f)
                                res = _recursive_search_code(drv, depth + 1)
                                if res:
                                    drv.switch_to.parent_frame()
                                    return res
                                drv.switch_to.parent_frame()
                            except:
                                try: drv.switch_to.parent_frame()
                                except: pass
                    return None

                # Loop wait code appearing (Polling 0.2s)
                final_code = None
                wait_code_end = time.time() + 10
                while time.time() < wait_code_end:
                    try: driver.switch_to.default_content()
                    except: pass
                    
                    final_code = _recursive_search_code(driver)
                    if final_code: break
                    time.sleep(0.2) # Fast poll

                if final_code:
                    print(f"   [Mail] -> CODE: {final_code}")
                    return final_code
                else:
                    print("   [Mail] Opened mail but code not found.")

            except Exception as e:
                print(f"   [Mail] Loop Error: {e}")

        return None

    except Exception as e:
        print(f"   [Mail] Error: {e}")
        return None

    finally:
        if len(driver.window_handles) > 1:
            try: driver.close()
            except: pass
            try: driver.switch_to.window(original_window)
            except: pass

def get_code_from_mail(driver, email, password):
    # Retry 3 lần
    for attempt in range(1, 4):
        code = _get_code_from_mail_attempt(driver, email, password)
        if code: return code
        if attempt < 3:
            time.sleep(2) # Giảm sleep retry xuống
    return None