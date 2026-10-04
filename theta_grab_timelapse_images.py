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
take_photo_every = 30 #s
check_camera_state_every = 300 #s
run_camera_in_silent_powermode = False
turn_off_camera_when_battery_below = 30 #%
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
#
# The file may also contain entries with "username" and "password" set to null
# to access the camera in direct mode (i.e. camera acting as a wifi AP).
# Typically, the entry would look like this if the computer is connected
# directly to the camera's wifi AP:
#
#   ...
#   "ap": {
#     "addr": "192.168.1.1",
#     "username": null,
#     "password": null
#   },
#   ...
#
#
# The address may also contain a port, if the connection to the camera is
# redirected (for instance with ssh: "ssh remote_machine -L8000:camera_ip:80"),
# like:
#
#   ...
#   "redirected_ap": {
#     "addr": "localhost:8000",
#     "username": null,
#     "password": null
#   },
#   ...
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

# File to store event timestamps (per camera), in case the script stops (or is
# stopped) and immediately restarted, to keep the timing of the photos correct
event_timestamps_file = "~/.ricoh_theta_timelapse_grab_event_timestamps-{}.json"



## Defines
INFO = 0
WARN = 1
ERROR = 2

POSTPONED = 90000000000
NEVER = POSTPONED



### Routines
def configure_camera_basic_setup(rt):
  """Configure the camera before starting the capture or after rebooting it
  Return the number of tries
  """

  if run_camera_in_silent_powermode:
    log(INFO, "Basic camera setup: power mode = silent")
  else:
    log(INFO, "Basic camera setup: UI = locked")
    log(INFO, "Basic camera setup: shutter volume = 0")
  log(INFO, "Basic camera setup: capture mode = image")
  log(INFO, "Basic camera setup: stitching mode = static")

  if run_camera_in_silent_powermode:
    options = {"_cameraPower": "silentMode"}
  else:
    options = {"_cameraControlSource": "app",
		"_shutterVolume": 0}
  options = {**options,
		**{"captureMode": "image",
			"_imageStitching": "static"}}

  _, tries = retry(rt, rt._set_options, options,
			reconnect_tries = reconnect_tries)

  return tries



def configure_camera_for_daytime_capture(rt):
  """Configure the camera to take daytime pictures
  Return the number of tries
  """

  log(INFO, "Daytime camera setup: exposure program = auto")
  log(INFO, "Daytime camera setup: filter = hdr")
  log(INFO, "Daytime camera setup: EV compensation = 0")

  options = {"exposureProgram": 2,
		"_filter": "off",
		"exposureCompensation": 0}

  _, tries = retry(rt, rt._set_options, options,
			reconnect_tries = reconnect_tries)

  return tries



def configure_camera_for_nighttime_capture(rt):
  """Configure the camera to take daytime pictures
  Return the number of tries
  """

  log(INFO, "Nighttime camera setup: exposure program = manual")
  log(INFO, "Nighttime camera setup: shutter_speed = 10s")
  log(INFO, "Nighttime camera setup: ISO sensitivity = 800")
  log(INFO, "Nighttime camera setup: EV compensation = 0")

  options = {"exposureProgram": 1,
		"shutterSpeed": 10,
		"iso": 800,
		"exposureCompensation": 0}

  _, tries = retry(rt, rt._set_options, options,
			reconnect_tries = reconnect_tries)

  return tries



def theta_camera_names_completer(**kwargs):
  """Argcomplete completer that returns all the names of the cameras declared in
  the Theta cameras' names and credentials file
  """

  try:
    with open(os.path.expanduser(theta_cameras_credentials_file), "r") as f:
      camera_names = json.load(f).keys()

  except:
    camera_names = ()

  return camera_names



