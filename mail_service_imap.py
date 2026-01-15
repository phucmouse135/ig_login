# mail_service_imap.py
import imaplib
import email
import re
import time
from email.header import decode_header

class MailServiceIMAP:
    def __init__(self, browser_manager=None):
        # browser_manager được giữ ở tham số để tương thích với code gọi cũ,
        # nhưng trong IMAP chúng ta không dùng Selenium driver.
        self.imap_server = "imap.mail.com"
        self.imap_port = 993

    def get_code(self, email_user, password):
        """
        Hàm chính: Kết nối IMAP -> Login -> Tìm mail -> Lấy code
        """
        mail = None
        try:
            print(f"   [IMAP] Connecting to {email_user}...")
            # 1. Kết nối đến Server
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            
            # 2. Login
            try:
                mail.login(email_user, password)
            except imaplib.IMAP4.error as e:
                print(f"   [IMAP] Login Failed: {e}")
                # Thường lỗi này do sai pass hoặc account Free bị chặn IMAP
                return None

            # 3. Chọn Inbox
            mail.select("inbox")

            # 4. Tìm kiếm mail (UNSEEN = Chưa đọc)
            # Tìm mail chưa đọc có tiêu đề chứa "Instagram" hoặc từ người gửi "Instagram"
            # Lưu ý: Mail.com search server side đôi khi không chuẩn, ta có thể search ALL UNSEEN rồi lọc
            status, messages = mail.search(None, '(UNSEEN)')
            
            if status != "OK":
                print("   [IMAP] No messages found.")
                return None

            # Lấy danh sách ID mail (đảo ngược để lấy mới nhất trước)
            mail_ids = messages[0].split()
            mail_ids = mail_ids[::-1] # Mới nhất lên đầu

            print(f"   [IMAP] Found {len(mail_ids)} unread mails. Scanning...")

            for num in mail_ids:
                # Fetch header và body
                _, msg_data = mail.fetch(num, "(RFC822)")
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Decode Subject
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else "utf-8", errors="ignore")
                
                # Decode Sender
                sender, encoding = decode_header(msg.get("From"))[0]
                if isinstance(sender, bytes):
                    sender = sender.decode(encoding if encoding else "utf-8", errors="ignore")

                # Filter: Chỉ xử lý nếu là mail từ Instagram
                if "instagram" in subject.lower() or "instagram" in sender.lower():
                    print(f"   [IMAP] Checking Mail: {subject}")
                    
                    # Lấy nội dung body
                    body = self._get_email_body(msg)
                    
                    # Extract code bằng Regex
                    code = self._extract_instagram_code(body)
                    
                    if code:
                        print(f"   [IMAP] => FOUND CODE: {code}")
                        return code
            
            print("   [IMAP] Code not found in unread mails.")
            return None

        except Exception as e:
            print(f"   [IMAP] Error: {e}")
            return None
        finally:
            # Đóng kết nối
            if mail:
                try:
                    mail.close()
                    mail.logout()
                except: pass

    def _get_email_body(self, msg):
        """Hàm helper để lấy nội dung text từ email object"""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                # Chỉ lấy text/plain hoặc text/html, bỏ qua attachment
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    return part.get_payload(decode=True).decode(errors="ignore")
                elif content_type == "text/html" and "attachment" not in content_disposition:
                     return part.get_payload(decode=True).decode(errors="ignore")
        else:
            return msg.get_payload(decode=True).decode(errors="ignore")
        return ""

    def _extract_instagram_code(self, text):
        """Dùng lại Logic Regex từ code cũ"""
        if not text: return None
        
        # 1. HTML Font Size pattern
        m_html = re.search(r'size=["\']6["\'][^>]*>([\d\s]{6,9})</font>', text, re.IGNORECASE)
        if m_html: return m_html.group(1).replace(" ", "").strip()

        # 2. Clean text & Regex Context
        clean = re.sub(r'<[^>]+>', ' ', text)
        clean = re.sub(r'\s+', ' ', clean).strip()
        
        patterns = [
            r"confirm your identity[:\s\W]*([0-9]{6,8})",
            r"security code[:\s\W]*([0-9]{6,8})",
            r"identity\s*(\d{6,8})",
            r"code\s*(\d{6,8})",
        ]
        for pat in patterns:
            m = re.search(pat, clean, re.IGNORECASE)
            if m: return m.group(1)
            
        return None