from django.urls import path
from .views import Home, History, VideoFeed, today_car_data

urlpatterns = [
    path("home/", Home, name="home"),
    path("camfeed/", VideoFeed, name="camfeed"),
    path("todayData/", today_car_data, name="todayData"),
    path("history/", History.as_view(), name="history")
]
