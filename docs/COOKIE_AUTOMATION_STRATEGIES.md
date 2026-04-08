# Cookie Automation Strategies

**Status**: Planning Phase
**Date**: January 12, 2026
**Priority**: High - Current manual process unsustainable with <7 day cookie expiration

## Problem Statement

### Current Situation

- Authentication cookie (`.AspNetCore.Cookies`) expires in **<7 days** (down from 14-30 days)
- Manual cookie export required every few days via browser DevTools
- Process: Login → DevTools → Copy cookie → Run script → Paste → Enter expiration
- **Blocks unattended operation** - system cannot run autonomously

### Why Automation is Blocked

Cloudflare Turnstile protection on login page detects and blocks ALL automation attempts:

- ❌ Basic Playwright automation
- ❌ Playwright with stealth mode
- ❌ Undetected Chrome Driver
- ❌ Real Edge/Chrome via Playwright
- ❌ Any browser automation library

**Result**: "Anmelden" button remains disabled when automation detected, preventing form submission.

### Historical Context

- **December 2025**: Migrated from Patchright to HTTPX (removed browser automation)
- **Current approach**: Manual cookie export is the ONLY working method
- **Documentation**: See `COOKIE_AUTHENTICATION.md` and `HTTPX_MIGRATION.md`

## Viable Automation Strategies

### Strategy 1: Mobile App API Reverse Engineering ⭐ RECOMMENDED

**Status**: ✅ **iOS App "DER AKTIONÄR" confirmed to exist**
⚠️ **CRITICAL FINDING** (2026-01-13): Mobile app uses "Laden" (Load) → "Lesen" (Read) viewer, NOT direct PDF download

**Hypothesis**: Mobile apps bypass Cloudflare Turnstile and use token-based authentication with longer lifetimes.

**Critical Question**: Does the mobile app/API provide access to PDF files, or only a proprietary viewer format?

#### Why Mobile APIs Are Different

Mobile apps CANNOT use cookie-based session authentication like websites because:

