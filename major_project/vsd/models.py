from django.db import models


class Car(models.Model):
    car_id = models.CharField(max_length=50)
    datetime = models.DateTimeField(auto_now_add=True)
    speed = models.FloatField()
    overspeeding = models.BooleanField()
    link = models.URLField(default=None, blank=True)

    def __str__(self):
        return self.car_id
