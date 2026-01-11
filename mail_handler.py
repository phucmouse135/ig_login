# mail_handler.py
import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def wait_element(driver, by, value, timeout=10):
    """Hàm chờ element xuất hiện và trả về element đó"""
    # Manual wait thay vì WebDriverWait
    steps = int(timeout / 0.5)
    for _ in range(steps):
        try:
            el = driver.find_element(by, value)
            if el.is_displayed():
                return el
        except: pass
        time.sleep(0.5)
    return None


def _find_rows_with_frame_search(driver):
    """Tìm table rows, nếu không thấy thì thử switch vào iframe"""
    # 1. Thử ở context hiện tại
    rows = driver.find_elements(By.XPATH, "//table[@id='mail-list']//tbody/tr")
    print(f"   [Mail] Tìm thấy {len(rows)} dòng mail ở context chính.")
    if rows: return rows

    # 2. Nếu không thấy, thử tìm iframe chứa mail-list
    frames = driver.find_elements(By.TAG_NAME, "iframe")
    for frame in frames:
        try:
            driver.switch_to.frame(frame)
            rows = driver.find_elements(By.XPATH, "//table[@id='mail-list']//tbody/tr")
            if rows:
                print(f"   [Mail] Found mail list in iframe!")
                return rows
            # Nếu không tìm thấy, thử tìm children frames (nested)
            # Tuy nhiên mail.com thường chỉ 1 level. 
            # Revert để thử frame tiếp theo
            driver.switch_to.default_content() 
        except:
            driver.switch_to.default_content()
    
    return []

def _find_target_mail_row(driver, target_subject):
    """
    Thuật toán mới (User Request):
    - Có hỗ trợ tìm trong IFRAME.
    - Tìm mail chưa có class 'marked' (Unread).
    - Check Sender/Subject có 'Instagram'.
    - Check Subject có 'Authenticate your account'.
    """
    try:
        # Sử dụng hàm tìm kiếm thông minh (có check iframe)
        rows = _find_rows_with_frame_search(driver)
        print(f"   [Mail] Tìm thấy {len(rows)} dòng mail trong Inbox.")
    except Exception as e:
        print(f"   [Mail] Error finding rows: {e}")
        return None

    if not rows:
        return None

    print(f"   [Mail] Đang duyệt {len(rows)} dòng trong Inbox (Bỏ qua TimeCheck)...")

    for idx, row in enumerate(rows):
        # 1. Bỏ qua Ad (Ad thường chứa thẻ 'th' hoặc iframe trực tiếp)
        if row.find_elements(By.TAG_NAME, "th"):
            continue

        try:
            row_desc = _describe_row_brief(row)

            # 2. Check Unread (Quan trọng nhất: Phải là mail chưa đọc - Không có class marked)
            if not _row_is_unread(row):
                # print(f"     [Row {idx}] Đã đọc -> Skip.")
                continue
            
            # Lấy thông tin Sender và Subject
            try:
                name_el = row.find_element(By.CSS_SELECTOR, "div.name")
                sender_txt = (name_el.text + " " + (name_el.get_attribute("title") or "")).lower()
            except: sender_txt = ""

            try:
                subj_el = row.find_element(By.CSS_SELECTOR, "span.subject")
                subj_txt = (subj_el.text + " " + (subj_el.get_attribute("title") or "")).lower()
            except: subj_txt = ""
            
            # 3. Check Condition: (Sender=Instagram OR Subject=Instagram) AND Subject="Authenticate your account"
            is_instagram = "instagram" in sender_txt or "instagram" in subj_txt
            is_target_subj = (target_subject.lower() in subj_txt) if target_subject else True
            
            if is_instagram and is_target_subj:
                print(f"   [Mail] => TÌM THẤY MAIL (Row {idx}): {row_desc}")
                return row
            else:
                 print(f"     [Row {idx}] Unread nhưng không khớp: Instagram={is_instagram}, Subj='{target_subject}' -> {is_target_subj}")

        except Exception as e:
            print(f"     [Row {idx}] Lỗi parse row: {e}")
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
        time.sleep(1)
        
        # Chiến thuật click mới: Cố gắng click vào phần Subject (an toàn nhất)
        # Nếu không có, click vào td chứa subject
        target = None
        
        # 1. Tìm thẻ subject cụ thể
        try:
            target = row.find_element(By.CSS_SELECTOR, "span.subject")
        except: pass
            
        # 2. Nếu không thấy, tìm td chứa subject
        if not target:
            try:
                target = row.find_element(By.CSS_SELECTOR, "td.subject")
            except: pass
            
        # 3. Fallback: Cell date
        if not target:
             try:
                target = row.find_element(By.CSS_SELECTOR, "div.date")
             except: pass
             
        # 4. Fallback cuối: Row
        if not target: target = row
        
        print(f"   [Mail] Target click: {target.tag_name} (Text: {target.text[:20]}...)")
        
        # Thực hiện click robust
        clicked = False
        
        # Thử JS Click first (Độ ổn định cao nhất cho mail client)
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
        
        time.sleep(1)

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