- No browser cookies in native apps
- Must use **token-based auth** (JWT, OAuth, Bearer tokens)
- Tokens stored securely in iOS Keychain / Android KeyStore
- **No Cloudflare Turnstile** (mobile apps can't solve visual challenges)
- Typically use REST/GraphQL APIs with JSON responses

This makes mobile API authentication fundamentally different - and much better for automation!

#### Detailed Investigation Guide

**See [MOBILE_API_INVESTIGATION_GUIDE.md](MOBILE_API_INVESTIGATION_GUIDE.md) for complete step-by-step instructions including:**

- **Traffic Interception Setup**: mitmproxy, Charles Proxy, or Burp Suite configuration
- **iOS Device Configuration**: Proxy setup and certificate installation
- **Capture Process**: How to capture login flow and analyze traffic
- **Content Format Investigation** ⚠️: Determine if PDFs are available or only proprietary viewer
- **Hybrid Approach Testing**: Use mobile token with web API endpoints
- **API Analysis**: Decode JWT tokens, map endpoints, test token lifetime
- **Python Implementation**: Complete `MobileApiClient` class with examples
- **MongoDB Integration**: Token storage and retrieval
- **Workflow Integration**: Update existing code to use mobile API
- **Troubleshooting**: Certificate pinning, device registration, content format issues

#### Mobile App Content Format Concern ⚠️

**Key Finding**: The iOS app doesn't show a "Download" button. Instead:

1. "Laden" (Load) button - downloads content for offline viewing
2. "Lesen" (Read) button - opens a viewer to read the edition

**This could mean**:

- ❌ **Worst case**: Proprietary viewer format, no PDF access → Strategy 1 NOT viable
- ⚠️ **Challenging**: Image-based pages that need conversion → Complex implementation
- ✅ **Best case**: PDF downloaded behind the scenes → Full Strategy 1 viable
- ✅ **Hybrid**: Mobile token works with web API downloads → Still valuable

**Investigation must determine**:

1. What format does "Laden" actually download? (PDF, images, proprietary)
2. Are PDF files accessible via mobile API endpoints?
3. Can mobile API token be used with web API download URLs?
4. Is this a UI limitation or fundamental API difference?

**If mobile app doesn't provide PDF access**, there's still potential value:

- Get 30+ day token from mobile API
- Use token with existing web API download endpoints
- Avoid <7 day cookie refresh cycle
- This "hybrid approach" would still be a significant improvement

#### Quick Summary of Investigation Steps

1. **Setup mitmproxy** on your computer (or Charles/Burp Suite)
2. **Configure iPhone** to use proxy + install mitmproxy certificate
3. **Delete and reinstall** "DER AKTIONÄR" app
4. **Capture login flow** while logging in fresh
5. **Document all API calls**: login endpoint, headers, request/response format
6. **Analyze token structure**: JWT decode, expiration time
7. **Test token validity**: Verify it works for 7+ days
8. **Implement `MobileApiClient`** in Python
9. **Integrate with workflow**: Replace cookie auth with token auth
10. **Deploy and test**: Verify automation works end-to-end

#### Expected Outcomes

**If Successful** (Token Lifetime ≥14 days):

- ✅ **Fully automated authentication** - no manual intervention
- ✅ **30+ day token lifetime** (typical for mobile APIs)
- ✅ **Automatic token refresh** before expiration
- ✅ **No Cloudflare Turnstile** issues
- ✅ **Robust solution** - mobile APIs rarely change

**Success Metrics**:

- Manual interventions: **0 per month** (down from 4-8)
- Time saved: **4-8 minutes per month**
- Reliability: **99%+** (vs 85% with cookie expiration issues)

**If Unsuccessful** (Token Lifetime ≤7 days):

- ⚠️ **No improvement** over current cookie approach
- 📋 **Fall back to Strategy 2** (Browser Extension)
- 📋 **Or implement Strategy 3** (Enhanced Alerting)

#### Advantages

- ✅ **Permanent solution**: Solves authentication problem completely
- ✅ **Zero manual intervention**: Fully automated
- ✅ **Long token lifetime**: 30+ days typical for mobile APIs
- ✅ **No Cloudflare Turnstile**: Mobile APIs don't use it
- ✅ **Automatic refresh**: Token renews before expiration
- ✅ **Lightweight**: No browser automation, small Docker image
- ✅ **Better API design**: JSON responses, clear error codes
- ✅ **Future-proof**: Mobile APIs more stable than web scraping

#### Disadvantages

- ❌ **Investigation effort**: 6-10 hours initial reverse engineering
- ❌ **Uncertainty**: Won't know token lifetime until tested
- ❌ **Certificate pinning**: May need jailbroken device or workarounds
- ❌ **API stability**: Could change without notice (low risk though)
- ❌ **ToS concerns**: Reverse engineering may violate terms of service
- ❌ **Device registration**: May require persistent device ID
- ❌ **No guarantees**: Might not be better than cookies (unlikely but possible)

#### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
| ---- | ---------- | ------ | ---------- |
| Certificate pinning blocks interception | Medium | High | Use jailbroken device, objection, or Android |
| Token lifetime ≤7 days | Low | High | Fall back to Strategy 2/3 |
| API requires complex attestation | Low | Medium | Analyze requirements, implement if feasible |
| API changes break implementation | Low | Medium | Monitor app updates, version lock if needed |
| ToS violation consequences | Low | Low | Personal use, paying subscriber |

**Overall Risk**: **Medium-Low** - Worth attempting given high potential payoff

#### Implementation Checklist

Phase 1: Investigation (6-8 hours)

- [x] Confirm iOS app "DER AKTIONÄR" exists ✅
- [ ] Setup mitmproxy on computer
- [ ] Configure iPhone proxy + certificate
- [ ] Delete and reinstall app (fresh login)
- [ ] Capture complete login flow
- [ ] Document login endpoint, headers, payload
- [ ] Document subscriptions/editions/download endpoints
- [ ] Decode JWT token structure (if applicable)
- [ ] Test captured token for 24 hours
- [ ] Test captured token for 7 days
- [ ] Test captured token for 14 days
- [ ] Measure actual token lifetime

Phase 2: Implementation (8-10 hours)

- [ ] Create `MobileApiClient` class
- [ ] Implement login and token refresh
- [ ] Implement subscription/edition/download methods
- [ ] Add MongoDB token storage methods
- [ ] Update settings for mobile API config
- [ ] Create `refresh_mobile_token.py` script
- [ ] Update workflow to use mobile API
- [ ] Add feature flag for gradual rollout

Phase 3: Testing (4-6 hours)

- [ ] Unit tests for `MobileApiClient`
- [ ] Integration tests (login, subscriptions, download)
- [ ] Test token refresh logic
- [ ] Test MongoDB persistence
- [ ] Test full workflow locally
- [ ] Deploy to Azure (feature flag OFF)
- [ ] Enable feature flag for one publication
- [ ] Monitor for 7 days
- [ ] Enable for all publications

Phase 4: Deployment & Monitoring

- [ ] Document API endpoints in MOBILE_API_INVESTIGATION_GUIDE.md
- [ ] Update COOKIE_AUTOMATION_STRATEGIES.md with results
- [ ] Create runbook for mobile API issues
- [ ] Setup monitoring for token refresh failures
- [ ] Remove cookie-based auth code (optional, keep as fallback)

**Decision Point**: After Phase 1, decide if token lifetime justifies Phase 2-4

**Critical Decision Factors**:

1. **Token lifetime**: Must be ≥14 days (ideally 30+)
2. **PDF accessibility**: Must be able to download PDFs via mobile API OR hybrid approach
3. **Implementation complexity**: Cost vs. benefit analysis

**Possible Outcomes**:

- ✅ **Full success**: Mobile API provides PDFs + 30+ day token → Implement fully
- ✅ **Hybrid success**: 30+ day token works with web API → Still worth implementing
- ⚠️ **Partial**: 14-20 day token, limited PDF access → Evaluate complexity
- ❌ **Not viable**: <7 day token OR no PDF access → Abandon Strategy 1

---

### Strategy 2: Browser Extension for Cookie Auto-Export

**Goal**: Reduce manual cookie export from 60 seconds to 5 seconds.

#### Architecture

```text
User logs in manually (browser)
      ↓
Browser Extension detects login success
      ↓
Extension extracts .AspNetCore.Cookies
      ↓
Extension POSTs to MongoDB API endpoint
      ↓
Notification: "Cookie updated successfully!"
```

#### Implementation Components

1. Browser Extension (Chrome/Edge)

    ```javascript
    // manifest.json
    {
    "manifest_version": 3,
    "name": "DepotButler Cookie Exporter",
    "version": "1.0",
    "permissions": ["cookies", "storage"],
    "host_permissions": ["https://konto.boersenmedien.com/*"],
    "background": {
        "service_worker": "background.js"
    }
    }

    // background.js
    chrome.cookies.onChanged.addListener(async (changeInfo) => {
    if (changeInfo.cookie.name === ".AspNetCore.Cookies" &&
        changeInfo.cookie.domain === ".boersenmedien.com") {

        const cookieValue = changeInfo.cookie.value;

        // Upload to MongoDB via API
        await fetch("https://your-api.azure.com/api/update-cookie", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${EXTENSION_API_KEY}`
        },
        body: JSON.stringify({
            cookie: cookieValue,
            expiration: new Date(Date.now() + 14*24*60*60*1000).toISOString()
        })
        });

        // Show notification
        chrome.notifications.create({
        type: "basic",
        title: "DepotButler",
        message: "Cookie automatically uploaded to MongoDB!"
        });
    }
    });
    ```

2. Azure Function API Endpoint

```python
# Azure Function to receive cookie from extension
import azure.functions as func
from motor.motor_asyncio import AsyncIOMotorClient

