from django.urls import path
from .views import Home, History, VideoFeed

urlpatterns = [
    path("home/", Home, name="home"),
    path("camfeed/", VideoFeed, name="camfeed")
]
