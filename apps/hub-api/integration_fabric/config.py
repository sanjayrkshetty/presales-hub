"""
Enterprise Integration Fabric — configuration constants.
All timeouts in seconds. All sizes in bytes.
"""

# Connector timeouts
CONNECTOR_CONNECT_TIMEOUT = 10
CONNECTOR_READ_TIMEOUT = 30
CONNECTOR_DEFAULT_PAGE_SIZE = 100

# Retry / DLQ
RETRY_MAX_ATTEMPTS = 5
RETRY_BASE_DELAY_S = 1.0
RETRY_MAX_DELAY_S = 300.0
RETRY_BACKOFF_FACTOR = 2.0
DLQ_MAX_SIZE = 10_000
DLQ_RETENTION_DAYS = 30

# Rate limits (per connector per tenant, requests/minute)
DEFAULT_RATE_LIMIT_RPM = 60
SALESFORCE_RATE_LIMIT_RPM = 100
HUBSPOT_RATE_LIMIT_RPM = 110
JIRA_RATE_LIMIT_RPM = 60
SERVICENOW_RATE_LIMIT_RPM = 50
SLACK_RATE_LIMIT_RPM = 60
TEAMS_RATE_LIMIT_RPM = 60
OUTLOOK_RATE_LIMIT_RPM = 60
GMAIL_RATE_LIMIT_RPM = 250
SHAREPOINT_RATE_LIMIT_RPM = 600
CONFLUENCE_RATE_LIMIT_RPM = 60
GDRIVE_RATE_LIMIT_RPM = 1000
WEBHOOK_RATE_LIMIT_RPM = 600

# OAuth2
OAUTH2_TOKEN_EXPIRY_BUFFER_S = 60   # refresh if token expires within this window
CREDENTIAL_ENCRYPTION_KEY_ENV = "INTEGRATION_CREDENTIAL_KEY"

# Webhook
WEBHOOK_SIGNATURE_HEADER = "X-Hub-Signature-256"
WEBHOOK_TIMEOUT_S = 10
WEBHOOK_MAX_RETRIES = 3
WEBHOOK_DELIVERY_TIMEOUT_S = 5

# Sync
SYNC_RECONCILE_INTERVAL_S = 300    # 5 minutes
SYNC_DRIFT_THRESHOLD_FIELDS = 3    # flag drift if ≥3 fields diverge
SYNC_CONFLICT_STRATEGY = "last_write_wins"  # last_write_wins | manual | source_wins

# Ingestion
INGESTION_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
INGESTION_SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
    "text/html",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

# RBAC
RBAC_ROLES = ["admin", "presales_lead", "sme", "executive", "approver", "analyst", "readonly"]
RBAC_AUDIT_RETENTION_DAYS = 365

# Observability
METRIC_RETENTION_DAYS = 90
HEALTH_CHECK_INTERVAL_S = 60
CONNECTOR_UNHEALTHY_FAILURE_THRESHOLD = 3
