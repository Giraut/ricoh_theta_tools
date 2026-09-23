#!/usr/bin/env python3
"""Ricoh Theta camera command-line client

Control a Ricoh Theta camera through wifi using the Ricoh Theta web API
"""

### Modules
import os
import re
import sys
import json
import argparse
import tempfile
from thetaclass.theta import Theta, \
				_default_live_preview_viewer_command

try:
  import argcomplete	# PYTHON_ARGCOMPLETE_OK
except:
  pass



### Parameters
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

# File containing the name of the previous Theta camera addressed by this tool
#
# The file must have the following format (but it is generated automatically
# when passing the -c / --camera argument)
#
# {
#   "name": "name1"
# }
current_theta_camera_name_file = "~/.current_ricoh_theta.json"

# By default, use sphereview installed in flatpak to view 360 images
# The crazy command is to fix up paths for flatpak, so sphereview finds the file
default_360_image_viewer_command = """FILE="{}"; """ \
					"""ABSFILE=$(realpath "$FILE"); """ \
					"""ABSDIR=$(dirname "$ABSFILE"); """ \
					"""RELFILE=$(basename "$ABSFILE"); """ \
					"""flatpak run """ \
					"""--env="ABSDIR=$ABSDIR" """ \
					"""--env="RELFILE=$RELFILE" """ \
					"""--filesystem="$ABSDIR" """ \
					"""--command=sh """ \
					"""io.github.dynobo.sphereview """ \
					"""-c 'cd "$ABSDIR" && """ \
					"""exec sphereview "$RELFILE"'"""

# By default, use vlc to play 360 videos
default_360_video_player_command = 'vlc "{}"'



### Constants
image_file_extensions = ["jpg", "jpeg", "png", "tiff", "tif", "gif", "bmp"]
video_file_extensions = ["mp4", "webm", "avi", "mov", "mpg"]



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



def printable_live_preview_format(width, height, framerate):
  """Return a short description string of a live preview format
  """

  desc = "{}x{} @ {} fps".format(width, height, framerate)

  return desc



def printable_file_format(filetype, width, height, codec, framerate, dualtrack):
  """Return a short description string of a file format
  """

  desc = "{}, {}x{}".format(filetype, width, height)

  if framerate is not None:
    desc += " @ {} fps".format(framerate)

  if codec is not None:
    desc += ", {}".format(codec)

  if dualtrack:
    desc += ", DualTrack"

  return desc



def prettyprint(j, file = sys.stdout):
  """Pretty-print a JSON structure or a simplified version of it when possible
  """

  if isinstance(j, dict):

    # If the response is just a name and a state, just display the state
    # (typically "done")
    if set(j.keys()) == {"name", "state"}:
      print(j["state"], file = file)

    # Otherwise pretty-print the JSON structure in full
    else:
      print(json.dumps(j, indent = 2), file = file)

  # Not JSON: just print it normally as a fallback
  else:
    print(j, file = file)



