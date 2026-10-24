#!/usr/bin/env python3
"""Compile photos taken at regular intervals by a Ricoh Theta camera into
a timelapse video, or combine them into a single image
"""
# PYTHON_ARGCOMPLETE_OK

### Parameters
image_exif_info_cache_file = "~/.ricoh_theta_image_exif_info_cache.json"
acceptable_image_extensions = ["jpg"]
is_nighttime_image = lambda exposuretime, iso: exposuretime > 1 and iso > 400

# Helper programs
ffmpeg_executable = "ffmpeg"
exiftool_executable = "exiftool"
mkvpropedit_executable = "mkvpropedit"

# Default timelapse video encoding options
default_timelapse_video_width = 4096 #px
default_timelapse_video_height = 2048 #px
default_timelapse_speedup = 375 #x

default_timelapse_delogo_show_zones_color = "red"

default_timelapse_timestamp_pos_x = 2048
default_timelapse_timestamp_pos_y = 1300
default_timelapse_timestamp_font_file = "/usr/share/fonts/truetype/dejavu/" \
						"DejaVuSans-Bold.ttf"
default_timelapse_timestamp_font_size = 24 #px

default_timelapse_temporal_denoise = 1
default_timelapse_spatial_denoise = 2

default_timelapse_shadows_correction = 0.10
default_timelapse_mediums_correction = 0.11
default_timelapse_highlights_correction = 0.12

# Note: +yaw moves the POV right in ffpmeg, left in Hugin
#       +pitch moves the POV up in ffmpeg, down in Hugin
#       +roll rotates the POV clockwise in ffmpeg, counterclockwise in Hugin
default_timelapse_pov_correction_yaw = 0 #deg
default_timelapse_pov_correction_pitch = 0 #deg
default_timelapse_pov_correction_roll = 0 #deg

default_timelapse_lagfun_decay_value = 0.99

default_timelapse_crosshairs_color = "red"

default_timelapse_x264_quality = 23
default_timelapse_vp9_quality = 30

default_timelapse_framerate = 25 #fps

# Default average image encoding options
max_averageable_images = 200	# Maximum number of images to average out so we
				# don't run in weird color problems

default_average_image_width = 0 # No rescaling
default_average_image_height = 0 # No rescaling

default_average_delogo_show_zones_color = "red"

default_average_spatial_denoise = 0

default_average_shadows_correction = 0.10
default_average_mediums_correction = 0.11
default_average_highlights_correction = 0.12

default_average_pov_correction_yaw = 0 #deg
default_average_pov_correction_pitch = 0 #deg
default_average_pov_correction_roll = 0 #deg

default_average_crosshairs_color = "red"

# Default combined image encoding options
default_combine_image_width = 0 # No rescaling
default_combine_image_height = 0 # No rescaling

default_combine_delogo_show_zones_color = "red"

default_combine_spatial_denoise = 0

default_combine_shadows_correction = 0.10
default_combine_mediums_correction = 0.11
default_combine_highlights_correction = 0.12

default_combine_pov_correction_yaw = 0 #deg
default_combine_pov_correction_pitch = 0 #deg
default_combine_pov_correction_roll = 0 #deg

default_combine_crosshairs_color = "red"



### Modules
import os
import re
import sys
import json
from collections import OrderedDict
import argparse
import subprocess
from datetime import datetime, timezone, timedelta
import exiftool	# type: ignore
from thetaclass.theta import Theta

try:
  import argcomplete
except:
  pass



### Classes
class ImageInfo:
  """Source image information
  """

  # Theta-style Date/time pattern regex
  __datetime_regex = re.compile(Theta._datetime_pattern)



  def __init__(self, fpath = None, json_dict = None):
    """Initialize the instance, either from EXIF data read in an image file
    whose path is fpath, or from a serialized JSON dictionary
    """

    assert not (fpath is not None and json_dict is not None), \
		"specifying both fpath and json_dict is not allowed"

    # Initialize the instance's attributes
    self.filename = None
    self._acceptable_filename_types = [str]

    self.datetime = datetime.fromtimestamp(0).replace(tzinfo = timezone.utc)
    self._acceptable_datetime_types = [datetime]

    self.exposuretime = None
    self._acceptable_exposuretime_types = [int, float]

    self.iso = None
    self._acceptable_iso_types = [int]

    # Get EXIF values from an image file
    if fpath is not None:

      # Read the image's EXIF tags and extract the ones we need
      with exiftool.ExifToolHelper() as et:
        metadata = et.get_tags(fpath, tags = ["EXIF:DateTimeOriginal",
						"EXIF:OffsetTimeOriginal",
						"EXIF:ExposureTime",
						"EXIF:ISO"]
				)[0]

      exif_datetime = metadata.get("EXIF:DateTimeOriginal")
      exif_tz_offset = metadata.get("EXIF:OffsetTimeOriginal")

      # Generate the date / time + timezone offset in ISO format
      m = self.__datetime_regex.match(exif_datetime)
      exif_datetime_iso = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}{}".\
				format(int(m[1]), int(m[2]), int(m[3]),
					int(m[4]), int(m[5]), int(m[6]),
					exif_tz_offset)

      # Store the EXIF values
      self.filename = os.path.basename(fpath)
      self.datetime = datetime.fromisoformat(exif_datetime_iso)
      self.exposuretime = metadata.get("EXIF:ExposureTime")
      self.iso = metadata.get("EXIF:ISO")

    # Get EXIF values from a serialized JSON dictionary
    elif json_dict is not None:

      for k in self.__dict__:
        if not k.startswith("_"):
          assert k in json_dict, \
		'missing key "{}" in serialized JSON dictionary'.format(k)

      for k in json_dict:
        assert not k.startswith("_") and k in self.__dict__, \
		'unknown key "{}" in serialized JSON dictionary'.format(k)

      # Convert the date / time from ISO format
      self.datetime = datetime.fromisoformat(json_dict["datetime"])

      # Allow initializing a blank instance if all the values in the JSON
      # dictionary are blank apart from "datetime"
      for k in json_dict:
        if k != "datetime" and json_dict[k] is not None:
          break
      else:
        return

      # At least one value is not None: check that all of them are the correct
      # type
      for k in json_dict:
        if k != "datetime":
          acceptable_types = getattr(self, "_acceptable_{}_types".format(k))
          assert type(json_dict[k]) in acceptable_types, \
		'key "{}" should be type {} in serialized JSON dictionary'.\
		format(k, " or ".join(t.__name__ for t in acceptable_types))
          setattr(self, k, json_dict[k])



  def to_json(self):
    """Serialize the instance's variables into a JSON-compatible dictionary
    """

    d = {}
    for k in self.__dict__:
      if not k.startswith("_"):
        if isinstance(self.__dict__[k], datetime):
          d[k] = self.__dict__[k].isoformat()
        else:
          d[k] = self.__dict__[k]

    return d



