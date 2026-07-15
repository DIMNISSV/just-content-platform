from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField(verbose_name='Электронная почта', unique=True)
    trust_score = models.IntegerField(default=0, verbose_name='Уровень доверия')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.email


class UserPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences', verbose_name='Пользователь')
    language_code = models.CharField(max_length=20, default='rus',
                                     verbose_name='Код языка',
                                     help_text="Жесткое ограничение языка (например: rus, eng)")
    preferred_voiceovers = models.JSONField(default=list, blank=True,
                                            verbose_name='Приоритетные студии озвучки',
                                            help_text="Массив приоритетов (например: ['LostFilm', 'HDrezka'])")
    auto_skip_intro = models.BooleanField(default=False, verbose_name='Автопропуск заставки',
                                          help_text="Автоматически пропускать заставки")

    class Meta:
        verbose_name = 'Настройки пользователя'
        verbose_name_plural = 'Настройки пользователей'

    def __str__(self):
        return f"Настройки пользователя {self.user}"
