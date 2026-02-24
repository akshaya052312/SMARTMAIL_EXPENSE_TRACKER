# app.py
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from dotenv import load_dotenv
load_dotenv()  # loads .env file automatically
import sqlite3
import hashlib
import os
import json
import threading
import time
import signal
import sys
from datetime import datetime, timedelta
from email_processor import EmailProcessor, test_email_connection
import atexit

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'smartmail-secret-key-change-in-production')
app.config['DATABASE'] = 'instance/expenses.db'
app.config['EMAIL_DB'] = 'instance/email_configs.db'
CORS(app)

# Create instance folder if it doesn't exist
os.makedirs('instance', exist_ok=True)
os.makedirs('templates', exist_ok=True)
os.makedirs('static', exist_ok=True)

# ============ INDIAN CURRENCY HELPER ============
def format_inr(amount):
    """Format amount in Indian numbering system (lakhs, crores)"""
    if amount is None:
        return '₹0'
    amount = float(amount)
    if amount < 0:
        return f'-₹{format_inr(-amount)[1:]}'
    if amount >= 10000000:
        return f'₹{amount/10000000:.2f}Cr'
    if amount >= 100000:
        return f'₹{amount/100000:.2f}L'
    # Indian comma formatting
    s = f'{amount:,.2f}'
    # Convert international to Indian: 1,234,567.00 -> 12,34,567.00
    parts = s.split('.')
    integer_part = parts[0].replace(',', '')
    decimal_part = parts[1] if len(parts) > 1 else '00'
    if len(integer_part) <= 3:
        return f'₹{integer_part}.{decimal_part}'
    result = integer_part[-3:]
    integer_part = integer_part[:-3]
    while integer_part:
        result = integer_part[-2:] + ',' + result
        integer_part = integer_part[:-2]
    return f'₹{result}.{decimal_part}'

# ============ DATABASE SETUP ============
def get_db(db_type='expenses'):
    """Get database connection"""
    if db_type == 'expenses':
        conn = sqlite3.connect(app.config['DATABASE'])
    else:
        conn = sqlite3.connect(app.config['EMAIL_DB'])
    
    conn.row_factory = sqlite3.Row
    return conn

