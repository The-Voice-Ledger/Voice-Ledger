# Registration State Loss Issue - Root Cause Analysis
**Date:** December 22, 2025  
**Severity:** 🔴 CRITICAL - Users lose registration progress  
**Status:** Identified, Solution Required

---

## Issue Summary

**Symptom:** User starts registration via `/register`, uploads farm photo when prompted, but receives "Session expired" error and must restart from beginning.

**Root Cause:** Registration state stored in-memory gets cleared when:
1. API server restarts
2. Code changes trigger auto-reload (development mode)
3. Server crashes or is redeployed

**Impact:**
- **User Frustration**: Must restart entire registration process
- **Data Loss**: All collected information (name, org, location, phone, PIN) lost
- **Poor UX**: Unpredictable behavior, users don't understand why session expired
- **Production Risk**: Same issue will occur in production during deployments

---

## Technical Details

### Current Architecture

**File:** `voice/telegram/register_handler.py` line 18

```python
# In-memory conversation state storage (for webhook mode)
# In production, could use Redis for persistence across server restarts
conversation_states: Dict[int, Dict[str, Any]] = {}
```

**How It Works:**
1. User sends `/register`
2. System creates entry in `conversation_states[user_id]`
3. Stores state (STATE_LANGUAGE, STATE_ROLE, etc.) + collected data
4. User progresses through states (language → role → name → org → location → phone → **PIN** → photo)
5. Photo upload triggers `handle_farm_photo_upload()` which checks `conversation_states[user_id]`
6. If found → process photo, if NOT found → "Session expired"

**Registration Flow States:**
```python
STATE_NONE = 0
STATE_LANGUAGE = 1
STATE_ROLE = 2
STATE_FULL_NAME = 3
STATE_ORG_NAME = 4
STATE_LOCATION = 5
STATE_PHONE = 6
STATE_SET_PIN = 7       # NEW (v1.7)
STATE_CONFIRM_PIN = 8    # NEW (v1.7)
STATE_REG_NUMBER = 9
STATE_REASON = 10
STATE_EXPORT_LICENSE = 11
STATE_PORT_ACCESS = 12
STATE_SHIPPING_CAPACITY = 13
STATE_BUSINESS_TYPE = 14
STATE_COUNTRY = 15
STATE_TARGET_VOLUME = 16
STATE_QUALITY_PREFS = 17
STATE_UPLOAD_FARM_PHOTO = 18  # ⚠️ Long-lived state where users get stuck
STATE_VERIFY_GPS = 19
```

### What Gets Stored

**Per-User State:**
```python
conversation_states[user_id] = {
    'state': 18,  # STATE_UPLOAD_FARM_PHOTO
    'data': {
        'telegram_username': 'john_doe',
        'telegram_first_name': 'John',
        'telegram_last_name': 'Doe',
        'preferred_language': 'en',
        'role': 'FARMER',
        'full_name': 'John Doe',
        'organization_name': 'Sidama Coffee Coop',
        'location': 'Hawassa, Ethiopia',
        'phone_number': '+251911234567',
        'pin_hash': '$2b$12$...',  # Bcrypt hash
        'temp_pin': None  # Cleared after confirmation
        # farm_photo added after upload
    }
}
```

**Size:** ~500 bytes per user  
**Lifetime:** Until server restart or code reload  
**Persistence:** ❌ NONE

---

## When State Is Lost

### Scenario 1: Development Code Changes (TODAY'S ISSUE)

**Evidence from logs:**
```
WARNING:  StatReload detected changes in 'voice/telegram/register_handler.py'. Reloading...
✅ IVR endpoints registered at /voice/ivr/*
✅ Telegram endpoints registered at /voice/telegram/*
...
```

**What Happened:**
1. User started registration at 20:45:00
2. We modified `register_handler.py` for PIN integration at 20:50:00
3. Uvicorn auto-reloaded the application
4. All `conversation_states` cleared (new empty dict)
5. User uploaded photo at 20:55:00
6. System: "Session expired" (user_id not in conversation_states)

