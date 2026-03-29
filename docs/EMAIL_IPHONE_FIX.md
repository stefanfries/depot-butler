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

1. **Wait for next production run** (Monday-Friday at 14:00 UTC / 16:00 CEST)
2. **Or trigger manual test:**

   ```powershell
   # Trigger Azure job manually
   az containerapp job start --name depot-butler-job --resource-group rg-FastAPI-AzureContainerApp-dev
   ```

3. **Check mobile email app** - email body should now display with all emojis and formatting

---

## Follow-up Issue: "No New Editions" notification body missing on mobile (March 29, 2026)

### Problem

After the initial charset fix was deployed, the **"No New Editions"** admin notification (sent when all editions are already processed) still showed only the subject line on mobile devices. Desktop (Outlook) rendered it correctly.

### Root Cause

The "No New Editions" case routes through `send_warning_notification` with `warning_msg` set to an **HTML snippet** (the consolidated daily report). In `create_warning_email_body`, this HTML snippet was inserted verbatim into the **plain text** alternative:

```python
# Before fix — raw HTML in plain text:
plain_text = f"""Hello {firstname},
DepotButler: No New Editions:
<h2>📊 DepotButler Daily Report</h2>
<p style='border-bottom: ...'><strong>Processed:</strong> 2 publication(s)<br>...
```

When a `MIMEMultipart("alternative")` message has a plain text part that contains HTML tags, strict mobile email clients detect the inconsistency and may fail to render any body content.

### Fix Applied

**File:** `src/depotbutler/mailer/templates.py`

Two changes were made:

**1. Strip HTML tags for the plain text alternative** — when `warning_msg` is an HTML snippet, HTML tags are stripped before inserting into the plain text part:

```python
is_html_content = warning_msg.startswith("<")

if is_html_content:
    plain_warning = re.sub(r"<[^>]+>", "\n", warning_msg)
    plain_warning = re.sub(r"\n\s*\n+", "\n\n", plain_warning).strip()
else:
    plain_warning = warning_msg
```

**2. Remove the extra `<div>` wrapper in the HTML body** — the HTML fragment was previously wrapped in an extra `border-left` styled `<div>`, which caused GMX app (and likely other mobile clients) to blank the entire email body. The fragment now embeds directly in the content area, identical in structure to `create_success_email_body`:

```html
<!-- Before: extra wrapper div caused GMX app to blank the body -->
<div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0;">
    {warning_msg}
</div>

<!-- After: direct embed, same as success template -->
<div style="padding: 20px;">
    <p>Hello {firstname},</p>
    {warning_msg}
    <p>The next automatic attempt will be made at the regular time.</p>
</div>
```

Also moved `import re` from inline (inside `create_success_email_body`) to the module top-level. Plain-text warnings (e.g. cookie expiry) continue to use the original yellow actionable template unchanged.

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
