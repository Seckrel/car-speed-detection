from django.contrib import admin
from .models import Car

# Register your models here.


class CarAdmin(admin.ModelAdmin):
    list_display = ('car_id', 'datetime', 'speed', 'overspeeding', 'link')


admin.site.register(Car, CarAdmin)
