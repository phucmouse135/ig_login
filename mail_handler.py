# mail_handler.py
import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException

def wait_element(driver, by, value, timeout=10):
    """Hàm chờ element xuất hiện và trả về element đó"""
    # Manual wait (polling)
    steps = int(timeout / 0.5)
    for _ in range(steps):
        try:
            el = driver.find_element(by, value)
            if el.is_displayed():
                return el
        except: pass
        time.sleep(0.5)
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
    except TimeoutException:
        _stop_loading(driver)
        return False
    except WebDriverException:
        _stop_loading(driver)
        return False


def _safe_refresh(driver, timeout=20) -> bool:
    try:
        driver.set_page_load_timeout(timeout)
    except Exception:
        pass
    try:
        driver.refresh()
        return True
    except TimeoutException:
        _stop_loading(driver)
        return False
    except WebDriverException:
        _stop_loading(driver)
        return False


def _wait_dom_ready(driver, timeout=10, poll=0.5) -> bool:
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


def _find_rows_with_frame_search(driver, verbose=True):
    """Find table rows, try iframe if not found"""
    # 1. Try current context
    rows = driver.find_elements(By.XPATH, "//table[@id='mail-list']//tbody/tr")
    if verbose:
        print(f"   [Mail] Found {len(rows)} rows in main context.")
    if rows: return rows

    # 2. Try iframe
    frames = driver.find_elements(By.TAG_NAME, "iframe")
    for frame in frames:
        try:
            driver.switch_to.frame(frame)
            rows = driver.find_elements(By.XPATH, "//table[@id='mail-list']//tbody/tr")
                time.sleep(0.3)
                if verbose:
                    print(f"   [Mail] Found mail list in iframe!")
                return rows
            # If not found, try children frames (nested)
            # Revert to try next frame
            driver.switch_to.default_content() 
        except:
            driver.switch_to.default_content()
    
                time.sleep(0.3)

def _wait_for_mail_rows(driver, timeout=12):
    end_time = time.time() + timeout
    while time.time() < end_time:
        rows = _find_rows_with_frame_search(driver, verbose=False)
            poll = 0.3
            while time.time() < end_time:
            return rows
        time.sleep(0.5)
    return []


                time.sleep(0.3)
    msg = f" ({reason})" if reason else ""
    print(f"   [Mail] Page seems stuck{msg}. Attempting recovery...")
    _stop_loading(driver)
    time.sleep(1)
    if not _safe_refresh(driver):
        _safe_get(driver, "https://www.mail.com/")
    _wait_dom_ready(driver, timeout=8)


                time.sleep(0.3)
    rows = _wait_for_mail_rows(driver, timeout=4)
    if rows:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        return True

    def _try_login() -> bool:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
                time.sleep(0.3)
        login_btn = wait_element(driver, By.ID, "login-button", timeout=6)
        if login_btn:
            driver.execute_script("arguments[0].click();", login_btn)
            time.sleep(1)

        email_inp = wait_element(driver, By.ID, "login-email", timeout=6)
        pass_inp = wait_element(driver, By.ID, "login-password", timeout=6)
        if not email_inp or not pass_inp:
            return False

        try:
            email_inp.clear()
        except Exception:
            pass
        email_inp.send_keys(email)

        try:
            pass_inp.clear()
        except Exception:
            pass
        pass_inp.send_keys(password)

        time.sleep(1)
        try:
            driver.find_element(By.CSS_SELECTOR, ".login-submit").click()
        except Exception:
            pass_inp.send_keys(Keys.ENTER)

        print("   [Mail] Login clicked, waiting redirect...")
        _wait_dom_ready(driver, timeout=10)
        return True

    if not _try_login():
        _recover_from_hang(driver, "login form not ready")
        if not _try_login():
            print("   [Mail] Login form still not ready.")
            return False

    rows = _wait_for_mail_rows(driver, timeout=8)
    try:
        driver.switch_to.default_content()
    except Exception:
        pass
    if rows:
        return True

    if "login" in driver.current_url or "logout" in driver.current_url:
        print("   [Mail] Login FAILED.")
        return False
    return True

