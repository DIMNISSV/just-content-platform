from django.contrib.auth import login
from django.shortcuts import render, redirect
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated

from .forms import UserRegistrationForm
from .models import UserPreference
from .serializers import UserPreferenceSerializer


def register_view(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = UserRegistrationForm()
    return render(request, 'registration/register.html', {'form': form})


class UserPreferenceAPIView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserPreferenceSerializer

    def get_object(self):
        # get_or_create на случай, если старые пользователи не имеют настроек
        pref, _ = UserPreference.objects.get_or_create(user=self.request.user)
        return pref
