

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User


# Shared widget styling. Every input picks up `.auth-input` from styles.css.
_INPUT = {"class": "auth-input"}


class MemberLoginForm(AuthenticationForm):
    """Username + password, styled to match the site."""

    username = forms.CharField(
        widget=forms.TextInput(
            attrs={**_INPUT, "placeholder": "Username", "autofocus": True}
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={**_INPUT, "placeholder": "Password"}
        )
    )


class SignUpForm(UserCreationForm):
    """Username + email + password (with confirmation)."""

    email = forms.EmailField(
        required=True,
        help_text="We'll only use this to send deal alerts you opt into.",
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {**_INPUT, "placeholder": "Choose a username", "autofocus": True}
        )
        self.fields["email"].widget.attrs.update(
            {**_INPUT, "placeholder": "you@email.com"}
        )
        self.fields["password1"].widget.attrs.update(
            {**_INPUT, "placeholder": "Create a password"}
        )
        self.fields["password2"].widget.attrs.update(
            {**_INPUT, "placeholder": "Confirm password"}
        )

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class ContactForm(forms.Form):
    name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={"class": "auth-input", "placeholder": "Your name"}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "auth-input", "placeholder": "you@email.com"}),
    )
    subject = forms.CharField(
        max_length=160,
        widget=forms.TextInput(attrs={"class": "auth-input", "placeholder": "What's this about?"}),
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={"class": "auth-input", "rows": 6, "placeholder": "How can we help?"}),
    )