def init_databases():
    """Initialize all database tables"""
    print("📊 Initializing databases...")
    
    # Expenses database
    conn = get_db('expenses')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            account_type TEXT DEFAULT 'free',
            telegram_chat_id TEXT DEFAULT '',
            notification_enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Migrate existing users table
    for col, default in [('account_type', "'free'"), ('telegram_chat_id', "''"), ('notification_enabled', '1'), ('google_id', "NULL")]:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT DEFAULT {default}")
        except:
            pass
    
    # Expenses table — INR default, added payment_method, gst_amount, transaction_id
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'INR',
            category TEXT,
            description TEXT,
            merchant TEXT,
            payment_method TEXT DEFAULT 'Unknown',
            gst_amount REAL DEFAULT 0,
            transaction_id TEXT DEFAULT '',
            source TEXT DEFAULT 'manual',
            receipt_data TEXT,
            expense_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Add new columns if they don't exist (migration for existing databases)
    try:
        cursor.execute("ALTER TABLE expenses ADD COLUMN payment_method TEXT DEFAULT 'Unknown'")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE expenses ADD COLUMN gst_amount REAL DEFAULT 0")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE expenses ADD COLUMN transaction_id TEXT DEFAULT ''")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE expenses ADD COLUMN confidence INTEGER DEFAULT 50")
    except:
        pass
    
    # Categories table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            color TEXT,
            icon TEXT,
            keywords TEXT
        )
    ''')
    
    # Indian expense categories with keywords
    default_categories = [
        ('Food Delivery', '#FF6B6B', '🍕', 'zomato,swiggy,food,restaurant,cafe,dining,biryani,thali,dominos,pizza'),
        ('Groceries', '#7209B7', '🛒', 'bigbasket,blinkit,zepto,grofers,grocery,vegetable,fruits,milk,dmart,kirana'),
        ('Online Shopping', '#FFD166', '🛍️', 'amazon,flipkart,myntra,ajio,meesho,snapdeal,nykaa,jiomart,shopping'),
        ('Travel & Transport', '#4ECDC4', '🚗', 'ola,uber,rapido,irctc,makemytrip,goibibo,train,flight,bus,cab,taxi'),
        ('Entertainment', '#06D6A0', '🎬', 'netflix,hotstar,bookmyshow,spotify,jiocinema,movie,concert,streaming'),
        ('Utilities & Bills', '#118AB2', '💡', 'electricity,water,gas,internet,phone,recharge,jio,airtel,vodafone,bill'),
        ('Healthcare', '#EF476F', '🏥', 'hospital,pharmacy,medicine,doctor,practo,1mg,pharmeasy,apollo,medical'),
        ('Education', '#F72585', '📚', 'unacademy,byju,udemy,coursera,upgrad,school,college,course,tuition,books'),
        ('EMI & Loans', '#B5179E', '🏦', 'emi,loan,installment,home loan,car loan,personal loan'),
        ('Investments', '#560BAD', '📈', 'mutual fund,sip,stocks,zerodha,groww,upstox,nps,ppf,fd'),
        ('Other', '#6C757D', '📦', '')
    ]
    
    cursor.executemany(
        "INSERT OR IGNORE INTO categories (name, color, icon, keywords) VALUES (?, ?, ?, ?)",
        default_categories
    )
    
    # Feedback table for user reports
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL DEFAULT 'general',
            message TEXT,
            expense_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Subscriptions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            merchant TEXT,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'INR',
            frequency TEXT DEFAULT 'monthly',
            category TEXT DEFAULT 'Other',
            next_due_date DATE,
            last_charged DATE,
            is_active INTEGER DEFAULT 1,
            auto_detected INTEGER DEFAULT 0,
            confidence INTEGER DEFAULT 50,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Budgets table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT DEFAULT 'Overall',
            amount REAL NOT NULL,
            period TEXT DEFAULT 'monthly',
            alert_threshold INTEGER DEFAULT 80,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Budget alerts history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budget_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            budget_id INTEGER NOT NULL,
            alert_type TEXT DEFAULT 'warning',
            message TEXT,
            percentage REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (budget_id) REFERENCES budgets (id)
        )
    ''')
    
    # Bill reminders
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bill_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            amount REAL,
            due_date DATE NOT NULL,
            recurrence TEXT DEFAULT 'none',
            category TEXT DEFAULT 'Utilities & Bills',
            is_paid INTEGER DEFAULT 0,
            notify_days_before INTEGER DEFAULT 3,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Investments
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS investments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'Mutual Fund',
            amount_invested REAL NOT NULL,
            current_value REAL,
            purchase_date DATE,
            maturity_date DATE,
            returns_percent REAL DEFAULT 0,
            platform TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Notifications
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT DEFAULT 'info',
            title TEXT NOT NULL,
            message TEXT,
            link TEXT DEFAULT '',
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # User preferences
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            budget_alerts INTEGER DEFAULT 1,
            bill_reminders INTEGER DEFAULT 1,
            spending_alerts INTEGER DEFAULT 1,
            weekly_summary INTEGER DEFAULT 1,
            telegram_enabled INTEGER DEFAULT 0,
            telegram_chat_id TEXT DEFAULT '',
            alert_threshold INTEGER DEFAULT 80,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Family members
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS family_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            member_user_id INTEGER NOT NULL,
            role TEXT DEFAULT 'member',
            can_view INTEGER DEFAULT 1,
            can_edit INTEGER DEFAULT 0,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users (id),
            FOREIGN KEY (member_user_id) REFERENCES users (id)
        )
    ''')
    
    # Shared budgets
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shared_budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            category TEXT DEFAULT 'Overall',
            amount REAL NOT NULL,
            period TEXT DEFAULT 'monthly',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users (id)
        )
    ''')
    
    # GST records
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gst_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            expense_id INTEGER,
            gstin TEXT DEFAULT '',
            cgst REAL DEFAULT 0,
            sgst REAL DEFAULT 0,
            igst REAL DEFAULT 0,
            total_gst REAL DEFAULT 0,
            invoice_number TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Expenses database initialized")
    
    # Email configurations database
    conn = get_db('email')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            email_address TEXT NOT NULL,
            provider TEXT NOT NULL,
            imap_server TEXT,
            imap_port INTEGER,
            username TEXT,
            app_password TEXT,
            is_active BOOLEAN DEFAULT 1,
            last_sync TIMESTAMP,
            sync_frequency INTEGER DEFAULT 15,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Processed emails table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_config_id INTEGER NOT NULL,
            email_id TEXT NOT NULL,
            message_id TEXT,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expense_id INTEGER,
            FOREIGN KEY (email_config_id) REFERENCES email_configs (id),
            UNIQUE(email_config_id, email_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Email database initialized")

# Initialize databases BEFORE creating the sync service
init_databases()

# ============ HELPER FUNCTIONS ============
def hash_password(password):
    """Hash password using SHA256"""
    salt = "smartmail-tracker-2024"
    return hashlib.sha256(f"{password}{salt}".encode()).hexdigest()

def login_required(f):
    """Decorator for routes that require login"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': 'Authentication required'}), 401
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

# ============ REAL EMAIL SYNC SERVICE (AUTO-SYNC ONLY) ============
class RealEmailSyncService:
    def __init__(self):
        self.running = False
        self.thread = None
        self.sync_interval = 60  # Check every 1 minute
        self.force_stop = threading.Event()
        self.sync_in_progress = False
        self.last_sync_time = None
        self.active_connections = {}
    
    def start(self):
        """Start the automatic email sync service"""
        if not self.running:
            self.running = True
            self.force_stop.clear()
            self.thread = threading.Thread(target=self._sync_loop, daemon=True)
            self.thread.start()
            print("📧 Auto-sync service started (checking every 1 minute)")
    
    def stop(self):
        """Stop the email sync service"""
        print("🛑 Stopping email sync service...")
        self.running = False
        self.force_stop.set()
        for email_key in list(self.active_connections.keys()):
            self._close_connection(email_key)
        if self.thread:
            self.thread.join(timeout=3)
        print("✅ Email sync service stopped")
    
    def _sync_loop(self):
        """Background loop that syncs emails automatically"""
        while self.running and not self.force_stop.is_set():
            try:
                self.sync_in_progress = True
                processed = self._sync_all_email_accounts()
                self.sync_in_progress = False
                
                if processed > 0:
                    print(f"✅ Auto-sync: {processed} new expenses found")
                
                for _ in range(self.sync_interval):
                    if self.force_stop.is_set():
                        break
                    time.sleep(1)
                    
            except Exception as e:
                self.sync_in_progress = False
                print(f"❌ Error in email sync loop: {e}")
                time.sleep(30)
    
    def _sync_all_email_accounts(self):
        """Sync emails for all active configurations"""
        try:
            conn = get_db('email')
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM email_configs WHERE is_active = 1")
            configs = cursor.fetchall()
            conn.close()
            
            if not configs:
                return 0
            
            total_processed = 0
            
            for config in configs:
                try:
                    result = self._process_email_account_fast(dict(config))
                    
                    if result.get('success'):
                        processed = result.get('processed', 0)
                        total_processed += processed
                        
                        conn = get_db('email')
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE email_configs SET last_sync = CURRENT_TIMESTAMP WHERE id = ?",
                            (config['id'],)
                        )
                        conn.commit()
                        conn.close()
                        
                except Exception as e:
                    print(f"   ❌ Error processing {config['email_address']}: {e}")
                    continue
            
            self.last_sync_time = datetime.now()
            return total_processed
            
        except Exception as e:
            print(f"❌ Database error in sync: {e}")
            return 0
    
    def _process_email_account_fast(self, config):
        """Fast email processing with connection caching"""
        try:
            email_key = config['email_address']
            
            processor = self.active_connections.get(email_key)
            
            if not processor or not self._test_connection(processor):
                processor = EmailProcessor(
                    imap_server=config['imap_server'],
                    imap_port=config['imap_port'],
                    username=config['username'],
                    password=config['app_password']
                )
                
                if not processor.connect():
                    return {'success': False, 'error': 'Failed to connect to email server'}
                
                self.active_connections[email_key] = processor
            
            emails = processor.get_unread_emails(days=1)
            
            processed_count = 0
            
            for email_data in emails:
                try:
                    conn = get_db('email')
                    cursor = conn.cursor()
                    
                    cursor.execute(
                        "SELECT id FROM processed_emails WHERE email_config_id = ? AND email_id = ?",
                        (config['id'], email_data['id'])
                    )
                    
                    if cursor.fetchone():
                        conn.close()
                        continue
                    
                    expense_data = processor.extract_expense_data(email_data)
                    
                    expense_id = None
                    if expense_data and expense_data.get('amount'):
                        expense_id = self._save_expense_to_db(expense_data, config['user_id'])
                        
                        if expense_id:
                            processed_count += 1
                    
                    cursor.execute(
                        "INSERT INTO processed_emails (email_config_id, email_id, message_id, expense_id) VALUES (?, ?, ?, ?)",
                        (config['id'], email_data['id'], email_data.get('message_id', ''), 
                         expense_id if expense_id else None)
                    )
                    conn.commit()
                    conn.close()
                    
                except Exception as e:
                    print(f"   ⚠️ Error processing email {email_data.get('id', '?')}: {e}")
                    continue
            
            return {
                'success': True,
                'processed': processed_count,
                'emails_found': len(emails),
                'expenses_created': processed_count
            }
            
        except Exception as e:
            if config['email_address'] in self.active_connections:
                del self.active_connections[config['email_address']]
            return {'success': False, 'error': str(e)}
    
    def _test_connection(self, processor):
        """Test if connection is still alive"""
        try:
            processor.mail.select("inbox")
            return True
        except:
            return False
    
    def _close_connection(self, email_key):
        """Close and remove a cached connection"""
        try:
            if email_key in self.active_connections:
                processor = self.active_connections[email_key]
                processor.disconnect()
                del self.active_connections[email_key]
        except:
            pass
    
    def _save_expense_to_db(self, expense_data, user_id):
        """Save extracted expense to database — INR default with payment_method/GST"""
        try:
            conn = get_db('expenses')
            cursor = conn.cursor()
            
            cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            if not cursor.fetchone():
                conn.close()
                return None
            
            cursor.execute('''
                SELECT id FROM expenses 
                WHERE user_id = ? AND amount = ? AND merchant = ? 
                AND expense_date = DATE(?)
            ''', (
                user_id,
                expense_data['amount'],
                expense_data['merchant'],
                expense_data['date'].strftime('%Y-%m-%d') if hasattr(expense_data['date'], 'strftime') else expense_data['date']
            ))
            
            if cursor.fetchone():
                conn.close()
                return None
            
            expense_date = expense_data['date']
            if hasattr(expense_date, 'strftime'):
                expense_date = expense_date.strftime('%Y-%m-%d')
            
            cursor.execute('''
                INSERT INTO expenses 
                (user_id, amount, currency, category, description, merchant, 
                 payment_method, gst_amount, transaction_id, confidence,
                 source, receipt_data, expense_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                expense_data['amount'],
                expense_data.get('currency', 'INR'),
                expense_data['category'],
                expense_data.get('description', ''),
                expense_data['merchant'],
                expense_data.get('payment_method', 'Unknown'),
                expense_data.get('gst_amount', 0),
                expense_data.get('transaction_id', ''),
                expense_data.get('confidence', 50),
                expense_data.get('source', 'email'),
                json.dumps(expense_data.get('email_data', {})),
                expense_date
            ))
            
            expense_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # Check budget alerts after saving expense
            try:
                check_budget_alerts(user_id, expense_data['category'], expense_data['amount'])
            except:
                pass
            
            return expense_id
            
        except Exception as e:
            return None

# Initialize auto email sync service
real_email_sync_service = RealEmailSyncService()

# ============ NAVIGATION ROUTES ============

@app.route('/')
def index():
    """Home page"""
    logged_in = 'user_id' in session
    username = session.get('username', '')
    return render_template('index.html', logged_in=logged_in, username=username)

@app.route('/about')
def about():
    """About page"""
    logged_in = 'user_id' in session
    username = session.get('username', '')
    return render_template('about.html', logged_in=logged_in, username=username)

@app.route('/login')
def login_page():
    """Login page"""
    if 'user_id' in session:
        return redirect('/dashboard')
    logged_in = 'user_id' in session
    return render_template('login.html', logged_in=logged_in)

@app.route('/register')
def register_page():
    """Registration page"""
    if 'user_id' in session:
        return redirect('/dashboard')
    logged_in = 'user_id' in session
    return render_template('register.html', logged_in=logged_in)

# ============ PROTECTED ROUTES ============

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard page"""
    username = session.get('username', '')
    return render_template('dashboard.html', logged_in=True, username=username)

@app.route('/email-settings')
@login_required
def email_settings():
    """Email settings page"""
    username = session.get('username', '')
    return render_template('email_config.html', logged_in=True, username=username)

@app.route('/settings')
@login_required
def settings():
    """Settings page"""
    username = session.get('username', '')
    return render_template('settings.html', logged_in=True, username=username)

@app.route('/reports')
@login_required
def reports():
    """Reports page"""
    username = session.get('username', '')
    return render_template('reports.html', logged_in=True, username=username)

# @app.route('/drawbacks')
# @login_required
# def drawbacks():
#     """Drawbacks & Limitations page"""
#     username = session.get('username', '')
#     return render_template('drawbacks.html', logged_in=True, username=username)

# ============ SYNC STATUS (kept for auto-sync polling) ============

@app.route('/api/email/sync-status', methods=['GET'])
@login_required
def api_sync_status():
    """Check background sync status"""
    last_sync = real_email_sync_service.last_sync_time
    return jsonify({
        'success': True,
        'syncing': real_email_sync_service.sync_in_progress,
        'last_sync': last_sync.isoformat() if last_sync else None,
        'timestamp': datetime.now().isoformat()
    })

# ============ AUTH API ENDPOINTS ============

@app.route('/api/register', methods=['POST'])
def api_register():
    """Register new user"""
    try:
        data = request.json
        
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({'success': False, 'error': 'Username and password required'}), 400
        
        username = data['username'].strip()
        password = data['password']
        email = data.get('email', '').strip()
        
        if len(password) < 6:
            return jsonify({'success': False, 'error': 'Password must be at least 6 characters'}), 400
        
        conn = get_db('expenses')
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (username, email)
        )
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Username or email already exists'}), 400
        
        password_hash = hash_password(password)
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email if email else None, password_hash)
        )
        user_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        session['user_id'] = user_id
        session['username'] = username
        
        return jsonify({
            'success': True,
            'message': 'Registration successful',
            'user': {'id': user_id, 'username': username, 'email': email}
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def api_login():
    """Login user"""
    try:
        data = request.json
        
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({'success': False, 'error': 'Username and password required'}), 400
        
        username = data['username'].strip()
        password = data['password']
        
        conn = get_db('expenses')
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,)
        )
        user = cursor.fetchone()
        conn.close()
        
        if not user or user['password_hash'] != hash_password(password):
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        
        session['user_id'] = user['id']
        session['username'] = user['username']
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': {'id': user['id'], 'username': user['username']}
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def api_logout():
    """Logout user"""
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out'})


