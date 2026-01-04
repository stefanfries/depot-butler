# DepotButler Documentation Index

## Quick Start

- **[README.md](../README.md)** - Project overview and quick start guide
- **[PRODUCTION_RUN_CHECKLIST.md](PRODUCTION_RUN_CHECKLIST.md)** - Pre-deployment checklist

## Architecture & Design

- **[ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md)** ⭐ NEW - Visual system architecture with Mermaid diagrams
  - System overview
  - Clean architecture layers
  - Workflow execution flow
  - Data model relationships
  - Authentication flow
  - State machines
  - Upload strategy
  - Admin scripts ecosystem
  - Error handling
  - Deployment architecture

- **[architecture.md](architecture.md)** - Detailed architecture description
  - Architectural style and layers
  - Current data model
  - MongoDB collections schema
  - Design patterns

- **[BUSINESS_REQUIREMENTS.md](BUSINESS_REQUIREMENTS.md)** - Business context and requirements

- **[decisions.md](decisions.md)** - Architecture decision records (ADRs)

## Operational Guides

- **[OPERATIONAL_RUNBOOK.md](OPERATIONAL_RUNBOOK.md)** ⭐ NEW - Day-to-day operations
  - Daily operations checklist
  - Weekly tasks (system health, cookie check, database maintenance)
  - Monthly tasks (subscription review, recipient audit, backups)
  - Emergency procedures
  - Monitoring & alerts
  - Incident response templates

- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** ⭐ NEW - Comprehensive troubleshooting guide
  - Authentication issues (cookie expired, OneDrive auth)
  - Database issues (connection, missing collections)
  - Download issues (edition not found, timeouts)
  - Email issues (not sent, attachment too large)
  - Upload issues (OneDrive failures)
  - Testing issues (tests failing, pre-commit hooks)
  - Production issues (workflow not running, false positives)
  - Performance issues
  - Data issues (recipient not receiving)
  - Common error messages reference

## Setup & Configuration

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Azure deployment guide
  - Prerequisites
  - Azure resources setup
  - Docker build and push
  - Container Apps configuration
  - Environment variables

- **[CONFIGURATION.md](CONFIGURATION.md)** - Configuration reference
  - Environment variables
  - Settings structure
  - MongoDB configuration
  - OneDrive setup
  - Email setup

- **[ONEDRIVE_SETUP.md](ONEDRIVE_SETUP.md)** - OneDrive OAuth setup
  - Microsoft Graph API app registration
  - OAuth flow walkthrough
  - Token refresh mechanism

- **[MONGODB.md](MONGODB.md)** - MongoDB Atlas setup and schema
  - Collections structure
  - Indexes
  - Queries
  - Maintenance

## Development

- **[TESTING.md](TESTING.md)** - Testing guide
  - Running tests
  - Test structure
  - Writing new tests
  - Coverage reports

- **[CODE_QUALITY.md](CODE_QUALITY.md)** - Code quality standards
  - Linting (ruff)
  - Type checking (mypy)
  - Pre-commit hooks
  - Code style

- **[DRY_RUN_MODE.md](DRY_RUN_MODE.md)** - Testing without side effects
  - How dry-run works
  - What is skipped
  - Use cases

## Technical Details

- **[COOKIE_AUTHENTICATION.md](COOKIE_AUTHENTICATION.md)** - Authentication mechanism
  - How cookie auth works
  - Cookie lifecycle
  - Refresh procedures

- **[ONEDRIVE_FOLDERS.md](ONEDRIVE_FOLDERS.md)** - OneDrive folder organization
  - Folder structure
  - Naming conventions
  - Custom folder configuration

- **[TIMEZONE_REMINDERS.md](TIMEZONE_REMINDERS.md)** - Timezone handling
  - UTC storage
  - CET display
  - Scheduling considerations

- **[HTTPX_MIGRATION.md](HTTPX_MIGRATION.md)** - Migration from Playwright to httpx
  - Rationale
  - Implementation details
  - Performance improvements

## Project Management

- **[MASTER_PLAN.md](MASTER_PLAN.md)** - Comprehensive project roadmap
  - Completed sprints (1-9)
  - Current sprint (Sprint 11: Documentation)
  - Planned sprints (10-12)
  - Future phases (PDF extraction, analytics)
  - Technology stack
  - Risk assessment

- **[TEST_COVERAGE_ANALYSIS.md](TEST_COVERAGE_ANALYSIS.md)** - Test coverage metrics
  - Coverage by module
  - Gaps and priorities

## Sprint Documentation (Archive)

- **[SPRINT4_EXAMPLES.md](SPRINT4_EXAMPLES.md)** - Sprint 4 examples
- **[SPRINT5_COMPLETION_REVIEW.md](SPRINT5_COMPLETION_REVIEW.md)** - Sprint 5 review
- **[SPRINT6_IMPROVEMENTS.md](SPRINT6_IMPROVEMENTS.md)** - Sprint 6 improvements
- **[SCRIPT_CLEANUP_PLAN.md](SCRIPT_CLEANUP_PLAN.md)** - Script consolidation plan
- **[SESSION_STATUS.md](SESSION_STATUS.md)** - Development session notes

---

## Documentation by Use Case

### I want to...

#### **...understand the system**

1. Start with [README.md](../README.md) for overview
2. Review [ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md) for visual architecture
3. Read [architecture.md](architecture.md) for detailed design
4. Check [BUSINESS_REQUIREMENTS.md](BUSINESS_REQUIREMENTS.md) for context

#### **...deploy to production**

