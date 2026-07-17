import uuid

from django.conf import settings
from django.db import models


class UserInterestProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='interest_profiles',
        verbose_name='Пользователь'
    )
    guest_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='ID гостя'
    )
    taxonomy_distribution = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Распределение таксономии',
        help_text='JSON вида {taxonomy_item_slug: accumulated_weight}'
    )
    type_distribution = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Распределение типов',
        help_text="JSON вида {'MOVIE': weight, 'SERIES': weight}"
    )
    year_distribution = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Распределение годов',
        help_text="JSON вида {'modern': weight, '2010s': weight, ...}"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    class Meta:
        verbose_name = 'Профиль интересов'
        verbose_name_plural = 'Профили интересов'
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                name='unique_user_profile',
                condition=models.Q(user__isnull=False)
            ),
            models.UniqueConstraint(
                fields=['guest_id'],
                name='unique_guest_profile',
                condition=models.Q(guest_id__isnull=False)
            ),
        ]

    def __str__(self):
        identifier = self.user.email if self.user else f"Guest {self.guest_id}"
        return f"Interest Profile for {identifier}"