@app.route('/api/user', methods=['GET'])
@login_required
def api_user():
    """Get current user info"""
    user_id = session['user_id']
    
    conn = get_db('expenses')
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT id, username, email, created_at FROM users WHERE id = ?",
        (user_id,)
    )
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return jsonify({
            'success': True,
            'user': dict(user)
        })
    else:
        return jsonify({'success': False, 'error': 'User not found'}), 404

# ============ EMAIL CONFIGURATION API ============

@app.route('/api/email/configs', methods=['GET', 'POST'])
@login_required
def api_email_configs():
    """Get or create email configurations"""
    user_id = session['user_id']
    
    if request.method == 'GET':
        conn = get_db('email')
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM email_configs WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        
        configs = cursor.fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'configs': [dict(config) for config in configs]
        })
    
    elif request.method == 'POST':
        try:
            data = request.json
            
            required_fields = ['email_address', 'provider', 'app_password']
            for field in required_fields:
                if field not in data:
                    return jsonify({'success': False, 'error': f'{field} is required'}), 400
            
            email_address = data['email_address'].strip()
            provider = data['provider']
            app_password = data['app_password']
            
            # Includes Indian email providers
            provider_configs = {
                'gmail': {
                    'imap_server': 'imap.gmail.com',
                    'imap_port': 993,
                    'username': email_address
                },
                'outlook': {
                    'imap_server': 'outlook.office365.com',
                    'imap_port': 993,
                    'username': email_address
                },
                'yahoo': {
                    'imap_server': 'imap.mail.yahoo.com',
                    'imap_port': 993,
                    'username': email_address
                },
                'rediffmail': {
                    'imap_server': 'imap.rediffmail.com',
                    'imap_port': 993,
                    'username': email_address
                }
            }
            
            if provider not in provider_configs:
                return jsonify({'success': False, 'error': 'Unsupported provider'}), 400
            
            config = provider_configs[provider]
            
            conn = get_db('email')
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT id FROM email_configs WHERE user_id = ? AND email_address = ?",
                (user_id, email_address)
            )
            if cursor.fetchone():
                conn.close()
                return jsonify({'success': False, 'error': 'Email configuration already exists'}), 400
            
            cursor.execute('''
                INSERT INTO email_configs 
                (user_id, email_address, provider, imap_server, imap_port, username, app_password, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, email_address, provider, 
                config['imap_server'], config['imap_port'],
                config['username'], app_password, 1
            ))
            
            config_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            try:
                test_result = test_email_connection(
                    config['imap_server'],
                    config['imap_port'],
                    config['username'],
                    app_password
                )
                
                if not test_result['success']:
                    conn = get_db('email')
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM email_configs WHERE id = ?", (config_id,))
                    conn.commit()
                    conn.close()
                    
                    return jsonify({
                        'success': False,
                        'error': f"Connection test failed: {test_result.get('error', 'Unknown error')}"
                    }), 400
            except Exception as e:
                print(f"Email connection test error: {e}")
            
            return jsonify({
                'success': True,
                'message': 'Email configuration added successfully',
                'config_id': config_id
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

# ============ EMAIL CONFIG MANAGEMENT (PUT/DELETE) ============

@app.route('/api/email/configs/<int:config_id>', methods=['PUT', 'DELETE'])
@login_required
def api_email_config_detail(config_id):
    """Update or delete a specific email configuration"""
    user_id = session['user_id']
    
    if request.method == 'PUT':
        try:
            data = request.json or {}
            is_active = data.get('is_active')
            
            conn = get_db('email')
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT id FROM email_configs WHERE id = ? AND user_id = ?",
                (config_id, user_id)
            )
            if not cursor.fetchone():
                conn.close()
                return jsonify({'success': False, 'error': 'Configuration not found'}), 404
            
            if is_active is not None:
                cursor.execute(
                    "UPDATE email_configs SET is_active = ? WHERE id = ? AND user_id = ?",
                    (1 if is_active else 0, config_id, user_id)
                )
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'Configuration updated successfully'
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    elif request.method == 'DELETE':
        try:
            conn = get_db('email')
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT id FROM email_configs WHERE id = ? AND user_id = ?",
                (config_id, user_id)
            )
            if not cursor.fetchone():
                conn.close()
                return jsonify({'success': False, 'error': 'Configuration not found'}), 404
            
            cursor.execute(
                "DELETE FROM processed_emails WHERE email_config_id = ?",
                (config_id,)
            )
            
            cursor.execute(
                "DELETE FROM email_configs WHERE id = ? AND user_id = ?",
                (config_id, user_id)
            )
            
            conn.commit()
            conn.close()
            
            for key in list(real_email_sync_service.active_connections.keys()):
                real_email_sync_service._close_connection(key)
            
            return jsonify({
                'success': True,
                'message': 'Configuration deleted successfully'
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

# ============ EMAIL STATS ENDPOINT ============

@app.route('/api/email/stats', methods=['GET'])
@login_required
def api_email_stats():
    """Get email sync statistics for the current user"""
    user_id = session['user_id']
    
    try:
        conn = get_db('email')
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT COUNT(*) as total FROM email_configs WHERE user_id = ?",
            (user_id,)
        )
        total_configs = cursor.fetchone()['total']
        
        cursor.execute(
            "SELECT COUNT(*) as active FROM email_configs WHERE user_id = ? AND is_active = 1",
            (user_id,)
        )
        active_configs = cursor.fetchone()['active']
        
        cursor.execute(
            "SELECT email_address, last_sync FROM email_configs WHERE user_id = ? ORDER BY last_sync DESC",
            (user_id,)
        )
        sync_rows = cursor.fetchall()
        sync_times = [
            {
                'email': row['email_address'],
                'last_sync': row['last_sync'] if row['last_sync'] else 'Never'
            }
            for row in sync_rows
        ]
        conn.close()
        
        conn = get_db('expenses')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as count FROM expenses WHERE user_id = ? AND source = 'email'",
            (user_id,)
        )
        email_expenses = cursor.fetchone()['count']
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_configs': total_configs,
                'active_configs': active_configs,
                'email_expenses': email_expenses,
                'sync_times': sync_times
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ EMAIL SYNC (background only, no manual buttons) ============

@app.route('/api/email/sync', methods=['POST'])
@login_required
def api_email_sync():
    """Sync emails (called internally by auto-sync, kept for email config test)"""
    user_id = session['user_id']
    
    try:
        data = request.json or {}
        config_id = data.get('config_id')
        
        conn = get_db('email')
        cursor = conn.cursor()
        
        if config_id:
            cursor.execute(
                "SELECT * FROM email_configs WHERE id = ? AND user_id = ?",
                (config_id, user_id)
            )
            config = cursor.fetchone()
            
            if not config:
                conn.close()
                return jsonify({'success': False, 'error': 'Configuration not found'}), 404
            
            result = real_email_sync_service._process_email_account_fast(dict(config))
            
            if result.get('success'):
                cursor.execute(
                    "UPDATE email_configs SET last_sync = CURRENT_TIMESTAMP WHERE id = ?",
                    (config_id,)
                )
                conn.commit()
                conn.close()
                
                return jsonify({
                    'success': True,
                    'message': f'Synced {result.get("processed", 0)} emails',
                    'details': result
                })
            else:
                conn.close()
                return jsonify({
                    'success': False,
                    'error': result.get('error', 'Sync failed')
                })
        
        else:
            cursor.execute(
                "SELECT * FROM email_configs WHERE user_id = ? AND is_active = 1",
                (user_id,)
            )
            configs = cursor.fetchall()
            conn.close()
            
            total_processed = 0
            results = []
            
            for config in configs:
                result = real_email_sync_service._process_email_account_fast(dict(config))
                if result.get('success'):
                    processed = result.get('processed', 0)
                    total_processed += processed
                    results.append({
                        'email': config['email_address'],
                        'processed': processed,
                        'success': True
                    })
                else:
                    results.append({
                        'email': config['email_address'],
                        'processed': 0,
                        'success': False,
                        'error': result.get('error')
                    })
            
            return jsonify({
                'success': True,
                'message': f'Synced {total_processed} emails from {len(configs)} accounts',
                'results': results
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/email/test', methods=['POST'])
@login_required
def api_test_email():
    """Test email connection (for setup)"""
    try:
        data = request.json
        
        if not data or 'email' not in data or 'password' not in data or 'provider' not in data:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        email_address = data['email'].strip()
        password = data['password']
        provider = data['provider']
        
        provider_configs = {
            'gmail': {
                'imap_server': 'imap.gmail.com',
                'imap_port': 993
            },
            'outlook': {
                'imap_server': 'outlook.office365.com',
                'imap_port': 993
            },
            'yahoo': {
                'imap_server': 'imap.mail.yahoo.com',
                'imap_port': 993
            },
            'rediffmail': {
                'imap_server': 'imap.rediffmail.com',
                'imap_port': 993
            }
        }
        
        if provider not in provider_configs:
            return jsonify({'success': False, 'error': 'Unsupported provider'}), 400
        
        config = provider_configs[provider]
        
        result = test_email_connection(
            imap_server=config['imap_server'],
            imap_port=config['imap_port'],
            username=email_address,
            password=password
        )
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': f'Connection successful! Found {result.get("emails_found", 0)} emails',
                'details': {
                    'emails_found': result.get('emails_found', 0),
                    'expenses_extracted': result.get('expenses_extracted', 0),
                    'sample_expenses': result.get('expenses', [])[:3]
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Connection failed')
            })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ EXPENSE MANAGEMENT API ============

@app.route('/api/expenses', methods=['GET', 'POST'])
@login_required
def api_expenses():
    """Get all expenses or add new expense — INR default"""
    user_id = session['user_id']
    
    if request.method == 'GET':
        category = request.args.get('category', '')
        source = request.args.get('source', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        payment_method = request.args.get('payment_method', '')
        search = request.args.get('search', '')
        limit = request.args.get('limit', 50, type=int)
        
        conn = get_db('expenses')
        cursor = conn.cursor()
        
        query = '''
            SELECT e.*, c.color, c.icon
            FROM expenses e
            LEFT JOIN categories c ON e.category = c.name
            WHERE e.user_id = ?
        '''
        params = [user_id]
        
        if category and category != 'All':
            query += " AND e.category = ?"
            params.append(category)
        
        if source and source != 'All':
            query += " AND e.source = ?"
            params.append(source)
        
        if payment_method and payment_method != 'All':
            query += " AND e.payment_method = ?"
            params.append(payment_method)
        
        if search:
            query += " AND (e.merchant LIKE ? OR e.description LIKE ? OR e.transaction_id LIKE ?)"
            search_term = f'%{search}%'
            params.extend([search_term, search_term, search_term])
        
        if start_date:
            query += " AND e.expense_date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND e.expense_date <= ?"
            params.append(end_date)
        
        query += " ORDER BY e.expense_date DESC, e.created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        expenses = cursor.fetchall()
        conn.close()
        
        result = [
            {
                'id': exp['id'],
                'amount': exp['amount'],
                'currency': exp['currency'] or 'INR',
                'category': exp['category'],
                'description': exp['description'],
                'merchant': exp['merchant'],
                'payment_method': exp['payment_method'] if 'payment_method' in exp.keys() else 'Unknown',
                'gst_amount': exp['gst_amount'] if 'gst_amount' in exp.keys() else 0,
                'transaction_id': exp['transaction_id'] if 'transaction_id' in exp.keys() else '',
                'confidence': exp['confidence'] if 'confidence' in exp.keys() else 50,
                'source': exp['source'],
                'receipt_data': json.loads(exp['receipt_data']) if exp['receipt_data'] else None,
                'date': exp['expense_date'],
                'created_at': exp['created_at'],
                'color': exp['color'],
                'icon': exp['icon']
            }
            for exp in expenses
        ]
        
        return jsonify({'success': True, 'expenses': result})
    
    elif request.method == 'POST':
        try:
            data = request.json
            
            required_fields = ['amount', 'category', 'date']
            for field in required_fields:
                if field not in data:
                    return jsonify({'success': False, 'error': f'{field} is required'}), 400
            
            amount = float(data['amount'])
            category = data['category']
            expense_date = data['date']
            description = data.get('description', '')
            merchant = data.get('merchant', '')
            currency = data.get('currency', 'INR')
            source = data.get('source', 'manual')
            payment_method = data.get('payment_method', 'Unknown')
            gst_amount = float(data.get('gst_amount', 0))
            transaction_id = data.get('transaction_id', '')
            
            conn = get_db('expenses')
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO expenses 
                (user_id, amount, currency, category, description, merchant, 
                 payment_method, gst_amount, transaction_id, source, expense_date) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, amount, currency, category, description, merchant,
                  payment_method, gst_amount, transaction_id, source, expense_date))
            
            expense_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # Check budget alerts after saving expense
            try:
                check_budget_alerts(user_id, category, amount)
            except:
                pass
            
            return jsonify({
                'success': True,
                'message': 'Expense added successfully',
                'expense_id': expense_id
            }), 201
            
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid amount'}), 400
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/expenses/recent', methods=['GET'])
@login_required
def api_recent_expenses():
    """Get only recent expenses (fast endpoint)"""
    user_id = session['user_id']
    limit = request.args.get('limit', 10, type=int)
    
    conn = get_db('expenses')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT e.*, c.color, c.icon
        FROM expenses e
        LEFT JOIN categories c ON e.category = c.name
        WHERE e.user_id = ?
        ORDER BY e.created_at DESC
        LIMIT ?
    ''', (user_id, limit))
    
    expenses = cursor.fetchall()
    conn.close()
    
    result = [
        {
            'id': exp['id'],
            'amount': exp['amount'],
            'currency': exp['currency'] or 'INR',
            'category': exp['category'],
            'description': exp['description'],
            'merchant': exp['merchant'],
            'payment_method': exp['payment_method'] if 'payment_method' in exp.keys() else 'Unknown',
            'gst_amount': exp['gst_amount'] if 'gst_amount' in exp.keys() else 0,
            'transaction_id': exp['transaction_id'] if 'transaction_id' in exp.keys() else '',
            'confidence': exp['confidence'] if 'confidence' in exp.keys() else 50,
            'source': exp['source'],
            'date': exp['expense_date'],
            'created_at': exp['created_at'],
            'color': exp['color'],
            'icon': exp['icon']
        }
        for exp in expenses
    ]
    
    return jsonify({'success': True, 'expenses': result})

