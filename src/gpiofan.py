#!/etc/ConsolePi/venv/bin/python3

# Original Author: Andreas Spiess
# Modified by Wade ~ Pack3tL0ss
#
# Provided with ConsolePi but not a required part of ConsolePi
# This script can be used to provide dynamic variable speed support
# for a fan via GPIO
#    currently the desired_temp GPIO pins and other variables are statically configured in this script
#        I will probably add an option to configure it in ConsolePi.yaml so updates to this script
#        don't revert your settings if you want to tweak them.
#          To customize, you can copy this script, then modify the unit file
#           to reference the new location
#
import logging
import logging.handlers
import os
import subprocess
from pathlib import Path
from time import sleep

import RPi.GPIO as GPIO

# Not elegant, but until I figure out how to pass an env var into venv
_fan_debug = os.getenv("FAN_DEBUG", "").lower()
DEBUG = True if _fan_debug == "true" or _fan_debug == "1" or Path("/tmp/FAN_DEBUG").is_file() else False

# -- // LOGGING \\ --
log = logging.getLogger("gpiofand")
log.setLevel(logging.INFO if not DEBUG else logging.DEBUG)
handler = logging.handlers.SysLogHandler(address="/dev/log")
log.addHandler(handler)

fan_pin = 4
battery_mon_pin = 18  # scl
DEFAULT_INTERVAL = 30  # Number of seconds between temp checks
BATTERY_MON = False  # disable / enable battery monitor auto-shutdown

desired_temp = 40  # The maximum temperature in Celsius after which we trigger the fan
# desired_temp = 31 # The maximum temperature in Celsius after which we trigger the fan

fan_speed = 0
prev_fan_speed = 0
sum = 0
pTemp = 15
iTemp = 0.4
interval = DEFAULT_INTERVAL


def do_shutdown():
    fan_off()
    os.system("sudo shutdown -h 1")
    sleep(100)


def get_temp():
    temp = subprocess.run(
        "vcgencmd measure_temp",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
    )
    temp = temp.stdout.decode("UTF-8").replace("temp=", "").replace("'C\n", "")
    log.debug(f"temp is {temp}'C    {round((float(temp) * 1.8), 1) + 32}'F")
    return temp


def fan_off(myPWM):
    myPWM.ChangeDutyCycle(0)  # switch fan off
    return


def handle_fan(myPWM):
    global fan_speed, sum, prev_fan_speed
    actual_temp = float(get_temp())
    diff = actual_temp - desired_temp
    sum = sum + diff
    pDiff = diff * pTemp
    iDiff = sum * iTemp
    fan_speed = round(pDiff + iDiff, 1)
    if fan_speed > 100:
        fan_speed = 100
    elif fan_speed < 15:
        fan_speed = 0

    if sum > 100:
        sum = 100
    elif sum < -100:
        sum = -100

    if fan_speed != prev_fan_speed:
        f_temp = round((actual_temp * 1.8) + 32, 1)
        # We increase the time between checks to 5 mins if the temp is 10+ over desired
        if not BATTERY_MON:
            interval = 320 if diff > 10 else DEFAULT_INTERVAL

        log.info(
            f"Fan Speed change: {prev_fan_speed}% --> {fan_speed}% CPU Temp: {f_temp}'F, "
            f"Desired Temp {(desired_temp * 1.8) + 32}'F, Next Check in {interval}s"  # type: ignore
        )
        prev_fan_speed = fan_speed
    log.debug(
        "actual_temp %4.2f desiredTemp %4.2f TempDiff %4.2f pDiff %4.2f iDiff %4.2f fan_speed %5d"
        % (
            round(actual_temp * 1.8 + 32, 1),
            desired_temp * 1.8 + 32,
            diff,
            pDiff,
            iDiff,
            fan_speed,
        )
    )
    myPWM.ChangeDutyCycle(fan_speed)
    return


def handle_battery():
    log.debug(GPIO.input(battery_mon_pin))
    if GPIO.input(battery_mon_pin) == 0:
        ("do_shutdown()")
        sleep(5)
        do_shutdown()
    return


# Unused debug function
def set_pin(mode):
    GPIO.output(fan_pin, mode)
    return


def main():
    log.debug(f"--- GPIO Fan Monitor Startup DEBUG Enabled ---")
    try:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(fan_pin, GPIO.OUT)
        myPWM = GPIO.PWM(fan_pin, 50)
        myPWM.start(50)

        if BATTERY_MON:
            GPIO.setup(battery_mon_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        fan_off(myPWM)
        while True:
            handle_fan(myPWM)
            if BATTERY_MON:
                handle_battery()
            sleep(interval)
    except KeyboardInterrupt:
        fan_off(myPWM)  # type: ignore
        GPIO.cleanup()  # resets all GPIO ports used by this program
    log.info(f"--- GPIO Fan Monitor ShutDown Fan is off---")


if __name__ == "__main__":
    main()
