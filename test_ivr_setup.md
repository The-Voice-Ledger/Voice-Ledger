# IVR Setup Test Guide

## What We've Implemented

✅ **Database**: Added `phone_number` field to `user_identities` table
✅ **User Registration**: `/start` now asks users to share their phone number
✅ **Contact Handler**: When users share contact, phone is stored and verified
✅ **IVR Authentication**: Phone-based authentication ready for IVR calls

## Setup Steps

### 1. Apply Database Migration

```bash
cd /Users/manu/Voice-Ledger

# Apply the migration
python -c "
from sqlalchemy import text
from database.connection import engine

with open('database/migrations/009_add_phone_to_users.sql', 'r') as f:
    sql = f.read()
    
with engine.connect() as conn:
    # Execute each statement separately
    for statement in sql.split(';'):
        if statement.strip():
            conn.execute(text(statement))
    conn.commit()

print('✅ Migration applied!')
"
```

### 2. Restart Your Server

```bash
# Stop current server (Ctrl+C)

# Restart
python -m voice.service.api
```

### 3. Test Telegram Registration Flow

**A. New User Registration:**

1. Open Telegram and send `/start` to `@voice_ledger_bot`
2. Bot should ask: "Please share your phone number"
3. Click "📱 Share Phone Number" button
4. Bot confirms: "✅ Registration complete! Phone: +XX..."

**B. Check Database:**

```bash
python -c "
from database.models import SessionLocal, UserIdentity

db = SessionLocal()
users = db.query(UserIdentity).filter(UserIdentity.phone_number.isnot(None)).all()

print(f'Users with phone numbers: {len(users)}\n')
for u in users[:5]:
    print(f'  - {u.telegram_username}: {u.phone_number}')
db.close()
"
```

### 4. Configure Twilio Webhooks

Go to: https://console.twilio.com/us1/develop/phone-numbers/manage/incoming

Find your number: **+41 62 539 1661**

**Set Webhooks:**

```
Voice Configuration:
  A CALL COMES IN: 
    Webhook: https://briary-torridly-raul.ngrok-free.dev/voice/ivr/incoming
    HTTP: POST
```

### 5. Test IVR Call Flow

**Test A: Unregistered Phone (Should REJECT)**

1. Call +41 62 539 1661 from a phone that's NOT registered
2. Expected: "Please register via Telegram first: @voice_ledger_bot"
3. Call should end

**Test B: Registered Phone (Should ACCEPT)**

1. Register your phone via Telegram (step 3)
2. Call +41 62 539 1661 from that same phone
3. Expected: "Welcome [YourName]! After the beep, speak clearly..."
4. Record your voice command
5. Receive SMS confirmation with batch ID

### 6. End-to-End Test

```bash
# 1. Register via Telegram
Send /start → Share phone: +41774855288

# 2. Call IVR
Dial: +41 62 539 1661
Say: "I harvested 50 kilograms of Yirgacheffe coffee from Gedeo"

# 3. Check batch was created
python -c "
from database.models import SessionLocal, CoffeeBatch, UserIdentity

db = SessionLocal()
user = db.query(UserIdentity).filter_by(phone_number='+41774855288').first()
if user:
    batches = db.query(CoffeeBatch).filter_by(farmer_id=user.id).all()
    print(f'✅ User {user.telegram_username} has {len(batches)} batches')
    for b in batches[-3:]:
        print(f'  - {b.batch_id}: {b.quantity_kg}kg {b.variety}')
else:
    print('❌ User not found')
db.close()
"
```

## Authentication Flow

```
┌─────────────────────────────────────────┐
│ 1. User calls +41 62 539 1661           │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│ 2. Twilio → POST /voice/ivr/incoming    │
│    Params: From=+41774855288            │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│ 3. Look up phone in database:           │
│    SELECT * FROM user_identities        │
│    WHERE phone_number = '+41774855288'  │
└─────────────┬───────────────────────────┘
              │
         ┌────┴────┐
         │         │
    NOT FOUND    FOUND
         │         │
         ▼         ▼
    ┌─────────┐ ┌──────────────────────┐
    │ REJECT  │ │ ACCEPT               │
    │ "Please │ │ "Welcome [Name]!"    │
    │ register│ │ Record voice →       │
    │ first"  │ │ Create batch with    │
    │         │ │ user's DID           │
    └─────────┘ └──────────────────────┘
```

## Troubleshooting

### Error: "Duplicate phone number"
- Phone already registered to another Telegram account
- Each phone can only be used once
- User needs to use original Telegram account

### Error: "User not found" during IVR call
- User didn't share phone via Telegram
- Phone format mismatch (E.164 vs local)
- Ask user to send `/start` and share contact again

### Error: "Webhook failed"
- Check ngrok is running: `ngrok http 8000`
- Verify NGROK_URL in .env matches current tunnel
- Check server logs: `tail -f logs/voice_api.log`

## Next Steps

Once testing is complete:

1. **Production Webhook**: Replace ngrok URL with permanent domain
2. **Phone Verification**: Add SMS code verification (optional security layer)
3. **Multi-Phone Support**: Allow users to register multiple phones (e.g., work + personal)
4. **Admin Dashboard**: View all registered phones and IVR call history

## Summary

✅ **Simple Phone Registration**: Users share contact via Telegram button
✅ **Automatic**: Phone extracted and stored in E.164 format
✅ **Secure**: IVR calls authenticated by phone number
✅ **Traceable**: All batches linked to verified user DIDs
