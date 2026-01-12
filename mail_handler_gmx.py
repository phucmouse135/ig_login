# mail_handler_gmx.py
"""
Simple GMX mail handler: uses adapted GMX login from `step1_login.py` then
attempts to scan the page content for an Instagram code using the general
`extract_instagram_code` function from `mail_handler.py`.

This is intentionally conservative: GMX webmail DOM varies, so this implementation
provides a working integration point and a basic scanning fallback. You can
refine selectors later to target the GMX inbox table similar to `mail_handler.py`.
"""
import time
from selenium.webdriver.common.by import By
from step1_login import login_gmx
from mail_handler import extract_instagram_code


def get_code_from_gmx(driver, email, password):
    original_window = driver.current_window_handle
    driver.execute_script("window.open('');")
    driver.switch_to.window(driver.window_handles[-1])

    try:
        print(f"   [GMX] Starting GMX flow for {email}...")
        # Navigate to GMX and login using helper
        driver.get("https://www.gmx.net/")
        time.sleep(2)

        if not login_gmx(driver, email, password):
            print("   [GMX] Login failed")
            return None

        # After login, try to go to mailbox area
        try:
            # Common mailbox entry
            driver.get("https://www.gmx.net/")
        except: pass

        # Try scanning the page / refreshing and searching for code
        for attempt in range(6):
            try:
                time.sleep(3)
                # Refresh to pick up new messages
                try:
                    driver.refresh()
                except: pass
                time.sleep(3)

                body_html = driver.find_element(By.TAG_NAME, "body").get_attribute("innerHTML")
                body_text = driver.find_element(By.TAG_NAME, "body").text

                # Try HTML first
                code = extract_instagram_code(body_html)
                if not code:
                    code = extract_instagram_code(body_text)

                if code:
                    print(f"   [GMX] Found code: {code}")
                    return code

            except Exception as e:
                print(f"   [GMX] Scan attempt {attempt+1} error: {e}")
                continue

        print("   [GMX] Code not found after scanning attempts")
        return None

    finally:
        if len(driver.window_handles) > 1:
            driver.close()
            driver.switch_to.window(original_window)
