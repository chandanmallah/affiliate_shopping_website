
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.shortcuts import render, redirect

from .forms import MemberLoginForm, SignUpForm


# Where to send people after they sign in / sign up / sign out.
# 'product_list' is the name of your home route in urls.py.
HOME_ROUTE = "product_list"


def _safe_next(request, fallback=HOME_ROUTE):
    """Honor ?next= but never redirect off-site (open-redirect guard)."""
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and nxt.startswith("/") and not nxt.startswith("//"):
        return nxt
    return fallback


def member_login(request):
    if request.user.is_authenticated:
        return redirect(HOME_ROUTE)

    if request.method == "POST":
        form = MemberLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            messages.success(request, f"Good to see you again, {user.username}.")
            return redirect(_safe_next(request))
        messages.error(request, "That username and password didn't match. Try again.")
    else:
        form = MemberLoginForm(request)

    return render(request, "registration/login.html", {"form": form})


def member_signup(request):
    if request.user.is_authenticated:
        return redirect(HOME_ROUTE)

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)  # log them straight in after signup
            messages.success(request, f"Welcome aboard, {user.username}. Your account is live.")
            return redirect(_safe_next(request))
        messages.error(request, "Please fix the highlighted fields below.")
    else:
        form = SignUpForm()

    return render(request, "registration/signup.html", {"form": form})


def member_logout(request):
    auth_logout(request)
    messages.info(request, "You've been logged out.")
    return redirect(HOME_ROUTE)