@app.route('/api/summary', methods=['GET'])
@login_required
def api_summary():
    """Get expense summary with Indian analytics"""
    user_id = session['user_id']
    period = request.args.get('period', 'month')
    
    conn = get_db('expenses')
    cursor = conn.cursor()
    
    today = datetime.now().date()
    
    if period == 'week':
        start_date = today - timedelta(days=today.weekday())
    elif period == 'month':
        start_date = today.replace(day=1)
    elif period == 'year':
        start_date = today.replace(month=1, day=1)
    elif period == 'fy':
        # Indian Financial Year (April to March)
        if today.month >= 4:
            start_date = today.replace(month=4, day=1)
        else:
            start_date = today.replace(year=today.year - 1, month=4, day=1)
    else:
        start_date = today.replace(day=1)
    
    # Basic summary
    cursor.execute('''
        SELECT 
            SUM(amount) as total,
            COUNT(*) as count,
            AVG(amount) as average,
            MAX(amount) as largest,
            SUM(CASE WHEN source = 'email' THEN 1 ELSE 0 END) as email_count,
            SUM(CASE WHEN source = 'manual' THEN 1 ELSE 0 END) as manual_count
        FROM expenses 
        WHERE user_id = ? AND expense_date >= ?
    ''', (user_id, start_date))
    
    summary = cursor.fetchone()
    
    # Average daily spend
    days_in_period = max((today - start_date).days, 1)
    total_amount = summary['total'] or 0
    avg_daily = total_amount / days_in_period
    
    # Previous period for MoM change
    period_days = (today - start_date).days
    prev_start = start_date - timedelta(days=max(period_days, 1))
    prev_end = start_date - timedelta(days=1)
    
    cursor.execute('''
        SELECT SUM(amount) as total
        FROM expenses 
        WHERE user_id = ? AND expense_date >= ? AND expense_date <= ?
    ''', (user_id, prev_start, prev_end))
    
    prev_total = cursor.fetchone()['total'] or 0
    mom_change = 0
    if prev_total > 0:
        mom_change = round(((total_amount - prev_total) / prev_total) * 100, 1)
    
    # Category breakdown
    cursor.execute('''
        SELECT 
            e.category,
            c.color,
            c.icon,
            SUM(e.amount) as total,
            COUNT(*) as count
        FROM expenses e
        LEFT JOIN categories c ON e.category = c.name
        WHERE e.user_id = ? AND e.expense_date >= ?
        GROUP BY e.category
        ORDER BY total DESC
        LIMIT 10
    ''', (user_id, start_date))
    
    categories = cursor.fetchall()
    
    # Payment method breakdown
    cursor.execute('''
        SELECT 
            payment_method,
            SUM(amount) as total,
            COUNT(*) as count
        FROM expenses 
        WHERE user_id = ? AND expense_date >= ?
        GROUP BY payment_method
        ORDER BY total DESC
    ''', (user_id, start_date))
    
    payment_methods = cursor.fetchall()
    
    # Source breakdown
    cursor.execute('''
        SELECT 
            source,
            SUM(amount) as total,
            COUNT(*) as count
        FROM expenses 
        WHERE user_id = ? AND expense_date >= ?
        GROUP BY source
    ''', (user_id, start_date))
    
    sources = cursor.fetchall()
    
    conn.close()
    
    return jsonify({
        'success': True,
        'summary': {
            'total': total_amount,
            'count': summary['count'] or 0,
            'average': summary['average'] or 0,
            'largest': summary['largest'] or 0,
            'avg_daily': round(avg_daily, 2),
            'mom_change': mom_change,
            'email_count': summary['email_count'] or 0,
            'manual_count': summary['manual_count'] or 0,
            'period': period,
            'currency': 'INR'
        },
        'categories': [
            {
                'name': cat['category'] or 'Uncategorized',
                'color': cat['color'] or '#6C757D',
                'icon': cat['icon'] or '📦',
                'total': cat['total'] or 0,
                'count': cat['count'] or 0
            }
            for cat in categories
        ],
        'payment_methods': [
            {
                'method': pm['payment_method'] or 'Unknown',
                'total': pm['total'] or 0,
                'count': pm['count'] or 0
            }
            for pm in payment_methods
        ],
        'sources': [
            {
                'source': src['source'],
                'total': src['total'] or 0,
                'count': src['count'] or 0
            }
            for src in sources
        ]
    })

