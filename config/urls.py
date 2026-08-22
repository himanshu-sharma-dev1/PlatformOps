import os
from pathlib import Path

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.views import serve as staticfiles_serve
from django.urls import include, path, re_path
from django.views.static import serve as static_serve

from cPlatformIO.views import LicenseFailView, UserLoginView

BASE_DIR = Path(__file__).resolve().parent.parent
config_path = os.path.join(BASE_DIR, 'cPlatformIO')


def _serve_prefix(prefix, view, **kwargs):
    route = r'^%s/(?P<path>.*)$' % prefix.lstrip('/').rstrip('/')
    return re_path(route, view, kwargs=kwargs)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', UserLoginView.as_view(), name='login'),
    path('license-fail/', LicenseFailView.as_view(), name='license_fail'),
    path('', include('django_prometheus.urls')),
    path('', include("django.contrib.auth.urls")),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('', include('cPlatformIO.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.IMG_URL, document_root=settings.IMG_ROOT)
else:
    # The mounted docker setup serves gunicorn directly on port 80, so Django
    # must serve static assets itself when DEBUG=False.
    urlpatterns += [
        _serve_prefix(settings.STATIC_URL, staticfiles_serve, insecure=True),
        _serve_prefix(settings.MEDIA_URL, static_serve, document_root=settings.MEDIA_ROOT),
        _serve_prefix(settings.IMG_URL, static_serve, document_root=settings.IMG_ROOT),
    ]

