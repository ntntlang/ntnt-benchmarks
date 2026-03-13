from django.urls import path
from bench import views

urlpatterns = [
    path('plaintext', views.plaintext),
    path('json', views.json_view),
    path('users/<int:user_id>', views.user_by_id),
    path('db', views.db_single),
    path('queries', views.queries),
    path('template', views.template),
]
