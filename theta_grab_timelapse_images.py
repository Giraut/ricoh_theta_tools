#!/usr/bin/env python3
"""Script to take images at regular intervals to create a timelapse video
"""

### Modules
import os
import re
import sys
import json
import argparse
from thetaclass.theta import Theta
from time import time, sleep
from datetime import datetime, timedelta, timezone
from timezonefinder import TimezoneFinder

try:
  from zoneinfo import ZoneInfo
except ImportError:
  from backports.zoneinfo import ZoneInfo

from astral import Observer, Depression
from astral.sun import dawn, dusk, elevation

try:
  import argcomplete	# PYTHON_ARGCOMPLETE_OK
except:
  pass



### Parameters
grab_image_every = 30 #s
retries = 20
wait_before_retry = 2 #s
reconnect_tries = 5

twilight_depression = Depression.NAUTICAL.value # sun ~12 deg below the horizon

# Theta cameras' names and credentials file
#
# The file must have the following format
#
# {
#   "name1": {
#     "addr": "address1",
#     "username": "THETAserial#1",
#     "password": "password1"
#   },
#   "name2": {
#     "addr": "address2",
#     "username": "THETAserial#2",
#     "password": "password2"
#   },
#   ...
# }
theta_cameras_credentials_file = "~/.ricoh_theta_creds.json"

# Theta cameras' location file (optional)
#
# The file must have the following format
#
# {
#   "name1": {
#     "latitude": 12.34567,
#     "longitude": 12.34567,
#     "altitude": 12.3
#   },
#   "name2": {
#     "latitude": 12.34567,
#     "longitude": 12.34567,
#     "altitude": 12.3
#   },
#   ...
# }
theta_cameras_locations_file = "~/.ricoh_theta_location.json"



## Defines
INFO = 0
WARN = 1
ERROR = 2



### Routines
def configure_camera_after_start(rt):
  """Configure the camera before starting the capture or after rebooting it
  """

  log(INFO, "Basic camera setup: UI = locked")
  retry(rt, rt.lock_ui, reconnect_tries = reconnect_tries)

  log(INFO, "Basic camera setup: shutter volume = 0")
  retry(rt, rt.set_shutter_volume, 0, reconnect_tries = reconnect_tries)

  log(INFO, "Basic camera setup: capture mode = image")
  retry(rt, rt.set_capture_mode, "image", reconnect_tries = reconnect_tries)

  log(INFO, "Basic camera setup: stitching mode = static")
  retry(rt, rt.set_capture_mode, "image", reconnect_tries = reconnect_tries)



def configure_camera_for_daytime_capture(rt):
  """Configure the camera to take daytime pictures
  """

  log(INFO, "Daytime camera setup: exposure program = auto")
  retry(rt, rt.set_exposure_program, "auto", reconnect_tries = reconnect_tries)

  log(INFO, "Daytime camera setup: filter = hdr")
  retry(rt, rt.set_filter, "hdr", reconnect_tries = reconnect_tries)

  log(INFO, "Daytime camera setup: EV compensation = 0")
  retry(rt, rt.set_exposure_compensation, 0, reconnect_tries = reconnect_tries)



def configure_camera_for_nighttime_capture(rt):
  """Configure the camera to take daytime pictures
  """

  log(INFO, "Nighttime camera setup: exposure program = manual")
  retry(rt, rt.set_exposure_program, "manual",
					reconnect_tries = reconnect_tries)

  log(INFO, "Nighttime camera setup: shutter_speed = 10s")
  retry(rt, rt.set_shutter_speed, 10, reconnect_tries = reconnect_tries)

  log(INFO, "Nighttime camera setup: ISO sensitivity = 800")
  retry(rt, rt.set_iso_sensitivity, 800, reconnect_tries = reconnect_tries)

  log(INFO, "Nighttime camera setup: EV compensation = 0")
  retry(rt, rt.set_exposure_compensation, 0, reconnect_tries = reconnect_tries)



