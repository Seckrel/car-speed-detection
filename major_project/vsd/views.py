from django.shortcuts import render, redirect
from django.views import View
import cv2
from django.views.decorators import gzip
from django.http import StreamingHttpResponse, JsonResponse
import threading
import dlib
import time
from datetime import datetime
import os
import numpy as np
from django.conf import settings
from .models import Car
from datetime import date
from django.utils import timezone
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt


speedLimit = 40


@gzip.gzip_page
def Home(request):
    global speedLimit
    if request.method == "POST":
        print("working here", request.POST)
        speedL = request.POST["speedL"]
        speedLimit = int(speedL)
        print("Change limited", speedLimit)

    context = {'video_feed_url': 'camfeed', "speedl": speedLimit}
    return render(request, "vsd/index.html", context)


@gzip.gzip_page
def VideoFeed(request):
    try:
        cam = VideoCamera()
        return StreamingHttpResponse(gen(cam), content_type="multipart/x-mixed-replace; boundary=frame")
    except:
        pass


def today_car_data(request):
    if request.method == 'GET':
        # Get today's date
        today = timezone.now().date()

        # Wait for new data to become available
        while True:
            # Query the Car model for objects where datetime is today's date
            cars = Car.objects.filter(
                Q(datetime__gte=today) & Q(datetime__lte=today))

            # If there is new data, return a JSON response with the car data
            if cars.exists():
                car_data = []
                for car in cars:
                    data = {
                        'car_id': car.car_id,
                        'datetime': car.datetime,
                        'speed': car.speed,
                        'overspeeding': car.overspeeding,
                        'link': car.link
                    }
                    car_data.append(data)

                return JsonResponse({'data': car_data})


class History(View):
    def get(self, request):
        context = {"error": "", "from_date": "",
                   "to_date": ""}
        return render(request, "vsd/history.html", context)

    def post(self, request):
        from_date_str = request.POST.get("from_date")
        to_date_str = request.POST.get("to_date")

        from_date = datetime.strptime(from_date_str, '%d/%m/%Y').date()
        to_date = datetime.strptime(to_date_str, '%d/%m/%Y').date()

        context = {"error": "", "from_date": from_date_str,
                   "to_date": to_date_str}

        if from_date and to_date:
            if from_date <= to_date:
                cars = Car.objects.filter(
                    Q(datetime__gte=from_date) & Q(datetime__lte=to_date))
                context["cars"] = cars
                return render(request, "vsd/history.html", context)
            else:
                context["error"] = "To date cannot be less than from date"
        else:
            context["error"] = "Both date need to filled"

        # Do something with my_data
        today = timezone.now().date()

        return render(request, "vsd/history.html", context)


@method_decorator(csrf_exempt, name="post")
class ChangeSpeedLimit(View):
    def post(self, request):
        speedL = request.POST["speedL"]
        global speedLimit
        speedLimit = speedL
        print("="*5, speedLimit, "=" % 5)


WIDTH = 1280
HEIGHT = 720
cropBegin = 240
mark1 = 120
mark2 = 360
markGap = 15
fpsFactor = 3
startTracker = {}
endTracker = {}


def blackout(image):
    xBlack = 360
    yBlack = 300
    triangle_cnt = np.array([[0, 0], [xBlack, 0], [0, yBlack]])
    triangle_cnt2 = np.array([[WIDTH, 0], [WIDTH-xBlack, 0], [WIDTH, yBlack]])
    cv2.drawContours(image, [triangle_cnt], 0, (0, 0, 0), -1)
    cv2.drawContours(image, [triangle_cnt2], 0, (0, 0, 0), -1)

    return image


def saveCar(speed, image):
    now = datetime.today().now()
    loc = os.path.join(settings.BASE_DIR, "vsd", "static", "overspeeding")
    nameCurTime = now.strftime("%d-%m-%Y-%H-%M-%S-%f")

    # link = loc+nameCurTime+'.jpeg'
    link = os.path.join(loc, nameCurTime+".jpeg")
    cv2.imwrite(link, image)
    return os.path.join("static", "overspeeding", nameCurTime+'.jpeg')


# FUNCTION TO CALCULATE SPEED----------------------------------------------------
def estimateSpeed(carID):
    timeDiff = endTracker[carID]-startTracker[carID]
    speed = round(markGap/timeDiff*fpsFactor*3.6, 2)
    return speed


