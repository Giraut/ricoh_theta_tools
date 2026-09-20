#!/usr/bin/env python3
"""Script to take images at regular intervals to create a timelapse video
"""

### Modules
import os
import sys
import json
import argparse
from thetaclass.theta import Theta
from time import time, sleep
from datetime import datetime

try:
  import argcomplete	# PYTHON_ARGCOMPLETE_OK
except:
  pass



### Parameters
grab_image_every = 30 #s
retries = 20
wait_before_retry = 2 #s
monitor_camera_state = True
reconnect_tries = 5

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



## Defines
INFO = 0
WARN = 1
ERROR = 2




### Routines
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

  assert args.camera in theta_cameras_credentials

  # Open the camera
  rt = Theta(**theta_cameras_credentials[args.camera])

  # Assume the camera needs setting up when starting
  do_setup = True
  do_reboot = False

  # Grab images forever
  while True:

    try:

      # Should we reboot the camera?
      if do_reboot:

        log(WARN, "Rebooting the camera")
        rt.reboot()

        do_reboot = False
        do_setup = True

      # Should we setup the camera?
      if do_setup:

        log(INFO, "Setting up the camera: power mode = silent")
        retry(rt, rt.set_power_mode, "silent",
		reconnect_tries = reconnect_tries)

        log(INFO, "Setting up the camera: capture mode = image")
        retry(rt, rt.set_capture_mode, "image",
		reconnect_tries = reconnect_tries)

        do_setup = False
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
      if monitor_camera_state:
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
