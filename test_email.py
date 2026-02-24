# test_email.py
from email_processor import EmailProcessor

# Replace with YOUR actual email and app password
EMAIL = "demo05122004@gmail.com"
APP_PASSWORD = "ecdwkdtjycxchmhd"  # Example: "abcd efgh ijkl mnop"

print("🧪 TESTING EMAIL CONNECTION...")
print(f"Email: {EMAIL}")
print("=" * 50)

processor = EmailProcessor(
    imap_server='imap.gmail.com',
    imap_port=993,
    username=EMAIL,
    password=APP_PASSWORD
)

print("\n1. Testing connection...")
if processor.connect():
    print("✅ Connection successful!")
    
    print("\n2. Fetching unread emails from last day...")
    emails = processor.get_unread_emails(days=1)
    
    if emails:
        print(f"✅ Found {len(emails)} email(s)")
        print("\n3. Extracting expenses...")
        
        for i, email_data in enumerate(emails, 1):
            print(f"\n   Email #{i}:")
            print(f"   Subject: {email_data['subject'][:80]}...")
            print(f"   From: {email_data['sender'][:50]}")
            
            expense = processor.extract_expense_data(email_data)
            if expense:
                print(f"   💰 EXPENSE FOUND: ${expense['amount']}")
                print(f"   🏪 Merchant: {expense['merchant']}")
                print(f"   📁 Category: {expense['category']}")
            else:
                print("   ⚠️ No expense data found in this email")
    else:
        print("⚠️ No unread emails found in the last day")
    
    processor.disconnect()
    print("\n✅ Test completed!")
else:
    print("❌ Connection failed!")
    
print("=" * 50)