# ============ ANALYTICS ENDPOINTS ============

@app.route('/api/analytics/trends', methods=['GET'])
@login_required
def api_analytics_trends():
    """Get daily spending trends for the past 30 days"""
    user_id = session['user_id']
    days = request.args.get('days', 30, type=int)
    
    conn = get_db('expenses')
    cursor = conn.cursor()
    
    start_date = (datetime.now().date() - timedelta(days=days)).isoformat()
    
    cursor.execute('''
        SELECT 
            expense_date as date,
            SUM(amount) as total,
            COUNT(*) as count
        FROM expenses 
        WHERE user_id = ? AND expense_date >= ?
        GROUP BY expense_date
        ORDER BY expense_date ASC
    ''', (user_id, start_date))
    
    trends = cursor.fetchall()
    conn.close()
    
    return jsonify({
        'success': True,
        'trends': [
            {
                'date': t['date'],
                'total': t['total'] or 0,
                'count': t['count'] or 0
            }
            for t in trends
        ]
    })

@app.route('/api/analytics/merchants', methods=['GET'])
@login_required
def api_analytics_merchants():
    """Get top merchants by spending"""
    user_id = session['user_id']
    period = request.args.get('period', 'month')
    limit = request.args.get('limit', 10, type=int)
    
    today = datetime.now().date()
    
    if period == 'week':
        start_date = today - timedelta(days=today.weekday())
    elif period == 'month':
        start_date = today.replace(day=1)
    elif period == 'year':
        start_date = today.replace(month=1, day=1)
    else:
        start_date = today.replace(day=1)
    
    conn = get_db('expenses')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            merchant,
            SUM(amount) as total,
            COUNT(*) as count,
            AVG(amount) as avg_amount
        FROM expenses 
        WHERE user_id = ? AND expense_date >= ? AND merchant != '' AND merchant IS NOT NULL
        GROUP BY merchant
        ORDER BY total DESC
        LIMIT ?
    ''', (user_id, start_date, limit))
    
    merchants = cursor.fetchall()
    conn.close()
    
    return jsonify({
        'success': True,
        'merchants': [
            {
                'name': m['merchant'],
                'total': m['total'] or 0,
                'count': m['count'] or 0,
                'avg_amount': round(m['avg_amount'] or 0, 2)
            }
            for m in merchants
        ]
    })

@app.route('/api/categories', methods=['GET'])
@login_required
def api_categories():
    """Get all categories"""
    conn = get_db('expenses')
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM categories ORDER BY name")
    categories = cursor.fetchall()
    conn.close()
    
    return jsonify({
        'success': True,
        'categories': [dict(cat) for cat in categories]
    })

@app.route('/api/expenses/<int:expense_id>', methods=['PUT', 'DELETE'])
@login_required
def api_expense_detail(expense_id):
    """Update or delete a specific expense"""
    user_id = session['user_id']
    
    if request.method == 'DELETE':
        try:
            conn = get_db('expenses')
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT id FROM expenses WHERE id = ? AND user_id = ?",
                (expense_id, user_id)
            )
            if not cursor.fetchone():
                conn.close()
                return jsonify({'success': False, 'error': 'Expense not found'}), 404
            
            cursor.execute(
                "DELETE FROM expenses WHERE id = ? AND user_id = ?",
                (expense_id, user_id)
            )
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'Expense deleted successfully'
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    elif request.method == 'PUT':
        try:
            data = request.json
            
            conn = get_db('expenses')
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM expenses WHERE id = ? AND user_id = ?",
                (expense_id, user_id)
            )
            if not cursor.fetchone():
                conn.close()
                return jsonify({'success': False, 'error': 'Expense not found'}), 404
            
            updates = []
            params = []
            
            for field in ['amount', 'category', 'description', 'merchant', 
                         'payment_method', 'gst_amount', 'transaction_id']:
                if field in data:
                    if field == 'amount' or field == 'gst_amount':
                        updates.append(f"{field} = ?")
                        params.append(float(data[field]))
                    else:
                        updates.append(f"{field} = ?")
                        params.append(data[field])
            
            if 'date' in data:
                updates.append("expense_date = ?")
                params.append(data['date'])
            
            if updates:
                params.extend([expense_id, user_id])
                cursor.execute(
                    f"UPDATE expenses SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
                    params
                )
                conn.commit()
            
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'Expense updated successfully'
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

# ============ FEEDBACK API ============

@app.route('/api/feedback', methods=['POST'])
@login_required
def api_feedback():
    """Submit user feedback — false positive reports, wrong categories, general issues"""
    user_id = session['user_id']
    
    try:
        data = request.json or {}
        feedback_type = data.get('type', 'general')  # 'false_positive', 'wrong_category', 'general'
        message = data.get('message', '').strip()
        expense_id = data.get('expense_id')
        
        if not message and not expense_id:
            return jsonify({'success': False, 'error': 'Message or expense_id required'}), 400
        
        conn = get_db('expenses')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO feedback (user_id, type, message, expense_id)
            VALUES (?, ?, ?, ?)
        ''', (user_id, feedback_type, message, expense_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Feedback submitted successfully. Thank you!'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ HEALTH CHECK ============

@app.route('/api/health', methods=['GET'])
def api_health():
    """Health check endpoint"""
    try:
        conn1 = get_db('expenses')
        cursor1 = conn1.cursor()
        cursor1.execute("SELECT 1")
        conn1.close()
        
        conn2 = get_db('email')
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT 1")
        conn2.close()
        
        return jsonify({
            'success': True,
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'services': {
                'database': 'connected',
                'email_sync': 'running' if real_email_sync_service.running else 'stopped',
                'cached_connections': len(real_email_sync_service.active_connections)
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# ============ HELPER: BUDGET ALERT CHECK ============

def check_budget_alerts(user_id, category, expense_amount):
    """Check if adding an expense triggers any budget alerts"""
    try:
        conn = get_db('expenses')
        cursor = conn.cursor()
        
        now = datetime.now()
        if now.month >= 4:
            fy_start = f'{now.year}-04-01'
        else:
            fy_start = f'{now.year-1}-04-01'
        month_start = now.strftime('%Y-%m-01')
        
        # Check category-specific budgets and overall budgets
        cursor.execute(
            "SELECT * FROM budgets WHERE user_id = ? AND is_active = 1 AND (category = ? OR category = 'Overall')",
            (user_id, category)
        )
        budgets = cursor.fetchall()
        
        for budget in budgets:
            period_start = month_start if budget['period'] == 'monthly' else fy_start
            
            if budget['category'] == 'Overall':
                cursor.execute(
                    "SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE user_id = ? AND expense_date >= ?",
                    (user_id, period_start)
                )
            else:
                cursor.execute(
                    "SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE user_id = ? AND category = ? AND expense_date >= ?",
                    (user_id, budget['category'], period_start)
                )
            
            result = cursor.fetchone()
            current_spend = result['total'] if result else 0
            percentage = (current_spend / budget['amount'] * 100) if budget['amount'] > 0 else 0
            
            threshold = budget['alert_threshold'] or 80
            
            if percentage >= 100:
                _create_notification(user_id, 'danger',
                    f"🚨 Budget Exceeded: {budget['category']}",
                    f"You've spent ₹{current_spend:,.0f} of your ₹{budget['amount']:,.0f} {budget['category']} budget ({percentage:.0f}%)",
                    '/budgets')
            elif percentage >= threshold:
                _create_notification(user_id, 'warning',
                    f"⚠️ Budget Alert: {budget['category']}",
                    f"You've spent ₹{current_spend:,.0f} of your ₹{budget['amount']:,.0f} {budget['category']} budget ({percentage:.0f}%)",
                    '/budgets')
        
        conn.close()
    except Exception as e:
        print(f"Budget alert check error: {e}")


def _create_notification(user_id, notif_type, title, message, link=''):
    """Create an in-app notification"""
    try:
        conn = get_db('expenses')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO notifications (user_id, type, title, message, link) VALUES (?, ?, ?, ?, ?)",
            (user_id, notif_type, title, message, link)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Notification creation error: {e}")


# ============ SUBSCRIPTION APIS ============

@app.route('/api/subscriptions', methods=['GET', 'POST'])
@login_required
def api_subscriptions():
    user_id = session['user_id']
    
    if request.method == 'GET':
        conn = get_db('expenses')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM subscriptions WHERE user_id = ? ORDER BY next_due_date ASC", (user_id,))
        subs = [dict(r) for r in cursor.fetchall()]
        conn.close()
        
        monthly_total = sum(s['amount'] for s in subs if s['is_active'] and s.get('frequency') == 'monthly')
        yearly_total = sum(s['amount'] * (12 if s.get('frequency') == 'monthly' else 1) for s in subs if s['is_active'])
        
        return jsonify({'success': True, 'subscriptions': subs, 'monthly_total': monthly_total, 'yearly_total': yearly_total})
    
    elif request.method == 'POST':
        data = request.json
        if not data or not data.get('name') or not data.get('amount'):
            return jsonify({'success': False, 'error': 'Name and amount required'}), 400
        
        conn = get_db('expenses')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO subscriptions (user_id, name, merchant, amount, frequency, category, next_due_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, data['name'], data.get('merchant', data['name']), data['amount'],
              data.get('frequency', 'monthly'), data.get('category', 'Other'),
              data.get('next_due_date'), data.get('notes', '')))
        sub_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'id': sub_id, 'message': 'Subscription added'})


@app.route('/api/subscriptions/<int:sub_id>', methods=['PUT', 'DELETE'])
@login_required
def api_subscription_detail(sub_id):
    user_id = session['user_id']
    conn = get_db('expenses')
    cursor = conn.cursor()
    
    if request.method == 'DELETE':
        cursor.execute("DELETE FROM subscriptions WHERE id = ? AND user_id = ?", (sub_id, user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Subscription deleted'})
    
    elif request.method == 'PUT':
        data = request.json
        cursor.execute('''
            UPDATE subscriptions SET name=?, merchant=?, amount=?, frequency=?, category=?,
            next_due_date=?, is_active=?, notes=? WHERE id=? AND user_id=?
        ''', (data.get('name'), data.get('merchant'), data.get('amount'), data.get('frequency'),
              data.get('category'), data.get('next_due_date'), data.get('is_active', 1),
              data.get('notes', ''), sub_id, user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Subscription updated'})


@app.route('/api/subscriptions/detect', methods=['GET'])
@login_required
def api_detect_subscriptions():
    """Auto-detect recurring subscriptions from expense history"""
    user_id = session['user_id']
    conn = get_db('expenses')
    cursor = conn.cursor()
    
    # Find merchants with 2+ charges of similar amounts in last 6 months
    cursor.execute('''
        SELECT merchant, ROUND(amount, 0) as rounded_amt, COUNT(*) as occurrences,
               AVG(amount) as avg_amount, MAX(expense_date) as last_date
        FROM expenses WHERE user_id = ? AND expense_date >= date('now', '-6 months')
        GROUP BY merchant, rounded_amt HAVING COUNT(*) >= 2
        ORDER BY occurrences DESC
    ''', (user_id,))
    
    detected = []
    for row in cursor.fetchall():
        # Check if already tracked
        cursor.execute("SELECT id FROM subscriptions WHERE user_id = ? AND merchant = ?", (user_id, row['merchant']))
        if not cursor.fetchone():
            freq = 'monthly' if row['occurrences'] >= 3 else 'quarterly' if row['occurrences'] >= 2 else 'yearly'
            detected.append({
                'merchant': row['merchant'],
                'amount': row['avg_amount'],
                'frequency': freq,
                'occurrences': row['occurrences'],
                'last_charged': row['last_date'],
                'confidence': min(95, 50 + row['occurrences'] * 10)
            })
    
    conn.close()
    return jsonify({'success': True, 'detected': detected})


# ============ BUDGET APIS ============

@app.route('/api/budgets', methods=['GET', 'POST'])
@login_required
def api_budgets():
    user_id = session['user_id']
    
    if request.method == 'GET':
        conn = get_db('expenses')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM budgets WHERE user_id = ? AND is_active = 1", (user_id,))
        budgets = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify({'success': True, 'budgets': budgets})
    
    elif request.method == 'POST':
        data = request.json
        if not data or not data.get('amount'):
            return jsonify({'success': False, 'error': 'Amount required'}), 400
        
        conn = get_db('expenses')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO budgets (user_id, category, amount, period, alert_threshold)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, data.get('category', 'Overall'), data['amount'],
              data.get('period', 'monthly'), data.get('alert_threshold', 80)))
        budget_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'id': budget_id, 'message': 'Budget created'})


@app.route('/api/budgets/<int:budget_id>', methods=['PUT', 'DELETE'])
@login_required
def api_budget_detail(budget_id):
    user_id = session['user_id']
    conn = get_db('expenses')
    cursor = conn.cursor()
    
    if request.method == 'DELETE':
        cursor.execute("DELETE FROM budgets WHERE id = ? AND user_id = ?", (budget_id, user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Budget deleted'})
    
    elif request.method == 'PUT':
        data = request.json
        cursor.execute('''
            UPDATE budgets SET category=?, amount=?, period=?, alert_threshold=?, is_active=?
            WHERE id=? AND user_id=?
        ''', (data.get('category'), data.get('amount'), data.get('period'),
              data.get('alert_threshold', 80), data.get('is_active', 1), budget_id, user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Budget updated'})


@app.route('/api/budgets/status', methods=['GET'])
@login_required
def api_budget_status():
    """Get current spending vs budget for all budgets"""
    user_id = session['user_id']
    conn = get_db('expenses')
    cursor = conn.cursor()
    
    now = datetime.now()
    month_start = now.strftime('%Y-%m-01')
    if now.month >= 4:
        fy_start = f'{now.year}-04-01'
    else:
        fy_start = f'{now.year-1}-04-01'
    
    cursor.execute("SELECT * FROM budgets WHERE user_id = ? AND is_active = 1", (user_id,))
    budgets = cursor.fetchall()
    
    status_list = []
    for budget in budgets:
        period_start = month_start if budget['period'] == 'monthly' else fy_start
        
        if budget['category'] == 'Overall':
            cursor.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE user_id = ? AND expense_date >= ?",
                (user_id, period_start))
        else:
            cursor.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE user_id = ? AND category = ? AND expense_date >= ?",
                (user_id, budget['category'], period_start))
        
        result = cursor.fetchone()
        spent = result['total'] if result else 0
        percentage = (spent / budget['amount'] * 100) if budget['amount'] > 0 else 0
        
        status_list.append({
            'id': budget['id'],
            'category': budget['category'],
            'budget_amount': budget['amount'],
            'spent': spent,
            'remaining': max(0, budget['amount'] - spent),
            'percentage': round(percentage, 1),
            'period': budget['period'],
            'status': 'exceeded' if percentage >= 100 else 'warning' if percentage >= budget['alert_threshold'] else 'ok'
        })
    
    conn.close()
    return jsonify({'success': True, 'budgets': status_list})


# ============ BILL REMINDER APIS ============

@app.route('/api/reminders', methods=['GET', 'POST'])
@login_required
def api_reminders():
    user_id = session['user_id']
    
    if request.method == 'GET':
        conn = get_db('expenses')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bill_reminders WHERE user_id = ? ORDER BY due_date ASC", (user_id,))
        reminders = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify({'success': True, 'reminders': reminders})
    
    elif request.method == 'POST':
        data = request.json
        if not data or not data.get('title') or not data.get('due_date'):
            return jsonify({'success': False, 'error': 'Title and due date required'}), 400
        
        conn = get_db('expenses')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO bill_reminders (user_id, title, amount, due_date, recurrence, category, notify_days_before, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, data['title'], data.get('amount', 0), data['due_date'],
              data.get('recurrence', 'none'), data.get('category', 'Utilities & Bills'),
              data.get('notify_days_before', 3), data.get('notes', '')))
        reminder_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'id': reminder_id, 'message': 'Reminder created'})


