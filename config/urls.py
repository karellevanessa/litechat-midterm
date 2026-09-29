from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Petal administration"
admin.site.site_title = "Petal admin"
admin.site.index_title = "Prices, credit and users"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("", include("chat.urls")),
]