def _find_target_mail_row(driver, target_subject, rows=None):
    """
    New Algorithm:
    - Support IFRAME search.
    - Find mail without 'marked' class (Unread).
    - Check Sender/Subject has 'Instagram'.
    - Check Subject has 'Authenticate your account'.
    """
    try:
        # Smart search
        if rows is None:
            rows = _find_rows_with_frame_search(driver)
        print(f"   [Mail] Found {len(rows)} rows in Inbox.")
    except Exception as e:
        print(f"   [Mail] Error finding rows: {e}")
        return None

    if not rows:
        return None

    print(f"   [Mail] Scanning {len(rows)} rows in Inbox...")

    for idx, row in enumerate(rows):
        # 1. Skip Ad
        if row.find_elements(By.TAG_NAME, "th"):
            continue

        # 2. Check Unread only, skip read mails
        if not _row_is_unread(row):
            continue

        try:
            row_desc = _describe_row_brief(row)

            # Get Sender and Subject
            try:
                name_el = row.find_element(By.CSS_SELECTOR, "div.name")
                sender_txt = (name_el.text + " " + (name_el.get_attribute("title") or "")).lower()
            except: sender_txt = ""

            try:
                subj_el = row.find_element(By.CSS_SELECTOR, "span.subject")
                subj_txt = (subj_el.text + " " + (subj_el.get_attribute("title") or "")).lower()
            except: subj_txt = ""

            # 3. Check Condition
            is_instagram = "instagram" in sender_txt or "instagram" in subj_txt
            is_target_subj = (target_subject.lower() in subj_txt) if target_subject else True

            if is_instagram and is_target_subj:
                print(f"   [Mail] => FOUND MAIL (Row {idx}): {row_desc}")
                return row
            else:
                print(f"     [Row {idx}] Unread but logic mismatch: Instagram={is_instagram}, Subj='{target_subject}' -> {is_target_subj}")

        except Exception as e:
            print(f"     [Row {idx}] Error parse row: {e}")
            continue

    return None


def _row_is_unread(row) -> bool:
    """Kiểm tra mail chưa đọc dựa trên class 'marked' (User: có class marked = unread)"""
    try:
        el = row.find_element(By.CSS_SELECTOR, "a.mail-read-mark")
        # Nếu class CÓ chứa 'marked' -> Unread (Updated logic)
        return "marked" in (el.get_attribute("class") or "")
    except Exception:
        return False  # Không xác định được -> coi như False

                            time.sleep(0.3)
def _describe_row_brief(row) -> str:
    """Helper để in log thông tin dòng mail"""
    sender = "Unknown"
    subject = "Unknown"
    date_text = "Unknown"
    is_unread = "Unknown"
    
    try:
        sender = row.find_element(By.CSS_SELECTOR, "div.name").text.strip()
    except: pass
    try:
        subject = row.find_element(By.CSS_SELECTOR, "span.subject").text.strip()
    except: pass
    try:
        date_text = row.find_element(By.CSS_SELECTOR, "div.date").text.strip()
    except: pass
    try:
        is_unread = "Yes" if _row_is_unread(row) else "No"
    except: pass

    return f"[Sender: {sender} | Subj: {subject} | Time: {date_text} | Unread: {is_unread}]"


def _click_mail_row(driver, row) -> None:
    """Click vào mail để mở (tránh checkbox/star)"""
    try:
        # Scroll - sử dụng block 'nearest' để đỡ bị trượt quá đà
        driver.execute_script("arguments[0].scrollIntoView({block: 'nearest', inline: 'nearest'});", row)
        time.sleep(0.25)

        # Ưu tiên click vào phần tử chứa code hoặc subject
        target = None
        # 1. Ưu tiên thẻ chứa code (nếu có)
        try:
            target = row.find_element(By.XPATH, ".//*[contains(text(), 'code') or contains(text(), 'mã')]")
        except: pass
        # 2. Nếu không thấy, tìm thẻ subject cụ thể
        if not target:
            try:
                target = row.find_element(By.CSS_SELECTOR, "span.subject")
            except: pass
        # 3. Nếu không thấy, tìm td chứa subject
        if not target:
            try:
                target = row.find_element(By.CSS_SELECTOR, "td.subject")
            except: pass
        # 4. Fallback: Cell date
        if not target:
            try:
                target = row.find_element(By.CSS_SELECTOR, "div.date")
            except: pass
        # 5. Fallback cuối: Row
        if not target: target = row

        print(f"   [Mail] Target click: {target.tag_name} (Text: {target.text[:20]}...)")

        # Thực hiện click robust
        clicked = False
        try:
            driver.execute_script("arguments[0].click();", target)
            print("   [Mail] Click JS Done.")
            clicked = True
        except: pass
        if not clicked:
            try:
                target.click()
                print("   [Mail] Click Thường Done.")
            except:
                try:
                    ActionChains(driver).move_to_element(target).click().perform()
                    print("   [Mail] Click ActionChains Done.")
                except:
                    print("   [Mail] Click Fail All Methods.")
        time.sleep(0.25)
    except Exception as e:
        print(f"   [Mail] Warning click row: {e}")