class VideoCamera(object):
    def __init__(self) -> None:
        # debug mode
        videLoc = os.path.join(settings.BASE_DIR, "vsd",
                               "static", "videoTest.mp4")
        self.video = cv2.VideoCapture(videLoc)

        cascadeLoc = os.path.join(
            settings.BASE_DIR, "vsd", "static", "cascade", "HaarCascadeClassifier.xml")
        self.carCascade = cv2.CascadeClassifier(cascadeLoc)

        (self.grabbed, self.frame) = self.video.read()
        threading.Thread(target=self.update, args=()).start()

    def __del__(self):
        self.video.release()

    def get_frame(self):
        image = self.frame
        _, jpeg = cv2.imencode(".jpg", image)
        return jpeg.tobytes()

    def update(self):
        carCascade = self.carCascade

        rectangleColor = (0, 255, 0)
        frameCounter = 0
        currentCarID = 0
        carTracker = {}
        while True:
            (self.grabbed, self.frame) = self.video.read()
            image = self.frame
            if type(image) == type(None):
                break

            frameTime = time.time()
            image = cv2.resize(image, (WIDTH, HEIGHT))[cropBegin:720, 0:1280]
            resultImage = blackout(image)
            cv2.line(resultImage, (0, mark1), (1280, mark1), (0, 0, 255), 2)
            cv2.line(resultImage, (0, mark2), (1280, mark2), (0, 0, 255), 2)

            frameCounter = frameCounter + 1

            # DELETE CARIDs NOT IN FRAME---------------------------------------------
            carIDtoDelete = []

            for carID in carTracker.keys():
                trackingQuality = carTracker[carID].update(image)

                if trackingQuality < 7:
                    carIDtoDelete.append(carID)

            for carID in carIDtoDelete:
                carTracker.pop(carID, None)

            if (frameCounter % 60 == 0):
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                cars = carCascade.detectMultiScale(gray, 1.1, 13, 18, (24, 24))

                for (_x, _y, _w, _h) in cars:

                    x = int(_x)
                    y = int(_y)
                    w = int(_w)
                    h = int(_h)

                    xbar = x + 0.5*w
                    ybar = y + 0.5*h

                    matchCarID = None

                    for carID in carTracker.keys():
                        trackedPosition = carTracker[carID].get_position()

                        tx = int(trackedPosition.left())
                        ty = int(trackedPosition.top())
                        tw = int(trackedPosition.width())
                        th = int(trackedPosition.height())

                        txbar = tx + 0.5 * tw
                        tybar = ty + 0.5 * th

                        if ((tx <= xbar <= (tx + tw)) and (ty <= ybar <= (ty + th)) and (x <= txbar <= (x + w)) and (y <= tybar <= (y + h))):
                            matchCarID = carID

                    if matchCarID is None:
                        tracker = dlib.correlation_tracker()
                        tracker.start_track(
                            image, dlib.rectangle(x, y, x + w, y + h))

                        carTracker[currentCarID] = tracker

                        currentCarID = currentCarID + 1

            for carID in carTracker.keys():
                trackedPosition = carTracker[carID].get_position()

                tx = int(trackedPosition.left())
                ty = int(trackedPosition.top())
                tw = int(trackedPosition.width())
                th = int(trackedPosition.height())

                cv2.rectangle(resultImage, (tx, ty),
                              (tx + tw, ty + th), rectangleColor, 2)
                cv2.putText(resultImage, str(carID), (tx, ty-5),
                            cv2.FONT_HERSHEY_DUPLEX, 1, (0, 255, 0), 1)

                if carID not in startTracker and mark2 > ty+th > mark1 and ty < mark1:
                    startTracker[carID] = frameTime

                elif carID in startTracker and carID not in endTracker and mark2 < ty+th:
                    endTracker[carID] = frameTime
                    speed = estimateSpeed(carID)
                    linkToSavedCar = None
                    overSpeedingFlag = False
                    if speed > speedLimit:
                        overSpeedingFlag = True
                        print(
                            'CAR-ID : {} : {} kmph - OVERSPEED'.format(carID, speed))
                        linkToSavedCar = saveCar(
                            speed, image[ty:ty+th, tx:tx+tw])
                    else:
                        print('CAR-ID : {} : {} kmph'.format(carID, speed))

                    car = Car(
                        car_id=carID,
                        speed=speed,
                        overspeeding=overSpeedingFlag,
                        link=linkToSavedCar if linkToSavedCar != None else ""
                    )

                    car.save()

            self.frame = resultImage


def gen(camera):
    while True:
        frame = camera.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