### Routines
def argparse_iso_date_time_zone_or_named_moment_type(value):
  """Argparse type for a valid date / time with or without timezone in ISO 8601
  format, or the word "now"

  If the timezone is omitted, use the system's timezone

  The value may contain "beginning", "end", "dawn[0-9]+" or "dusk[0-9]+"
  immediately followed by a time offset in days, hours, minutes or seconds.
  E.g.: start+1d, end-30s, dusk1+1h, dawn2-30m
  """

  m = re.match(r"^(beginning|end|dawn[0-9]+|dusk[0-9]+)" \
		r"(([+-][0-9\.]+)([dhms]))?$", value, re.I)

  if m:
    named_moment = m[1]
    if m[3] is not None and m[4] is not None:
      offset_seconds = float(m[3]) * \
			{"s": 1, "m": 60, "h": 3600, "d": 86400}[m[4].lower()]
    else:
      offset_seconds = 0

    return (named_moment.lower(), offset_seconds)

  else:
    named_moment = None
    offset_seconds = None

    try:
      dtz = datetime.fromisoformat(value)
    except:
      raise argparse.ArgumentTypeError("{}: invalid ISO 8601 date / time / "
					"zone or named moment".format(value))

    if dtz.tzinfo is None:
      return dtz.replace(tzinfo = datetime.now().astimezone().tzinfo)

    return dtz



def argparse_video_filename_type(value):
  """Argparse type for a valid mp4 or webm video filename
  """

  if not re.match(r"^.*\.(mp4|webm|m3u8)$", value, re.I):
    raise argparse.ArgumentTypeError("{}: unknown / unsupported video format".
					format(value))

  if not re.match(r"^.+\..+$", value, re.I):
    raise argparse.ArgumentTypeError("{}: the file doesn't have a basename".
					format(value))
  return value



def argparse_image_filename_type(value):
  """Argparse type for a valid png or jpg video filename
  """

  if not re.match(r"^.*\.(png|jpg)$", value, re.I):
    raise argparse.ArgumentTypeError("{}: unknown / unsupported image format".
					format(value))

  if not re.match(r"^.+\..+$", value, re.I):
    raise argparse.ArgumentTypeError("{}: the file doesn't have a basename".
					format(value))
  return value



def argparse_delogo_zone_type(value):
  """Argparse type for a valid delogo zone, expressed in XWindow geometry format
  for compacity (i.e. wxh+x+y)
  """

  m = re.match(r"^([0-9]+)x([0-9]+)\+([0-9]+)\+([0-9]+)$", value)

  if m is None:
    raise argparse.ArgumentTypeError("{}: invalid delogo zone".format(value))

  return (int(m[3]), int(m[4]), int(m[1]), int(m[1]))



def mark_file_spherical(fpath):
  """Mark an image or video file as spherical
  """

  # Exiftool can't modify webm video files: use mkvpropedit instead
  if os.path.splitext(fpath)[1][1:].lower() == "webm":

    try:

        # Create the mkvpropedit command
      mkvpropedit_cmd = [mkvpropedit_executable,
				fpath,
				"--edit", "track:v1",
				"--set", "projection-type=1"]

      # Run the mkvpropedit command
      for i, arg in enumerate(mkvpropedit_cmd):
        print("{:>19}: {}".format("mkvpropedit command" if i == 0 else \
					"arg #{}".format(i),
					mkvpropedit_cmd[i]))
      print()
      subprocess.run(mkvpropedit_cmd, check = True)

    except KeyboardInterrupt:
      print()
      print("Interrupted")
      return -1

    except Exception as e:
      print("mkvpropedit command failed: {}".format(e))
      return -1

  # Run exiftool on files other than webm
  else:

    # Create the exiftool command
    exiftool_cmd = [exiftool_executable,
			"-overwrite_original",
			"-XMP-GPano:UsePanoramaViewer=true",
			"-XMP-GPano:ProjectionType=equirectangular",
			"-XMP-GPano:PoseHeadingDegrees=0.0",
			"-XMP-GPano:PosePitchDegrees=0.0",
			"-XMP-GPano:PoseRollDegrees=0.0",
			"-XMP-GPano:InitialViewHeadingDegrees=0.0",
			"-XMP-GPano:InitialViewPitchDegrees=0.0",
			"-XMP-GPano:InitialViewRollDegrees=0.0",
			"-XMP-GSpherical:Spherical=true",
			"-XMP-GSpherical:Stitched=true",
			"-XMP-GSpherical:ProjectionType=equirectangular",
			fpath]

    # Run the exiftool command
    try:

      for i, arg in enumerate(exiftool_cmd):
        print("{:>16}: {}".format("exiftool command" if i == 0 else \
					"arg #{}".format(i),
					exiftool_cmd[i]))
      print()

      subprocess.run(exiftool_cmd, check = True)

    except KeyboardInterrupt:
      print()
      print("Interrupted")
      return -1

    except Exception as e:
      print("exiftool command failed: {}".format(e))
      return -1



