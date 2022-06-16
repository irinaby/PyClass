from django import forms
from django.contrib.auth.forms import UserCreationForm, UsernameField
from django.contrib.auth.models import User

class PersonalNameField(forms.CharField):
    def __init__(
        self, *, max_length=None, min_length=None, strip=True, empty_value="", **kwargs
    ):
         super().__init__(max_length=5, min_length=min_length, strip=strip, empty_value=empty_value, **kwargs)

class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "first_name", "last_name")
        field_classes = {"username": UsernameField, "first_name": PersonalNameField, "last_name": PersonalNameField}
