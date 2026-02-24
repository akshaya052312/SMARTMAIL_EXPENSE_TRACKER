# email_processor.py
import imaplib
import email
from email.header import decode_header
import re
from datetime import datetime, timedelta
import time


# ============ SPAM / PROMOTIONAL EMAIL FILTERS ============

# Blocked sender patterns — marketing, promotional, newsletter senders
BLOCKED_SENDER_PATTERNS = [
    r'@campaigns\.', r'@marketing\.', r'@promo\.', r'@newsletter\.',
    r'@mailer\.', r'@offers\.', r'@deals\.', r'@info\.', r'@news\.',
    r'@notifications\.zomato\.com', r'@notifications\.swiggy\.com',
    r'noreply.*sale', r'noreply.*offer', r'noreply.*deal',
    r'@engage\.', r'@bulk\.', r'@mass\.', r'@blast\.',
    r'@promotions\.', r'@updates\.', r'@digest\.',
    r'@email\.mg\.', r'@sendgrid\.', r'@mailchimp\.',
    r'@exacttarget\.', r'@emarsys\.', r'@moengage\.',
    r'@clevertap\.', r'@webengage\.', r'@netcore\.',
]

# Trusted sender patterns — known transaction/receipt senders
TRUSTED_SENDER_PATTERNS = [
    # Banks — India
    r'alerts@hdfcbank\.net', r'alerts@icicibank\.com', r'alerts@sbi\.co\.in',
    r'alerts@axisbank\.com', r'alerts@kotak\.com', r'alerts@idfcfirstbank\.com',
    r'alerts@yesbank\.in', r'donotreply@indusind\.com',
    # E-commerce — receipts/order confirmation
    r'auto-confirm@amazon\.in', r'order-update@amazon\.in', r'ship-confirm@amazon\.in',
    r'noreply@flipkart\.com', r'no-reply@flipkart\.com',
    r'noreply@myntra\.com', r'noreply@ajio\.com', r'noreply@meesho\.com',
    r'noreply@tatacliq\.com', r'noreply@nykaa\.com',
    # Food delivery
    r'no-reply@swiggy\.in', r'noreply@zomato\.com',
    r'orders@swiggy\.in', r'orders@zomato\.com',
    r'receipts@uber\.com', r'noreply@dunzo\.com',
    # Travel
    r'noreply@irctc\.co\.in', r'ticket@irctc\.co\.in',
    r'booking@makemytrip\.com', r'noreply@goibibo\.com',
    r'noreply@redbus\.in', r'noreply@cleartrip\.com',
    r'noreply@ola\.money', r'receipts@uber\.com',
    # Payments / UPI
    r'noreply@paytm\.com', r'noreply@phonepe\.com',
    r'noreply@razorpay\.com', r'noreply@payu\.in',
    r'alerts@cred\.club',
    # Utilities
    r'noreply@jio\.com', r'noreply@airtel\.in',
    r'noreply@tatapowerdel\.com',
    # Entertainment
    r'noreply@netflix\.com', r'noreply@hotstar\.com',
    r'noreply@bookmyshow\.com', r'noreply@spotify\.com',
    # Groceries
    r'noreply@bigbasket\.com', r'noreply@blinkit\.com',
    r'noreply@zepto\.co', r'no-reply@grofers\.com',
]

# Subject keywords that indicate SPAM/promotional emails (case-insensitive)
SPAM_SUBJECT_KEYWORDS = [
    'sale', 'offer', '% off', 'discount', 'deal of', 'deals',
    'coupon', 'cashback offer', 'subscribe', 'newsletter',
    'exclusive offer', 'limited time', 'flash sale', 'mega sale',
    'festival offer', 'diwali sale', 'holi offer', 'republic day sale',
    'independence day', 'big billion', 'great indian',
    'unsubscribe', 'weekly digest', 'daily digest',
    'recommended for you', 'you might like', 'trending',
    'new arrivals', 'just launched', 'coming soon', 'pre-order',
    'earn rewards', 'refer and earn', 'invite friends',
    'survey', 'feedback request', 'rate your', 'review your',
    'wishlist', 'price drop', 'back in stock',
    'free shipping', 'free delivery', 'buy 1 get',
    'top picks', 'best sellers', 'don\'t miss',
    'last chance', 'hurry', 'limited stock',
    'win big', 'congratulations', 'jackpot', 'lucky winner',
    'claim your', 'act now', 'only today', 'expires soon',
    'shop now', 'grab now', 'buy now', 'order now',
    'biggest sale', 'clearance', 'warehouse sale',
    'summer sale', 'winter sale', 'end of season',
    'loyalty points', 'reward points', 'bonus points',
    'special promotion', 'promo code', 'voucher',
]

