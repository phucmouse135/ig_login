import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Lightweight helper similar to gmx_core.find_element_safe

def find_element_safe(driver, by, value, timeout=10, click=False, send_keys=None):
    try:
        el = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))
        if el and click:
            try:
                el.click()
            except:
                driver.execute_script("arguments[0].click();", el)
        if el and send_keys is not None:
            el.clear()
            el.send_keys(send_keys)
        return el
    except Exception:
        return None


# Adapted GMX login logic (accepts an existing driver)
def login_gmx(driver, user, password):
    """Attempt login on GMX using provided driver. Returns True on success."""
    try:
        print(f"--- START GMX LOGIN: {user} ---")
        # 1. Enter site
        driver.get("https://www.gmx.net/")
        time.sleep(2)
        driver.get("https://www.gmx.net/")
        time.sleep(1)

        # 2. Handle Consent (one trust)
        try:
            find_element_safe(driver, By.ID, "onetrust-accept-btn-handler", timeout=5, click=True)
        except: pass

        # 3. Try to find username input
        user_selectors = [
            (By.CSS_SELECTOR, "input[data-testid='input-email']"),
            (By.NAME, "username"),
            (By.ID, "username"),
            (By.CSS_SELECTOR, "input[type='email']"),
            (By.XPATH, "//input[@autocomplete='username']"),
        ]

        found = False
        for by, val in user_selectors:
            if find_element_safe(driver, by, val, timeout=2, send_keys=user):
                found = True
                break

        if not found:
            # Try look for iframe login
            frames = driver.find_elements(By.TAG_NAME, 'iframe')
            for f in frames:
                try:
                    driver.switch_to.frame(f)
                    for by, val in user_selectors:
                        if find_element_safe(driver, by, val, timeout=2, send_keys=user):
                            found = True
                            break
                    driver.switch_to.default_content()
                    if found: break
                except:
                    try: driver.switch_to.default_content()
                    except: pass

        if not found:
            print("❌ GMX login: username input not found")
            return False

        # Click Next / submit username if necessary
        # Try common buttons
        if not find_element_safe(driver, By.CSS_SELECTOR, "button[data-testid='login-submit']", timeout=2, click=True):
            find_element_safe(driver, By.CSS_SELECTOR, "button[type='submit']", timeout=2, click=True)

        time.sleep(1)

        # 7. Enter password
        pass_ok = False
        if find_element_safe(driver, By.CSS_SELECTOR, "input[data-testid='input-password']", timeout=5, send_keys=password):
            pass_ok = True
        elif find_element_safe(driver, By.ID, "password", send_keys=password):
            pass_ok = True
        elif find_element_safe(driver, By.NAME, "password", send_keys=password):
            pass_ok = True
        else:
            if find_element_safe(driver, By.XPATH, "//input[@type='password']", timeout=5, send_keys=password):
                pass_ok = True

        if not pass_ok:
            print("❌ GMX login: password input not found")
            return False

        # Click login final
        if not find_element_safe(driver, By.CSS_SELECTOR, "button[data-testid='login-submit']", timeout=3, click=True):
            find_element_safe(driver, By.CSS_SELECTOR, "button[type='submit']", timeout=3, click=True)

        time.sleep(5)

        # Check result - heuristics: URL change or presence of mailbox container
        cur = driver.current_url.lower()
        if 'mail' in cur or 'postfach' in cur:
            print("✅ GMX login likely successful (url contains mail/postfach)")
            return True

        # Try to detect mailbox area
        try:
            if driver.find_elements(By.CSS_SELECTOR, "div.mailbox"):
                return True
        except: pass

        # Fallback: check redirect to navigator like pattern
        for _ in range(6):
            if 'navigator' in driver.current_url:
                return True
            time.sleep(1)

        print("❌ GMX login: did not detect mailbox after login")
        return False

    except Exception as e:
        print(f"❌ GMX login error: {e}")
        return False
