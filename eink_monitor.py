#!/usr/bin/env python3

import os
import socket
import logging
import struct
import time
import datetime
import re
import sys
import psutil
import smbus  # type:ignore[reportMissingImports]
import RPi.GPIO as GPIO  # type:ignore[reportMissingImports]
from waveshare_epd import epd2in13_V4  # type:ignore[reportMissingImports]
from PIL import Image, ImageDraw, ImageFont  # type:ignore[reportMissingImports]

REFRESH_RATE = 1
ROTATE = True
FULL_UPDATE_INTERVAL = 60

CW2015_ADDRESS   = 0X62
CW2015_REG_VCELL = 0X02
CW2015_REG_SOC   = 0X04
CW2015_REG_MODE  = 0X0A

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(funcName)s: %(message)s",
                    datefmt='%H:%M:%S')

assets = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'assets')
bold13 = ImageFont.truetype(os.path.join(assets, 'PT_Sans_bold.ttf'), 13)
bold24 = ImageFont.truetype(os.path.join(assets, 'PT_Sans_bold.ttf'), 24)
regular10 = ImageFont.truetype(os.path.join(assets, 'PT_Sans-Web-Regular.ttf'), 10)
chargingIcon = Image.open(os.path.join(assets, "Charging.bmp"))
lastFullUpdate = time.time()
bus = smbus.SMBus(1)
epd = epd2in13_V4.EPD()
screen = Image.new('1', (epd.height, epd.width), 255)
draw = ImageDraw.Draw(screen)


def drawUI():
    def getRPiModel():
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read().strip('\x00')
        model = re.sub(r'\s*Rev\s*[\d.]+$', '', model, flags=re.IGNORECASE)
        if model.startswith("Raspberry Pi"):
            line = "RPi " + model[len("Raspberry Pi"):].strip()
        else:
            line = model
        return line

    def getLocalIP():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except (socket.error, OSError):
            return "127.0.0.1"

    def drawHostnameInfo(draw, font, x, y):
        fullText = f"{os.getlogin()}@{socket.gethostname()}"
        hostnameOnly = socket.gethostname()

        fullBbox = font.getbbox(fullText)
        fullWidth = fullBbox[2] - fullBbox[0]
        maxWidth = epd.height - x

        if fullWidth <= maxWidth: draw.text((x, y), fullText, font=font, fill=0)
        else: draw.text((x, y), hostnameOnly, font=font, fill=0)

    logging.info("Drawing UI...")

    for (bmp, pos) in [("Battery.bmp", (0, 0)),
                       ("CPU.bmp", (0, 30)),
                       ("RAM.bmp", (0, 60)),
                       ("Internet.bmp", (173, 50)),
                       ("Clock.bmp", (173, 66)),
                       ("Temperature.bmp", (173, 82)),
                       ("MicroSD.bmp", (0, 90))]:
        icon = Image.open(os.path.join(assets, bmp))
        screen.paste(icon, pos)

    draw.line([(168, 0), (168, 120)], fill=0, width=3)  # Вертикальная линия
    draw.line([(168, 45), (260, 45)], fill=0, width=3)  # Горизонтальная линия
    draw.text((186, 48), f"{getLocalIP()}", font=regular10, fill=0)  # IP адрес
    draw.text((175, 95), getRPiModel(), font=regular10, fill=0)  # Модель Raspberry Pi
    drawHostnameInfo(draw, regular10, 175, 105)

    buffer = epd.getbuffer(screen.transpose(Image.ROTATE_180)) if ROTATE else epd.getbuffer(screen)

    epd.displayPartBaseImage(buffer)

    logging.info("UI done, now running main loop...")


def getValues() -> dict:
    info = {}

    if UPSDetected:
        info["voltage"] = readVoltage(bus)
        info["capacity"] = readCapacity(bus)

    with open('/sys/class/thermal/thermal_zone0/temp', 'r') as tempFile: info["temp"] = tempFile.read()
    info["uptime"] = time.time() - psutil.boot_time()
    info["mem"] = psutil.virtual_memory()
    info["disk"] = psutil.disk_usage('/')
    info["CPUPercent"] = psutil.cpu_percent()
    info["CPUFreq"] = psutil.cpu_freq()
    info["datetime"] = datetime.datetime.now()

    return info