# --- HÀM CHÍNH ---
def get_code_from_mail(driver, email, password):
    original_window = driver.current_window_handle
    driver.execute_script("window.open('');")
    driver.switch_to.window(driver.window_handles[-1])
    
    print(f"   [Mail] Đang truy cập: {email}...")
    
    try:
        try:
            driver.get("https://www.mail.com/")
        except:
            driver.execute_script("window.stop();")
        
        time.sleep(3)

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
        print("   [Mail] Bắt đầu Login...")
        login_btn = wait_element(driver, By.ID, "login-button")
        if login_btn: driver.execute_script("arguments[0].click();", login_btn)
        
        time.sleep(1)
        wait_element(driver, By.ID, "login-email").send_keys(email)
        
        pass_inp = wait_element(driver, By.ID, "login-password")
        pass_inp.send_keys(password)
        
        time.sleep(1)
        try:
            driver.find_element(By.CSS_SELECTOR, ".login-submit").click()
        except:
            pass_inp.send_keys(Keys.ENTER)

        print("   [Mail] Đã nhấn Login, chờ chuyển hướng...")
        time.sleep(8)

        # 3. Check Login
        if "login" in driver.current_url or "logout" in driver.current_url:
            print("   [Mail] Login thất bại.")
            return None

        # 4. Quét Mail
        print("   [Mail] Đang quét Inbox (Tìm mail đầu tiên)...")
        target_subject = "Authenticate your account"

        for i in range(5):
            try:
                print(f"   [Mail] Lần quét {i+1}...")
                driver.switch_to.default_content()
                
                # REFRESH PAGE LOGIC ROBUST
                driver.refresh()
                # Chờ load xong
                try:
                    WebDriverWait(driver, 15).until(
                        lambda d: d.execute_script('return document.readyState') == 'complete'
                    )
                except: pass
                time.sleep(5) # Thêm thời gian chờ cứng để load AJAX mail list

                # --- LOGIC MỚI: DUYỆT TABLE TÌM UNREAD MAIL ---
                target_row = _find_target_mail_row(driver, target_subject)

                if not target_row:
                    print(f"   [Mail] Chưa thấy mail phù hợp (Unread + Subject '{target_subject}' + Mới) trong lần quét này.")
                    continue

                # Click mở mail
                _click_mail_row(driver, target_row)
                
                # Check xem đã mở mail chưa (Check xem list có bị ẩn hay nội dung có hiện lên chưa?)
                # Hoặc đơn giản là chờ lâu hơn chút
                print("   [Mail] Đang đợi nội dung mail load...")
                time.sleep(8) 

                # --- LOGIC MỚI: TÌM KIẾM ĐỆ QUY & TRÍCH XUẤT TRỰC TIẾP ---
                def _attempt_extract_in_current_frame(drv):
                    # 1. Thử XPath cụ thể user yêu cầu (Deep structure)
                    # Mục tiêu: P[4] chứa code
                    xpath_deep = '//*[@id="email_content"]/table/tbody/tr[4]/td/table/tbody/tr/td/table/tbody/tr[2]/td/table/tbody/tr/td/table/tbody/tr/td[2]/table/tbody/tr/td/p[4]'
                    try:
                        el = drv.find_element(By.XPATH, xpath_deep)
                        txt = el.text.strip()
                        raw = el.get_attribute("innerHTML")
                        # print(f"     [Debug] Found Deep XPath P4: Text='{txt}'")
                        code = extract_instagram_code(txt) or extract_instagram_code(raw)
                        if code: return code
                    except: pass

                    # 2. Thử #email_content container
                    try:
                        div = drv.find_element(By.ID, "email_content")
                        code = extract_instagram_code(div.get_attribute("innerHTML"))
                        if code: return code
                    except: pass

                    # 3. Thử quét toàn bộ Body (Fallback)
                    try:
                        body_txt = drv.find_element(By.TAG_NAME, "body").text
                        # Chỉ check nếu có keywords Instagram
                        if "instagram" in body_txt.lower() or "confirm" in body_txt.lower():
                            body_html = drv.find_element(By.TAG_NAME, "body").get_attribute("innerHTML")
                            code = extract_instagram_code(body_html) # Ưu tiên HTML
                            if not code: code = extract_instagram_code(body_txt)
                            if code: return code
                    except: pass
                    
                    return None

                def _recursive_search_code(drv, depth=0):
                    # 1. Check frame hiện tại
                    found_code = _attempt_extract_in_current_frame(drv)
                    if found_code: return found_code
                    
                    # 2. Check iframes con
                    if depth < 4: # Max depth 4
                        frames = drv.find_elements(By.TAG_NAME, "iframe")
                        # print(f"     [Debug] Depth {depth}: Found {len(frames)} iframes.")
                        for idx, f in enumerate(frames):
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

                print("   [Mail] Bắt đầu quét nội dung đệ quy (Recursive Search)...")
                final_code = _recursive_search_code(driver)
                
                if final_code:
                    print(f"   [Mail] -> TÌM THẤY CODE: {final_code}")
                    return final_code
                else:
                    print("   [Mail] Không tìm thấy code sau khi quét sâu các iframe.")

            except Exception as e:
                print(f"   [Mail] Lỗi vòng lặp: {e}")

        return None

    except Exception as e:
        print(f"   [Mail] Crash lỗi: {e}")
        return None

    finally:
        if len(driver.window_handles) > 1:
            driver.close()
            driver.switch_to.window(original_window)