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


class KodikDumpProcessedID(models.Model):
    """
    Stores identifiers of titles already processed during a dump sync
    to avoid redundant processing and deep API calls.
    """
    kp_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    imdb_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    shiki_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    mdl_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Processed ID (KP:{self.kp_id}, IMDb:{self.imdb_id}, Shiki:{self.shiki_id}, MDL:{self.mdl_id})"