def theta_camera_names_completer(**kwargs):
  """Argcomplete completer that returns all the names of the cameras declared in
  the Theta cameras' names and credentials file
  """

  global theta_cameras_credentials_file

  try:
    with open(theta_cameras_credentials_file, "r") as f:
      camera_names = json.load(f).keys()

  except:
    camera_names = ()

  return camera_names



def retry(rt, fct, *args, **kwargs):
  """Retry a function call a number of times before failing
  """

  t = 0
  while True:

    t += 1
    try:

      # Close the session to force a reconnect
      rt.close()

      # Retry the function call
      return fct(*args, **kwargs)

    except Exception as e:
      log(ERROR, e)
      if t > retries:
        raise

      log(INFO, "Retry...")
      sys.stdout.flush()

      sleep(wait_before_retry)

      pass



def log(loglevel, *args, prefix = True, linefeed = True, file = sys.stdout):
  """Print part or all of a timestamped log message into the supplied
  file handle
  """

  __last_linefeed = getattr(log, "__last_linefeed", True)

  if prefix:
    if not __last_linefeed:
      print(file = file)
    print(("[INFO] ", "[WARN] ", "[ERROR]")[loglevel],
		"{:%Y-%m-%d %H:%M:%S}".format(datetime.now()),
		end = " ", file = file)

  print(*args, end = "", file = file)

  if linefeed:
    print(file = file)

  setattr(log, "__last_linefeed", linefeed)

  file.flush()



