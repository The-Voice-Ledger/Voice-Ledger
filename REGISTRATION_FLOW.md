# Registration Flow Summary

## Two-Tier Registration System

### Tier 1: `/start` - Basic Registration (All Users)

**Purpose:** Get user into the system with phone number for IVR access

**Flow:**
```
1. User sends: /start
2. System checks: Does user exist?
   
   NO → Request phone number:
         "📱 Please share your phone number"
         [Share Phone Number button]
         
   YES (with phone) → Show welcome message
   
   YES (no phone) → Request phone number
   
3. User clicks "Share Phone Number"
4. System creates UserIdentity:
   - telegram_user_id
   - telegram_username
   - telegram_first_name, telegram_last_name
   - phone_number ✅
   - phone_verified_at
   - did (auto-generated)
   - role = 'FARMER' (default)
   
5. User can now:
   ✅ Send voice messages in Telegram
   ✅ Call IVR: +41 62 539 1661
   ✅ Receive SMS notifications
   ✅ Create batches (farmer role)
```

### Tier 2: `/register` - Advanced Roles (Managers/Exporters/Buyers)

**Purpose:** Request elevated permissions for verification or supply chain roles

**Prerequisite:** Must have completed `/start` first

**Flow:**
```
1. User sends: /register
2. System checks: Does user exist?
   
   NO → Redirect to /start:
        "👋 Please send /start first to complete basic registration"
        
   YES → Continue to role selection
   
3. System checks: User role?
   
   role = FARMER && is_approved = TRUE:
     → Show language selection (English/Amharic)
     → Show role selection (COOPERATIVE_MANAGER/EXPORTER/BUYER)
     
   role != FARMER && is_approved = TRUE:
     → "✅ Already registered as: [ROLE]"
     
   status = PENDING:
     → "⏳ Pending Registration: REG-0042"
     
4. Registration conversation (7-8 questions):
   - Language preference (en/am)
   - Role (COOPERATIVE_MANAGER, EXPORTER, BUYER)
   - Full name
   - Organization name
   - Location
   - Phone number → REUSES from /start if exists! ✅
   - Registration number (optional)
   - Reason for registering
   
   [Role-specific questions for EXPORTER/BUYER]
   
5. System creates PendingRegistration record
6. Admin receives notification
7. Admin approves via /admin or web dashboard
8. User receives notification: "✅ Approved as COOPERATIVE_MANAGER"
9. User can now:
   ✅ Verify batches (/verify command)
   ✅ Issue credentials on behalf of cooperative
   ✅ Access manager-specific features
```

## Key Design Decisions

### ✅ No Duplication
- Phone collected ONCE in `/start`
- `/register` reuses phone from user_identities
- Fallback: If no phone in `/start`, `/register` will ask

### ✅ Separation of Concerns
- `/start` = Identity creation + IVR access
- `/register` = Role elevation + organizational affiliation

### ✅ Progressive Enhancement
- Farmers: Just need `/start` → can immediately use system
- Managers: Need `/start` + `/register` + admin approval
- Exporters/Buyers: Same as managers

## Database State

### After `/start`:
```sql
user_identities {
  telegram_user_id: "5753848438"
  phone_number: "+41774855288"
  phone_verified_at: "2025-12-21 10:30:00"
  did: "did:key:z6Mk..."
  role: "FARMER"  -- default
  is_approved: TRUE
  organization_id: NULL
}
```

### After `/register` (PENDING):
```sql
user_identities {
  -- Same as above, unchanged
}

pending_registrations {
  telegram_user_id: "5753848438"
  requested_role: "COOPERATIVE_MANAGER"
  full_name: "Abebe Bikila"
  organization_name: "Yirgacheffe Cooperative"
  location: "Gedeo Zone"
  phone_number: "+41774855288"  -- copied from user_identities
  status: "PENDING"
}
```

### After Admin Approval:
```sql
organizations {
  id: 1
  name: "Yirgacheffe Cooperative"
  type: "COOPERATIVE"
  did: "did:key:z6Mk..."  -- org DID
}

user_identities {
  telegram_user_id: "5753848438"
  phone_number: "+41774855288"
  did: "did:key:z6Mk..."
  role: "COOPERATIVE_MANAGER"  -- updated
  is_approved: TRUE
  organization_id: 1  -- linked
}

pending_registrations {
  status: "APPROVED"  -- updated
  reviewed_by_admin_id: 5753848438
  reviewed_at: "2025-12-21 11:00:00"
}
```

## IVR Authentication

When someone calls +41 62 539 1661:

```python
# 1. Extract phone from Twilio
from_number = "+41774855288"

# 2. Look up in database
user = db.query(UserIdentity).filter_by(
    phone_number=from_number
).first()

# 3. Authenticate
if not user:
    return TwiML("Please register via Telegram: @voice_ledger_bot")
    
if not user.is_approved:
    return TwiML("Your account is pending approval")

# 4. Proceed with voice recording
return TwiML(f"Welcome {user.telegram_first_name}! Record after beep...")

# 5. When recording complete, link to user
batch = create_batch(
    farmer_id=user.id,
    created_by_did=user.did,
    created_by_user_id=user.id
)
```

## Edge Cases Handled

### User hasn't done `/start` but tries `/register`:
```
Response: "👋 Please send /start first..."
```

### User shares phone twice (different number):
```
System updates to new phone_number
phone_verified_at updated to NOW()
```

### Phone already registered to another account:
```
Error: "❌ This phone number is already registered"
UNIQUE constraint prevents duplicates
```

### User completes `/register` then shares new phone via `/start`:
```
System updates phone_number in user_identities
pending_registrations phone_number NOT updated (snapshot)
Admin sees original phone at time of registration
```

## Testing Checklist

- [ ] New user: `/start` → Share phone → Success
- [ ] Existing user: `/start` → Welcome message (no phone request)
- [ ] New user: `/register` → Redirect to `/start`
- [ ] Farmer: `/register` → Reuses phone → No phone question
- [ ] Farmer without phone: `/register` → Still asks for phone (fallback)
- [ ] IVR call (registered phone) → Accepted
- [ ] IVR call (unregistered phone) → Rejected
- [ ] Duplicate phone → Error message
- [ ] Phone update → Updates in database