async def main(req: func.HttpRequest) -> func.HttpResponse:
    # Verify API key
    api_key = req.headers.get("Authorization")
    if api_key != f"Bearer {EXTENSION_API_KEY}":
        return func.HttpResponse("Unauthorized", status_code=401)

    # Parse request
    data = req.get_json()
    cookie_value = data["cookie"]
    expiration = data["expiration"]

    # Update MongoDB
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DB_NAME]
    await db.config.update_one(
        {"_id": "auth"},
        {
            "$set": {
                "cookie": cookie_value,
                "cookie_expiration": expiration,
                "updated_at": datetime.utcnow(),
                "updated_by": "browser_extension"
            }
        }
    )

    return func.HttpResponse("OK", status_code=200)
```

**Advantages

- ✅ Reduces manual work from 60s to 5s (just login)
- ✅ User stays in control (must approve login)
- ✅ No Cloudflare issues (user performs login manually)
- ✅ Works with existing cookie-based approach
- ✅ Can add expiration estimation UI

**Disadvantages

- ❌ Still requires manual user action every <7 days
- ❌ Requires browser extension development (4-6 hours)
- ❌ Need to maintain extension for Chrome + Edge
- ❌ Requires Azure Function API endpoint
- ❌ Security: Extension API key management

**Implementation Checklist

- [ ] Create browser extension scaffold
- [ ] Implement cookie detection and extraction
- [ ] Create Azure Function API endpoint
- [ ] Add authentication (API key via environment variable)
- [ ] Update MongoDB schema for extension metadata
- [ ] Test extension on Chrome
- [ ] Test extension on Edge
- [ ] Create installation documentation
- [ ] Publish extension (Chrome Web Store optional)
- [ ] Add extension settings UI for MongoDB endpoint

---

### Strategy 3: Enhanced Alerting & Notification System

**Goal**: Make manual cookie updates as frictionless as possible with timely alerts.

#### Current Alerting

- Email sent **3 days before** expiration (configurable)
- Estimated expiration stored in MongoDB (manually entered, currently 14 days but actual is <7 days)
- Email template with instructions
- Sent to admin email address

#### Cookie Expiration Detection Problem

**Challenge**: The `.AspNetCore.Cookies` expiration is encrypted inside the cookie value - we cannot read it.

**Current approach limitations:**

- Manual estimation (user enters 14 days) stored in MongoDB
- Actual expiration is <7 days (recently changed)
- Alerts based on estimated date, not actual validity
- Risk: Cookie expires before estimated date

#### Proposed Solution: Hybrid Detection

**1. Proactive Validation Checks** (Scheduled Job)

```python
# New: Cookie validation service
class CookieValidationService:
    async def validate_cookie(self) -> bool:
        """
        Make lightweight authenticated request to verify cookie is still valid.
        Returns True if valid, False if expired.
        """
        try:
            async with httpx.AsyncClient() as client:
                # Make test request to account page
                response = await client.get(
                    "https://konto.boersenmedien.com/produkte/abonnements",
                    cookies={".AspNetCore.Cookies": cookie_value},
                    timeout=10.0
                )

                # Check if we're still authenticated
                if response.status_code == 200 and "Anmelden" not in response.text:
                    return True  # Cookie valid
                else:
                    return False  # Cookie expired (redirected to login)

        except Exception:
            return False  # Assume expired on error

    async def scheduled_validation_check(self):
        """
        Run validation check and update MongoDB with actual status.
        Schedule: Every 12 hours via Azure Container Apps scheduled job.
        """
        is_valid = await self.validate_cookie()

        await mongodb.config.update_one(
            {"_id": "auth"},
            {
                "$set": {
                    "last_validation_check": datetime.utcnow(),
                    "cookie_valid": is_valid,
                    "validation_failures": 0 if is_valid else failures + 1
                }
            }
        )

        if not is_valid:
            # Cookie actually expired - send URGENT alert
            await self.send_urgent_expiration_alert()