def drawValues():
    def clearData():
        draw.rectangle([(38, 4), (164, 120)], fill=1)   # Очистка левой панели
        draw.rectangle([(170, 0), (250, 36)], fill=1)   # Очистка времени и даты
        draw.rectangle([(186, 64), (250, 76)], fill=1)  # Очистка uptime
        draw.rectangle([(186, 80), (250, 90)], fill=1)  # Очистка температуры
        draw.rectangle([(5, 12), (22, 20)], fill=1)     # Очистка батареи

    def drawUptime(draw, font, x, y):
        uptimeSeconds = info["uptime"]

        days = int(uptimeSeconds // 86400)
        hours = int((uptimeSeconds % 86400) // 3600)
        minutes = int((uptimeSeconds % 3600) // 60)
        seconds = int(uptimeSeconds % 60)

        variants = []
        componentsList = [
            [(days, 'd'), (hours, 'h'), (minutes, 'm'), (seconds, 's')],
            [(days, 'd'), (hours, 'h'), (minutes, 'm')],
            [(days, 'd'), (hours, 'h')],
        ]

        for componentsConfig in componentsList:
            components = []
            for value, unit in componentsConfig:
                if value > 0:
                    components.append(f"{value}{unit}")

            if not components:
                lastUnitValue = componentsConfig[-1][0] if componentsConfig else seconds
                unit = componentsConfig[-1][1] if componentsConfig else 's'
                components.append(f"{lastUnitValue}{unit}")

            variants.append(" ".join(components))

        maxWidth = epd.height - x
        selectedUptime = variants[-1]

        for text in variants:
            bbox = regular10.getbbox(text)
            width = bbox[2] - bbox[0]

            if width <= maxWidth:
                selectedUptime = text
                break

        draw.text((x, y), selectedUptime, font=font, fill=0)

    def formatRAM() -> str:
        mem = info["mem"]
        totalGB = mem.total / 1024**3
        used = mem.total - mem.available
        unit = "GB" if totalGB >= 1 else "MB"
        factor = 1024**3 if unit == "GB" else 1024**2
        return f'{mem.percent:.0f}%  -  {used / factor:.0f}/ {mem.total / factor:.0f} {unit}'

    def formatDisk() -> str:
        disk = info["disk"]
        totalGB = disk.total / 1024**3
        usedGB = disk.used / 1024**3
        percent = disk.percent
        unit = "GB" if totalGB >= 1 else "MB"
        return f'{percent}%  - {usedGB:.1f}/ {totalGB:.1f} {unit}'

    def formatCPU():
        CPUPercent = info["CPUPercent"]
        CPUFreq = info["CPUFreq"]
        return f"{CPUPercent:.0f}%  -  {CPUFreq.current / 1000:.1f}/ {CPUFreq.max / 1000:.1f} GHz"

    def formatTemperature():
        temp = info["temp"]
        return int(temp) / 1000.0

    def setBatteryIcon():
        if not UPSDetected: return  # Если UPS не подключен, не рисуем иконку
        capacity = round(info["capacity"])
        if capacity >= 0:
            draw.rectangle([(5, 12), (6, 20)], fill=0)
        if capacity >= 20:
            draw.rectangle([(9, 12), (10, 20)], fill=0)
        if capacity >= 60:
            draw.rectangle([(13, 12), (14, 20)], fill=0)
        if capacity >= 80:
            draw.rectangle([(17, 12), (18, 20)], fill=0)
        if capacity >= 100:
            draw.rectangle([(21, 12), (22, 20)], fill=0)

    def setChargingIcon():
        if not UPSDetected: return  # Если UPS не подключен, не рисуем иконку
        if GPIO.input(4) == GPIO.HIGH:
            batteryBbox = bold13.getbbox(f'{round(info["capacity"])}% | {round(info["voltage"], 2)}V')
            batteryWidth = batteryBbox[2] - batteryBbox[0]
            screen.paste(chargingIcon, (batteryWidth + 50, 11))

    def updateScreen():
        global lastFullUpdate
        buffer = epd.getbuffer(screen.transpose(Image.ROTATE_180)) if ROTATE else epd.getbuffer(screen)
        if time.time() - lastFullUpdate > FULL_UPDATE_INTERVAL:
            logging.debug("Full refresh to prevent ghosting")
            epd.display(buffer)
            epd.displayPartBaseImage(buffer)
            lastFullUpdate = time.time()
        else:
            epd.displayPartial(buffer)

    logging.debug("Refreshing EPD...")
    clearData()
    formatRAM()
    setBatteryIcon()
    setChargingIcon()
    drawUptime(draw, regular10, 186, 64)  # Uptime
    if not UPSDetected: draw.text((38, 6), "UPS not detected", font=bold13, fill=0)
    else: draw.text((38, 6), f'{round(info["capacity"])}%  -  {round(info["voltage"], 2)}V', font=bold13)
    draw.text((38, 36), formatCPU(), font=bold13)                                     # Процессор
    draw.text((38, 66), formatRAM(), font=bold13)                                     # ОЗУ
    draw.text((38, 96), formatDisk(), font=bold13)                                    # Память
    draw.text((172, 0), info["datetime"].strftime("%H:%M"), font=bold24, fill=0)      # Часы и минуты
    draw.text((233, 10), ":" + info["datetime"].strftime("%S"), font=bold13, fill=0)  # Секунды
    draw.text((180, 22), info["datetime"].strftime("%d.%m.%Y"), font=bold13, fill=0)  # Дата
    draw.text((186, 80), f"{formatTemperature():.1f} °C", font=regular10, fill=0)     # Температура
    updateScreen()


def initEPD():
    logging.info("Initializing EPD...")
    epd.init()
    epd.Clear()
    logging.info("EPD initialized")


def initUPS() -> bool:
    logging.info("Initializing UPS...")
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(4, GPIO.IN)  # GPIO4 is used to detect whether an external power supply is inserted
    try: bus.write_word_data(CW2015_ADDRESS, CW2015_REG_MODE, 0x30)
    except OSError as e:
        if "Input/output error" in str(e):
            logging.warning("UPS not detected!")
            GPIO.cleanup()
            return False
        else:
            logging.error(f"Failed to initialize UPS: {e}")
            GPIO.cleanup()
            sys.exit(1)
    else:
        logging.info("UPS initialized")
        return True


def readVoltage(bus):
    "This function returns as float the voltage from the Raspi UPS Hat via the provided SMBus object"
    read = bus.read_word_data(CW2015_ADDRESS, CW2015_REG_VCELL)
    swapped = struct.unpack("<H", struct.pack(">H", read))[0]
    voltage = swapped * 0.305 / 1000
    return voltage


def readCapacity(bus):
    "This function returns as a float the remaining capacity of the battery connected to the Raspi UPS Hat via the provided SMBus object"
    read = bus.read_word_data(CW2015_ADDRESS, CW2015_REG_SOC)
    swapped = struct.unpack("<H", struct.pack(">H", read))[0]
    capacity = swapped / 256
    return capacity


def shutdown():
    logging.info("Clearing EPD...")
    epd.init()
    epd.Clear(0xFF)
    epd.sleep()
    epd2in13_V4.epdconfig.module_exit(cleanup=True)
    exit()


if __name__ == "__main__":
    try:
        UPSDetected = initUPS()
        initEPD()
        drawUI()
        while True:
            start = time.time()
            info = getValues()
            drawValues()
            elapsed = time.time() - start
            sleep_time = max(0, REFRESH_RATE - elapsed)
            if UPSDetected and info["capacity"] <= 0 and not GPIO.input(4):
                logging.info("Capacity is 0%, shutting down...")
                shutdown()  # Отключить при 0% зарядки чтобы на дисплее не осталось картинки
            time.sleep(sleep_time)
    except KeyboardInterrupt:
        logging.info("Ctrl+C pressed")
        shutdown()