### Main routine
def main():
  """Main routine
  """

  global theta_cameras_credentials_file

  # Parse the command line arguments
  argparser = argparse.ArgumentParser()

  argparser.add_argument(
	  "camera",
	  help = "Name of the camera to use, declared in {}".
			format(theta_cameras_credentials_file),
	  type = str
	).completer = theta_camera_names_completer

  # Expand the tilde in configuration files
  theta_cameras_credentials_file = \
			os.path.expanduser(theta_cameras_credentials_file)

  if "argcomplete" in globals():
    argcomplete.autocomplete(argparser, always_complete_options = False)

  args = argparser.parse_args()

  # Load the Theta cameras' names and credentials file
  with open(os.path.expanduser(theta_cameras_credentials_file), "r") as f:
    theta_cameras_credentials = json.load(f)

  # Try to load the Theta cameras' location file and figure out the location's
  # timezone. If the it doesn't exist, just log a warning
  fp = os.path.expanduser(theta_cameras_locations_file)
  if os.path.exists(os.path.expanduser(fp)):

    with open(fp, "r") as f:
      theta_cameras_locations = json.load(f)

    location = theta_cameras_locations[args.camera]

    latitude = location["latitude"]
    longitude = location["longitude"]
    altitude = location["altitude"]

    observer = Observer(latitude = latitude,
			longitude = longitude,
			elevation = altitude)

    timezone_name = TimezoneFinder().timezone_at(lat = latitude,
							lng = longitude)
    timezone = ZoneInfo(timezone_name)

  else:
    location = None
    log(WARN, "No camera locations file found: no auto day/night config")

  assert args.camera in theta_cameras_credentials

  # Open the camera
  rt = Theta(**theta_cameras_credentials[args.camera])

  # Assume the camera needs setting up when starting, and we don't know whether
  # capture parameters are set for daytime or nighttime, but it doesn't need
  # rebooting at this point
  do_basic_setup = True
  camera_set_for_daytime = None
  do_reboot = False

  # Grab images forever
  while True:

    try:

      # Should we reboot the camera?
      if do_reboot:

        log(WARN, "Rebooting the camera")
        rt.reboot()

        do_reboot = False
        do_basic_setup = True
        camera_set_for_daytime = None

      # Should we do a basic setup of the camera?
      if do_basic_setup:

        configure_camera_after_start(rt)

        do_basic_setup = False
        next_shot_tstamp = time()

      # Wait until the next shot, if needed
      wait_for = next_shot_tstamp - time()
      late_by = -wait_for

      if wait_for > 0:
        log(INFO, "Waiting {:0.1f} s until next the shot".format(wait_for))
        sleep(wait_for)

      elif late_by > 0.5:
        log(INFO, "Not waiting for the next shot as it is already "
			"{:0.1f} s late".format(late_by))

        # Make sure we never run more than one full cycle late
        if late_by > grab_image_every:
          next_shot_tstamp += late_by - grab_image_every
          log(WARN, "Capping the lateness to {:0.1f} s".
			format(grab_image_every))

      # Get the battery's SoC, temperature, PCB temperature and camera errors
      state = retry(rt, rt.get_state, reconnect_tries = reconnect_tries)

      batt_percent = state["batteryLevel"] * 100
      batt_state = state["_batteryState"]
      batt_temp = state["_batteryTemp"]
      pcb_temp = state["_boardTemp"]

      errors = state["_cameraError"]

      if errors:
        errors = ",".join(errors)
      else:
        errors = "/"

      log(INFO, "Batt {:0.0f}% ({}), {:0.1f}C - PCB {:0.1f}C - Errors: {}".
			format(batt_percent, batt_state, batt_temp, pcb_temp,
				errors))

      # Do we have location data?
      if location:

        # Get the time at the camera's location
        now = datetime.now(timezone)

        # try to calculate the nautical dawn and dusk times for today and
        # tomorrow - which may fail in high latitudes when the sun never rises
        # or never sets
        try:

          tomorrow = now + timedelta(days = 1)

          today_dawn_time = dawn(observer,
					date = now.date(),
					depression = twilight_depression,
					tzinfo = now.tzinfo)

          today_dusk_time = dusk(observer,
					date = now.date(),
					depression = twilight_depression,
					tzinfo = now.tzinfo)

          tomorrow_dawn_time = dawn(observer,
					date = tomorrow.date(),
					depression = twilight_depression,
					tzinfo = tomorrow.tzinfo)

          # Determine whether it's daytime or nighttime, and what time the next
          # dusk or dawn is
          if now < today_dawn_time:
            is_daytime = False
            next_dawn_dusk_time = today_dawn_time

          elif now < today_dusk_time:
            is_daytime = True
            next_dawn_dusk_time = today_dusk_time

          else:
            is_daytime = False
            next_dawn_dusk_time = tomorrow_dawn_time

          log(INFO, "Camera location time {:%Y-%m-%d %H:%M:%S} ({}time)".
			format(now,
				"day" if is_daytime else "night"))
          log(INFO, "Next {}: {:%Y-%m-%d %H:%M:%S}".
			format("dusk" if is_daytime else "dawn",
				next_dawn_dusk_time))

        # If calculating dusk and dawn times failed: determine whether it's
        # daytime or nighttime by checking the elevation of the sun
        except:

          is_daytime = elevation(observer, now) >= twilight_depression

          log(INFO, "Cmaera location time {:%Y-%m-%d %H:%M:%S} ({}time)".
			format(now,
				"day" if is_daytime else "night",
				"dusk" if is_daytime else "dawn"))

        # If we don't know whether the camera is setup for day or night shots,
        # or if it's set for the wrong time of the day, reconfigure it
        if is_daytime:
          if camera_set_for_daytime is None or not camera_set_for_daytime:
            configure_camera_for_daytime_capture(rt)
            camera_set_for_daytime = True

        else:	# nighttime
          if camera_set_for_daytime is None or camera_set_for_daytime:
            configure_camera_for_nighttime_capture(rt)
            camera_set_for_daytime = False

      # Take a shot
      log(INFO, "Taking a photo")
      r  = retry(rt, rt.take_photo, reconnect_tries = reconnect_tries)

      file_url = r["results"]["fileUrl"]
      log(INFO, file_url)

      # Schedule the next shot
      next_shot_tstamp += grab_image_every

    except Exception as e:

      log(ERROR, e)
      do_reboot = True



### Main program
if __name__ == "__main__":
  sys.exit(main())
