from django.db import models


class KodikSyncState(models.Model):
    """
    Stores the cursor/progress state for various synchronization tasks.
    """
    key = models.CharField(max_length=100, unique=True, help_text="Unique identifier for the sync task")
    state_data = models.JSONField(default=dict, help_text="Stored state (e.g., next_page_url, last_index)")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key