**Timeline:**
```
20:45:00 - User: /register (session created)
20:46:00 - User: Selects English
20:47:00 - User: Selects FARMER role
20:48:00 - User: Enters name "Abebe Bekele"
20:49:00 - User: Reaches STATE_UPLOAD_FARM_PHOTO
20:50:00 - DEV: Modifies register_handler.py (adds PIN states)
20:50:01 - SERVER: Auto-reload triggered
20:50:02 - SERVER: conversation_states = {} (empty!)
20:55:00 - User: Uploads farm photo
20:55:01 - SERVER: "❌ Session expired. Please /register again."
20:55:02 - User: 😡 Frustrated
```

### Scenario 2: Server Restart

**Frequency:** 
- Development: Multiple times per day
- Production: Weekly deployments, occasional crashes

**Impact:** ALL active registration sessions lost

### Scenario 3: Server Crash

**Causes:**
- Out of memory
- Unhandled exception
- Network issues
- Database connection loss

**Impact:** Partial data loss (user may have spent 10 minutes filling out form)

### Scenario 4: Load Balancer / Multiple Instances

**If deployed with multiple API instances:**
- User hits Instance A → creates session
- Next request hits Instance B → session not found
- Each instance has its own `conversation_states` dict

---

## User Experience Impact

### Time Lost Per Registration Failure

**Farmer Registration (Shortest):**
1. Language selection: 10 seconds
2. Role selection: 5 seconds
3. Farm photo upload: 30-60 seconds (walk to farm, take photo)
4. **Total:** ~1-2 minutes lost

**Manager/Exporter/Buyer Registration (Longest):**
1. Language: 10s
2. Role: 5s
3. Full name: 20s (typing on mobile)
4. Organization: 20s
5. Location: 20s
6. Phone: 15s (if not shared in /start)
7. **PIN setup: 30s** (NEW in v1.7 - 4 digits + confirmation)
8. **PIN confirmation: 15s**
9. Registration number: 30s
10. Reason: 60s (paragraph of text)
11. Role-specific questions: 60-120s
12. **Total:** ~4-6 minutes lost

**User Frustration Level:**
- 1st failure: Confused 😕
- 2nd failure: Annoyed 😠
- 3rd failure: Abandons registration 🚫

---

## Why This Is Critical

### 1. Registration Is Entry Point
- Users can't use system without registering
- First impression of Voice Ledger
- If broken → users don't come back

### 2. Long Multi-Step Process
- 8-11 states to complete (depending on role)
- Takes 2-6 minutes of focused attention
- Mobile users often interrupted (calls, messages)
- Photo upload requires physical movement (go to farm)

### 3. PIN Integration Makes It Worse (v1.7)
- Added 2 more states (SET_PIN, CONFIRM_PIN)
- Increases time to complete
- More chances for session to expire mid-flow

### 4. Production Deployments
- We deploy updates weekly
- Each deployment → all registrations lost
- Zero-downtime deployment still restarts workers

---

## Solutions (Ranked by Priority)

### Option 1: Redis-Based Session Storage (RECOMMENDED)

**Priority:** 🔴 CRITICAL  
**Time to Implement:** 2-3 hours  
**Complexity:** Medium

**Architecture:**
```python
# Use Redis instead of in-memory dict
import redis
import json

redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=0,
    decode_responses=True
)

def save_conversation_state(user_id: int, state_data: dict):
    """Save state to Redis with 24-hour expiry"""
    key = f"registration_state:{user_id}"
    redis_client.setex(
        key,
        86400,  # 24 hours
        json.dumps(state_data)
    )

def get_conversation_state(user_id: int) -> Optional[dict]:
    """Load state from Redis"""
    key = f"registration_state:{user_id}"
    data = redis_client.get(key)
    return json.loads(data) if data else None

def delete_conversation_state(user_id: int):
    """Remove state from Redis"""
    key = f"registration_state:{user_id}"
    redis_client.delete(key)
```

**Benefits:**
- ✅ Survives server restarts
- ✅ Survives code reloads
- ✅ Works across multiple instances (load balanced)
- ✅ Automatic expiry (24 hours)
- ✅ Fast (<1ms latency for local Redis)
- ✅ Easy to monitor (Redis CLI)