### Main routine
def main():
  """Main routine
  """
  global theta_cameras_credentials_file
  global current_theta_camera_name_file

  # Parse the command-line arguments
  argparser = argparse.ArgumentParser()
  subparsers = argparser.add_subparsers()
  subparsers.required = True
  subparsers.dest = 'command'

  # Option valid for all commands
  argparser.add_argument(
	  "-c", "--camera",
	  type = str,
	  help = "Name of the camera to use, declared in {}. If omitted, use "
			"name saved in {}".
			format(theta_cameras_credentials_file,
				current_theta_camera_name_file)
	).completer = theta_camera_names_completer

  # Subparsers
  subparser_info = subparsers.add_parser(
	  "info",
	  help = "Query camera information"
	)
  subparser_state = subparsers.add_parser(
	  "state",
	  help = "Query the state of the camera"
	)
  subparser_password = subparsers.add_parser(
	  "password",
	  help = "Set the client-mode password when connected in AP mode"
	)

  subparser_eventlog = subparsers.add_parser(
	  "eventlog",
	  help = "Retrieve the event log"
	)

  subparser_powermode = subparsers.add_parser(
	  "powermode",
	  help = "Get or set the power mode"
	)

  subparser_powersaving = subparsers.add_parser(
	  "powersaving",
	  help = "Get or set power saving"
	)

  subparser_volume = subparsers.add_parser(
	  "volume",
	  help = "Get or set the shutter volume"
	)

  subparser_wlanantenna = subparsers.add_parser(
	  "wlanantenna",
	  help = "Get or set the WLAN antenna config when connected in AP mode"
	)

  subparser_gps = subparsers.add_parser(
	  "gps",
	  help = "Get or set GPS tag recording"
	)

  subparser_reboot = subparsers.add_parser(
	  "reboot",
	  help = "Reboot the camera"
	)

  subparser_ui = subparsers.add_parser(
	  "ui",
	  help = "Lock or unlock the UI"
	)

  subparser_live_preview_format = subparsers.add_parser(
	  "previewformat",
	  help = "Get or set the live preview MJPEG stream format"
	)

  subparser_live_preview = subparsers.add_parser(
	  "preview",
	  help = "View the live preview MJPEG stream"
	)

  subparser_file_format = subparsers.add_parser(
	  "fileformat",
	  help = "list, get or set the file format"
	)

  subparser_filter = subparsers.add_parser(
	  "filter",
	  help = "Get or set the filter"
	)

  subparser_program = subparsers.add_parser(
	  "program",
	  help = "Get or set the exposure program"
	)

  subparser_speed = subparsers.add_parser(
	  "speed",
	  help = "Get or set the shutter speed"
	)

  subparser_iso = subparsers.add_parser(
	  "iso",
	  help = "Get or set the ISO sensitivity"
	)

  subparser_ev = subparsers.add_parser(
	  "ev",
	  help = "Get or set the exposure compensation"
	)

  subparser_stitching_mode = subparsers.add_parser(
	  "stitching",
	  help = "Get or set the stitching mode"
	)

  subparser_capture_mode = subparsers.add_parser(
	  "capturemode",
	  help = "Get or set the capture mode"
	)

  subparser_exposure_delay = subparsers.add_parser(
	  "delay",
	  help = "Get or set the exposure delay"
	)

  subparser_capture = subparsers.add_parser(
	  "capture",
	  help = "Start or stop video capture"
	)

  subparser_take_photo = subparsers.add_parser(
	  "takephoto",
	  help = "Take a photo"
	)

  subparser_storage_info = subparsers.add_parser(
	  "storage",
	  help = "Get storage information"
	)

  subparser_list_files = subparsers.add_parser(
	  "list",
	  help = "List files"
	)

  subparser_last_file = subparsers.add_parser(
	  "last",
	  help = "Get the last file created"
	)

  subparser_delete_files = subparsers.add_parser(
	  "delete",
	  help = "delete one or more files"
	)

  subparser_metadata = subparsers.add_parser(
	  "metadata",
	  help = "Get a file's metadata"
	)

  subparser_download_files = subparsers.add_parser(
	  "download",
	  help = "download one or more files"
	)

  subparser_view = subparsers.add_parser(
	  "view",
	  help = "View a file URL from the camera or a local file"
	)

  # Command-specific arguments
  subparser_password.add_argument(
	  "password",
	  type = str,
	  help = "Client-mode password to set"
	)

  subparser_powermode.add_argument(
	  "mode",
	  nargs = "?",
	  type = str,
	  choices = ("on", "silent", "sleep", "off"),
	  default = None,
	  help = "Power mode to set. Get the current power mode if omitted"

	)

  subparser_powersaving.add_argument(
	  "state",
	  nargs = "?",
	  type = str,
	  choices = ("enabled", "disabled"),
	  default = None,
	  help = "Power saving state to set. Get the current power saving "
			"state if omitted"
	)

  subparser_volume.add_argument(
	  "volume",
	  nargs = "?",
	  type = int,
	  default = None,
	  help = "Shutter volume to set. Get the current shutter volume "
			"if omitted"
	)

  subparser_wlanantenna.add_argument(
	  "config",
	  nargs = "?",
	  type = str,
	  choices = ("siso", "mimo"),
	  default = None,
	  help = "WLAN antenna configuration to set. Get the current WLAN "
			"antenna configuration if omitted"
	)

  subparser_gps.add_argument(
	  "state",
	  nargs = "?",
	  type = str,
	  choices = ("enabled", "disabled"),
	  default = None,
	  help = "GPS tag recording state to set. Get the current GPS tag "
			"recording state if omitted"
	)

  subparser_ui.add_argument(
	  "state",
	  type = str,
	  choices = ("locked", "unlocked"),
	  help = "UI locking state to set"
	)

  subparser_live_preview_format.add_argument(
	  "format",
	  nargs = "?",
	  choices = ["list"] + \
			["{}".format(i + 1) for i in \
				range(len(Theta._valid_live_preview_formats))],
          type = str,
	  default = None,
	  help = 'Number of the pedefined live preview format to set or "list" '
			'to list all the formats. Get the current live preview '
			'format if omitted'
	)

  subparser_live_preview.add_argument(
	  "viewer_command",
	  nargs = "?",
	  type = str,
	  default = _default_live_preview_viewer_command,
	  help = "Alternative MJPEG stream viewer command. Default if "
			"unspecified: {}".
			format(_default_live_preview_viewer_command)
	)

  subparser_file_format.add_argument(
	  "format",
	  nargs = "?",
	  choices = ["list"] + \
			["{}".format(i + 1) for i in \
				range(len(Theta._valid_file_formats))],
          type = str,
	  default = None,
	  help = 'Number of the pedefined file format to set for the current '
			'capture mode, or "list" to list all the formats. Get '
			'the current file format for the current capture mode '
			'if omitted'
	)

  subparser_filter.add_argument(
	  "filter",
	  nargs = "?",
	  type = str,
	  choices = Theta._valid_filters,
	  default = None,
	  help = "Filter to set in image capture mode. Get the current filter "
			"if omitted"
	)

  subparser_program.add_argument(
	  "program",
	  nargs = "?",
	  type = str,
	  choices = [Theta._exposure_programs[p] \
			for p in sorted(Theta._exposure_programs)],
	  default = None,
	  help = "Exposure program to set for the current capture mode. Get "
			"the current exposure program for the current capture "
			"mode if omitted"
	)

  subparser_speed.add_argument(
	  "speed",
	  nargs = "?",
	  type = str,
	  choices = [Theta._shutter_speeds[s] \
			for s in sorted(Theta._shutter_speeds)],
	  default = None,
	  help = "Shutter speed to set for the current capture mode. Get "
			"the current shutter speed for the current capture "
			"mode if omitted"
	)

  subparser_iso.add_argument(
	  "iso",
	  nargs = "?",
	  type = int,
	  choices = Theta._iso_sensitivities,
	  default = None,
	  help = "ISO sensitivity to set for the current capture mode. Get "
			"the current ISO sensitivity for the current capture "
			"mode if omitted"
	)

  subparser_ev.add_argument(
	  "ev",
	  nargs = "?",
	  type = float,
	  choices = sorted(Theta._allowed_ev_values),
	  default = None,
	  help = "Exposure compensation (EV) value to set for the current "
			"capture mode. Get the current exposure compensation "
			"value for the current capture mode if omitted"
	)

  subparser_stitching_mode.add_argument(
	  "mode",
	  nargs = "?",
	  type = str,
	  choices = Theta._valid_stitching_modes,
	  default = None,
	  help = 'Stitching mode to set in image capture mode. Get the current '
			'stitching mode if omitted (note: reverts to "auto" '
			'when switching to video capture mode)'
	)

  subparser_capture_mode.add_argument(
	  "mode",
	  nargs = "?",
	  type = str,
	  choices = ["image", "video"],
	  default = None,
	  help = "Capture mode to set. Get the current capture mode if omitted"
	)

  subparser_exposure_delay.add_argument(
	  "delay",
	  nargs = "?",
	  type = int,
	  choices = range(10 + 1),
	  default = None,
	  help = "Exposure delay to set. Get the current exposure delay if "
			"omitted"
	)

  subparser_capture.add_argument(
	  "action",
	  type = str,
	  choices = ["start", "stop"],
	  help = "Start or stop video capture"
	)

  subparser_list_files.add_argument(
	  "-f", "--filetype",
	  type = str,
	  choices = ["all", "image", "video"],
	  default = "all",
	  help = "Type of files to list. Default: all"
	)

  subparser_delete_files.add_argument(
	  "files",
	  nargs = "+",
	  type = str,
	  help = 'List of files to delete. "all" to delete all files. "last" '
			'to delete the last file created'
	)

  subparser_metadata.add_argument(
	  "file",
	  type = str,
	  help = "File to get the metadata of"
	)

  subparser_download_files.add_argument(
	  "files",
	  nargs = "+",
	  type = str,
	  help = 'List of files to download. "all" to download all files. '
			'"all_images" to download all images. "all_videos" to '
			'download all viddos. last" to download the last file '
			'created'
	)

  subparser_view.add_argument(
	  "file",
	  type = str,
	  help = 'File or Theta URL to view. "last" to view the last file '
			'created'
	)

  subparser_view.add_argument(
	  "-i", "--image-viewer-command",
	  type = str,
	  default = default_360_image_viewer_command,
	  help = "Alternative panoramic image viewer command. Default if "
			"unspecified: {}".
			format(default_360_image_viewer_command.
				format("file.jpg"))
	)

  subparser_view.add_argument(
	  "-v", "--video-player-command",
	  type = str,
	  default = default_360_video_player_command,
	  help = "Alternative panoramic video player command. Default if "
			"unspecified: {}".
			format(default_360_video_player_command.
				format("file.mp4"))
	)

  # Expand the tilde in configuration files
  theta_cameras_credentials_file = \
			os.path.expanduser(theta_cameras_credentials_file)
  current_theta_camera_name_file = \
			os.path.expanduser(current_theta_camera_name_file)

  if "argcomplete" in globals():
    argcomplete.autocomplete(argparser, always_complete_options = False)

  args = argparser.parse_args()

  # Try to read the name of the previously-used camera in the save file
  try:
    with open(current_theta_camera_name_file, "r") as f:
      prev_camera_name = json.load(f)["name"]
    assert isinstance(prev_camera_name, str) and prev_camera_name
  except:
    prev_camera_name = None

  # If no camera name was supplied, use the previous name instead
  if not args.camera:
    args.camera = prev_camera_name

  # If we don't have a camera name, throw an error
  if not args.camera:
    print("[ERROR] Cannot get camera name from {}. Supply it with "
		"-c / --camera".format(current_theta_camera_name_file))
    return -1

  # Load the Theta cameras' names and credentials file if the command is not
  # "password" or "wlanantenna"
  if args.command not in ("password", "wlanantenna"):
    with open(os.path.expanduser(theta_cameras_credentials_file), "r") as f:
      theta_cameras_credentials = json.load(f)

  if args.camera not in theta_cameras_credentials:
    print('[ERROR] Unknown camera "{}"'.format(args.camera))
    return -1

  # If the name is different from the one in the save file, or there was no
  # existing file, or it was empty, update the file
  if prev_camera_name is None or prev_camera_name != args.camera:
    try:
      with open(current_theta_camera_name_file, "w") as f:
        print(json.dumps({"name": args.camera}, indent = 2), file = f)
    except:
      print("[WARNING] Cannot save camera name in {}".
		format(current_theta_camera_name_file))

  # No camera name supplied
  else:
    args.camera = prev_camera_name

  # Load the Theta cameras' names and credentials file if the command is not
  # "password" or "wlanantenna"
  if args.command not in ("password", "wlanantenna"):
    with open(os.path.expanduser(theta_cameras_credentials_file), "r") as f:
      theta_cameras_credentials = json.load(f)

    assert args.camera in theta_cameras_credentials

  try:

    # Open the camera
    #
    # If the command is not "password" or "wlanantenna", it is meant to be
    # executed with the cmaera connected to a wifi AP in client mode: use the
    # credentials from the names and credentials file to authenticate with it
    #
    # If the command is "password" or "wlanantenna", it is meant to be executed
    # with the computer connected to the camera in configured in wifi AP mode:
    # set the camera's IP to 192.168.1.1 and no credentials
    if args.command not in ("password", "wlanantenna"):
      rt = Theta(**theta_cameras_credentials[args.camera])
    else:
      rt = Theta(addr = "192.168.1.1", username = None, password = None)

    # Execute the command:

    # Get cmaera information
    if args.command == "info":
      prettyprint(rt.get_info())

    # Get the state of the camera
    elif args.command == "state":
      prettyprint(rt.get_state())

    # Set the client-mode password
    elif args.command == "password":
      prettyprint(rt.set_client_mode_password(args.password))

    # Get the event log
    elif args.command == "eventlog":
      for l in rt.get_event_log():
        print(l)

    # Get or set the power mode
    elif args.command == "powermode":
      if args.mode is None:
        print(rt.get_power_mode())
      else:
        if args.mode in ("sleep", "off"):
          rt.set_power_mode(args.mode)
          print("done")
        else:
          prettyprint(rt.set_power_mode(args.mode))

    # Enable or disable power saving
    elif args.command == "powersaving":
      if args.state is None:
        print("enabled" if rt.get_power_saving() else "disabled")
      else:
        prettyprint(rt.set_power_saving(args.state == "enabled"))

    # Get or set the shutter volume
    elif args.command == "volume":
      if args.volume is None:
        print(rt.get_shutter_volume())
      else:
        prettyprint(rt.set_shutter_volume(args.volume))

    # Get or set the WLAN antenna configuration
    elif args.command == "wlanantenna":
      if args.config is None:
        print(rt.get_wlan_antenna_config())
      else:
        prettyprint(rt.set_wlan_antenna_config(args.config))

    # Enable or disable GPS tag recording
    elif args.command == "gps":
      if args.state is None:
        print("enabled" if rt.get_gps_tag_recording() else "disabled")
      else:
        prettyprint(rt.set_gps_tag_recording(args.state == "enabled"))

    # Reboot the camera
    elif args.command == "reboot":
        prettyprint(rt.reboot())

    # Lock or unlock the UI
    elif args.command == "ui":
        prettyprint((rt.lock_ui if args.state == "locked" else rt.unlock_ui)())

    # Get or set the live preview format
    elif args.command == "previewformat":

        if args.format is None:

          r = rt.get_live_preview_format()
          f = (r["width"], r["height"], r["framerate"])

          if f in Theta._valid_live_preview_formats:
            i = Theta._valid_live_preview_formats.index(f) + 1
            print("#{}: {}".format(i, printable_live_preview_format(*f)))

          else:
            print("Unknown file format: {}".
			format(printable_live_preview_format(*f)))

        elif args.format == "list":
          for i, f  in enumerate(Theta._valid_live_preview_formats):
            print("#{}: {}".format(i + 1, printable_live_preview_format(*f)))

        else:
          f = Theta._valid_live_preview_formats[int(args.format) - 1]
          prettyprint(rt.set_live_preview_format(*f))

    # Play the live preview
    elif args.command == "preview":
        rt.live_preview(viewer_cmd = args.viewer_command)

    # Get or set the file format
    elif args.command == "fileformat":

        if args.format is None:

          r = rt.get_file_format()
          f = (r["filetype"], r["width"], r["height"],
		r["codec"], r["framerate"], r["dualtrack"])

          if f in Theta._valid_file_formats:
            i = Theta._valid_file_formats.index(f) + 1
            print("#{}: {}".format(i, printable_file_format(*f)))

          else:
            print("Unknown file format: {}".format(printable_file_format(*f)))

        elif args.format == "list":
          for i, f  in enumerate(Theta._valid_file_formats):
            print("#{}: {}".format(i + 1, printable_file_format(*f)))

        else:
          f = Theta._valid_file_formats[int(args.format) - 1]
          prettyprint(rt.set_file_format(*f))

    # Get or set the filter
    elif args.command == "filter":
      if args.filter is None:
        print(rt.get_filter())
      else:
        prettyprint(rt.set_filter(args.filter))

    # Get or set the exposure program
    elif args.command == "program":
      if args.program is None:
        print(rt.get_exposure_program())
      else:
        prettyprint(rt.set_exposure_program(args.program))

    # Get or set the shutter speed
    elif args.command == "speed":
      if args.speed is None:
        print(rt.get_shutter_speed())
      else:
        prettyprint(rt.set_shutter_speed(args.speed))

    # Get or set the ISO sensitivity
    elif args.command == "iso":
      if args.iso is None:
        print(rt.get_iso_sensitivity())
      else:
        prettyprint(rt.set_iso_sensitivity(args.iso))

    # Get or set the exposure compensation value
    elif args.command == "ev":
      if args.ev is None:
        print(rt.get_exposure_compensation())
      else:
        prettyprint(rt.set_exposure_compensation(args.ev))

    # Get or set the stitching mode
    elif args.command == "stitching":
      if args.mode is None:
        print(rt.get_stitching_mode())
      else:
        prettyprint(rt.set_stitching_mode(args.mode))

    # Get or set the capture mode
    elif args.command == "capturemode":
      if args.mode is None:
        print(rt.get_capture_mode())
      else:
        prettyprint(rt.set_capture_mode(args.mode))

    # Get or set the exposure delay
    elif args.command == "delay":
      if args.delay is None:
        print(rt.get_exposure_delay())
      else:
        prettyprint(rt.set_exposure_delay(args.delay))

    # Start / stop the video capture
    elif args.command == "capture":
      prettyprint((rt.start_capture if args.action == "start" else \
			rt.stop_capture)())

    # Take a photo
    elif args.command == "takephoto":
      prettyprint(rt.take_photo())

    # Get storage information
    elif args.command == "storage":
      r = rt.get_storage_info()
      print("Total:     {:0.2f} G".format(r["total"] / 1024 ** 3))
      print("Remaining: {:0.2f} G".format(r["remaining"] / 1024 ** 3))

    # List files
    elif args.command == "list":
      r = rt.get_file_list(filetype = args.filetype)
      d = {e["fileUrl"]: (e["size"], e["dateTimeZone"]) for e in r}
      for k in sorted(d):
        print("{:>12}\t{}\t{}".format(d[k][0], d[k][1], k))

    # Get the last file created
    elif args.command == "last":
      print(rt.get_last_file())

    # Delete files
    elif args.command == "delete":
      file_urls = set(args.files)
      if file_urls == {"last"}:
        prettyprint(rt.delete_last_file())
      else:
        prettyprint(rt.delete_files(file_urls))

    # Get a file's metadata
    elif args.command == "metadata":
      prettyprint(rt.get_file_metadata(args.file))

    # Download files
    elif args.command == "download":
      file_urls = set(args.files)
      if file_urls == {"last"}:
        rt.download_last_file()
      else:
        rt.download_files(file_urls)
      print("done")

    # View a file in the camera or a local file
    elif args.command == "view":

      if args.file == "last":
        args.file = rt.get_last_file()

      ext = "" if "." not in args.file else args.file.rsplit(".", 1)[1].lower()
      assert ext in image_file_extensions or ext in video_file_extensions, \
		"unknow file type"

      if re.match(Theta._file_url_pattern, args.file):

        temp_fd, temp_fpath = tempfile.mkstemp(suffix = "." + ext)
        os.close(temp_fd)

        try:
          rt.download_file(args.file,
				save_dir = os.path.dirname(temp_fpath),
				save_fname = os.path.basename(temp_fpath))

          if ext in image_file_extensions:
            os.system(args.image_viewer_command.format(temp_fpath))
          else:
            os.system(args.video_player_command.format(temp_fpath))

        finally:
          os.unlink(temp_fpath)

      else:
        if ext in image_file_extensions:
          os.system(args.image_viewer_command.format(args.file))
        else:
          os.system(args.video_player_command.format(args.file))

  except Exception as e:
    print("[ERROR]", end = "")
    e = "{}".format(e)
    if e:
      print(" " + e[0].upper() + e[1:])

  return 0



### Main program
if __name__ == "__main__":
  sys.exit(main())