```

**2. Scheduled Validation Job**

```yaml
# Azure Container Apps Job: cookie-validator
schedule: "0 */12 * * *"  # Every 12 hours
command: "python -m depotbutler.jobs.validate_cookie"
```

**3. Progressive Alerts Based on BOTH Signals**

```python
# Alert logic combining estimated date + validation status
async def determine_alert_urgency():
    cookie_info = await mongodb.get_cookie_info()

    days_until_estimated_expiry = (
        cookie_info.estimated_expiration - datetime.utcnow()
    ).days

    actual_is_valid = cookie_info.cookie_valid  # From validation checks
    validation_failures = cookie_info.validation_failures

    # Priority 1: Validation failed (actual expiration detected)
    if not actual_is_valid or validation_failures > 0:
        return "URGENT"  # Send all channels immediately

    # Priority 2: Close to estimated expiration
    elif days_until_estimated_expiry <= 1:
        return "HIGH"  # Email + Push

    elif days_until_estimated_expiry <= 3:
        return "MEDIUM"  # Email only

    else:
        return "NONE"  # No alert needed
```

**Detection Strategy Summary:**

- ✅ **Estimated expiration**: User enters conservative estimate (e.g., 5 days instead of 14)
- ✅ **Validation checks**: Automated job runs every 12 hours to test cookie
- ✅ **Dual signal alerts**: Warn on estimated date OR validation failure
- ✅ **Accurate detection**: Know immediately when cookie actually expires
- ✅ **No false positives**: Don't rely solely on estimate

#### Enhanced Alerting Features

**1. Multi-Channel Notifications**

```python
# Notification channels
- Email (existing)
- Push notification (Pushover, Telegram)
- SMS (Twilio)
- Discord/Slack webhook
```

**2. Progressive Alert Urgency**

```python
# Alert schedule (based on BOTH estimated date AND validation status)
- Validation PASSED + 3+ days remaining: No alert
- Validation PASSED + 2-3 days remaining: Email (low priority)
- Validation PASSED + 1 day remaining: Email + Push notification
- Validation PASSED + <12 hours remaining: Email + Push + SMS
- Validation FAILED (actual expiration detected): Email + Push + SMS (URGENT - immediate)
```

**3. Mobile-Optimized Cookie Update**

```python
# Create mobile-friendly web interface
https://depot-butler-admin.azure.com/update-cookie
- Simple form: paste cookie + submit
- Conservative expiration estimate (default 5 days, not 14)
- Works on mobile browser
- QR code in email for quick access
```

#### Implementation Components

**1. Pushover Integration**

```python
# src/depotbutler/services/pushover_service.py
class PushoverService:
    async def send_urgent_alert(self, title: str, message: str):
        await httpx.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": PUSHOVER_APP_TOKEN,
                "user": PUSHOVER_USER_KEY,
                "title": title,
                "message": message,
                "priority": 2,  # Require acknowledgment
                "sound": "siren"
            }
        )