**Drawbacks:**
- ❌ Requires Redis installation
- ❌ Another dependency to manage
- ❌ Slightly more complex code

**Implementation Steps:**
1. Install Redis: `brew install redis` (Mac) or `apt-get install redis` (Linux)
2. Start Redis: `redis-server` or use Docker
3. Add python-redis: `pip install redis`
4. Replace dict operations with Redis calls
5. Add Redis connection health check
6. Update deployment docs

---

### Option 2: Database-Based Session Storage

**Priority:** 🟡 MEDIUM  
**Time to Implement:** 3-4 hours  
**Complexity:** Medium-High

**Architecture:**
```sql
-- New table
CREATE TABLE registration_sessions (
    id SERIAL PRIMARY KEY,
    telegram_user_id VARCHAR(50) UNIQUE NOT NULL,
    state INTEGER NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '24 hours'
);

CREATE INDEX idx_registration_sessions_telegram_user 
    ON registration_sessions(telegram_user_id);
CREATE INDEX idx_registration_sessions_expires 
    ON registration_sessions(expires_at) 
    WHERE expires_at > NOW();
```

**Benefits:**
- ✅ Survives all restarts
- ✅ No new infrastructure (already have PostgreSQL)
- ✅ Easy to query/debug
- ✅ Can add cleanup cron job

**Drawbacks:**
- ❌ Slower than Redis (~5-10ms vs <1ms)
- ❌ More database load
- ❌ Requires migration
- ❌ JSONB queries less intuitive

---

### Option 3: Client-Side State (Telegram Callback Data)

**Priority:** 🟢 LOW  
**Time to Implement:** 6-8 hours  
**Complexity:** High

**Idea:** Store state in Telegram inline keyboard callback data

```python
# Instead of:
'inline_keyboard': [
    [{'text': '🇺🇸 English', 'callback_data': 'reg_lang_en'}]
]

# Do:
'inline_keyboard': [
    [{'text': '🇺🇸 English', 'callback_data': json.dumps({
        'action': 'reg_lang',
        'value': 'en',
        'state': 1,
        'session_id': 'abc123'
    })}]
]
```

**Benefits:**
- ✅ No server state at all
- ✅ Survives any restart
- ✅ No Redis/DB needed

**Drawbacks:**
- ❌ Telegram callback_data limited to 64 bytes
- ❌ Can't store large data (full name, org, etc.)
- ❌ Doesn't work for text input (only buttons)
- ❌ Complex state reconstruction
- ❌ Security concerns (data in URLs)

---

### Option 4: Hybrid Approach

**Priority:** 🟢 LOW  
**Time to Implement:** 4-5 hours  
**Complexity:** Medium-High

**Combine:**
- Redis for active sessions (fast)
- Database for completed registrations (persistent)
- Automatic fallback if Redis unavailable

**Example:**
```python
def get_conversation_state(user_id: int) -> Optional[dict]:
    # Try Redis first (fast)
    try:
        return redis_get_state(user_id)
    except redis.ConnectionError:
        # Fallback to database
        logger.warning("Redis unavailable, using database")
        return db_get_state(user_id)
```

**Benefits:**
- ✅ Best of both worlds
- ✅ Resilient to Redis failures
- ✅ Can replay from database

**Drawbacks:**
- ❌ Most complex solution
- ❌ Harder to debug
- ❌ Data sync issues

---

## Immediate Workaround (Until Redis Implemented)

### Add Session Timeout Warning

**File:** `voice/telegram/register_handler.py`

```python
async def handle_register_command(user_id: int, ...):
    # After initializing state
    conversation_states[user_id] = {...}
    
    return {
        'message': (
            "🌍 *Welcome to Voice Ledger*\n\n"
            "Please select your preferred language for voice commands:\n"
            "የድምጽ ትዕዛዞችዎን ቋንቋ ይምረጡ:\n\n"
            "⏱️ _Note: Please complete registration in one session. "
            "If interrupted, you may need to start over._"  # ⚠️ Warning added
        ),
        ...
    }
```

### Add Session Recovery Prompt

