# 🕐 Timezone Adjustment Reminders for depot-butler-job

## ⚠️ Important: Manual Cron Schedule Updates Required

Azure Container Apps cron schedules use **UTC time only** and do not automatically adjust for daylight saving time. You must manually update the cron expression twice per year when Germany switches between winter and summer time.

---

## 📅 Upcoming Timezone Changes

### 2026 Schedule Updates

#### ☀️ Summer Time (CEST) - March 29, 2026

**When:** Last Sunday of March at 2:00 AM → clocks move forward to 3:00 AM
**Action Required:** Update cron to run at 14:00 UTC

```bash
az containerapp job update \
  --name depot-butler-job \
  --resource-group rg-FastAPI-AzureContainerApp-dev \
  --cron-expression "0 14 * * 1-5"
```

**Explanation:** 14:00 UTC = 16:00 CEST (4 PM German summer time)

---

#### 🍂 Winter Time (CET) - October 25, 2026

**When:** Last Sunday of October at 3:00 AM → clocks move back to 2:00 AM
**Action Required:** Update cron to run at 15:00 UTC

```bash
az containerapp job update \
  --name depot-butler-job \
  --resource-group rg-FastAPI-AzureContainerApp-dev \
  --cron-expression "0 15 * * 1-5"
```

**Explanation:** 15:00 UTC = 16:00 CET (4 PM German winter time)

---

## 📋 Quick Reference

| Season | German Time Zone | UTC Offset | Cron Expression | UTC Time | German Time |
|--------|------------------|------------|-----------------|----------|-------------|
| Winter | CET | UTC+1 | `0 15 * * 1-5` | 15:00 | 16:00 (4 PM) |
| Summer | CEST | UTC+2 | `0 14 * * 1-5` | 14:00 | 16:00 (4 PM) |

---

## ✅ Current Configuration

**As of March 29, 2026:**

- **Season:** Summer Time (CEST)
- **Cron Expression:** `0 14 * * 1-5`
- **Runs at:** 14:00 UTC = 16:00 CEST = 4 PM German time
- **Days:** Monday through Friday

---

## 🔔 How to Set Reminders

### Option 1: Outlook Calendar

1. Open Outlook Calendar
2. Create recurring events:
   - **Title:** "Update depot-butler-job to Summer Time (CEST)"
   - **Date:** Last Sunday of March, yearly
   - **Reminder:** 1 week before
   - **Description:** Run command to change cron to `0 14 * * 1-5`

   - **Title:** "Update depot-butler-job to Winter Time (CET)"
   - **Date:** Last Sunday of October, yearly
   - **Reminder:** 1 week before
   - **Description:** Run command to change cron to `0 15 * * 1-5`

### Option 2: Microsoft To Do

1. Create task: "Update depot-butler-job timezone - March"
2. Set due date: March 29, 2026
3. Add reminder: 1 week before
4. Repeat: Yearly

### Option 3: Azure Monitor Alert (Advanced)

Set up an Azure Logic App that triggers a notification 1 week before timezone change dates.

---

## 🛠️ Verification Commands

After updating the cron expression, verify the change:

```bash
# Check current cron schedule
az containerapp job show \
  --name depot-butler-job \
  --resource-group rg-FastAPI-AzureContainerApp-dev \
  --query "properties.configuration.scheduleTriggerConfig.cronExpression"

# Check job execution history to confirm timing
az containerapp job execution list \
  --name depot-butler-job \
  --resource-group rg-FastAPI-AzureContainerApp-dev \
  --query "[].{Name:name, Status:properties.status, StartTime:properties.startTime}" \
  --output table
```

---

## 📝 Notes

- **Germany** follows EU timezone rules
- **Daylight Saving Time starts:** Last Sunday of March at 2:00 AM (clocks forward)
- **Daylight Saving Time ends:** Last Sunday of October at 3:00 AM (clocks back)
- The job runs **Monday-Friday only** (no weekends)
- Always test with a manual execution after updating: `az containerapp job start ...`

---

## 🔗 Related Documentation

- [Azure Container Apps Cron Expressions](https://learn.microsoft.com/en-us/azure/container-apps/jobs-cron-expressions)
- [German Timezone Information](https://www.timeanddate.com/time/zone/germany)

---

**Last Updated:** March 29, 2026
**Next Action Required:** October 25, 2026 (Switch to Winter Time)
