from rest_framework import serializers

from .models import UserPreference


class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = ['language_code', 'preferred_voiceovers', 'auto_skip_intro']