def retry(rt, fct, *args, **kwargs):
  """Retry a function call a number of times before failing
  Return the result of the call and the number of tries
  """

  t = 0
  while True:

    t += 1
    try:

      # Close the session to force a reconnect
      rt.close()

      # Retry the function call
      return (fct(*args, **kwargs), t)

    except Exception as e:

      e = str(e)
      log(ERROR, e)

      # If we get an error 403, something has gone seriously wrong with the
      # camera, so stop retrying to let the main loop reboot the camera
      # immediately
      if e.startswith("403 Client Error: Forbidden"):
        raise RuntimeError("THETA:{}".format(e))

      if t > retries:
        raise RuntimeError("THETA:{}".format(e))

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

  # Parse the command line arguments
  argparser = argparse.ArgumentParser()

  argparser.add_argument(
	  "camera",
	  help = "Name of the camera to use, declared in {}".
			format(theta_cameras_credentials_file),
	  type = str
	).completer = theta_camera_names_completer

  argparser.add_argument(
	  "-i", "--intervalometer",
	  help = "Don't take the photos if the shots are triggered with an "
			"an external intervalometer, but still monitor the "
			"state of the camera, and automatically reconfigure "
			"it for daytime and nighttime capture at dawn and dusk",
	  action = "store_true"
	)

  argparser.add_argument(
	  "-d", "--download",
	  help = "If we take the photos, download each photo in the current "
			"directory after taking it",
	  action = "store_true"
	)

  if "argcomplete" in globals():
    argcomplete.autocomplete(argparser, always_complete_options = False)

  args = argparser.parse_args()

  # Load the Theta cameras' names and credentials file
  try:
    with open(os.path.expanduser(theta_cameras_credentials_file), "r") as f:
      theta_cameras_credentials = json.load(f)

  except Exception as e:
    log(ERROR, "Cannot load names and credentials file {}: {}".
		format(theta_cameras_credentials_file, str(e)))
    return -1

  if args.camera not in theta_cameras_credentials:
    log(ERROR, 'Camera "{}" not found in {}'.
		format(args.camera, theta_cameras_credentials_file))
    return -1

  # Try to load the Theta cameras' location file and figure out the location's
  # timezone. If the it doesn't exist, just log a warning
  fp = os.path.expanduser(theta_cameras_locations_file)
  if os.path.exists(fp):

    try:
      with open(fp, "r") as f:
        theta_cameras_locations = json.load(f)

    except Exception as e:
      log(ERROR, "Cannot load camera locations file {}: {}".
			format(theta_cameras_locations_file, str(e)))
      return -1

    if args.camera in theta_cameras_locations:

      location = theta_cameras_locations[args.camera]

      latitude = location["latitude"]
      longitude = location["longitude"]
      altitude = location["altitude"]

      observer = Observer(latitude = latitude,
			longitude = longitude,
			elevation = altitude)

      timezone_cam_name = TimezoneFinder().timezone_at(lat = latitude,
							lng = longitude)
      timezone_cam = ZoneInfo(timezone_cam_name)

    else:
      location = None
      log(WARN, 'Location of camera "{}" not found in {}: no auto day/night '
		'config'.format(args.camera, theta_cameras_locations_file))

  else:
    location = None
    log(WARN, "No camera locations file found: no auto day/night config")

  # Open the camera
  rt = Theta(**theta_cameras_credentials[args.camera])

  # Assume the camera needs setting up when starting, and we don't know whether
  # capture parameters are set for daytime or nighttime, but it doesn't need
  # rebooting at this point
  next_reboot_tstamp = NEVER
  next_basic_setup_tstamp = time()
  next_day_night_setup_tstamp = NEVER
  next_state_check_tstamp = NEVER
  next_photo_tstamp = NEVER

  # Try to reload event timings from the save file, in case the script was
  # stopped and restarted, to keep the timing of the photos correct
  # Don't use timestamps that are too far in the past or in the future
  now = time()

  try:

    with open(os.path.expanduser(event_timestamps_file.format(args.camera)),
		"r") as f:
      j = json.load(f)

    saved_next_day_night_setup_tstamp = j["next_day_night_setup_tstamp"]
    saved_next_state_check_tstamp = j["next_state_check_tstamp"]
    saved_next_photo_tstamp = j["next_photo_tstamp"]

    assert type(saved_next_day_night_setup_tstamp) in (int, float), \
		"Saved next_day_night_setup_tstamp should be an int or a float"
    assert type(saved_next_state_check_tstamp) in (int, float), \
		"Saved next_state_check_tstamp should be an int or a float"
    assert type(saved_next_photo_tstamp) in (int, float), \
		"Saved next_photo_tstamp should be an int or a float"

    use_saved_tstamps = True

    if now - saved_next_day_night_setup_tstamp > 60 * 2:
      log(WARN, "Saved next daytime / nighttime reconfiguration attempt "
		"scheduled too far in the past")
      use_saved_tstamps = False

    if saved_next_day_night_setup_tstamp < POSTPONED and \
		saved_next_day_night_setup_tstamp - now > 12 * 60 * 60:
      log(WARN, "Saved next daytime / nighttime reconfiguration attempt "
		"scheduled too far in the future")
      use_saved_tstamps = False

    if now - saved_next_state_check_tstamp > check_camera_state_every * 2:
      log(WARN, "Saved camera check scheduled too far in the past")
      use_saved_tstamps = False

    if saved_next_state_check_tstamp < POSTPONED and \
		saved_next_state_check_tstamp - now > check_camera_state_every:
      log(WARN, "Saved camera check scheduled too far in the future")
      use_saved_tstamps = False

    if now - saved_next_photo_tstamp > take_photo_every * 2:
      log(WARN, "Saved next photo scheduled too far in the past")
      use_saved_tstamps = False

    if saved_next_photo_tstamp  < POSTPONED and \
		saved_next_photo_tstamp - now > take_photo_every:
      log(WARN, "Saved next photo scheduled too far in the future")
      use_saved_tstamps = False

    if use_saved_tstamps:

      next_day_night_setup_tstamp = saved_next_day_night_setup_tstamp
      next_state_check_tstamp = saved_next_state_check_tstamp
      next_photo_tstamp = saved_next_photo_tstamp

      log(INFO, "Reusing saved event timestamps")

    else:
      log(WARN, "Not reusing saved event timestamps")

  except Exception as e:
    log(WARN, "Could not load event timestamps from {}: {}".
		format(event_timestamps_file.format(args.camera), str(e)))

  tries = 0

  while True:

    try:

      now = time()

      # Save the timestamps, in case the script stops but restarts soon enough
      # afterward that we can reuse them
      try:
        with open(os.path.expanduser(event_timestamps_file.format(args.camera)),
			"w") as f:
          j = {"next_day_night_setup_tstamp": next_day_night_setup_tstamp,
		"next_state_check_tstamp": next_state_check_tstamp,
		"next_photo_tstamp": next_photo_tstamp}
          print(json.dumps(j, indent = 2), file = f)

      except Exception as e:
        log(WARN, "Could not save event timestamps in {}: {}".
		format(event_timestamps_file.format(args.camera), str(e)))

      # If the last command took more than one try to go through, redo the basic
      # setup of the camera because it has probably lost its marbles
      if tries > 1:
        next_basic_setup_tstamp = time()

      # Cap the lateness of any scheduled repeating event if we're running late
      if now - next_state_check_tstamp > check_camera_state_every:
        next_state_check_tstamp = now - check_camera_state_every

      if now - next_day_night_setup_tstamp > 60:
        next_day_night_setup_tstamp = now - 60

      if now - next_photo_tstamp > take_photo_every:
        log(WARN, "Capping the next shot's lateness to {} s".
		format(take_photo_every))
        next_photo_tstamp = now - take_photo_every

      # Is a photo scheduled?
      if next_photo_tstamp != NEVER:

        # If the next daytime / nighttime reconfiguration attempt is scheduled
        # too close before a photo, postpone it so the photo takes precedence
        # and happens exactly on time
        if 0 <= next_photo_tstamp - next_day_night_setup_tstamp <= 5:
          next_day_night_setup_tstamp += POSTPONED

        # If the next state check is scheduled too close before a photo, cancel
        # it so the photo takes precedence and happens exactly on time
        if 0 <= next_photo_tstamp - next_state_check_tstamp <= 5:
          next_state_check_tstamp += POSTPONED

      # Determine which event timeout is coming up next
      next_event_tstamp = min(next_basic_setup_tstamp,
				next_reboot_tstamp,
				next_day_night_setup_tstamp,
				next_state_check_tstamp,
				next_photo_tstamp)

      # Wait until the next event, if needed
      wait_for = next_event_tstamp - now
      if wait_for > 0:
        sleep(wait_for)
        now = time()

      # Should we reboot the camera?
      if now >= next_reboot_tstamp:

        log(WARN, "Rebooting the camera")
        try:
          rt.reboot()
          next_reboot_tstamp = NEVER
          next_basic_setup_tstamp = now

        except Exception as e:
          log(ERROR, str(e))
          next_reboot_tstamp = now

      # Should we do a basic setup of the camera?
      elif now >= next_basic_setup_tstamp:

        tries = configure_camera_basic_setup(rt)

        next_basic_setup_tstamp = NEVER

        # If we have location data and daytime / nighttime reconfiguration
        # hasn't been started, schedule the next daytime / nighttime
        # reconfiguration rightaway
        if location:
          if next_day_night_setup_tstamp == NEVER:
            camera_set_for_daytime = None	# Current setup presumed unknown
            next_day_night_setup_tstamp = time()

        # We don't have location data:
        else:

          # If the shots are triggered by an external intervalometer and
          # checking the state of the camera hasn't been started yet, schedule
          # the next check
          if args.intervalometer:
            if next_state_check_tstamp == NEVER:
              next_state_check_tstamp = time() + 1

          # We take the photos ourselves: if taking photos hasn't been started
          # yet, schedule the next photo
          elif next_photo_tstamp == NEVER:
            next_photo_tstamp = time()

      # Should we configure the camera for daytime or nighttime capture?
      elif now >= next_day_night_setup_tstamp:

        # Get the time at the camera's location
        now_cam = datetime.fromtimestamp(now, timezone_cam)

        # try to calculate the nautical dawn and dusk times for today and
        # tomorrow - which may fail in high latitudes when the sun never rises
        # or never sets
        try:

          today_cam = now_cam.date()
          tomorrow_cam = today_cam + timedelta(days = 1)

          today_dawn_time_cam = dawn(observer,
					date = today_cam,
					depression = twilight_depression,
					tzinfo = timezone_cam)

          today_dusk_time_cam = dusk(observer,
					date = today_cam,
					depression = twilight_depression,
					tzinfo = timezone_cam)

          tomorrow_dawn_time_cam = dawn(observer,
					date = tomorrow_cam,
					depression = twilight_depression,
					tzinfo = timezone_cam)

          # Determine whether it's daytime or nighttime, and what time the next
          # dusk or dawn is
          if now_cam < today_dawn_time_cam:
            is_daytime = False
            next_dawn_dusk_time_cam = today_dawn_time_cam

          elif now_cam < today_dusk_time_cam:
            is_daytime = True
            next_dawn_dusk_time_cam = today_dusk_time_cam

          else:
            is_daytime = False
            next_dawn_dusk_time_cam = tomorrow_dawn_time_cam

        # If calculating dusk and dawn times failed: determine whether it's
        # daytime or nighttime by checking the elevation of the sun
        except:

          is_daytime = elevation(observer, now_cam) >= -twilight_depression
          next_dawn_dusk_time_cam = None

        # Should we configure or reconfigure the camera?
        if is_daytime != camera_set_for_daytime:

          log(INFO, "Camera location time {:%Y-%m-%d %H:%M:%S} ({}time)".
			format(now_cam, "day" if is_daytime else "night"))

          if next_dawn_dusk_time_cam is not None:
            log(INFO, "Next {}: {:%Y-%m-%d %H:%M:%S}".
			format("dusk" if is_daytime else "dawn",
				next_dawn_dusk_time_cam))

          if is_daytime:
            tries = configure_camera_for_daytime_capture(rt)
          else:
            tries = configure_camera_for_nighttime_capture(rt)

          # If the shots are triggered by an external intervalometer and we had
          # to try more than once to set daytime or nighttime capture, it's
          # probably because a shot was being taken, so ignore the retries
          if args.intervalometer and tries > 1:
            tries = 1

          camera_set_for_daytime = is_daytime

        # Schedule the next daytime / nighttime reconfiguration attempt
        if next_dawn_dusk_time_cam:
          next_day_night_setup_tstamp += (next_dawn_dusk_time_cam - \
						now_cam).seconds + 1
        else:
          next_day_night_setup_tstamp += 60

        # If the shots are triggered by an external intervalometer and
        # checking the state of the camera hasn't been started yet, schedule
        # the next check
        if args.intervalometer:
          if next_state_check_tstamp == NEVER:
            next_state_check_tstamp = time() + 1

        # We take the photos ourselves: if taking photos hasn't been started
        # yet, schedule the next photo
        elif next_photo_tstamp == NEVER:
          next_photo_tstamp = time()

      # Should we take a photo?
      elif now >= next_photo_tstamp:

        log(INFO, "Taking a photo{}".format("" if wait_for > -0.5 else \
						" (late by {:0.1f} s)".
							format(-wait_for)))
        r, tries  = retry(rt, rt.take_photo,
				reconnect_tries = reconnect_tries)

        file_url = r["results"]["fileUrl"]

        t1 = time()
        log(INFO, "Done in {:0.1f} s".format(t1 - now))

        # Download the photo if needed
        if args.download:

          log(INFO, "Downloading {}".format(file_url))

          _, tries  = retry(rt, rt.download_file, file_url,
				reconnect_tries = reconnect_tries)

          t2 = time()
          log(INFO, "Done in {:0.1f} s".format(t2 - t1))

        else:
          log(INFO, file_url)

        # Schedule the next photo
        next_photo_tstamp += take_photo_every

        # If daytime / nighttime reconfiguration has been postponed because it
        # was too close before a photo event, let it go through at the next pass
        if next_day_night_setup_tstamp > POSTPONED:
          next_day_night_setup_tstamp -= POSTPONED

        # If checking the state of the camera  has been postponed because it
        # was too close before a photo event, let it go through at the next pass
        if next_state_check_tstamp > POSTPONED:
          next_day_night_setup_tstamp -= POSTPONED

        # If checking the state of the camera hasn't been started yet, schedule
        # the next check
        if next_state_check_tstamp == NEVER:
          next_state_check_tstamp = time() + 1

      # Should we check the camera's state?
      elif now >= next_state_check_tstamp:

        state, tries = retry(rt, rt.get_state,
				reconnect_tries = reconnect_tries)

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

        # Turn off the camera if the battery is too low
        if batt_percent < turn_off_camera_when_battery_below:

          log(INFO, "Battery below {}%: turning off camera".
		format(turn_off_camera_when_battery_below))

          while True:
            try:
              rt.set_power_mode("off")
              return 0
            except:
              sleep(1)

        # Schedule the next state check
        next_state_check_tstamp += check_camera_state_every

    except KeyboardInterrupt:

      log(WARN, "Interrupted")
      return -1

    except RuntimeError as e:

      if not str(e).startswith("THETA"):
        raise

      next_day_night_setup_tstamp = NEVER
      next_state_check_tstamp = NEVER
      next_photo_tstamp = NEVER

      # Only reboot the camera if we take the photos ourselves
      if args.intervalometer:
        next_basic_setup_tstamp = time()
      else:
        next_reboot_tstamp = time()



### Main program
if __name__ == "__main__":
  sys.exit(main())