# Body keywords that strongly indicate SPAM/promotional content
SPAM_BODY_KEYWORDS = [
    'unsubscribe', 'opt-out', 'opt out', 'click here to unsubscribe',
    'manage your preferences', 'email preferences', 'manage subscriptions',
    'you are receiving this', 'you received this email because',
    'if you no longer wish', 'to stop receiving',
    'view in browser', 'view this email in your browser',
    'add us to your address book', 'add to contacts',
    'this is a promotional', 'this is an advertisement',
    'terms and conditions apply', 't&c apply', '*t&c',
    'shop the collection', 'explore now', 'browse collection',
    'curated for you', 'handpicked for you', 'just for you',
    'we thought you', 'you may also like', 'customers also bought',
    'use code', 'apply code', 'coupon code', 'promo code',
    'flat ₹', 'flat rs', 'upto ₹', 'upto rs', 'up to ₹', 'up to rs',
    'minimum order', 'no minimum', 'above ₹', 'above rs',
    'download the app', 'install our app', 'get the app',
    'follow us on', 'like us on', 'join us on',
    'share with friends', 'tell a friend', 'spread the word',
]

# Subject keywords that indicate a REAL transaction/expense email
TRANSACTION_SUBJECT_KEYWORDS = [
    'payment', 'receipt', 'invoice', 'bill',
    'debited', 'credited', 'debit', 'transaction',
    'order confirmed', 'order confirmation', 'booking confirmed',
    'booking confirmation', 'purchase', 'paid',
    'payment successful', 'payment received', 'payment confirmation',
    'your order', 'order details', 'order placed',
    'e-ticket', 'ticket confirmed', 'ticket booked',
    'statement', 'emi', 'installment', 'due',
    'subscription renewed', 'subscription charged',
    'recharge successful', 'recharge done',
    'delivery', 'shipped', 'dispatched',
    'refund', 'reversal', 'chargeback',
    'otp',  # Sometimes transaction alerts contain OTP context
    'upi', 'neft', 'imps', 'rtgs',
    'auto-debit', 'auto debit', 'mandate',
    'renewal', 'charged',
]

# Body keywords that strongly suggest a real transaction
TRANSACTION_BODY_KEYWORDS = [
    'amount debited', 'amount credited', 'total amount',
    'transaction id', 'order id', 'booking id', 'reference number',
    'payment of', 'paid ₹', 'paid rs', 'paid inr',
    '₹', 'rs.', 'inr ',
    'upi ref', 'upi id', 'imps ref',
    'card ending', 'account ending', 'a/c',
    'invoice number', 'bill number', 'receipt number',
    'gst', 'cgst', 'sgst', 'igst',
    'net amount', 'grand total', 'subtotal',
    'available balance', 'closing balance',
]


def is_blocked_sender(sender_email):
    """Check if sender matches blocked patterns"""
    sender_lower = sender_email.lower()
    for pattern in BLOCKED_SENDER_PATTERNS:
        if re.search(pattern, sender_lower):
            return True
    return False


def is_trusted_sender(sender_email):
    """Check if sender matches trusted patterns"""
    sender_lower = sender_email.lower()
    for pattern in TRUSTED_SENDER_PATTERNS:
        if re.search(pattern, sender_lower):
            return True
    return False


def has_spam_subject(subject):
    """Check if subject contains spam/promotional keywords"""
    subject_lower = subject.lower()
    spam_count = 0
    for keyword in SPAM_SUBJECT_KEYWORDS:
        if keyword in subject_lower:
            spam_count += 1
    return spam_count >= 1


def has_spam_body(body):
    """Check if email body contains spam/promotional indicators"""
    body_lower = body.lower()
    spam_count = 0
    for keyword in SPAM_BODY_KEYWORDS:
        if keyword in body_lower:
            spam_count += 1
    # If 3 or more spam body indicators found, it's likely promotional
    return spam_count >= 3