def extract_instagram_code(text: str) -> str | None:
    # print("   [Mail] Đang cố gắng extract Instagram code từ nội dung mail...", text)
    if not text: return None
    
    # Check bypass marker
    if text.startswith("DIRECT_CODE:"):
        return text.split(":", 1)[1].strip()
    
    # 1. Regex HTML tag <font size="6"> (Rất chính xác)
    # User sample: <font size="6">65407089</font>
    m_html = re.search(r'size=["\']6["\'][^>]*>([\d\s]{6,9})</font>', text, re.IGNORECASE)
    if m_html:
        return m_html.group(1).replace(" ", "").strip()

    # 2. Regex Multiline trực tiếp trên raw text (Xử lý trường hợp code nằm dòng dưới)
    # Pattern: "confirm your identity" ... (xuống dòng/ký tự lạ) ... 65407089
    # cờ re.DOTALL cho phép dấu chấm (.) match cả newline
    raw_patterns = [
        r"confirm your identity.*?(\d{6,8})",
        r"security code.*?(\d{6,8})",
    ]
    for pat in raw_patterns:
        # Tìm trong khoảng ngắn < 150 ký tự sau keyword để tránh match sai số ở xa
        m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if m:
            code_candidate = m.group(1)
            # Kiểm tra độ dài match trung gian không quá dài
            if len(m.group(0)) < 150: 
                return code_candidate

    # 3. Regex dựa trên ngữ cảnh Clean Text (User cung cấp)
    # "If this was you, please use the following code to confirm your identity: 65407089"
    # Normalize: xóa tag, xóa xuống dòng thừa
    clean_text = re.sub(r'<[^>]+>', ' ', text)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    # Các pattern định danh chính xác (Có từ khóa ngữ cảnh)
    context_patterns = [
        r"confirm your identity[:\s\W]*([0-9]{6,8})",  
        r"security code[:\s\W]*([0-9]{6,8})",
        # "use the following code to confirm your identity 65407089"
        r"identity\s*(\d{6,8})", 
        # "code 65407089"
        r"code\s*(\d{6,8})",
    ]
    
    for pat in context_patterns:
        m = re.search(pat, clean_text, re.IGNORECASE)
        if m: return m.group(1)

    # 4. Fallback: CHỈ chấp nhận số 6-8 chữ số nếu nó nằm trong đoạn text ngắn liên quan đến Instagram 
    # (Không tìm "mù" toàn bộ văn bản nữa để tránh lấy nhầm số lạ)
    
    return None

