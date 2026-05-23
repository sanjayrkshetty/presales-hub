# Import all adapters to trigger @ConnectorRegistry.register decorators.
from integration_fabric.adapters import (  # noqa: F401
    salesforce,
    hubspot,
    jira,
    servicenow,
    slack,
    teams,
    outlook,
    gmail,
    sharepoint,
    confluence,
    gdrive,
    webhook_adapter,
)