def has_transaction_indicators(subject, body):
    """Check if email has transaction-related keywords"""
    text_lower = (subject + ' ' + body).lower()

    subject_lower = subject.lower()
    subject_hits = sum(1 for kw in TRANSACTION_SUBJECT_KEYWORDS if kw in subject_lower)

    body_lower = body.lower()
    body_hits = sum(1 for kw in TRANSACTION_BODY_KEYWORDS if kw in body_lower)

    return subject_hits, body_hits


def calculate_confidence(sender, subject, body, amount, merchant):
    """Calculate confidence score (0-100) for an extracted expense"""
    score = 0

    # Trusted sender: +30
    if is_trusted_sender(sender):
        score += 30

    # Blocked sender: -50
    if is_blocked_sender(sender):
        score -= 50

    # Transaction subject keywords: up to +25
    subject_hits, body_hits = has_transaction_indicators(subject, body)
    score += min(subject_hits * 10, 25)

    # Transaction body keywords: up to +25
    score += min(body_hits * 5, 25)

    # Spam subject keywords penalty: -15 each (max -30)
    subject_lower = subject.lower()
    spam_hits = sum(1 for kw in SPAM_SUBJECT_KEYWORDS if kw in subject_lower)
    score -= min(spam_hits * 15, 30)

    # Amount found with ₹/Rs/INR pattern: +10
    text = subject + ' ' + body
    if re.search(r'[₹]|Rs\.?|INR', text, re.IGNORECASE):
        score += 10

    # Known merchant detected: +10
    if merchant and merchant != 'Unknown Merchant':
        score += 10

    # Clamp to 0-100
    return max(0, min(100, score))