```

**2. Progressive Notification Service**

```python
# src/depotbutler/services/progressive_alert_service.py
class ProgressiveAlertService:
    async def check_and_alert(self):
        days_remaining = await self.get_cookie_days_remaining()

        if days_remaining <= 0:
            # URGENT: Cookie expired
            await self.send_all_channels(
                priority="URGENT",
                title="🚨 Cookie EXPIRED",
                message="DepotButler cannot run. Update immediately."
            )
        elif days_remaining <= 0.5:  # 12 hours
            await self.send_push_and_email(...)
        elif days_remaining <= 1:  # 24 hours
            await self.send_push_notification(...)
        elif days_remaining <= 3:
            await self.send_email(...)
```

**3. Mobile Web Interface**

```python
# Azure Static Web App
# File: static-web-app/update-cookie.html
<form id="cookieForm">
  <h1>Update Cookie</h1>
  <textarea name="cookie" placeholder="Paste cookie here"></textarea>
  <button type="submit">Update</button>
</form>

<script>
document.getElementById('cookieForm').onsubmit = async (e) => {
  e.preventDefault();
  const cookie = e.target.cookie.value;

  await fetch('/api/update-cookie', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({cookie, expiration: 14})
  });

  alert('✅ Cookie updated successfully!');
};
</script>
```

#### Advantages

- ✅ **Accurate detection**: Knows immediately when cookie actually expires
- ✅ **Early warning**: Still alerts based on conservative estimate
- ✅ **Dual signal safety**: Won't miss expiration even if estimate is wrong
- ✅ Quick to implement (3-5 hours with validation service)
- ✅ Works with existing cookie approach
- ✅ Minimizes disruption to current workflow
- ✅ Multi-channel redundancy (won't miss alerts)
- ✅ Mobile-optimized reduces friction

#### Disadvantages

- ❌ Still requires manual intervention
- ❌ Doesn't solve root problem
- ❌ User must respond within <7 days
- ❌ Additional Azure scheduled job (cookie validator runs every 12 hours)
- ❌ Slightly increased complexity

#### Implementation Checklist

- [ ] Create `CookieValidationService` class
- [ ] Add scheduled validation job (Azure Container Apps)
- [ ] Update MongoDB schema for validation status fields
- [ ] Add Pushover service integration
- [ ] Implement progressive alert service (with validation status)
- [ ] Create mobile web interface (Azure Static Web App)
- [ ] Update settings for multi-channel config
- [ ] Add alert scheduling logic
- [ ] Test validation service locally
- [ ] Deploy validation job to Azure
- [ ] Test push notifications on mobile
- [ ] Update conservative expiration default (5 days, not 14)
- [ ] Create QR code generator for mobile access
- [ ] Document mobile workflow
- [ ] Update `COOKIE_AUTHENTICATION.md`

---

### Strategy 4: Contact Provider for API Access

**Goal**: Request official API access from boersenmedien.com.

#### Approach

1. **Identify point of contact**
   - Customer support email
   - Technical/developer relations team
   - Business development contact

2. **Draft request email**

   ```text
   Subject: API Access Request for Automated Subscription Management

   Dear Börsenmedien Team,

   I am a long-time subscriber to [publications]. I have built a personal
   automation tool to manage my subscription downloads and organization.

   Currently, I use cookie-based authentication, but frequent expiration
   requires manual intervention. Would it be possible to:

   1. Receive an API key for programmatic access?
   2. Use a service account with extended session lifetime?
   3. Access a developer API for subscribers?

   I am happy to sign any required agreements and understand this may
   not be a standard offering.

   Thank you for considering this request.
   ```

3. **Follow up with use case details**
   - Personal automation (not commercial resale)
   - Paying subscriber in good standing
   - Willing to provide technical details

#### Advantages

- ✅ Official, supported solution
- ✅ No reverse engineering needed
- ✅ No ToS concerns
- ✅ May get long-lived API key
- ✅ Future-proof if site changes

#### Disadvantages

- ❌ May be declined (not standard offering)
- ❌ Long response time (weeks/months)
- ❌ No guarantee of success
- ❌ May require business justification

#### Implementation Checklist

- [ ] Research contact information
- [ ] Draft request email
- [ ] Send initial inquiry
- [ ] Follow up after 1 week
- [ ] If approved: Document API endpoints
- [ ] Implement API client
- [ ] Update authentication flow

---

## Recommended Implementation Order

### Phase 1: Quick Wins (This Week)

1. **Strategy 3**: Enhanced alerting with Pushover (2-4 hours)
   - Immediate improvement in notification reliability
   - Reduces missed expirations
   - No architectural changes

### Phase 2: Investigation (Next Week)

2. **Strategy 1**: Mobile app API research (4-8 hours)
   - Check for mobile app existence
   - Intercept API traffic if available
   - If successful: This is THE solution

### Phase 3: Fallback (If no mobile API)

3. **Strategy 2**: Browser extension (4-6 hours)
   - Reduces manual burden significantly
   - Good middle ground if mobile API doesn't exist

### Phase 4: Parallel Track (Optional)

4. **Strategy 4**: Contact provider (1-2 hours initial)
   - Low effort to send email
   - May take weeks/months for response
   - Keep as backup plan

---

## Success Metrics

### Current State

- Manual intervention required: **Every 5-7 days**
- Time per update: **60-90 seconds**
- Risk of missed expiration: **High** (email-only alerts)

### Target State (Strategy 1 - Mobile API)

- Manual intervention required: **Never** (fully automated)
- Time per update: **0 seconds**
- Risk of missed expiration: **None**

### Target State (Strategy 2 - Browser Extension)

- Manual intervention required: **Every 5-7 days**
- Time per update: **5-10 seconds** (just login)
- Risk of missed expiration: **Low** (auto-upload on login)

### Target State (Strategy 3 - Enhanced Alerts)

- Manual intervention required: **Every 5-7 days**
- Time per update: **30-40 seconds** (mobile-optimized)
- Risk of missed expiration: **Very Low** (multi-channel alerts)

---

## Technical Debt & Future Considerations

### MongoDB Schema Updates

```python
# config collection - auth document
{
    "_id": "auth",

    # Current fields
    "cookie": "...",
    "cookie_expiration": "2026-01-26T15:23:42Z",
    "updated_at": "2026-01-12T16:24:20Z",
    "updated_by": "2026-01-12, 16:23 / Stefan Fries",

    # New fields for automation
    "auth_method": "cookie" | "mobile_api" | "api_key",  # Track method
    "mobile_api_token": "...",  # If using Strategy 1
    "mobile_api_refresh_token": "...",  # If using Strategy 1
    "api_key": "...",  # If using Strategy 4
    "last_refresh_attempt": "2026-01-12T16:00:00Z",
    "refresh_failures": 0,
    "extension_enabled": false,  # If using Strategy 2
}
```

### Settings Updates

```python
# src/depotbutler/settings.py
class NotificationSettings(BaseSettings):
    # Existing
    cookie_warning_days: int = 3
    admin_emails: list[str] = []

    # New for Strategy 3
    pushover_app_token: str = ""
    pushover_user_key: str = ""
    alert_channels: list[str] = ["email"]  # ["email", "pushover", "sms"]
    urgent_alert_threshold_hours: int = 12

    # New for Strategy 2
    extension_api_key: str = ""
    extension_api_endpoint: str = ""
