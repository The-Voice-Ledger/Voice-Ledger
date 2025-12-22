# Global Forest Watch API Setup Guide

## Overview
The Global Forest Watch API is **FREE** and provides satellite data for EUDR deforestation compliance checking. This guide walks you through registration and setup.

## Why Get an API Key?

**Without API Key:**
- ❌ Lowest rate limiting tier
- ❌ No domain whitelisting
- ❌ Requests may be throttled randomly

**With FREE API Key:**
- ✅ Better rate limits
- ✅ Domain whitelisting (more secure)
- ✅ More reliable access
- ✅ Still **$0.00 cost**

## Step-by-Step Registration

### Option 1: Using the Automated Script (Recommended)

We've provided a Python script to automate the registration:

```bash
python scripts/register_gfw_api.py
```

Follow the prompts to:
1. Sign up with your email
2. Get an access token
3. Create an API key
4. Automatically save it to your `.env` file

### Option 2: Manual Registration via API

#### 1. Sign Up
```bash
curl -X POST "https://data-api.globalforestwatch.org/auth/sign-up" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Your Name",
    "email": "your@email.com"
  }'
```

**Response:** You'll receive a confirmation email. Follow the link to verify your account and set a password.

#### 2. Get Access Token
```bash
curl -X POST "https://data-api.globalforestwatch.org/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password&username=your@email.com&password=your_password"
```

**Response:**
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer"
}
```

Save the `access_token` for the next step.

#### 3. Create API Key
```bash
curl -X POST "https://data-api.globalforestwatch.org/auth/apikey" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "alias": "Voice-Ledger EUDR",
    "organization": "Voice-Ledger",
    "email": "your@email.com",
    "domains": ["voiceledger.com", "*.voiceledger.com", "localhost"],
    "never_expires": false
  }'
```

**Response:**
```json
{
  "data": {
    "api_key": "YOUR-API-KEY-UUID",
    "created_on": "2025-12-22T...",
    "expires_on": "2026-12-22T...",
    "alias": "Voice-Ledger EUDR",
    "domains": ["voiceledger.com", "*.voiceledger.com", "localhost"]
  },
  "status": "success"
}
```

Copy the `api_key` value.

#### 4. Add to Environment Variables

Add to your `.env` file:
```bash
# =============================================================================
# Global Forest Watch API (EUDR Deforestation Checking)
# =============================================================================
# Free API - Register at: https://data-api.globalforestwatch.org
GFW_API_KEY=YOUR-API-KEY-UUID
```

### Option 3: Using the Web Interface (If Available)

Visit the Global Forest Watch Data API portal at:
https://data-api.globalforestwatch.org

Look for a registration or sign-up link and follow the web-based flow.

## Verifying Your Setup

Test your API key with the verification script:

```bash
python scripts/test_gfw_api.py
```

Or manually:

```bash
curl -X GET "https://data-api.globalforestwatch.org/datasets" \
  -H "x-api-key: YOUR-API-KEY-UUID"
```

You should see a list of available datasets.

## Using the API Key in Voice-Ledger

Once configured in `.env`, the system automatically uses it:

```python
from voice.verification.deforestation_checker import DeforestationChecker

# Automatically reads GFW_API_KEY from environment
checker = DeforestationChecker()

# Check deforestation
result = checker.check_deforestation(
    latitude=9.0320,
    longitude=38.7469,
    radius_meters=1000
)

print(f"EUDR Compliant: {result.compliant}")
print(f"Risk Level: {result.risk_level}")
```

## Managing Your API Keys

### List Your Keys
```bash
curl -X GET "https://data-api.globalforestwatch.org/auth/apikeys" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Validate a Key
```bash
curl -X GET "https://data-api.globalforestwatch.org/auth/apikey/YOUR_KEY/validate" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Delete a Key
```bash
curl -X DELETE "https://data-api.globalforestwatch.org/auth/apikey/YOUR_KEY" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Key Expiration

By default, API keys are valid for **1 year**. You'll need to:
1. Renew before expiration (you'll receive email notifications)
2. Or create a new key when the old one expires

## Rate Limits

With an API key, you get:
- **Higher rate limits** than anonymous requests
- **Priority processing** during high traffic
- **Better reliability** for production use

Exact limits aren't publicly documented, but typical usage for EUDR checking (1-2 requests per farmer registration) is well within limits.

## Troubleshooting

### API Key Not Working
1. Check that it's in your `.env` file as `GFW_API_KEY`
2. Verify the key hasn't expired (check email or query `/auth/apikeys`)
3. Ensure domains are correctly whitelisted if using from a web app

### Getting 401 Unauthorized
- Your key may have expired
- Domain whitelist mismatch
- Key was deleted

### Getting 422 Unprocessable Entity
- This is a geometry/query error, not an auth issue
- Check your coordinates are valid
- Our code handles this gracefully

### Rate Limited (429)
- Wait a few seconds and retry
- Our code implements exponential backoff automatically
- Consider adding caching for frequently checked locations

## Support

For issues with the GFW API itself:
- Email: gfw@wri.org
- Documentation: https://data-api.globalforestwatch.org
- GitHub: https://github.com/wri/gfw-data-api

For Voice-Ledger integration issues:
- Check `tests/test_deforestation_checker.py`
- Review logs in `logs/deforestation_checks.log`
- See EUDR system documentation in `README.md`

## Cost Summary

| Item | Cost |
|------|------|
| GFW API Registration | **FREE** |
| API Key Creation | **FREE** |
| API Requests | **FREE** |
| Data Access | **FREE** |
| Rate Limits | **Generous (free tier)** |
| **Total** | **$0.00** |

The only costs are:
- IPFS storage for photos: ~$0.05/farmer/month
- Database storage: ~$0.01/farmer/month
- **Total**: $0.065/farmer/month

## Next Steps

After setup:
1. ✅ Test with real coordinates: `pytest tests/test_deforestation_checker.py -v`
2. ✅ Run end-to-end workflow: `pytest tests/test_eudr_workflow.py -v`
3. ✅ Verify in production: Check first farmer registration with GPS photo
4. ✅ Monitor usage: Track API response times and errors

---

**Last Updated:** December 22, 2025  
**Status:** Production Ready  
**EUDR Compliance:** Articles 9, 10, 33 ✅