class EmailProcessor:
    def __init__(self, imap_server, imap_port, username, password):
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.username = username
        self.password = password
        self.mail = None
        self.connected = False

    def connect(self):
        """Connect to IMAP server"""
        try:
            self.mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.mail.login(self.username, self.password)
            self.connected = True
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    def disconnect(self):
        """Disconnect from IMAP server"""
        if self.mail:
            try:
                self.mail.logout()
            except:
                pass
        self.connected = False

    def is_connected(self):
        """Check if still connected"""
        if not self.connected or not self.mail:
            return False

        try:
            self.mail.noop()
            return True
        except:
            self.connected = False
            return False

    def get_unread_emails_fast(self, limit=10):
        """Get unread emails quickly with spam filtering"""
        try:
            if not self.is_connected():
                if not self.connect():
                    return []

            self.mail.select("inbox")

            date_since = (datetime.now() - timedelta(days=2)).strftime("%d-%b-%Y")

            status, messages = self.mail.search(None, f'(UNSEEN SINCE "{date_since}")')

            if status != "OK":
                return []

            email_ids = messages[0].split()

            # Fetch more than limit to account for filtered-out spam
            fetch_limit = min(len(email_ids), limit * 3)
            if fetch_limit > 0:
                email_ids = email_ids[:fetch_limit]

            emails = []

            for email_id in email_ids:
                if len(emails) >= limit:
                    break

                try:
                    status, msg_data = self.mail.fetch(email_id, "(BODY.PEEK[])")

                    if status != "OK":
                        continue

                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    subject = self._decode_header_fast(msg.get("Subject", ""))
                    sender = msg.get("From", "")
                    date_str = msg.get("Date", "")
                    email_date = self.parse_email_date_fast(date_str)

                    # ========== SPAM FILTERING ==========

                    # 1. Block known spam/promotional senders
                    if is_blocked_sender(sender):
                        continue

                    # 2. Check if subject is purely promotional
                    if has_spam_subject(subject):
                        # Allow if sender is trusted (e.g., Flipkart order + promo in subject)
                        if not is_trusted_sender(sender):
                            continue

                    # 3. Get body for deeper analysis
                    body = self.get_email_body_fast(msg, max_chars=3000)

                    # 3.5 Check for spam body content (unsubscribe links, promo patterns)
                    if has_spam_body(body):
                        if not is_trusted_sender(sender):
                            continue

                    # 4. Check for transaction indicators
                    subj_hits, body_hits = has_transaction_indicators(subject, body)

                    # If NO transaction indicators at all, skip
                    if subj_hits == 0 and body_hits == 0:
                        # Allow trusted senders even without keywords
                        if not is_trusted_sender(sender):
                            continue

                    # Passed all filters — include this email
                    emails.append({
                        'id': email_id.decode(),
                        'message_id': msg.get('Message-ID', ''),
                        'subject': subject,
                        'sender': sender,
                        'date': email_date,
                        'body': body,
                        'raw': raw_email.decode('utf-8', errors='ignore')[:5000]
                    })

                except Exception as e:
                    print(f"Error processing email {email_id}: {e}")
                    continue

            return emails

        except Exception as e:
            print(f"Error fetching emails: {e}")
            self.connected = False
            return []

    def get_unread_emails(self, days=3):
        """Get unread emails (full version)"""
        return self.get_unread_emails_fast(limit=20)

    def _decode_header_fast(self, header):
        """Fast header decoding"""
        try:
            decoded_parts = decode_header(header)
            decoded_str = ""

            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_str += part.decode(encoding)
                    else:
                        decoded_str += part.decode('utf-8', errors='ignore')
                else:
                    decoded_str += str(part)

            return decoded_str
        except:
            return str(header)

    def get_email_body_fast(self, msg, max_chars=3000):
        """Extract email body text (fast version)"""
        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')[:max_chars]
                        break
                    except:
                        try:
                            body = str(part.get_payload(decode=True))[:max_chars]
                            break
                        except:
                            pass
        else:
            try:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')[:max_chars]
            except:
                body = str(msg.get_payload(decode=True))[:max_chars]

        return body

    def parse_email_date_fast(self, date_str):
        """Parse email date string quickly — supports Indian DD/MM/YYYY formats"""
        try:
            # Standard email date formats
            for fmt in [
                "%a, %d %b %Y %H:%M:%S %z",
                "%d %b %Y %H:%M:%S %z",
                "%a, %d %b %Y %H:%M:%S",
                "%d %b %Y %H:%M:%S",
            ]:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except:
                    continue

            # Indian DD/MM/YYYY formats
            for fmt in [
                "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y %H:%M",
                "%d/%m/%Y",
                "%d-%m-%Y %H:%M:%S",
                "%d-%m-%Y",
            ]:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except:
                    continue

            return datetime.now()
        except:
            return datetime.now()

    def extract_expense_data_fast(self, email_data):
        """Fast expense extraction with Indian context + confidence scoring"""
        subject = email_data['subject']
        body = email_data['body']
        sender = email_data.get('sender', '')

        text = f"{subject}\n{body}"

        # Extract amount in ₹
        amount = self._extract_amount_fast(text)
        if not amount:
            return None

        # Extract merchant (Indian merchants first)
        merchant = self._extract_merchant_fast(text, sender)

        # Determine category (Indian context)
        category = self._determine_category_fast(text)

        # Detect payment method
        payment_method = self._detect_payment_method(text)

        # Extract GST if present
        gst_amount = self._extract_gst(text)

        # Extract transaction ID
        transaction_id = self._extract_transaction_id(text)

        # Calculate confidence score
        confidence = calculate_confidence(sender, subject, body, amount, merchant)

        # Skip low confidence extractions (likely spam that passed filters)
        if confidence < 35:
            return None

        return {
            'amount': amount,
            'currency': 'INR',
            'merchant': merchant,
            'category': category,
            'payment_method': payment_method,
            'gst_amount': gst_amount,
            'transaction_id': transaction_id,
            'confidence': confidence,
            'description': f"Email: {subject[:50]}..." if len(subject) > 50 else f"Email: {subject}",
            'date': email_data['date'],
            'source': 'email',
            'email_data': {
                'subject': subject[:100],
                'sender': sender[:100],
                'date': email_data['date'].isoformat() if hasattr(email_data['date'], 'isoformat') else str(email_data['date'])
            }
        }

    def extract_expense_data(self, email_data):
        """Extract expense information from email"""
        return self.extract_expense_data_fast(email_data)

    def _extract_amount_fast(self, text):
        """Extract amount — prioritizes ₹/Rs/INR patterns, then falls back to generic"""
        # Indian currency patterns (highest priority)
        indian_patterns = [
            r'₹\s*([\d,]+\.?\d*)',                    # ₹1,234.56 or ₹ 1,234
            r'Rs\.?\s*([\d,]+\.?\d*)',                 # Rs.1234 or Rs 1,234.56
            r'INR\s*([\d,]+\.?\d*)',                   # INR 1234.56
            r'Rupees?\s*([\d,]+\.?\d*)',                # Rupee 1234
            r'(?:amount|total|paid|charged|debited|credited)\s*(?::|is|of|for)?\s*(?:₹|Rs\.?|INR)?\s*([\d,]+\.?\d*)',
        ]

        text_content = text

        for pattern in indian_patterns:
            try:
                matches = re.findall(pattern, text_content, re.IGNORECASE)
                if matches:
                    amounts = []
                    for m in matches:
                        cleaned = m.replace(',', '')
                        try:
                            val = float(cleaned)
                            if 1 <= val <= 10000000:  # ₹1 to ₹1Cr reasonable range
                                amounts.append(val)
                        except:
                            continue
                    if amounts:
                        return max(amounts)
            except:
                continue

        # Generic USD fallback patterns
        fallback_patterns = [
            r'\$([\d,]+\.?\d*)',
            r'USD\s*([\d,]+\.?\d*)',
            r'\b(\d+\.\d{2})\b',
        ]

        text_lower = text.lower()
        for pattern in fallback_patterns:
            try:
                matches = re.findall(pattern, text_lower)
                if matches:
                    amounts = [float(m.replace(',', '')) for m in matches if float(m.replace(',', '')) >= 1]
                    return max(amounts) if amounts else None
            except:
                continue

        return None

    def _extract_merchant_fast(self, text, sender=""):
        """Extract merchant name — Indian merchants prioritized"""
        # Indian merchant mapping
        merchant_map = {
            # E-commerce
            'flipkart': 'Flipkart',
            'myntra': 'Myntra',
            'ajio': 'AJIO',
            'meesho': 'Meesho',
            'snapdeal': 'Snapdeal',
            'nykaa': 'Nykaa',
            'tatacliq': 'Tata CLiQ',
            'jiomart': 'JioMart',
            'amazon': 'Amazon India',

            # Food delivery
            'zomato': 'Zomato',
            'swiggy': 'Swiggy',
            'eatsure': 'EatSure',
            'dominos': "Domino's",
            'dunzo': 'Dunzo',

            # Travel
            'irctc': 'IRCTC',
            'makemytrip': 'MakeMyTrip',
            'goibibo': 'Goibibo',
            'cleartrip': 'Cleartrip',
            'yatra': 'Yatra',
            'ola': 'Ola',
            'uber': 'Uber India',
            'rapido': 'Rapido',
            'redbus': 'RedBus',
            'ixigo': 'ixigo',

            # Groceries
            'bigbasket': 'BigBasket',
            'blinkit': 'Blinkit',
            'grofers': 'Grofers',
            'zepto': 'Zepto',
            'dmart': 'DMart',
            'instamart': 'Swiggy Instamart',

            # Entertainment
            'netflix': 'Netflix',
            'hotstar': 'Disney+ Hotstar',
            'primevideo': 'Amazon Prime Video',
            'prime video': 'Amazon Prime Video',
            'bookmyshow': 'BookMyShow',
            'spotify': 'Spotify',
            'jiocinema': 'JioCinema',
            'sonyliv': 'SonyLIV',
            'zee5': 'ZEE5',

            # Payments / UPI
            'paytm': 'Paytm',
            'phonepe': 'PhonePe',
            'googlepay': 'Google Pay',
            'google pay': 'Google Pay',
            'razorpay': 'Razorpay',
            'payu': 'PayU',
            'ccavenue': 'CCAvenue',
            'bharatpe': 'BharatPe',

            # Banking
            'hdfc': 'HDFC Bank',
            'icici': 'ICICI Bank',
            'sbi': 'SBI',
            'axis': 'Axis Bank',
            'kotak': 'Kotak Mahindra',
            'idfc': 'IDFC First',

            # Utilities / Telecom
            'jio': 'Jio',
            'airtel': 'Airtel',
            'vodafone': 'Vodafone Idea',
            'bsnl': 'BSNL',
            'tatapower': 'Tata Power',
            'adani': 'Adani',

            # Healthcare
            'practo': 'Practo',
            '1mg': '1mg',
            'pharmeasy': 'PharmEasy',
            'netmeds': 'Netmeds',
            'apollo': 'Apollo',

            # Education
            'unacademy': 'Unacademy',
            'byju': "BYJU'S",
            'udemy': 'Udemy',
            'coursera': 'Coursera',
            'upgrad': 'upGrad',

            # International (kept for compatibility)
            'walmart': 'Walmart',
            'starbucks': 'Starbucks',
            'mcdonalds': "McDonald's",
        }

        text_lower = text.lower()
        sender_lower = sender.lower()

        # Check text first
        for keyword, merchant in merchant_map.items():
            if keyword in text_lower or keyword in sender_lower:
                return merchant

        # Try to extract from subject/body
        lines = text.split('\n')
        for line in lines[:5]:
            line_lower = line.lower()
            for keyword, merchant in merchant_map.items():
                if keyword in line_lower:
                    return merchant

        return 'Unknown Merchant'

    def _determine_category_fast(self, text):
        """Fast category determination — Indian expense categories"""
        text_lower = text.lower()

        categories = {
            'Food Delivery': [
                'zomato', 'swiggy', 'eatsure', 'dunzo', 'food order',
                'food delivery', 'dominos', 'pizza hut', 'kfc', 'burger king',
                'restaurant', 'cafe', 'dining', 'biryani', 'thali'
            ],
            'Groceries': [
                'bigbasket', 'blinkit', 'grofers', 'zepto', 'dmart',
                'instamart', 'grocery', 'supermarket', 'vegetables',
                'fruits', 'milk', 'ration', 'kirana'
            ],
            'Online Shopping': [
                'flipkart', 'amazon', 'myntra', 'ajio', 'meesho',
                'snapdeal', 'nykaa', 'tatacliq', 'jiomart', 'shopping',
                'order confirmed', 'shipment', 'delivered', 'purchase'
            ],
            'Travel & Transport': [
                'irctc', 'makemytrip', 'goibibo', 'cleartrip', 'yatra',
                'ola', 'uber', 'rapido', 'redbus', 'ixigo', 'flight',
                'train', 'bus', 'cab', 'taxi', 'booking', 'ticket',
                'airline', 'indigo', 'spicejet', 'air india', 'vistara'
            ],
            'Entertainment': [
                'netflix', 'hotstar', 'prime video', 'bookmyshow',
                'spotify', 'jiocinema', 'sonyliv', 'zee5', 'movie',
                'cinema', 'concert', 'game', 'streaming', 'subscription'
            ],
            'Utilities & Bills': [
                'electricity', 'water', 'gas', 'internet', 'phone',
                'bill', 'recharge', 'jio', 'airtel', 'vodafone', 'bsnl',
                'broadband', 'dth', 'tata power', 'adani', 'piped gas',
                'mobile recharge', 'postpaid', 'prepaid'
            ],
            'Healthcare': [
                'hospital', 'pharmacy', 'medicine', 'doctor', 'dental',
                'medical', 'health', 'clinic', 'practo', '1mg',
                'pharmeasy', 'netmeds', 'apollo', 'diagnostic', 'lab test'
            ],
            'Education': [
                'unacademy', 'byju', 'udemy', 'coursera', 'upgrad',
                'course', 'tuition', 'school', 'college', 'books',
                'scholarship', 'coaching', 'exam', 'fee'
            ],
            'EMI & Loans': [
                'emi', 'loan', 'installment', 'equated monthly',
                'home loan', 'car loan', 'personal loan', 'credit card bill'
            ],
            'Investments': [
                'mutual fund', 'sip', 'stocks', 'shares', 'demat',
                'zerodha', 'groww', 'upstox', 'investment', 'nps',
                'ppf', 'fixed deposit', 'fd', 'rd'
            ],
        }

        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return category

        return 'Other'

    def _detect_payment_method(self, text):
        """Detect payment method from email text"""
        text_lower = text.lower()

        # UPI detection
        upi_keywords = ['upi', 'google pay', 'phonepe', 'paytm', 'bhim',
                        'bharatpe', 'upi id', 'upi ref', '@ybl', '@paytm',
                        '@oksbi', '@okaxis', '@okhdfcbank']
        for kw in upi_keywords:
            if kw in text_lower:
                # Try to identify specific UPI app
                if 'google pay' in text_lower or 'gpay' in text_lower:
                    return 'UPI - Google Pay'
                elif 'phonepe' in text_lower:
                    return 'UPI - PhonePe'
                elif 'paytm' in text_lower:
                    return 'UPI - Paytm'
                elif 'bhim' in text_lower:
                    return 'UPI - BHIM'
                return 'UPI'

        # Credit Card
        if any(kw in text_lower for kw in ['credit card', 'visa', 'mastercard', 'rupay', 'amex']):
            if 'rupay' in text_lower:
                return 'Credit Card - RuPay'
            elif 'visa' in text_lower:
                return 'Credit Card - Visa'
            elif 'mastercard' in text_lower:
                return 'Credit Card - Mastercard'
            return 'Credit Card'

        # Debit Card
        if any(kw in text_lower for kw in ['debit card', 'atm card']):
            return 'Debit Card'

        # Net Banking
        if any(kw in text_lower for kw in ['net banking', 'netbanking', 'neft', 'rtgs', 'imps']):
            return 'Net Banking'

        # Wallet
        if any(kw in text_lower for kw in ['wallet', 'paytm wallet', 'freecharge', 'mobikwik']):
            return 'Wallet'

        # EMI
        if any(kw in text_lower for kw in ['emi', 'equated monthly', 'installment']):
            return 'EMI'

        # Cash on Delivery
        if any(kw in text_lower for kw in ['cash on delivery', 'cod', 'pay on delivery']):
            return 'Cash on Delivery'

        return 'Unknown'

    def _extract_gst(self, text):
        """Extract GST amount from email text"""
        patterns = [
            r'(?:GST|CGST|SGST|IGST)\s*(?::|@|amount)?\s*(?:₹|Rs\.?|INR)?\s*([\d,]+\.?\d*)',
            r'(?:tax|gst)\s*(?:amount)?\s*(?::|=)?\s*(?:₹|Rs\.?|INR)?\s*([\d,]+\.?\d*)',
        ]

        for pattern in patterns:
            try:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    amounts = [float(m.replace(',', '')) for m in matches if float(m.replace(',', '')) > 0]
                    if amounts:
                        return sum(amounts)  # Sum CGST + SGST if both present
            except:
                continue

        return 0

    def _extract_transaction_id(self, text):
        """Extract transaction/order ID"""
        patterns = [
            r'(?:order\s*(?:id|#|no\.?|number)?)\s*[:\-]?\s*([A-Z0-9\-]{6,25})',
            r'(?:transaction\s*(?:id|#|no\.?)?\s*[:\-]?\s*([A-Z0-9\-]{6,25}))',
            r'(?:upi\s*ref\s*(?:no\.?|#)?)\s*[:\-]?\s*(\d{10,16})',
            r'(?:ref\s*(?:no\.?|#|id)?)\s*[:\-]?\s*([A-Z0-9\-]{6,25})',
            r'(?:booking\s*id)\s*[:\-]?\s*([A-Z0-9\-]{6,25})',
        ]

        for pattern in patterns:
            try:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1)
            except:
                continue

        return ''


def test_email_connection(imap_server, imap_port, username, password):
    """Test email connection and return sample data"""
    try:
        processor = EmailProcessor(imap_server, imap_port, username, password)

        if not processor.connect():
            return {'success': False, 'error': 'Failed to connect to email server'}

        emails = processor.get_unread_emails_fast(limit=5)

        if not emails:
            processor.disconnect()
            return {
                'success': True,
                'emails_found': 0,
                'expenses_extracted': 0,
                'expenses': []
            }

        expenses = []
        for email_data in emails:
            expense = processor.extract_expense_data_fast(email_data)
            if expense:
                expenses.append(expense)

        processor.disconnect()

        return {
            'success': True,
            'emails_found': len(emails),
            'expenses_extracted': len(expenses),
            'expenses': expenses[:3]
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}