@app.route('/api/reminders/<int:reminder_id>', methods=['PUT', 'DELETE'])
@login_required
def api_reminder_detail(reminder_id):
    user_id = session['user_id']
    conn = get_db('expenses')
    cursor = conn.cursor()
    
    if request.method == 'DELETE':
        cursor.execute("DELETE FROM bill_reminders WHERE id = ? AND user_id = ?", (reminder_id, user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Reminder deleted'})
    
    elif request.method == 'PUT':
        data = request.json
        cursor.execute('''
            UPDATE bill_reminders SET title=?, amount=?, due_date=?, recurrence=?, category=?,
            is_paid=?, notify_days_before=?, notes=? WHERE id=? AND user_id=?
        ''', (data.get('title'), data.get('amount'), data.get('due_date'), data.get('recurrence'),
              data.get('category'), data.get('is_paid', 0), data.get('notify_days_before', 3),
              data.get('notes', ''), reminder_id, user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Reminder updated'})


# ============ CALENDAR EVENTS API ============

@app.route('/api/calendar/events', methods=['GET'])
@login_required
def api_calendar_events():
    """Aggregate all financial events for calendar view"""
    user_id = session['user_id']
    start = request.args.get('start', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    end = request.args.get('end', (datetime.now() + timedelta(days=60)).strftime('%Y-%m-%d'))
    
    conn = get_db('expenses')
    cursor = conn.cursor()
    events = []
    
    # Bill reminders
    cursor.execute("SELECT * FROM bill_reminders WHERE user_id = ? AND due_date BETWEEN ? AND ?",
                   (user_id, start, end))
    for r in cursor.fetchall():
        events.append({
            'id': f'bill_{r["id"]}', 'title': f'💡 {r["title"]}',
            'date': r['due_date'], 'type': 'bill', 'amount': r['amount'],
            'color': '#118AB2', 'is_paid': r['is_paid']
        })
    
    # Subscription renewals
    cursor.execute("SELECT * FROM subscriptions WHERE user_id = ? AND is_active = 1 AND next_due_date BETWEEN ? AND ?",
                   (user_id, start, end))
    for s in cursor.fetchall():
        events.append({
            'id': f'sub_{s["id"]}', 'title': f'🔄 {s["name"]}',
            'date': s['next_due_date'], 'type': 'subscription', 'amount': s['amount'],
            'color': '#7209B7'
        })
    
    # Past expenses
    cursor.execute("SELECT * FROM expenses WHERE user_id = ? AND expense_date BETWEEN ? AND ? ORDER BY expense_date",
                   (user_id, start, end))
    for e in cursor.fetchall():
        events.append({
            'id': f'exp_{e["id"]}', 'title': f'💸 {e["merchant"] or e["category"]}',
            'date': e['expense_date'], 'type': 'expense', 'amount': e['amount'],
            'color': '#EF476F'
        })
    
    conn.close()
    return jsonify({'success': True, 'events': events})


# ============ INVESTMENT APIS ============

@app.route('/api/investments', methods=['GET', 'POST'])
@login_required
def api_investments():
    user_id = session['user_id']
    
    if request.method == 'GET':
        conn = get_db('expenses')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM investments WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        investments = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify({'success': True, 'investments': investments})
    
    elif request.method == 'POST':
        data = request.json
        if not data or not data.get('name') or not data.get('amount_invested'):
            return jsonify({'success': False, 'error': 'Name and amount required'}), 400
        
        conn = get_db('expenses')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO investments (user_id, name, type, amount_invested, current_value,
            purchase_date, maturity_date, returns_percent, platform, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, data['name'], data.get('type', 'Mutual Fund'), data['amount_invested'],
              data.get('current_value', data['amount_invested']), data.get('purchase_date'),
              data.get('maturity_date'), data.get('returns_percent', 0),
              data.get('platform', ''), data.get('notes', '')))
        inv_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'id': inv_id, 'message': 'Investment added'})


@app.route('/api/investments/<int:inv_id>', methods=['PUT', 'DELETE'])
@login_required
def api_investment_detail(inv_id):
    user_id = session['user_id']
    conn = get_db('expenses')
    cursor = conn.cursor()
    
    if request.method == 'DELETE':
        cursor.execute("DELETE FROM investments WHERE id = ? AND user_id = ?", (inv_id, user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Investment deleted'})
    
    elif request.method == 'PUT':
        data = request.json
        cursor.execute('''
            UPDATE investments SET name=?, type=?, amount_invested=?, current_value=?,
            purchase_date=?, maturity_date=?, returns_percent=?, platform=?, notes=?, is_active=?
            WHERE id=? AND user_id=?
        ''', (data.get('name'), data.get('type'), data.get('amount_invested'), data.get('current_value'),
              data.get('purchase_date'), data.get('maturity_date'), data.get('returns_percent', 0),
              data.get('platform', ''), data.get('notes', ''), data.get('is_active', 1), inv_id, user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Investment updated'})


@app.route('/api/investments/summary', methods=['GET'])
@login_required
def api_investment_summary():
    user_id = session['user_id']
    conn = get_db('expenses')
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM investments WHERE user_id = ? AND is_active = 1", (user_id,))
    investments = cursor.fetchall()
    
    total_invested = sum(i['amount_invested'] for i in investments)
    total_current = sum((i['current_value'] or i['amount_invested']) for i in investments)
    total_pl = total_current - total_invested
    pl_percent = (total_pl / total_invested * 100) if total_invested > 0 else 0
    
    by_type = {}
    for inv in investments:
        t = inv['type']
        if t not in by_type:
            by_type[t] = {'invested': 0, 'current': 0, 'count': 0}
        by_type[t]['invested'] += inv['amount_invested']
        by_type[t]['current'] += (inv['current_value'] or inv['amount_invested'])
        by_type[t]['count'] += 1
    
    conn.close()
    return jsonify({
        'success': True,
        'total_invested': total_invested, 'total_current': total_current,
        'total_pl': total_pl, 'pl_percent': round(pl_percent, 2),
        'by_type': by_type, 'count': len(investments)
    })


# ============ NOTIFICATION APIS ============

@app.route('/api/notifications', methods=['GET'])
@login_required
def api_notifications():
    user_id = session['user_id']
    limit = request.args.get('limit', 50, type=int)
    
    conn = get_db('expenses')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                   (user_id, limit))
    notifs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify({'success': True, 'notifications': notifs})


@app.route('/api/notifications/unread-count', methods=['GET'])
@login_required
def api_notifications_unread():
    user_id = session['user_id']
    conn = get_db('expenses')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM notifications WHERE user_id = ? AND is_read = 0", (user_id,))
    count = cursor.fetchone()['count']
    conn.close()
    return jsonify({'success': True, 'count': count})


@app.route('/api/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def api_notification_read(notif_id):
    user_id = session['user_id']
    conn = get_db('expenses')
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?", (notif_id, user_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/notifications/read-all', methods=['POST'])
@login_required
def api_notifications_read_all():
    user_id = session['user_id']
    conn = get_db('expenses')
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'All notifications marked as read'})


# ============ GST TRACKING APIS ============

@app.route('/api/gst/summary', methods=['GET'])
@login_required
def api_gst_summary():
    user_id = session['user_id']
    period = request.args.get('period', 'month')
    
    conn = get_db('expenses')
    cursor = conn.cursor()
    
    now = datetime.now()
    if period == 'fy':
        if now.month >= 4:
            start_date = f'{now.year}-04-01'
        else:
            start_date = f'{now.year-1}-04-01'
    else:
        start_date = now.strftime('%Y-%m-01')
    
    # From expenses
    cursor.execute('''
        SELECT COALESCE(SUM(gst_amount), 0) as total_gst, COUNT(*) as count
        FROM expenses WHERE user_id = ? AND gst_amount > 0 AND expense_date >= ?
    ''', (user_id, start_date))
    expense_gst = cursor.fetchone()
    
    # From GST records
    cursor.execute('''
        SELECT COALESCE(SUM(cgst), 0) as total_cgst, COALESCE(SUM(sgst), 0) as total_sgst,
               COALESCE(SUM(igst), 0) as total_igst, COALESCE(SUM(total_gst), 0) as total_gst
        FROM gst_records WHERE user_id = ? AND created_at >= ?
    ''', (user_id, start_date))
    gst_data = cursor.fetchone()
    
    # Top GST-paying categories
    cursor.execute('''
        SELECT category, SUM(gst_amount) as gst FROM expenses
        WHERE user_id = ? AND gst_amount > 0 AND expense_date >= ?
        GROUP BY category ORDER BY gst DESC LIMIT 5
    ''', (user_id, start_date))
    top_categories = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    return jsonify({
        'success': True,
        'total_gst_from_expenses': expense_gst['total_gst'],
        'gst_expense_count': expense_gst['count'],
        'cgst': gst_data['total_cgst'], 'sgst': gst_data['total_sgst'],
        'igst': gst_data['total_igst'], 'total_gst_records': gst_data['total_gst'],
        'top_categories': top_categories, 'period': period
    })


@app.route('/api/gst/records', methods=['POST'])
@login_required
def api_gst_record():
    user_id = session['user_id']
    data = request.json
    
    conn = get_db('expenses')
    cursor = conn.cursor()
    total = (data.get('cgst', 0) or 0) + (data.get('sgst', 0) or 0) + (data.get('igst', 0) or 0)
    cursor.execute('''
        INSERT INTO gst_records (user_id, expense_id, gstin, cgst, sgst, igst, total_gst, invoice_number)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, data.get('expense_id'), data.get('gstin', ''),
          data.get('cgst', 0), data.get('sgst', 0), data.get('igst', 0),
          total, data.get('invoice_number', '')))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'GST record added'})


# ============ ACCOUNT & PLAN APIS ============

@app.route('/api/account/plan', methods=['GET'])
@login_required
def api_account_plan():
    user_id = session['user_id']
    conn = get_db('expenses')
    cursor = conn.cursor()
    cursor.execute("SELECT account_type FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    plan = (user['account_type'] if user else 'free') or 'free'
    plans = {
        'free': {'name': 'Free', 'budgets': 3, 'investments': False, 'gst': False, 'family': False, 'telegram': False, 'advanced_analytics': False},
        'premium': {'name': 'Premium', 'budgets': -1, 'investments': True, 'gst': False, 'family': False, 'telegram': True, 'advanced_analytics': True},
        'business': {'name': 'Business', 'budgets': -1, 'investments': True, 'gst': True, 'family': False, 'telegram': True, 'advanced_analytics': True},
        'family': {'name': 'Family', 'budgets': -1, 'investments': True, 'gst': False, 'family': True, 'telegram': True, 'advanced_analytics': True}
    }
    
    return jsonify({'success': True, 'current_plan': plan, 'features': plans.get(plan, plans['free']), 'all_plans': plans})


@app.route('/api/account/upgrade', methods=['POST'])
@login_required
def api_account_upgrade():
    user_id = session['user_id']
    data = request.json
    new_plan = data.get('plan', 'premium')
    
    if new_plan not in ['free', 'premium', 'business', 'family']:
        return jsonify({'success': False, 'error': 'Invalid plan'}), 400
    
    conn = get_db('expenses')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET account_type = ? WHERE id = ?", (new_plan, user_id))
    conn.commit()
    conn.close()
    
    _create_notification(user_id, 'success', '🎉 Plan Upgraded!',
                         f'Your account has been upgraded to {new_plan.title()} plan. Enjoy the new features!',
                         '/settings')
    
    return jsonify({'success': True, 'message': f'Upgraded to {new_plan}', 'plan': new_plan})


# ============ USER PREFERENCES APIS ============

@app.route('/api/user/preferences', methods=['GET', 'PUT'])
@login_required
def api_user_preferences():
    user_id = session['user_id']
    conn = get_db('expenses')
    cursor = conn.cursor()
    
    if request.method == 'GET':
        cursor.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,))
        prefs = cursor.fetchone()
        if not prefs:
            cursor.execute("INSERT INTO user_preferences (user_id) VALUES (?)", (user_id,))
            conn.commit()
            cursor.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,))
            prefs = cursor.fetchone()
        conn.close()
        return jsonify({'success': True, 'preferences': dict(prefs)})
    
    elif request.method == 'PUT':
        data = request.json
        cursor.execute("SELECT id FROM user_preferences WHERE user_id = ?", (user_id,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO user_preferences (user_id) VALUES (?)", (user_id,))
        
        cursor.execute('''
            UPDATE user_preferences SET budget_alerts=?, bill_reminders=?, spending_alerts=?,
            weekly_summary=?, telegram_enabled=?, telegram_chat_id=?, alert_threshold=?
            WHERE user_id=?
        ''', (data.get('budget_alerts', 1), data.get('bill_reminders', 1),
              data.get('spending_alerts', 1), data.get('weekly_summary', 1),
              data.get('telegram_enabled', 0), data.get('telegram_chat_id', ''),
              data.get('alert_threshold', 80), user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Preferences updated'})


# ============ FAMILY ACCOUNT APIS ============

@app.route('/api/family/members', methods=['GET', 'POST'])
@login_required
def api_family_members():
    user_id = session['user_id']
    conn = get_db('expenses')
    cursor = conn.cursor()
    
    if request.method == 'GET':
        cursor.execute('''
            SELECT fm.*, u.username, u.email FROM family_members fm
            JOIN users u ON fm.member_user_id = u.id
            WHERE fm.owner_id = ?
        ''', (user_id,))
        members = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify({'success': True, 'members': members})
    
    elif request.method == 'POST':
        data = request.json
        username = data.get('username', '').strip()
        
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        member = cursor.fetchone()
        if not member:
            conn.close()
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        if member['id'] == user_id:
            conn.close()
            return jsonify({'success': False, 'error': 'Cannot add yourself'}), 400
        
        try:
            cursor.execute('''
                INSERT INTO family_members (owner_id, member_user_id, role, can_view, can_edit)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, member['id'], data.get('role', 'member'),
                  data.get('can_view', 1), data.get('can_edit', 0)))
            conn.commit()
        except:
            conn.close()
            return jsonify({'success': False, 'error': 'Member already added'}), 400
        
        conn.close()
        _create_notification(member['id'], 'info', '👨‍👩‍👧‍👦 Family Invitation',
                             f'You have been added to a family account by {session.get("username")}', '/settings')
        return jsonify({'success': True, 'message': f'{username} added to family'})


@app.route('/api/family/members/<int:member_id>', methods=['DELETE'])
@login_required
def api_family_member_delete(member_id):
    user_id = session['user_id']
    conn = get_db('expenses')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM family_members WHERE id = ? AND owner_id = ?", (member_id, user_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Member removed'})


# ============ NEW PAGE ROUTES ============

@app.route('/subscriptions')
@login_required
def subscriptions_page():
    username = session.get('username', '')
    return render_template('subscriptions.html', logged_in=True, username=username)

@app.route('/budgets')
@login_required
def budgets_page():
    username = session.get('username', '')
    return render_template('budgets.html', logged_in=True, username=username)

@app.route('/investments')
@login_required
def investments_page():
    username = session.get('username', '')
    return render_template('investments.html', logged_in=True, username=username)

@app.route('/calendar')
@login_required
def calendar_page():
    username = session.get('username', '')
    return render_template('calendar.html', logged_in=True, username=username)

@app.route('/notifications')
@login_required
def notifications_page():
    username = session.get('username', '')
    return render_template('notifications.html', logged_in=True, username=username)


# ============ ERROR HANDLERS ============

@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

# ============ STARTUP AND SHUTDOWN ============

def on_startup():
    """Initialize on startup"""
    print("=" * 60)
    print("₹ SMARTMAIL EXPENSE TRACKER (INDIAN EDITION)")
    print("=" * 60)
    print("Server running on: http://localhost:5000")
    print("\nFeatures:")
    print("  ✅ Indian Rupee (₹) as default currency")
    print("  ✅ Indian merchant detection (Zomato, Flipkart, IRCTC...)")
    print("  ✅ UPI / Credit Card / Net Banking tracking")
    print("  ✅ GST amount extraction")
    print("  ✅ Auto email sync every 1 minute (no manual sync)")
    print("  ✅ Spam/promotional email filtering")
    print("  ✅ Confidence scoring for extracted expenses")
    print("  ✅ Chart.js powered analytics dashboard")
    print("=" * 60)
    
    real_email_sync_service.start()

def on_shutdown():
    """Cleanup on shutdown"""
    print("\n🛑 Shutting down SmartMail Expense Tracker...")
    real_email_sync_service.stop()
    print("✅ Clean shutdown complete")

atexit.register(on_shutdown)

def signal_handler(sig, frame):
    print('\n\n👋 Received shutdown signal. Goodbye!')
    on_shutdown()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == '__main__':
    on_startup()
    try:
        app.run(debug=True, port=5000, use_reloader=False)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        on_shutdown()