1. Review [PRODUCTION_RUN_CHECKLIST.md](PRODUCTION_RUN_CHECKLIST.md)
2. Follow [DEPLOYMENT.md](DEPLOYMENT.md) step-by-step
3. Configure via [CONFIGURATION.md](CONFIGURATION.md)
4. Set up MongoDB using [MONGODB.md](MONGODB.md)
5. Set up OneDrive via [ONEDRIVE_SETUP.md](ONEDRIVE_SETUP.md)

#### **...operate the system daily**

1. Follow [OPERATIONAL_RUNBOOK.md](OPERATIONAL_RUNBOOK.md) for daily/weekly tasks
2. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) when issues arise
3. Use admin scripts documented in [ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md)

#### **...fix a problem**

1. Start with [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Check [OPERATIONAL_RUNBOOK.md](OPERATIONAL_RUNBOOK.md) emergency procedures
3. Review logs as described in troubleshooting guide
4. Follow incident response template

#### **...develop new features**

1. Review [MASTER_PLAN.md](MASTER_PLAN.md) for planned work
2. Read [architecture.md](architecture.md) for design patterns
3. Check [CODE_QUALITY.md](CODE_QUALITY.md) for standards
4. Write tests per [TESTING.md](TESTING.md)
5. Use [DRY_RUN_MODE.md](DRY_RUN_MODE.md) for safe testing

#### **...add a recipient**

1. See "Recipient Requests" in [OPERATIONAL_RUNBOOK.md](OPERATIONAL_RUNBOOK.md)
2. Use `scripts/manage_recipient_preferences.py`
3. Verify with `scripts/check_recipients.py`

#### **...refresh authentication**

1. Cookie: [COOKIE_AUTHENTICATION.md](COOKIE_AUTHENTICATION.md)
2. OneDrive: [ONEDRIVE_SETUP.md](ONEDRIVE_SETUP.md)
3. Use `scripts/update_cookie_mongodb.py` or `scripts/setup_onedrive_auth.py`

#### **...understand data model**

1. Visual ER diagram in [ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md)
2. Detailed schema in [MONGODB.md](MONGODB.md)
3. Pydantic models in [architecture.md](architecture.md)

---

## Recent Updates

### Sprint 11 (January 2026) ⭐

New documentation created:

- **ARCHITECTURE_DIAGRAMS.md** - 10 Mermaid diagrams covering entire system
- **TROUBLESHOOTING.md** - Comprehensive troubleshooting guide with solutions
- **OPERATIONAL_RUNBOOK.md** - Day-to-day operations and emergency procedures
- **DOCUMENTATION_INDEX.md** - This file, documentation navigation hub

### Sprint 8 (January 2026)

New admin tools:

- `scripts/manage_recipient_preferences.py` - 10 commands for preference management
- User activation/deactivation (single + bulk)
- Preference statistics and coverage reporting

### Sprint 9 (December 2025)

Observability enhancements:

- Metrics collection to MongoDB
- Structured logging
- Admin notifications
- Cookie expiry monitoring

---

## Contributing

### Documentation Standards

1. **Keep it current** - Update docs with code changes
2. **Be concise** - Link to details rather than duplicate
3. **Use examples** - Show don't just tell
4. **Add diagrams** - Mermaid for architecture, flows, models
5. **Test procedures** - Verify commands actually work

### Adding New Documentation

1. Create file in `docs/` directory
2. Add to this index under appropriate section
3. Link from related documents
4. Update "Recent Updates" section
5. Add to git commit

### Documentation Review Checklist

- [ ] Accurate (reflects current implementation)
- [ ] Complete (covers all aspects of topic)
- [ ] Clear (understandable by target audience)
- [ ] Examples provided (with expected output)
- [ ] Links to related docs
- [ ] Mermaid diagrams for complex flows
- [ ] Troubleshooting section if applicable

---

## Getting Help

### Within Documentation

1. Use this index to find relevant guide
2. Check troubleshooting guide for errors
3. Review operational runbook for procedures

### External Resources

- **GitHub Repository:** <https://github.com/stefanfries/depot-butler>
- **Issues:** Report bugs or request features
- **Discussions:** Ask questions

### Support Contacts

- **Admin Email:** Configured in `ADMIN_NOTIFICATION_EMAILS`
- **Repository Owner:** Stefan Fries

---

## Document Status

| Document | Status | Last Updated | Completeness |
| -------- | ------ | ------------ | ------------ |
| README.md | ✅ Current | 2025-12 | Complete |
| ARCHITECTURE_DIAGRAMS.md | ✅ Current | 2026-01 | Complete |
| TROUBLESHOOTING.md | ✅ Current | 2026-01 | Complete |
| OPERATIONAL_RUNBOOK.md | ✅ Current | 2026-01 | Complete |
| architecture.md | ✅ Current | 2025-12 | Complete |
| DEPLOYMENT.md | ✅ Current | 2025-12 | Complete |
| CONFIGURATION.md | ✅ Current | 2025-11 | Complete |
| TESTING.md | ✅ Current | 2025-11 | Complete |
| MONGODB.md | ✅ Current | 2025-11 | Complete |
| MASTER_PLAN.md | ✅ Current | 2026-01 | Complete |
| ONEDRIVE_SETUP.md | ✅ Current | 2025-11 | Complete |
| CODE_QUALITY.md | ⚠️ Partial | 2025-11 | 80% |
| COOKIE_AUTHENTICATION.md | ✅ Current | 2025-11 | Complete |
| DRY_RUN_MODE.md | ✅ Current | 2025-11 | Complete |

**Legend:**

- ✅ Current - Up to date with latest implementation
- ⚠️ Partial - Mostly current but may have minor gaps
- ⛔ Outdated - Needs significant updates

---

Last Updated: January 4, 2026