# --- HÀM CHÍNH (INTERNAL) ---
def _get_code_from_mail_attempt(driver, email, password):
    original_window = driver.current_window_handle
    driver.execute_script("window.open('');")
    driver.switch_to.window(driver.window_handles[-1])
    
    print(f"   [Mail] Accessing: {email}...")
    
    try:
        if not _safe_get(driver, "https://www.mail.com/"):
            print("   [Mail] Initial load timeout, retrying...")
            _safe_get(driver, "https://www.mail.com/")
        _wait_dom_ready(driver, timeout=10)
        time.sleep(1)

        # 1. Popup Cookie
        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                try:
                    driver.switch_to.frame(iframe)
                    btns = driver.find_elements(By.XPATH, "//button[contains(text(), 'Agree') or contains(text(), 'Accept') or contains(text(), 'Zustimmen')]")
                    if btns:
                        driver.execute_script("arguments[0].click();", btns[0])
                        driver.switch_to.default_content(); break
                    driver.switch_to.default_content()
                except: driver.switch_to.default_content()
        except: pass

        # 2. Login
        print("   [Mail] Starting Login...")
        if not _ensure_logged_in(driver, email, password):
            return None

        # 4. Scan Mail
        print("   [Mail] Scanning Inbox (Finding first mail)...")
        target_subject = "Authenticate your account"

        for i in range(5):
            try:
                print(f"   [Mail] Scan # {i+1}...")
                driver.switch_to.default_content()
                
                # REFRESH PAGE LOGIC ROBUST
                if not _safe_refresh(driver):
                    print("   [Mail] Refresh timeout, trying recovery...")
                    _recover_from_hang(driver, "refresh timeout")
                _wait_dom_ready(driver, timeout=12)

                rows = _wait_for_mail_rows(driver, timeout=12)
                if not rows:
                    print("   [Mail] Inbox not ready, possible hang.")
                    _recover_from_hang(driver, "inbox not ready")
                    if not _ensure_logged_in(driver, email, password):
                        return None
                    continue

                # --- NEW LOGIC: FIND UNREAD MAIL ---
                target_row = _find_target_mail_row(driver, target_subject, rows=rows)

                if not target_row:
                    print(f"   [Mail] No suitable mail found (Unread + Subject '{target_subject}' + New) in this scan.")
                    continue

                # Click open
                _click_mail_row(driver, target_row)
                
                # Check opened
                print("   [Mail] Waiting for mail content...")


                # --- NEW LOGIC: RECURSIVE SEARCH ---
                def _attempt_extract_in_current_frame(drv):
                    # 1. Try Specific XPath
                    xpath_deep = '//*[@id="email_content"]/table/tbody/tr[4]/td/table/tbody/tr/td/table/tbody/tr[2]/td/table/tbody/tr/td/table/tbody/tr/td[2]/table/tbody/tr/td/p[4]'
                    try:
                        el = drv.find_element(By.XPATH, xpath_deep)
                        txt = el.text.strip()
                        raw = el.get_attribute("innerHTML")
                        code = extract_instagram_code(txt) or extract_instagram_code(raw)
                        if code: return code
                    except: pass
                    # 2. Try #email_content container
                    try:
                        div = drv.find_element(By.ID, "email_content")
                        code = extract_instagram_code(div.get_attribute("innerHTML"))
                        if code: return code
                    except: pass
                    # 3. Try Body scan (Fallback)
                    try:
                        body_txt = drv.find_element(By.TAG_NAME, "body").text
                        if "instagram" in body_txt.lower() or "confirm" in body_txt.lower():
                            body_html = drv.find_element(By.TAG_NAME, "body").get_attribute("innerHTML")
                            code = extract_instagram_code(body_html) or extract_instagram_code(body_txt)
                            if code: return code
                    except: pass
                    return None

                def _recursive_search_code(drv, depth=0):
                    found_code = _attempt_extract_in_current_frame(drv)
                    if found_code: return found_code
                    if depth < 4:
                        frames = drv.find_elements(By.TAG_NAME, "iframe")
                        for idx, f in enumerate(frames):
                            try:
                                drv.switch_to.frame(f)
                                res = _recursive_search_code(drv, depth + 1)
                                drv.switch_to.parent_frame()
                                if res:
                                    return res
                            except:
                                try: drv.switch_to.parent_frame()
                                except: pass
                    return None

                print("   [Mail] Starting Recursive Search...")
                final_code = None
                end_time = time.time() + 12
                while time.time() < end_time and not final_code:
                    try:
                        driver.switch_to.default_content()
                    except Exception:
                        pass
                    final_code = _recursive_search_code(driver)
                    if final_code:
                        break
                    time.sleep(0.25)

                if final_code:
                    print(f"   [Mail] -> FOUND CODE: {final_code}")
                    return final_code
                else:
                    print("   [Mail] Code not found after deep scan.")
                    _recover_from_hang(driver, "mail content not ready")

            except Exception as e:
                print(f"   [Mail] Loop Error: {e}")

        return None

    except Exception as e:
        print(f"   [Mail] Crash Error: {e}")
        return None

    finally:
        # Clean up tab mail
        if len(driver.window_handles) > 1:
            try:
                driver.close()
            except: pass
            
            try:
                driver.switch_to.window(original_window)
            except: pass

def get_code_from_mail(driver, email, password):
    """
    Wrapper: Retry full process (tab -> login -> get code) up to 3 times.
    """
    for attempt in range(1, 4):
        print(f"   [Mail] (Attempt {attempt}/3) Starting mail code retrieval...")
        try:
            code = _get_code_from_mail_attempt(driver, email, password)
            if code:
                return code
        except Exception as e:
            print(f"   [Mail] Exception at attempt {attempt}: {e}")
        
        if attempt < 3:
            print("   [Mail] Failed or error. Waiting 5s before retry...")
            time.sleep(5)
    
    print("   [Mail] => Failed after 3 attempts. No code retrieved.")
    return None