### Main routine
def main():

  # Parse the command line arguments
  argparser = argparse.ArgumentParser()
  subparsers = argparser.add_subparsers()
  subparsers.required = True
  subparsers.dest = 'command'

  # Subparsers
  subparser_analyze = subparsers.add_parser(
	  "analyze",
	  help = "Analyse the source images (cache the information)"
	)

  subparser_timelapse = subparsers.add_parser(
	  "timelapse",
	  help = "Create a timelapse video (mp4, m3u8 or webm)"
	)

  subparser_average = subparsers.add_parser(
	  "average",
	  help = "Create an average image (jpg or png)"
	)

  subparser_combine = subparsers.add_parser(
	  "combine",
	  help = "Create an combined image (jpg or png) composed of the "
			"brightest pixels in the sources images"
	)

  # Option valid for all commmands
  for sp in [subparser_analyze,
		subparser_timelapse,
		subparser_average,
		subparser_combine]:

    sp.add_argument(
	  "srcdir",
	  type = str,
	  help = "Directory containing the source images"
	)

  # Option valid for all encoding commands
  for sp in [subparser_timelapse,
		subparser_average,
		subparser_combine]:

    sp.add_argument(
	  "beginning",
	  type = argparse_iso_date_time_zone_or_named_moment_type,
	  help = "Beginning time in ISO format or named moment [+-offset]. "
			"E.g. 2026-09-24 18:38:20+03:00, beginning, dusk1+1h, "
			"dawn2-30m, end-10s"
	)

    sp.add_argument(
	  "end",
	  type = argparse_iso_date_time_zone_or_named_moment_type,
	  help = "End time in ISO format or named moment [+-offset]. "
			"E.g. 2026-09-24 18:38:20+03:00, beginning, dusk1+1h, "
			"dawn2-30m, end-10s"
	)

    sp.add_argument(
	  "-v", "--ffmpeg-verbose",
	  action = "store_true",
	  help = "Restore ffmpeg's default verbosity . Default: suppress most "
			"of its output"
	)

  # Options for the timelapse command
  subparser_timelapse.add_argument(
	  "videofile",
	  type = argparse_video_filename_type,
	  help = "Video file to generate"
	)

  subparser_timelapse.add_argument(
	  "-W", "--width",
	  type = int,
	  help = "Video width. If 0, don't scale the source images. "
			"Default: {}".
			format("no rescaling" \
				if default_timelapse_video_width == 0 else \
				"{} px".format(default_timelapse_video_width)),
	  default = default_timelapse_video_width
	)

  subparser_timelapse.add_argument(
	  "-H", "--height",
	  type = int,
	  help = "Video height. If 0, don't scale the source images. "
			"Default: {}".
			format("no rescaling" \
				if default_timelapse_video_height == 0 else \
				"{} px".format(default_timelapse_video_height)),
	  default = default_timelapse_video_height
	)

  subparser_timelapse.add_argument(
	  "-dz", "--delogo-zones",
	  type = argparse_delogo_zone_type,
	  nargs = "*",
	  help = "Delogo zone(s) definition. Format per zone: wxh+x+y"
	)

  subparser_timelapse.add_argument(
	  "-d", "--delogo",
	  action = "store_true",
	  help = "Apply delogo on the defined zone(s). Default: don't apply"
	)

  subparser_timelapse.add_argument(
	  "-dsz", "--delogo-show-zones",
	  action = "store_true",
	  help = "Show defined delogo zone(s) - with or without applying "
		"delogo. Default: don't show"
	)

  subparser_timelapse.add_argument(
	  "-dszc", "--delogo-show-zones-color",
	  type = str,
	  help = "When showing delogo zone(s), color of the border. "
			"Default: {}".
			format(default_timelapse_delogo_show_zones_color),
	  default = default_timelapse_delogo_show_zones_color
	)

  subparser_timelapse.add_argument(
	  "-s", "--speedup",
	  type = float,
	  help = "Speedup. Default: {}x".format(default_timelapse_speedup),
	  default = default_timelapse_speedup
	)

  subparser_timelapse.add_argument(
	  "-nt", "--no-timestamp",
	  action = "store_true",
	  help = "Disable in-video timestamp. Default: enabled"
	)

  subparser_timelapse.add_argument(
	  "-tx", "--timestamp-pos-x",
	  type = int,
	  help = "Timestamp X position. "
			"Default: {}".format(default_timelapse_timestamp_pos_x),
	  default = default_timelapse_timestamp_pos_x
	)

  subparser_timelapse.add_argument(
	  "-ty", "--timestamp-pos-y",
	  type = int,
	  help = "Timestamp Y position. "
			"Default: {}".format(default_timelapse_timestamp_pos_y),
	  default = default_timelapse_timestamp_pos_y
	)

  subparser_timelapse.add_argument(
	  "-tff", "--timestamp-font-file",
	  type = str,
	  help = "Timestamp font file. Default: {}".
			format(default_timelapse_timestamp_font_file),
	  default = default_timelapse_timestamp_font_file
	)

  subparser_timelapse.add_argument(
	  "-tfs", "--timestamp-font-size",
	  type = int,
	  help = "Timestamp font size. Default: {}".
			format(default_timelapse_timestamp_font_size),
	  default = default_timelapse_timestamp_font_size
	)

  subparser_timelapse.add_argument(
	  "-td", "--temporal-denoise",
	  type = int,
	  help = "Temporal denoise. 0 to disable. Default: {}".
			format(default_timelapse_temporal_denoise),
	  default = default_timelapse_temporal_denoise
	)

  subparser_timelapse.add_argument(
	  "-sd", "--spatial-denoise",
	  type = int,
	  help = "Spatial denoise. 0 to disable. Default: {}".
			format(default_timelapse_spatial_denoise),
	  default = default_timelapse_spatial_denoise
	)

  subparser_timelapse.add_argument(
	  "-cs", "--color-correction-shadows",
	  type = float,
	  help = "Shadows color correction. Default: {}".
			format(default_timelapse_shadows_correction),
	  default = default_timelapse_shadows_correction
	)

  subparser_timelapse.add_argument(
	  "-cm", "--color-correction-mediums",
	  type = float,
	  help = "Mediums color correction. Default: {}".
			format(default_timelapse_mediums_correction),
	  default = default_timelapse_mediums_correction
	)

  subparser_timelapse.add_argument(
	  "-ch", "--color-correction-highlights",
	  type = float,
	  help = "Highlights color correction. Default: {}".
			format(default_timelapse_highlights_correction),
	  default = default_timelapse_highlights_correction
	)

  subparser_timelapse.add_argument(
	  "-y", "--pov-correction-yaw",
	  type = float,
	  help = "POV correction yaw. Default: {} deg".
			format(default_timelapse_pov_correction_yaw),
	  default = default_timelapse_pov_correction_yaw
	)

  subparser_timelapse.add_argument(
	  "-p", "--pov-correction-pitch",
	  type = float,
	  help = "POV correction pitch. Default: {} deg".
			format(default_timelapse_pov_correction_pitch),
	  default = default_timelapse_pov_correction_pitch
	)

  subparser_timelapse.add_argument(
	  "-r", "--pov-correction-roll",
	  type = float,
	  help = "POV correction roll. Default: {} deg".
			format(default_timelapse_pov_correction_roll),
	  default = default_timelapse_pov_correction_roll
	)

  subparser_timelapse.add_argument(
	  "-R", "--enable-remanence",
	  action = "store_true",
	  help = 'Emable remanence ("smearing"). Default: disabled',
	)

  subparser_timelapse.add_argument(
	  "-Rr", "--remanence-rate",
	  type = float,
	  help = 'Rate of remanence ("smearing"). Useful values 0.90 > 1. '
			"1 == no decay (i.e. permanent remanence). "
			"Default: {}".
			format(default_timelapse_lagfun_decay_value),
	  default = default_timelapse_lagfun_decay_value
	)

  subparser_timelapse.add_argument(
	  "-c", "--crosshairs",
	  action = "store_true",
	  help = "Enable crosshairs in the rendered image. "
			"Default: no crosshairs"
	)

  subparser_timelapse.add_argument(
	  "-cc", "--crosshairs-color",
	  type = str,
	  help = "Crosshairs color. Default: {}".
			format(default_timelapse_crosshairs_color),
	  default = default_timelapse_crosshairs_color
	)

  subparser_timelapse.add_argument(
	  "-qx", "--x264-quality",
	  type = str,
	  help = "x264 encoding (mp4) quality. Useful values: 28 (lower) > "
			"32 (higher). Default: {}".
			format(default_timelapse_x264_quality),
	  default = default_timelapse_x264_quality
	)

  subparser_timelapse.add_argument(
	  "-qv", "--vp9-quality",
	  type = str,
	  help = "VP9 encoding (webm) quality. Useful values: 28 (lower) > "
			"32 (higher). Default: {}".
			format(default_timelapse_vp9_quality),
	  default = default_timelapse_vp9_quality
	)

  subparser_timelapse.add_argument(
	  "-f", "--framerate",
	  type = float,
	  help = "Timelapse video framerate. Default: {} fps".
			format(default_timelapse_framerate),
	  default = default_timelapse_framerate
	)

  # Options for the average command
  subparser_average.add_argument(
	  "imagefile",
	  type = argparse_image_filename_type,
	  help = "Image file to generate"
	)

  subparser_average.add_argument(
	  "-W", "--width",
	  type = int,
	  help = "Image width. If 0, don't scale the source images. "
			"Default: {}".
			format("no rescaling" \
				if default_average_image_width == 0 else \
				"{} px".format(default_average_image_width)),
	  default = default_average_image_width
	)

  subparser_average.add_argument(
	  "-H", "--height",
	  type = int,
	  help = "Image height. If 0, don't scale the source images. "
			"Default: {}".
			format("no rescaling" \
				if default_average_image_height == 0 else \
				"{} px".format(default_average_image_height)),
	  default = default_average_image_height
	)

  subparser_average.add_argument(
	  "-dz", "--delogo-zones",
	  type = argparse_delogo_zone_type,
	  nargs = "*",
	  help = "Delogo zone(s) definition. Format per zone: wxh+x+y"
	)

  subparser_average.add_argument(
	  "-d", "--delogo",
	  action = "store_true",
	  help = "Apply delogo on the defined zone(s). Default: don't apply"
	)

  subparser_average.add_argument(
	  "-dsz", "--delogo-show-zones",
	  action = "store_true",
	  help = "Show defined delogo zone(s) - with or without applying "
		"delogo. Default: don't show"
	)

  subparser_average.add_argument(
	  "-dszc", "--delogo-show-zones-color",
	  type = str,
	  help = "When showing delogo zone(s), color of the border. "
			"Default: {}".
			format(default_average_delogo_show_zones_color),
	  default = default_average_delogo_show_zones_color
	)

  subparser_average.add_argument(
	  "-sd", "--spatial-denoise",
	  type = int,
	  help = "Spatial denoise. 0 to disable. Default: {}".
			format(default_average_spatial_denoise),
	  default = default_average_spatial_denoise
	)

  subparser_average.add_argument(
	  "-cs", "--color-correction-shadows",
	  type = float,
	  help = "Shadows color correction. Default: {}".
			format(default_average_shadows_correction),
	  default = default_average_shadows_correction
	)

  subparser_average.add_argument(
	  "-cm", "--color-correction-mediums",
	  type = float,
	  help = "Mediums color correction. Default: {}".
			format(default_average_mediums_correction),
	  default = default_average_mediums_correction
	)

  subparser_average.add_argument(
	  "-ch", "--color-correction-highlights",
	  type = float,
	  help = "Highlights color correction. Default: {}".
			format(default_average_highlights_correction),
	  default = default_average_highlights_correction
	)

  subparser_average.add_argument(
	  "-y", "--pov-correction-yaw",
	  type = float,
	  help = "POV correction yaw. Default: {} deg".
			format(default_average_pov_correction_yaw),
	  default = default_average_pov_correction_yaw
	)

  subparser_average.add_argument(
	  "-p", "--pov-correction-pitch",
	  type = float,
	  help = "POV correction pitch. Default: {} deg".
			format(default_average_pov_correction_pitch),
	  default = default_average_pov_correction_pitch
	)

  subparser_average.add_argument(
	  "-r", "--pov-correction-roll",
	  type = float,
	  help = "POV correction roll. Default: {} deg".
			format(default_average_pov_correction_roll),
	  default = default_average_pov_correction_roll
	)

  subparser_average.add_argument(
	  "-c", "--crosshairs",
	  action = "store_true",
	  help = "Enable crosshairs in the rendered image. "
			"Default: no crosshairs"
	)

  subparser_average.add_argument(
	  "-cc", "--crosshairs-color",
	  type = str,
	  help = "Crosshairs color. Default: {}".
			format(default_average_crosshairs_color),
	  default = default_average_crosshairs_color
	)

  # Options for the combine command
  subparser_combine.add_argument(
	  "imagefile",
	  type = argparse_image_filename_type,
	  help = "Image file to generate"
	)

  subparser_combine.add_argument(
	  "-W", "--width",
	  type = int,
	  help = "Image width. If 0, don't scale the source images. "
			"Default: {}".
			format("no rescaling" \
				if default_combine_image_width == 0 else \
				"{} px".format(default_combine_image_width)),
	  default = default_combine_image_width
	)

  subparser_combine.add_argument(
	  "-H", "--height",
	  type = int,
	  help = "Image height. If 0, don't scale the source images. "
			"Default: {}".
			format("no rescaling" \
				if default_combine_image_height == 0 else \
				"{} px".format(default_combine_image_height)),
	  default = default_combine_image_height
	)

  subparser_combine.add_argument(
	  "-dz", "--delogo-zones",
	  type = argparse_delogo_zone_type,
	  nargs = "*",
	  help = "Delogo zone(s) definition. Format per zone: wxh+x+y"
	)

  subparser_combine.add_argument(
	  "-d", "--delogo",
	  action = "store_true",
	  help = "Apply delogo on the defined zone(s). Default: don't apply"
	)

  subparser_combine.add_argument(
	  "-dsz", "--delogo-show-zones",
	  action = "store_true",
	  help = "Show defined delogo zone(s) - with or without applying "
		"delogo. Default: don't show"
	)

  subparser_combine.add_argument(
	  "-dszc", "--delogo-show-zones-color",
	  type = str,
	  help = "When showing delogo zone(s), color of the border. "
			"Default: {}".
			format(default_combine_delogo_show_zones_color),
	  default = default_combine_delogo_show_zones_color
	)

  subparser_combine.add_argument(
	  "-sd", "--spatial-denoise",
	  type = int,
	  help = "Spatial denoise. 0 to disable. Default: {}".
			format(default_combine_spatial_denoise),
	  default = default_combine_spatial_denoise
	)

  subparser_combine.add_argument(
	  "-cs", "--color-correction-shadows",
	  type = float,
	  help = "Shadows color correction. Default: {}".
			format(default_combine_shadows_correction),
	  default = default_combine_shadows_correction
	)

  subparser_combine.add_argument(
	  "-cm", "--color-correction-mediums",
	  type = float,
	  help = "Mediums color correction. Default: {}".
			format(default_combine_mediums_correction),
	  default = default_combine_mediums_correction
	)

  subparser_combine.add_argument(
	  "-ch", "--color-correction-highlights",
	  type = float,
	  help = "Highlights color correction. Default: {}".
			format(default_combine_highlights_correction),
	  default = default_combine_highlights_correction
	)

  subparser_combine.add_argument(
	  "-y", "--pov-correction-yaw",
	  type = float,
	  help = "POV correction yaw. Default: {} deg".
			format(default_combine_pov_correction_yaw),
	  default = default_combine_pov_correction_yaw
	)

  subparser_combine.add_argument(
	  "-p", "--pov-correction-pitch",
	  type = float,
	  help = "POV correction pitch. Default: {} deg".
			format(default_combine_pov_correction_pitch),
	  default = default_combine_pov_correction_pitch
	)

  subparser_combine.add_argument(
	  "-r", "--pov-correction-roll",
	  type = float,
	  help = "POV correction roll. Default: {} deg".
			format(default_combine_pov_correction_roll),
	  default = default_combine_pov_correction_roll
	)

  subparser_combine.add_argument(
	  "-c", "--crosshairs",
	  action = "store_true",
	  help = "Enable crosshairs in the rendered image. "
			"Default: no crosshairs"
	)

  subparser_combine.add_argument(
	  "-cc", "--crosshairs-color",
	  type = str,
	  help = "Crosshairs color. Default: {}".
			format(default_combine_crosshairs_color),
	  default = default_combine_crosshairs_color
	)

  if "argcomplete" in globals():
    argcomplete.autocomplete(argparser, always_complete_options = False)

  args = argparser.parse_args()

  # Resolve ~ in filespecs
  args.srcdir = os.path.expanduser(args.srcdir)
  _image_exif_info_cache_file = os.path.expanduser(image_exif_info_cache_file)

  cached_imgs_info = {}

  # Try to load the EXIF info cache JSON file
  j = {}
  if os.path.isfile(_image_exif_info_cache_file):
    try:
      with open(_image_exif_info_cache_file, "r") as f:
        j =json.load(f)
    except Exception as e:
      print("Error: could not load EXIF info cache file: {}".format(e))
      return -1

  # If the files still exist, add the corresponding JSON entries to the cache
  # Drop them otherwise
  for fpath in j:
    if os.path.isfile(fpath):
      cached_imgs_info[fpath] = ImageInfo(json_dict = j[fpath])

  imgs_info = {}

  try:

    # Get information on the source images
    # Analyze them if they're not in the cache
    for name in sorted(os.listdir(args.srcdir)):
      if os.path.splitext(name)[1][1:].lower() in acceptable_image_extensions:

        fpath = os.path.abspath(os.path.join(args.srcdir, name))

        if fpath not in cached_imgs_info:

          print(name, end = "")

          try:
            cached_imgs_info[fpath] = ImageInfo(fpath)
            print()

          except KeyboardInterrupt:
            raise

          except:
            cached_imgs_info[fpath] = ImageInfo()
            print(" (analysis failed - ignored)")

        # If the file was analyzed properly, add it to the list of files we need
        # to process
        if cached_imgs_info[fpath].filename is not None:
          imgs_info[fpath] = cached_imgs_info[fpath]

  except KeyboardInterrupt:
    print()
    print("Interrupted")
    return -1

  # Sort the cache by date
  cached_imgs_info = OrderedDict(sorted(cached_imgs_info.items(),
					key = lambda item: item[1].datetime))

  # Save the new EXIF info cache file
  j = json.dumps(cached_imgs_info,default = lambda x: x.to_json(), indent = 2)
  with open(_image_exif_info_cache_file, "w") as f:
    print(j, file = f)

  # Sort the info of the images we're concerned with by date
  imgs_info = OrderedDict(sorted(imgs_info.items(),
					key = lambda item: item[1].datetime))
  total_imgs = len(imgs_info)

  # Mark whether the images were shot during the night or during the day
  nighttime_imgs = 0
  for k, v in imgs_info.items():
    imgs_info[k].is_nighttime_image = is_nighttime_image(v.exposuretime, v.iso)
    if imgs_info[k].is_nighttime_image:
      nighttime_imgs += 1

  # Make sure we have at least one image to process
  if total_imgs < 1:
    print("No images")
    return -1

  print("  Daytime images: {} / {}".format(total_imgs - nighttime_imgs,
						total_imgs))
  print("Nighttime images: {} / {}".format(nighttime_imgs, total_imgs))
  print()

  # Find special named moments: dawn / dusk transition times, midnights, noons
  # and beginning / end times
  named_moments = {}
  dusks = 1
  dawns = 1

  first_image = True
  for k, v in imgs_info.items():

    if first_image:

      is_nighttime_image_prev = v.is_nighttime_image
      datetime_prev = v.datetime

      print("Beginning: {}: {}".format(v.datetime, k))
      named_moments["beginning"] = v.datetime

      first_image = False
      continue

    if not is_nighttime_image_prev and v.is_nighttime_image:
      named_moments["dusk{}".format(dusks)] = v.datetime
      print("    dusk{}: {}: {}".
		format(dusks, v.datetime.isoformat(sep = " "), k))
      dusks += 1

    elif is_nighttime_image_prev and not v.is_nighttime_image:
      named_moments["dawn{}".format(dawns)] = v.datetime
      print("    dawn{}: {}: {}".
		format(dawns, v.datetime.isoformat(sep = " "), k))
      dawns += 1

    is_nighttime_image_prev = v.is_nighttime_image

  print("      End: {}: {}".format(v.datetime, k))
  named_moments["end"] = v.datetime

  # If we only analyze the source images, we're done
  if args.command == "analyze":
    return 0

  print()

  # If args.beginning or args.end are named moments, convert them to datetimes
  if not isinstance(args.beginning, datetime):
    if args.beginning[0] not in named_moments:
      argparser.error('beginning "{}" undefined'.format(args.beginning[0]))
    args.beginning = named_moments[args.beginning[0]] + \
			timedelta(seconds = args.beginning[1])

  if not isinstance(args.end, datetime):
    if args.end[0] not in named_moments:
      argparser.error('end "{}" undefined'.format(args.end[0]))
    args.end = named_moments[args.end[0]] + \
			timedelta(seconds = args.end[1])

  # Make sure the end is after the beginning
  if args.beginning == args.end:
    argparser.error("beginning and end are the same")

  elif args.beginning > args.end:
    argparser.error("beginning after the end")

  # Exclude images before the beginning and after the end
  for k in list(imgs_info):
    if imgs_info[k].datetime < args.beginning:
      del(imgs_info[k])

  for k in list(imgs_info):
    if imgs_info[k].datetime > args.end:
      del(imgs_info[k])

  nb_images = len(imgs_info)
  if nb_images == 0:
    print("Error: no images to compile between {} and {}".
		format(args.beginning.isoformat(sep = " "),
			args.end.isoformat(sep = " ")))
    return -1

  # If we're building an average image, decimate images so we don't have more
  # than the tmix video filter can chew
  if args.command == "average" and nb_images > max_averageable_images:

    step = nb_images / float(max_averageable_images)
    keepers_idx = {int(round(i * step)) for i in range(max_averageable_images)}

    for i, k in list(enumerate(imgs_info)):
      if i not in keepers_idx:
        del imgs_info[k]

    nb_images = len(imgs_info)

  print("{} images to compile between {} and {}".
		format(nb_images,
			args.beginning.isoformat(sep = " "),
			args.end.isoformat(sep = " ")))
  print()

  # Split the file path's components
  outfile = args.videofile if args.command == "timelapse" else args.imagefile
  outfile_dir = os.path.dirname(outfile)
  basename = os.path.basename(outfile)
  stem, ext = os.path.splitext(basename)
  ext = ext[1:].lower()

  # Create the video filters
  video_filters = ""

  # Add delogo filters
  if args.delogo_zones:

    # Apply delogo
    if args.delogo:
      video_filters += ",".join("delogo=" \
					"x={}:" \
					"y={}:" \
					"w={}:" \
					"h={}:" \
					"show=0".format(*z) \
				for z in args.delogo_zones) + ","

    # Show delogo zones
    if args.delogo_show_zones:
      video_filters += ",".join("drawbox=" \
					"x={}:" \
					"y={}:" \
					"w={}:" \
					"h={}:" \
					"t=fill:" \
					"color={}@0.1" \
					"".format(*z,
						args.delogo_show_zones_color) \
				for z in args.delogo_zones) + ","

  # Add scale filter
  if args.width and args.height:
    video_filters += "scale={}:{},".format(args.width, args.height)

  # Add temporal denoise
  if args.command == "timelapse" and args.temporal_denoise > 0:
    video_filters += "tmedian=radius={},".format(args.temporal_denoise)

  # Add spatial denoise
  if args.spatial_denoise > 0:
    video_filters += "removegrain={},".format(args.spatial_denoise)

  # Add color correction
  video_filters += "colorbalance=" \
				"rs={s}:gs={s}:bs={s}:" \
				"rm={m}:gm={m}:bm={m}:" \
				"rh={h}:gh={h}:bh={h},".\
				format(s = args.color_correction_shadows,
					m = args.color_correction_mediums,
					h = args.color_correction_highlights)

  # Add POV correction
  if args.pov_correction_yaw != 0 or \
	args.pov_correction_pitch != 0 or \
	args.pov_correction_roll != 0:
    video_filters += "v360=" \
				"input=equirect:" \
				"output=equirect:" \
				"yaw={}:" \
				"pitch={}:" \
				"roll={},".\
				format(args.pov_correction_yaw,
					args.pov_correction_pitch,
					args.pov_correction_roll)

  # Add remanence effect
  if args.command == "timelapse" and args.enable_remanence:
    video_filters += "lagfun=decay={},".format(args.remanence_rate)

  # Add remanence effect
  if args.command == "timelapse" and args.enable_remanence:
    video_filters += "lagfun=decay={},".format(args.remanence_rate)

  # Add in-video timestamp
  if args.command == "timelapse" and not args.no_timestamp:

    first_img_tstamp = next(iter(imgs_info.values())).datetime.timestamp()

    video_filters += "drawtext=" \
				"fontsize={}:" \
				"fontfile={}:" \
				r"text='%{{pts\:localtime\:{}\:%H\\\:%M}}':" \
				"fontcolor=white:" \
				"box=1:" \
				"boxcolor=black@0.5:" \
				"boxborderw=5:" \
				"x={}-text_w/2:" \
				"y={}-text_h-5,".\
				format(args.timestamp_font_size,
					args.timestamp_font_file,
					first_img_tstamp,
					args.timestamp_pos_x,
					args.timestamp_pos_y)

  # Crosshairs arguments
  crosshairs_vf_args = "drawbox=" \
				"x=0:" \
				"y=(ih-2)/2:" \
				"w=iw:" \
				"h=1:" \
				"color={c}," \
			"drawbox=" \
				"x=(iw-2)/2:" \
				"y=0:" \
				"w=1:" \
				"h=ih:" \
				"color={c}".format(c = args.crosshairs_color)

  # Determine the ffmpeg verbosity arguments
  if args.ffmpeg_verbose:
    ffmpeg_verbosity_args = []
  else:
    ffmpeg_verbosity_args = ["-hide_banner",
				"-loglevel", "error",
				"-stats"]

  # Should we create a video file?
  if args.command == "timelapse":

    # Build the ffmpeg concat file list with durations
    concat_list = ""
    last_tstamp = None
    duration = None

    for fpath, v in imgs_info.items():

      tstamp = v.datetime.timestamp()

      if last_tstamp is not None:
        duration = tstamp - last_tstamp
        concat_list += "duration {}\n".format(duration)

      last_tstamp = tstamp

      concat_list += "file 'file:{}'\n".format(fpath)

    if duration is not None:
      concat_list += "duration {}\n".format(duration)

    # Add crosshairs
    if args.crosshairs:
      video_filters += crosshairs_vf_args + ","

    # Set the new PTS to achieve the desired speedup
    video_filters += "setpts=PTS/{}".format(args.speedup)

    # Determine the format-specific video encoding parameters
    if ext == "mp4":
      video_encoding_args = ["-c:v", "libx264",
				"-crf", "{}".format(args.x264_quality),
				"-b:v", "0",
				"-pix_fmt", "yuv420p",
				"-f", "mp4"]

    elif ext == "webm":
      video_encoding_args = ["-c:v", "libvpx-vp9",
				"-crf", "{}".format(args.vp9_quality),
				"-b:v", "0",
				"-pix_fmt", "yuv420p",
				"-f", "webm"]

    elif ext == "m3u8":
      video_encoding_args = ["-c:v", "libx264",
				"-crf", "{}".format(args.x264_quality),
				"-b:v", "0",
				"-pix_fmt", "yuv420p",
				"-g", "{}".format(args.framerate * 2),
				"-keyint_min", "{}".format(args.framerate * 2),
				"-sc_threshold", "0",
				"-c:a", "aac",
				"-b:a", "128k",
				"-start_number", "0",
				"-hls_time", "10",
				"-hls_segment_type", "fmp4",
				"-hls_playlist_type", "vod",
				"-hls_list_size", "0",
				"-async", "1",
				"-f", "hls"]

      # Create a directory of the same name as the stem of the filename
      # to contain the output file and all the m3u8 parts
      outfile_dir = os.path.join(outfile_dir, stem)
      os.makedirs(outfile_dir, exist_ok = True)

    outfile = os.path.join(outfile_dir, basename)

    try:

      # Build the ffmpeg command
      ffmpeg_cmd = [ffmpeg_executable] + \
			ffmpeg_verbosity_args + [
			"-y",
			"-protocol_whitelist", "pipe,file",
			"-f", "concat",
			"-safe", "0",
			"-i", "pipe:0",
			"-vf", video_filters,
			"-r", "{}".format(args.framerate)] + \
			video_encoding_args + [ \
			outfile]

      # Run the ffmpeg command
      for i, arg in enumerate(ffmpeg_cmd):
        print("{:>14}: {}".format("ffmpeg command" if i == 0 else \
					"arg #{}".format(i),
					ffmpeg_cmd[i]))
      print()

      subprocess.run(ffmpeg_cmd,
			input = concat_list,
			stderr = subprocess.STDOUT,
			text = True,
			check = True)
      print()

    except KeyboardInterrupt:
      print()
      print("Interrupted")
      return -1

    except Exception as e:
      print("ffmpeg command failed: {}".format(e))
      return -1

    # Mark the video as spherical
    if ext != "m3u8":
      mark_file_spherical(outfile)

    # If the video is an m3u8, since it's encoded as fragmented MP4, it has a
    # init.mp4 header file that we need to set the spherical tags into
    #
    # Unfortunately, it doesn't have a boundary data media block (mdat box),
    # which prevents exiftool from working
    #
    # To side-step this, tack an empty mdat box to the end of the file, run
    # exiftool, then peel off the empty mdat box
    else:

      hdr_file = os.path.join(outfile_dir, "init.mp4")
      empty_mdat_box = b"\x00\x00\x00\x08mdat"

      # Tack on empty mdat box
      with open(hdr_file, "ab") as f:
        f.write(empty_mdat_box)

      # Mark the header as spherical
      mark_file_spherical(hdr_file)

      # Peel off the empty mdat box
      with open(hdr_file, "r+b") as f:
        f.seek(0, 2)  # seek the end of the file
        hdr_size = f.tell()
        f.truncate(hdr_size - len(empty_mdat_box))

  # Should we create an average file?
  elif args.command == "average":

    # Build the ffmpeg concat file list without durations
    concat_list = ""
    for fpath in imgs_info:
      concat_list += "file 'file:{}'\n".format(fpath)

    # Set the frame mixing arguments
    video_filters += "format=yuv420p," \
			"tmix=" \
			"frames={}:" \
			"weights=1".\
			format(nb_images)

    # Add crosshairs
    if args.crosshairs:
      video_filters += "," + crosshairs_vf_args

    try:

      # Build the ffmpeg command
      ffmpeg_cmd = [ffmpeg_executable] + \
			ffmpeg_verbosity_args + [
			"-y",
			"-protocol_whitelist", "pipe,file",
			"-f", "concat",
			"-safe", "0",
			"-i", "pipe:0",
			"-vf", video_filters,
			"-update", "1",
			outfile]

      # Run the ffmpeg command
      for i, arg in enumerate(ffmpeg_cmd):
        print("{:>14}: {}".format("ffmpeg command" if i == 0 else \
					"arg #{}".format(i),
					ffmpeg_cmd[i]))
      print()

      subprocess.run(ffmpeg_cmd,
			input = concat_list,
			stderr = subprocess.STDOUT,
			text = True,
			check = True)
      print()

    except KeyboardInterrupt:
      print()
      print("Interrupted")
      return -1

    except Exception as e:
      print("ffmpeg command failed: {}".format(e))
      return -1

    # Mark the image as spherical
    mark_file_spherical(outfile)

  # Should we create an combined file?
  elif args.command == "combine":

    # Build the ffmpeg concat file list without durations
    concat_list = ""
    for fpath in imgs_info:
      concat_list += "file 'file:{}'\n".format(fpath)

    # Set the frame combining arguments
    video_filters += "format=rgb24," \
			"lagfun=" \
				"decay=1"

    # Add crosshairs
    if args.crosshairs:
      video_filters += "," + crosshairs_vf_args

    try:

      # Build the ffmpeg command
      ffmpeg_cmd = [ffmpeg_executable] + \
			ffmpeg_verbosity_args + [
			"-y",
			"-protocol_whitelist", "pipe,file",
			"-f", "concat",
			"-safe", "0",
			"-i", "pipe:0",
			"-vf", video_filters,
			"-update", "1",
			outfile]

      # Run the ffmpeg command
      for i, arg in enumerate(ffmpeg_cmd):
        print("{:>14}: {}".format("ffmpeg command" if i == 0 else \
					"arg #{}".format(i),
					ffmpeg_cmd[i]))
      print()

      subprocess.run(ffmpeg_cmd,
			input = concat_list,
			stderr = subprocess.STDOUT,
			text = True,
			check = True)
      print()

    except KeyboardInterrupt:
      print()
      print("Interrupted")
      return -1

    except Exception as e:
      print("ffmpeg command failed: {}".format(e))
      return -1

    # Mark the image as spherical
    mark_file_spherical(outfile)

  return 0



### Main program
if __name__ == "__main__":
  sys.exit(main())