```python
async def handle_farm_photo_upload(user_id: int, ...):
    if user_id not in conversation_states:
        return {
            'message': (
                "❌ *Session Expired*\n\n"
                "Your registration session has expired. This can happen if:\n"
                "• You took too long to complete registration\n"
                "• The server was restarted\n"
                "• You switched to another app for a while\n\n"
                "Please send /register to start over.\n\n"
                "💡 Tip: Complete registration in one sitting (takes 2-5 minutes)."
            ),
            'parse_mode': 'Markdown'
        }
```

---

## Recommended Implementation Plan

### Phase 1: Immediate (Today) ✅
- [x] Document the issue
- [x] Add session expiry warnings to UI
- [ ] Test registration flow end-to-end
- [ ] Monitor for more failures

### Phase 2: Short-Term (This Week) 🔴 HIGH PRIORITY
- [ ] Install Redis locally
- [ ] Implement Redis session storage
- [ ] Test with server restarts
- [ ] Update deployment docs
- [ ] Deploy to staging

### Phase 3: Medium-Term (Next Sprint)
- [ ] Add Redis to production infrastructure
- [ ] Deploy Redis-backed registration
- [ ] Monitor session persistence
- [ ] Add Redis metrics/alerts

### Phase 4: Long-Term (Optional)
- [ ] Consider hybrid Redis+DB approach
- [ ] Add session analytics (completion rates)
- [ ] Implement partial save/resume
- [ ] Add "Resume Registration" button

---

## Testing Checklist

### Before Redis Implementation
- [ ] Start registration
- [ ] Restart API server mid-flow
- [ ] Try to continue → Expect "Session expired"
- [ ] Verify error message is clear

### After Redis Implementation
- [ ] Start registration
- [ ] Restart API server mid-flow
- [ ] Continue registration → Should work!
- [ ] Complete registration successfully
- [ ] Verify data saved correctly
- [ ] Check Redis keys expire after 24h
- [ ] Test Redis connection failure (fallback?)

---

## Additional Considerations

### PIN Integration Impact (v1.7)

**Added Complexity:**
- 2 more states (SET_PIN, CONFIRM_PIN)
- PIN stored temporarily in session before hashing
- Security: PIN must not be logged or exposed

**Recommendation:**
- Redis implementation should encrypt sensitive data
- Clear PIN from session immediately after hashing
- Log session IDs, not session content

### Multi-Language Support

**Current:**
- Language stored in session: `preferred_language: 'en'` or `'am'`
- Error messages adapt to language

**With Redis:**
- Ensure language preference survives reload
- Test both English and Amharic flows

### Admin Approval Workflow

**Not Affected:**
- Completed registrations go to `pending_registrations` table (persistent)
- Admin approval doesn't depend on session state
- Only active registrations at risk

---

## Monitoring & Alerts

### Metrics to Track (Post-Redis)

1. **Registration Start Rate**: /register commands per hour
2. **Registration Completion Rate**: % that reach final submit
3. **Session Expiry Rate**: % that get "Session expired" error
4. **Average Time to Complete**: Minutes from start to submit
5. **Redis Hit Rate**: % of successful state retrievals

### Alerts to Set Up

- 🚨 **Redis Down**: Connection failures → fallback to DB
- ⚠️ **High Session Expiry Rate**: >10% → investigate
- ⚠️ **Long Registration Times**: >30 min → user may be stuck
- 📊 **Low Completion Rate**: <50% → UX issue

---

## References

**Files to Modify:**
- `voice/telegram/register_handler.py` - Main registration logic
- `voice/telegram/telegram_api.py` - Photo upload routing
- `voice/service/api.py` - Add Redis connection on startup
- `requirements.txt` - Add `redis` package
- `docker-compose.yml` - Add Redis service (if using Docker)
- `.env.example` - Add `REDIS_HOST`, `REDIS_PORT`

**Related Issues:**
- PIN Integration (v1.7) - Phase 3
- Registration Audit - Language bug fixed
- Voice-first registration - Not implemented (separate issue)

---

**Next Steps:** Install Redis and implement session persistence (Priority: CRITICAL)
