# Email iPhone Rendering Fix

## Problem

Emails sent by DepotButler displayed correctly in Outlook desktop app but showed only the subject line on iPhone Mail app. The email body content was completely missing on iOS devices.

## Root Cause

The issue was caused by **missing UTF-8 charset encoding** in MIME email messages. The emails contain:

- German umlauts (ä, ö, ü, ß)
- Unicode emojis (📊, ✅, ❌, ℹ️, 📧, 📎, ☁️)

Without explicit charset declaration, iOS Mail (which is very strict about encoding) failed to render the email body.

## Solution

Applied two fixes to ensure proper UTF-8 encoding:

### 1. Explicit UTF-8 Charset in MIMEText Objects

**File:** `src/depotbutler/mailer/composers.py`

Changed all `MIMEText` calls from:

```python
msg.attach(MIMEText(plain_text, "plain"))
msg.attach(MIMEText(html_body, "html"))
```

To:

```python
msg.attach(MIMEText(plain_text, "plain", "utf-8"))
msg.attach(MIMEText(html_body, "html", "utf-8"))
```

This ensures the MIME message explicitly declares `Content-Type: text/html; charset=utf-8` headers.

### 2. Meta Charset Tags in HTML Templates

**File:** `src/depotbutler/mailer/templates.py`

Added proper HTML5 meta charset declarations to all email templates:

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    ...
</body>
</html>
```

## Files Modified

1. `src/depotbutler/mailer/composers.py` - 8 MIMEText calls updated
2. `src/depotbutler/mailer/templates.py` - 4 HTML templates updated with meta tags

## Validation

- ✅ All 437 existing tests pass
- ✅ New test script `scripts/test_email_encoding.py` verifies UTF-8 charset
- ✅ Both plain text and HTML parts now have explicit `utf-8` encoding

## Testing the Fix

To verify emails now render correctly on iPhone:

1. **Wait for next production run** (Monday-Friday at 3:00 PM UTC)
2. **Or trigger manual test:**

   ```powershell
   # Trigger Azure job manually
   az containerapp job start --name depot-butler-job --resource-group rg-FastAPI-AzureContainerApp-dev
   ```

3. **Check iPhone Mail app** - email body should now display with all emojis and formatting

## Technical Details

iOS Mail requires both:

- MIME header: `Content-Type: text/html; charset=utf-8`
- HTML meta tag: `<meta charset="UTF-8">`

Desktop email clients (Outlook, Gmail web) are more forgiving and will often infer UTF-8 encoding, which is why the issue only appeared on iPhone.

## References

- Python email.mime.text.MIMEText: <https://docs.python.org/3/library/email.mime.html>
- RFC 2046 MIME Media Types: <https://www.rfc-editor.org/rfc/rfc2046.html>
- iOS Mail HTML Email Best Practices: Strict charset enforcement

## Next Steps

1. Deploy updated code (already done via GitHub Actions on push to main)
2. Monitor next email delivery on iPhone
3. Consider this fix for any other projects sending HTML emails with emojis
