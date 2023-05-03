import torch
import cv2
import threading
import time
import pyfirmata
import serial.tools.list_ports
import locale
from pyfirmata.util import Iterator
from flask import Flask, render_template, make_response, request

# U SLUČAJU DA SE POGREŠNA KAMERA PRIKAZUJE, ILI NEMA SLIKE, PROMIJENITE BROJ KAMERE!

KAMERA = 1  # Broj kamere

# THREAD ZA DETEKCIJU
def detekcija():
    global img

    torch.no_grad()
    model = torch.hub.load('ultralytics/yolov5', 'custom', 'best.pt') # YOLOv5 model + custom dataset
    cam = cv2.VideoCapture(KAMERA, cv2.CAP_DSHOW)

    while(cam.isOpened()):
        ret, frame = cam.read()                                 # Slika s kamere
        #frame = cv2.imread("pozar.jpg")
        frame = cv2.resize(frame, (640, 480))                   # Promijeni veličinu slike
        results = model(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)) # Procesuiraj sliku kroz model
        results.render()                                        # Nacrtaj rezultate na sliku
        img = results.ims[0]                                    # Stavi sliku u varijablu img za dalje korištenje

# THREAD ZA SENZORE
def arduino():
    global temp1, temp2
    port = ""
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if "Arduino" in p.description:
            port = p.device  # Automatsko pronalaženje porta na kojem je Arduino
    print(port)

    board = pyfirmata.Arduino(port)
    iterator = Iterator(board)
    iterator.start()
    senzor1 = board.get_pin('a:0:i') # Pinovi za sensore
    senzor2 = board.get_pin('a:1:i')

    led = False
    
    while senzor2.read() is None:
        continue
    while True:
        s1 = 0
        s2 = 0
        for i in range(25):  # 25 očitavanja oba senzora
            time.sleep(0.01)
            s1 += 5.0*100*senzor1.read()
            s2 += 5.0*100*senzor2.read()

        temp1 = int(s1/25)  # Prosjek od 25 očitavanja
        temp2 = int(s2/25)

        if (temp1 > 40 or temp2 > 40):
            led = not(led)                  # Blinkaj LED
            board.digital[12].write(led)    
            board.digital[11].write(1)      # Upali piezo
        else:
            board.digital[12].write(0)      # LED
            board.digital[11].write(0)      # Ugasi piezo

        #print(f"Senzor 1: {temp1} Celsius")
        #print(f"Senzor 2: {temp2} Celsius")

locale.setlocale(locale.LC_TIME, "bs")
pozari = [{
    "lokacija": [43.6518, 17.9631],
    "vrijeme": time.strftime("%a %d %b %Y, %H:%M"),
    "opis": "gori gori gori"
},
{
    "lokacija": [43.6528, 17.9691],
    "vrijeme": time.strftime("%a %d %b %Y, %H:%M"),
    "opis": "gori gori gori"
},
{
    "lokacija": [43.6528, 17.9651],
    "vrijeme": time.strftime("%a %d %b %Y, %H:%M"),
    "opis": "gori gori gori"
}]

#threading.Thread(target=detekcija, daemon=True).start() # Započni thread za detekciju
threading.Thread(target=arduino, daemon=True).start()   # Započni thread za arduino

app = Flask(__name__)

# Glavna stranica
@app.route("/")
def index():
    return render_template('home.html')

# Temperature senzora
@app.route("/temp")
def temp():
    try:
        return [temp1, temp2]
    except NameError: # U slučaju da thread za Arduino nije započet i "temp1" i "temp2" nisu definisani
        return ""

@app.route('/<path:path>')
def serve_html(path):
    return render_template(path + '.html')

@app.route("/pozar", methods=['GET', 'POST'])
def pozar():
    if(request.method == "POST"): 
        pozari.append({
            "lokacija": request.form.get("lokacija"),
            "vrijeme": time.strftime("%a %d %b %Y, %H:%M"),
            "tip": request.form.get("tip"),
            "opis": request.form.get("opis")
        })
        return "OK", 200
    if(request.method == "GET"):
        return pozari

# Slika
@app.route("/image")
def image():
    try:
        global img # "img" varijabla od prije
        retval, buffer = cv2.imencode('.jpg', cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        return make_response(buffer.tobytes())
    except NameError:   # U slučaju da thread za detekciju nije započet i "img" nije definisan
        return ""
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80, debug=True, use_reloader=False)