```

### Testing Requirements

```python
# tests/test_mobile_api_auth.py (Strategy 1)
# tests/test_browser_extension_api.py (Strategy 2)
# tests/test_progressive_alerts.py (Strategy 3)
```

---

## Next Steps

1. **Immediate**: Implement Strategy 3 (Enhanced Alerting)
   - PR: "Add Pushover notifications for cookie expiration"
   - Reduces risk of missed expirations TODAY

2. **Investigation**: Research Strategy 1 (Mobile API)
   - Document findings in `MOBILE_API_INVESTIGATION.md`
   - If successful, this becomes the long-term solution

3. **Backup**: Implement Strategy 2 (Browser Extension)
   - Only if Strategy 1 not viable
   - PR: "Add browser extension for cookie auto-export"

4. **Optional**: Send email for Strategy 4 (Provider API)
   - Parallel track, may take months
   - Keep as long-term option

---

## Related Documentation

- [COOKIE_AUTHENTICATION.md](COOKIE_AUTHENTICATION.md) - Current manual process
- [HTTPX_MIGRATION.md](HTTPX_MIGRATION.md) - Why Playwright was abandoned
- [architecture.md](architecture.md) - System architecture overview
- [OPERATIONAL_RUNBOOK.md](OPERATIONAL_RUNBOOK.md) - Production operations

---

## Questions for Next Session

1. **Mobile app availability**: Does boersenmedien.com have an iOS/Android app?
2. **Alert preferences**: Which notification channels do you prefer? (Pushover, Telegram, SMS)
3. **Time budget**: How many hours can we dedicate to mobile API research?
4. **Risk tolerance**: Willing to reverse engineer mobile API despite potential ToS issues?
5. **Browser preference**: Chrome or Edge for extension development?

---

**Last Updated**: January 12, 2026
**Next Review**: After mobile API investigation
