"""Rich Theta web API client class
"""

### Parameters
from .default import _default_connect_timeout, \
			_default_reconnect_tries, \
			_default_request_timeout, \
			_default_stop_video_capture_timeout, \
			_default_file_operations_timeout, \
			_default_check_photo_taken_every, \
			_default_max_wait_photo_taken, \
			_default_max_wait_rebooted, \
			_default_live_preview_viewer_command



### Modules
import os
import re
import requests
from requests.auth import HTTPDigestAuth
from time import time, sleep
from datetime import datetime
import exiftool	# type: ignore
import subprocess



### classes
class Theta:
  """Web API communication class for Ricoh Theta cameras
  """

  ### Constants
  _file_url_pattern = r"^http://(.*)/files/" \
			r"([0-9a-fA-F]{32}/)" \
			r"([0-9]{3}RICOH/)" \
			r"(R[0-9]{7}\.(?:JPG|MP4))$"

  _allowed_ev_values = (-4.0, -3.7, -3.3, -3.0, -2.7, -2.3,
			-2.0, -1.7, -1.3, -0.7, -0.3, 0.0,
			+0.3, +0.7, +1.0, +1.3, +1.7, +2.0,
			+2.3, +2.7, +3.0, +3.3, +3.7, +4.0)

  _exposure_programs = {1: "manual",
			2: "auto",
			3: "aperture",
			4: "shutter",
			9: "iso"}

  _valid_file_formats = (# Type,  Width, Height, Codec, framerate, dualtrack

			# Theta A1 and Theta X image
			("jpeg", 11008, 5504,   None,               None, None),
			("jpeg", 5504,  2752,   None,               None, None),

			# Theta Z1 image
			("jpeg", 6720,  3360,   None,               None, None),
			("raw+", 6720,  3360,   None,               None, None),

			# Theta A1 video and Theta X video
			("mp4",  7680,  3840,   "H.264/MPEG-4 AVC", 10,   None),
			("mp4",  7680,  3840,   "H.264/MPEG-4 AVC", 5,    None),
			("mp4",  7680,  3840,   "H.264/MPEG-4 AVC", 2,    None),
			("mp4",  5760,  2880,   "H.264/MPEG-4 AVC", 10,   None),
			("mp4",  5760,  2880,   "H.264/MPEG-4 AVC", 5,    None),
			("mp4",  5760,  2880,   "H.264/MPEG-4 AVC", 2,    None),
			("mp4",  3840,  1920,   "H.264/MPEG-4 AVC", 30,   None),
			("mp4",  3840,  1920,   "H.264/MPEG-4 AVC", 10,   None),
			("mp4",  1920,  960,    "H.264/MPEG-4 AVC", 30,   None),

			# Theta A1 video
			("mp4",  3840,  1920,   "H.264/MPEG-4 AVC", 5,    None),
			("mp4",  3840,  1920,   "H.264/MPEG-4 AVC", 2,    None),
			("mp4",  7680,  3840,   "H.265/HEVC",       10,   None),
			("mp4",  7680,  3840,   "H.265/HEVC",       5,    None),
			("mp4",  7680,  3840,   "H.265/HEVC",       2,    None),
			("mp4",  5760,  2880,   "H.265/HEVC",       10,   None),
			("mp4",  5760,  2880,   "H.265/HEVC",       5,    None),
			("mp4",  5760,  2880,   "H.265/HEVC",       2,    None),
			("mp4",  3840,  1920,   "H.265/HEVC",       30,   None),
			("mp4",  3840,  1920,   "H.265/HEVC",       10,   None),
			("mp4",  3840,  1920,   "H.265/HEVC",       5,    None),
			("mp4",  3840,  1920,   "H.265/HEVC",       2,    None),
			("mp4",  1920,  960,    "H.265/HEVC",       30,   None),

			# Theta X video
			("mp4",  5760,  2880,   "H.264/MPEG-4 AVC", 30,   None),
			("mp4",  5760,  2880,   "H.264/MPEG-4 AVC", 15,   None),
			("mp4",  3840,  1920,   "H.264/MPEG-4 AVC", 60,   None),
			("mp4",  3840,  1920,   "H.264/MPEG-4 AVC", 15,   None),
			("mp4",  1920,  960,    "H.264/MPEG-4 AVC", 60,   None),

			# Theta X fisheye video (_0 and _1 files)
			("mp4",  2752,  2752,   "H.264/MPEG-4 AVC", 30,   None),
			("mp4",  2752,  2752,   "H.264/MPEG-4 AVC", 10,   None),
			("mp4",  2752,  2752,   "H.264/MPEG-4 AVC", 5,    None),
			("mp4",  2752,  2752,   "H.264/MPEG-4 AVC", 2,    None),

			# Theta Z1 video
			("mp4",  3840,  1920,  "H.264/MPEG-4 AVC",  None, None),
			("mp4",  1920,  960,   "H.264/MPEG-4 AVC",  None, None),

			# Theta Z1 fisheye video (_0 and _1 files)
			("mp4",  3648,  3648,  "H.264/MPEG-4 AVC",  2,    None),
			("mp4",  3648,  3648,  "H.264/MPEG-4 AVC",  1,    None),
			("mp4",  2688,  2688,  "H.264/MPEG-4 AVC",  2,    None),
			("mp4",  2688,  2688,  "H.264/MPEG-4 AVC",  1,    None),

			# Theta Z1 fisheye video (2 tracks)
			("mp4",  3648,  3648,  "H.264/MPEG-4 AVC",  2,    True),
			("mp4",  3648,  3648,  "H.264/MPEG-4 AVC",  1,    True),
			("mp4",  2688,  2688,  "H.264/MPEG-4 AVC",  2,    True),
			("mp4",  2688,  2688,  "H.264/MPEG-4 AVC",  1,    True))

  _valid_filters = ("off",
			"DR Comp",
			"Noise Reduction",
			"hdr",
			"Hh hdr")

  _valid_hdr_brackets = {#: (Min EV, Max EV)
			 0: (-4,     +2),
			 1: (-1,     +1),
			 2: (-2,     +1),
			 3: (-3,     +3),
			 4: (-4,     +4),
			 5: (-5,     +2)}

  _valid_stitching_modes = ("auto",
				"static",
				"dynamic",
				"dynamicAuto",
				"dynamicSemiAuto",
				"dynamicSave",
				"dynamicLoad",
				"none")



  ### Methods
  def __init__(self,
		addr,		# 192.168.1.1 when the camera is in wifi AP mode
		username,	# "THETA<camera S/N>" - e.g. "THETAYR30123456"
		password):	# See "set_client_mode_password" method below
    """__init__ method
    """

    # Sanity-check the arguments
    assert isinstance(addr, str), \
		"addr should be a string"
    assert addr != "", \
		"addr required"
    assert username is None or isinstance(username, str), \
		"username should be a string or None"
    if username is not None:
      assert username != "", \
		"username required"
    assert password is None or isinstance(password, str), \
		"password should be a string or None"
    if password is not None:
      assert password != "", \
		"password required"

    self.addr = addr

    if username is not None and password is not None:
      self.__digest_auth = HTTPDigestAuth(username, password)
    else:
      self.__digest_auth = None

    self.session = None

    # File URL pattern regex
    self.__file_url_regex = re.compile(self._file_url_pattern)

    # Exposure program numbers by name
    self.__exposure_program_names = {v: k for k, v in \
					self._exposure_programs.items()}

    # HDR bracket by min/max values
    self.__valid_hdr_bracket_min_max_evs = {v: k for k, v in \
					self._valid_hdr_brackets.items()}

    # Camera information
    self.info = None

    # Camera state and update throttle
    self.state = None
    self._state_fingerprint = None
    self._last_state_update_check_tstamp = None
    self._state_update_check_throttle = None

    # Last command's ID
    self.cmd_id = None



  def close(self):
    """Close the session if it's opeh
    """

    if self.session is not None:
      self.session.close()
      self.session = None



  def __enter__(self):
    """__enter__ method
    """

    return self



  def __exit__(self,
		exc_type,
		exc_value,
		exc_traceback):
    """__exit__ method
    """

    self.close()



  def _request(self,
		endpoint = None,
		url = None,
		json_req = None,
		stream = False,
		connect_timeout = _default_connect_timeout,
		reconnect_tries = _default_reconnect_tries,
		read_timeout = _default_request_timeout):
    """Send a request to the camera, return the response
    """

    # Sanity-check the arguments
    assert endpoint is None or isinstance(endpoint, str), \
		"endpoint should be a string or None"
    if endpoint is not None:
      assert endpoint != "", \
		"endpoint required"
    assert url is None or isinstance(url, str), \
		"url should be a string or None"
    if url is not None:
      assert url != "", \
		"url required"
    assert (endpoint and not url) or (not endpoint and url), \
		"endpoint or url required but not both"
    assert json_req is None or isinstance(json_req, dict), \
		"json_req should be a dict or None"
    assert type(connect_timeout) in (int, float), \
		"connect_timeout required and should be an int or float"
    assert isinstance(reconnect_tries, int), \
		"reconnect_timeout required and should be an int"
    assert reconnect_tries >= 0, \
		"reconnect_tries should be >= 0"
    assert type(read_timeout) in (int, float), \
		"read_timeout required and should be an int or float"

    # If an endpoint was supplied, construct the URL
    if endpoint:
      url = "http://{}{}".format(self.addr, endpoint)

    # Build the session.get or session.post arguments
    kwargs = {"timeout": (connect_timeout, read_timeout)}

    if json_req is not None:
      kwargs["json"] = json_req

    if self.__digest_auth is not None:
      kwargs["auth"] = self.__digest_auth

    if stream:
      kwargs["stream"] = True

    # Communicate with the camera
    #
    # If the session already existed and the communication times out, try
    # reconnecting by closing the session and creating another, then
    # communicationg again
    #
    # If the session didn't exist to begin with, only try once
    t = 0
    while True:

      # Increment the try counter
      t += 1

      # Do we have an existing session?
      if self.session is None:

        # If this is the first try, make sure we don't try again
        if t == 1:
          reconnect_tries = 0

        # Create the session
        self.session = requests.Session()

        # Set headers globally for all requests in the session
        self.session.headers.update({"Content-Type": 
					"application/json; charset=utf-8"})

      # Send the request to the camera and read a response
      try:
        resp = (self.session.get if json_req is None else \
		self.session.post)(url, **kwargs)
        resp.raise_for_status()
        break

      except (TimeoutError,
		requests.exceptions.Timeout,
		requests.exceptions.ConnectionError,
		requests.exceptions.ConnectTimeout,
		requests.exceptions.ReadTimeout):

        # Close the session to force a reconnect
        self.session.close()

        # If we're retried too many times, raise the exception
        if t > reconnect_tries:
          raise

        sleep(1)

    return resp



  def get_info(self,
		connect_timeout = _default_connect_timeout,
		reconnect_tries = _default_reconnect_tries,
		read_timeout = _default_request_timeout):
    """Get the camera's information and save it in the instance
    """

    json_resp = self._request(endpoint = "/osc/info",
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout).json()

    assert "manufacturer" in json_resp, \
		"malformed JSON response: missing manufacturer"
    assert "model" in json_resp, \
		"malformed JSON response: missing model"
    assert "serialNumber" in json_resp, \
		"malformed JSON response: missing serialNumber"

    self.info = json_resp

    return self.info



  def get_state(self,
		connect_timeout = _default_connect_timeout,
		reconnect_tries = _default_reconnect_tries,
		read_timeout = _default_request_timeout):
    """Get the camera's state and save it in the instance
    """

    json_resp = self._request(endpoint = "/osc/state",
				json_req = {},
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout).json()

    assert "fingerprint" in json_resp, \
		"malformed JSON response: missing fingerprint"
    assert "state" in json_resp, \
		"malformed JSON response: missing state"

    self.fingerprint = json_resp["fingerprint"]
    self.state = json_resp["state"]

    return self.state



  def check_for_updates(self,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_request_timeout):
    """Check for changes to the Theta state
    If the method is called too often, thottle the rate of checks
    Return True if the state was changed, False otherwise
    """

    # Wait if check_for_update was called too recently
    if self._last_state_update_check_tstamp is not None and \
	self._state_update_check_throttle is not None:

      wait_for = self._last_state_update_check_tstamp + \
			self._state_update_check_throttle - time()
      if wait_for > 0:
        sleep(wait_for)

    json_resp = self._request(endpoint = "/osc/checkForUpdates",
				json_req = {},
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout).json()

    assert "stateFingerprint" in json_resp, \
		"malformed JSON response: missing stateFingerprint"
    assert "throttleTimeout" in json_resp, \
		"malformed JSON response: missing throttleTimeout"

    self._last_state_update_check_tstamp = time()

    self._state_update_check_throttle = json_resp["throttleTimeout"]
    if isinstance(self._state_update_check_throttle, str):
      self._state_update_check_throttle = int(self._state_update_check_throttle)

    prev_state_fingerprint = self._state_fingerprint
    self._state_fingerprint = json_resp["stateFingerprint"]

    return self._state_fingerprint != prev_state_fingerprint



  def _execute(self,
		cmd,
		params = None,
		stream = False,
		connect_timeout = _default_connect_timeout,
		reconnect_tries = _default_reconnect_tries,
		read_timeout = _default_request_timeout):
    """Execute a command
    """

    # Sanity-check the arguments
    assert isinstance(cmd, str), \
		"cmd should be a string"
    assert cmd != "", \
		"cmd required"
    assert params is None or isinstance(params, dict), \
		"params should be a dict or None"

    json_req = {"name": cmd}
    if params is not None:
      json_req["parameters"] = params

    resp = self._request(endpoint = "/osc/commands/execute",
				json_req = json_req,
				stream = stream,
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)

    # If a stream was requested, don't process the response
    if stream:
      return resp

    json_resp = resp.json()

    # If the command returns an ID, save it so it's usable to check its status
    # later
    self.cmd_id = json_resp.get("id", self.cmd_id)
    if isinstance(self.cmd_id, str):
      self.cmd_id = int(self.cmd_id)

    return json_resp
				


  def get_command_status(self,
				cmd_id = None,
				connect_timeout = _default_connect_timeout,
				reconnect_tries = _default_reconnect_tries,
				read_timeout = _default_request_timeout):
    """Check on a command's status
    If the command ID is supplied, override the last saved one
    """

    if cmd_id is None:
      cmd_id = self.cmd_id
      assert cmd_id is not None, \
		"no previous command"

    # Sanity-check the arguments
    assert isinstance(cmd_id, int), \
		"cmd_id should be an int"

    return self._request(endpoint = "/osc/commands/status",
				json_req = {
					"id": cmd_id},
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout).json()



  def _get_options(self,
			option_names,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_request_timeout):
    """Get the values of several options
    """

    # Sanity-check the arguments
    assert isinstance(option_names, set) and option_names, \
		"option_names should be a non-empty set of non-empty string"
    assert all(isinstance(name, str) and name != "" for name in option_names), \
		"option_names should be a non-empty set of non-empty string"

    json_resp = self._execute(cmd = "camera.getOptions",
				params = {
					"optionNames": list(option_names)},
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)

    assert "state" in json_resp, \
		"malformed JSON response: missing state"
    json_resp_state = json_resp["state"]
    assert json_resp_state == "done", \
		'command returned state "{}"'.format(json_resp_state)

    assert "results" in json_resp, \
		"malformed JSON response: missing results"
    json_resp_results = json_resp["results"]

    assert "options" in json_resp_results, \
		"malformed JSON response: missing options"
    json_resp_results_options = json_resp_results["options"]

    assert set(json_resp_results_options) == option_names, \
		"command returned options {} - should be {}".\
			format(", ".join('"{}"'.format(name) \
					for name in json_resp_results_options),
				", ".join('"{}"'.format(name) \
					for name in option_names))

    return json_resp_results_options
				


  def _get_option(self,
			option_name,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_request_timeout):
    """Get the value of one option
    """

    # Sanity-check the arguments
    assert isinstance(option_name, str) and option_name != "", \
		"option_name required and should be a string"

    return self._get_options(option_names = {option_name},
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)[option_name]
				


  def _set_options(self,
			options,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_request_timeout):
    """Set the values of several options
    """

    # Sanity-check the arguments
    assert isinstance(options, dict) and options, \
		"options should be a non-empty dict with non-empty key strings "
    assert all(isinstance(key, str) for key in options.keys()), \
		"keys in the options dict should be strings "

    return self._execute(cmd = "camera.setOptions",
				params = {
					"options": options},
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)
				


  def _set_option(self,
			option,
			value,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_request_timeout):
    """Set the value of one option
    """

    # Sanity-check the arguments
    assert isinstance(option, str) and option != "", \
		"option required and should be a string"

    return self._set_options(options = {option: value},
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)
				


  def set_client_mode_password(self,
				password,
				connect_timeout = _default_connect_timeout,
				reconnect_tries = _default_reconnect_tries,
				read_timeout = _default_request_timeout):
    """Set the client-mode password (different from the wifi password!)

    This is the password used to access the web API in wifi client mode, and
    required for most operations provided by this very class - i.e. it's the
    same password passed to __init__.

    This password may be set for the first time using Ricoh's new Ricoh360
    Android app (com.ricoh360.mobile), or it may be set using this class by
    connecting to the camera in wifi AP mode - aka "direct mode", instanciating
    the class with the camera's IP in AP mode (ormally 192.168.1.1) and password
    set to None, then calling this method.

    The password may only be set when connected to the camera in AP mode - aka
    "direct mode".
    """

    # Sanity-check the arguments
    assert isinstance(password, str), \
		"password should be a string"

    return self._set_option("_password", password,
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)



  def get_open_source_licenses(self,
				connect_timeout = _default_connect_timeout,
				reconnect_tries = _default_reconnect_tries,
				read_timeout = _default_request_timeout):
    """Get the open-source license information used by the Theta camera
    """

    return self._request(endpoint = "/legal-information/open-source-licenses",
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout).text



  def get_event_log(self,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_request_timeout):
    """Get the event log
    """

    return self._request(endpoint = "/log/eventLog",
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout).text.splitlines()



  def get_power_mode(self,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_request_timeout):
    """Get the current power mode: "on" or "silent"
    """

    mode = self._get_option("_cameraPower",
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)

    return "silent" if mode == "silentMode" else mode



  def set_power_mode(self,
			power,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_request_timeout):
    """Set the camera's power to "on" (display on), ""silent" (display off),
    "sleep" or "off" (turns the camera off)
    """

    # Sanity-check the arguments
    assert power in ("on", "silent", "sleep", "off"), \
    		'power should be "on", "silent", "sleep" or "off"'

    if power in ("sleep", "off"):

      json_resp = None

      try:
        self._set_option("_cameraPower", power,
				connect_timeout = connect_timeout,
				reconnect_tries = 0,
				read_timeout = 0.1)

        # Close the session since the camera has now gone silent
        self.session.close()
        self.session = None

      except (TimeoutError,
		requests.exceptions.ConnectionError,
		requests.exceptions.ConnectTimeout,
		requests.exceptions.ReadTimeout):
        pass

    else:
      json_resp =  self._set_option("_cameraPower",
					"silentMode" if power == "silent" else \
					power,
					connect_timeout = connect_timeout,
					reconnect_tries = reconnect_tries,
					read_timeout = read_timeout)

    return json_resp



  def get_power_saving(self,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_request_timeout):
    """Get the current state of power saving
    Returns True if it's enabled, False if not
    """

    return self._get_option("_powerSaving",
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout).lower() == "on"



  def set_power_saving(self,
			enabled,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_request_timeout):
    """Enable or disable power saving
    """

    return self._set_option("_powerSaving", "ON" if enabled else "OFF",
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)



  def reboot(self,
		wait_rebooted = _default_max_wait_rebooted,
		connect_timeout = _default_connect_timeout,
		reconnect_tries = _default_reconnect_tries,
		read_timeout = _default_request_timeout):
    """Reboot the camera
    If wait_rebooted > 0, wait until the device comes back online for that
    number of seconds at the most
    """

    # Sanity-check the arguments
    assert type(wait_rebooted) in (int, float), \
		"wait_rebooted required and should be an int or float"
    assert wait_rebooted >= 0, \
		"wait_rebooted should be >= 0"

    # Reboot the camera
    json_resp = self._execute(cmd = "camera._reboot",
				params = {},
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)

    assert "state" in json_resp, \
		"malformed JSON response: missing state"
    json_resp_state = json_resp["state"]
    assert json_resp_state == "done", \
		'command returned state "{}"'.format(json_resp_state)

    # Close the session since the camera has now gone silent
    self.session.close()
    self.session = None

    if wait_rebooted:

      # Try to get the camera's information until it goes from not replying to
      # replying
      now = time()
      start_wait_tstamp = now
      stop_wait_tstamp = now + wait_rebooted

      prev_json_resp = json_resp

      while not (prev_json_resp is None and json_resp is not None):

        prev_json_resp = json_resp

        # Ensure we don't poll faster than once per second
        recontact_at_tstamp = now + 1

        try:
          json_resp = self.get_info(connect_timeout = connect_timeout,
					reconnect_tries = 0,
					read_timeout = read_timeout)
          now = time()

        except (TimeoutError,
		requests.exceptions.ConnectionError,
		requests.exceptions.ConnectTimeout,
		requests.exceptions.ReadTimeout):
          now = time()
          if now >= stop_wait_tstamp:
            raise
          json_resp = None

        # Wait until at least once second has passed since the beginning of the
        # last attempt to contact the device
        wait_for =  recontact_at_tstamp - now
        if wait_for > 0:
          sleep(wait_for)
          now = time()

      # Add the reboot time in seconds to the reply of the info comand, for
      # reference
      json_resp["reboot_time"] = now - start_wait_tstamp

    return json_resp



  def lock_ui(self,
		connect_timeout = _default_connect_timeout,
		reconnect_tries = _default_reconnect_tries,
		read_timeout = _default_request_timeout):
    """Lock the camera's user interfae
    """

    return self._set_option("_cameraControlSource", "app",
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)



  def unlock_ui(self,
		connect_timeout = _default_connect_timeout,
		reconnect_tries = _default_reconnect_tries,
		read_timeout = _default_request_timeout):
    """Lock the camera's user interfae
    """

    return self._set_option("_cameraControlSource", "camera",
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)



  def get_live_preview_format(self,
				connect_timeout = _default_connect_timeout,
				reconnect_tries = _default_reconnect_tries,
				read_timeout = _default_request_timeout):
    """Get the live preview MJPEG stream format
    """

    json_resp = self._get_option("previewFormat",
					connect_timeout = connect_timeout,
					reconnect_tries = reconnect_tries,
					read_timeout = read_timeout)

    assert "framerate" in json_resp, \
		"malformed JSON response: missing framerate"
    assert "width" in json_resp, \
		"malformed JSON response: missing width"
    assert "height" in json_resp, \
		"malformed JSON response: missing height"

    return json_resp



  def live_preview(self,
			viewer_cmd = _default_live_preview_viewer_command,
			viewer_stdout = subprocess.DEVNULL,
			viewer_stderr = subprocess.DEVNULL,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_request_timeout):
    """Get the live preview stream and pipe it to an external viewer's stdin
    By default, the viewer's stdout and stderr are supressed
    """

    # Sanity-check the arguments
    assert isinstance(viewer_cmd, str) and viewer_cmd != "", \
		"viewer_cmd required and should be a string"

    # Spawn the viewer
    viewer_process = subprocess.Popen(viewer_cmd,
					stdin = subprocess.PIPE,
					stdout = viewer_stdout,
					stderr = viewer_stderr,
					shell = True)

    # Get the live preview stream and send it to the viewer's stdin
    resp = None
    try:
      resp = self._execute(cmd = "camera.getLivePreview",
				params = {},
				stream = True,
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)

      # Get data chunks and send them to the viewer
      for chunk in resp.iter_content(chunk_size = 8192):
        if chunk:	# filter out keepalive chunks
          try:
            viewer_process.stdin.write(chunk)
            viewer_process.stdin.flush()

          except BrokenPipeError:
            # The viewer exited: close its stdin to avoid an unhandled
            # BrokenPipeError exception
            try:
              viewer_process.stdin.close()
            except BrokenPipeError:
              pass
            break

    finally:
      # Close the connection if it was open
      if resp is not None:
        resp.close()

      # Clean up the process
      if viewer_process.poll() is None:
        viewer_process.terminate()

      try:
        viewer_process.wait(timeout = 5)

      except subprocess.TimeoutExpired:
        viewer_process.kill()
        viewer_process.wait()



  def get_file_format(self,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_request_timeout):
    """Get the current file format for the current capture mode
    """

    json_resp = self._get_option("fileFormat",
					connect_timeout = connect_timeout,
					reconnect_tries = reconnect_tries,
					read_timeout = read_timeout)

    assert "type" in json_resp, \
		"malformed JSON response: missing type"
    assert "width" in json_resp, \
		"malformed JSON response: missing width"
    assert "height" in json_resp, \
		"malformed JSON response: missing height"

    json_resp["filetype"] = json_resp["type"]
    del(json_resp["type"])

    if "_codec" in json_resp:
      json_resp["codec"] = json_resp["_codec"]
      del(json_resp["_codec"])
    else:
      json_resp["codec"] = None

    if "_frameRate" in json_resp:
      json_resp["framerate"] = json_resp["_frameRate"]
      del(json_resp["_frameRate"])
    else:
      json_resp["framerate"] = None

    if "_dualTrack" in json_resp:
      json_resp["dualtrack"] = json_resp["_dualTrack"]
      del(json_resp["_dualTrack"])
    else:
      json_resp["dualtrack"] = None

    return json_resp



  def set_file_format(self,
			filetype = None,
			width = None,
			height = None,
			codec = None,
			framerate = None,
			dualtrack = None,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_request_timeout):
    """Set the file format for the current capture mode
    """

    dualtrack = True if dualtrack else None

    # Sanity-check the arguments
    assert filetype in ("jpeg", "raw+", "mp4"), \
    		'filetype should be "jpeg", "raw+" or "mp4"'
    assert isinstance(width, int), \
		"width required and should be an int"
    assert isinstance(height, int), \
		"height required and should be an int"
    assert codec is None or isinstance(codec, str), \
		"codec should be a string or None"
    assert framerate is None or isinstance(framerate, int), \
		"framerate should be an int or None"
    assert (filetype, width, height, codec, framerate, dualtrack) in \
			self._valid_file_formats, \
		"invalid file format"

    # Build the option's value
    fileformat = {"type": filetype, "width": width, "height": height}

    if codec is not None:
      fileformat["_codec"] = codec

    if framerate is not None:
      fileformat["_frameRate"] = framerate

    if dualtrack is not None:
      fileformat["_dualTrack"] = dualtrack

    return self._set_option("fileFormat", fileformat,
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)



  def get_filter(self,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_request_timeout):
    """Get the current filter - one of "off", "DR Comp", "Noise Reduction",
    "hdr" or "Hh hdr"
    """

    return self._get_option("_filter",
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)



  def set_filter(self,
			filter,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_request_timeout):
    """Get the current filter - one of "off", "DR Comp", "Noise Reduction",
    "hdr" or "Hh hdr"
    """

    # Sanity-check the arguments
    assert filter in self._valid_filters, \
		"filter should be {}".\
			format(" or ".
				join(", ".join('"{}"'.format(f) \
						for f in self._valid_filters
					).rsplit(", ", 1)))

    return self._set_option("_filter", filter,
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)



  def get_exposure_program(self,
				connect_timeout = _default_connect_timeout,
				reconnect_tries = _default_reconnect_tries,
				read_timeout = _default_request_timeout):
    """Get the current exposure program
    Return the name of the program if found, the returned program number
    otherwise
    """

    n = self._get_option("exposureProgram",
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)

    return self._exposure_programs.get(n, n)



  def set_exposure_program(self,
				program,
				connect_timeout = _default_connect_timeout,
				reconnect_tries = _default_reconnect_tries,
				read_timeout = _default_request_timeout):
    """Set the exposure program - one of manual, auto, aperture, shutter, iso
    or an integer that will be used directly as program number
    """

    # Sanity-check the arguments and convert program from a string to a
    # program number
    if isinstance(program, str):
      assert program in self.__exposure_program_names, \
		"program should be {}".\
			format(" or ".
				join(", ".join('"{}"'.format(f) \
					for f in self.__exposure_program_names
					).rsplit(", ", 1)))
      program = self.__exposure_program_names[program]

    assert isinstance(program, int), \
		"program should be an int or a string"

    return self._set_option("exposureProgram", program,
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)



  def get_exposure_compensation(self,
				connect_timeout = _default_connect_timeout,
				reconnect_tries = _default_reconnect_tries,
				read_timeout = _default_request_timeout):
    """Get the current EV value - one of -4.0, -3.7, -3.3, -3.0, -2.7, -2.3,
    -2.0, -1.7, -1.3, -0.7, -0.3, 0.0, +0.3, +0.7, +1.0, +1.3, +1.7, +2.0,
    +2.3, +2.7, +3.0, +3.3, +3.7 or +4.0
    """

    return self._get_option("exposureCompensation",
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)



  def set_exposure_compensation(self,
				ev,
				connect_timeout = _default_connect_timeout,
				reconnect_tries = _default_reconnect_tries,
				read_timeout = _default_request_timeout):
    """Set the EV value - one of -4.0, -3.7, -3.3, -3.0, -2.7, -2.3,
    -2.0, -1.7, -1.3, -0.7, -0.3, 0.0, +0.3, +0.7, +1.0, +1.3, +1.7,
    +2.0, +2.3, +2.7, +3.0, +3.3, +3.7 or +4.0
    """

    # Sanity-check the arguments
    assert type(ev) in (int, float), \
		"ev required and should be int or a flot"
    assert ev in self._allowed_ev_values, \
		"ev should be {}".\
			format(" or ".
				join(", ".join("{}".format(f) \
					for f in self._allowed_ev_values
					).rsplit(", ", 1)))

    return self._set_option("exposureCompensation", ev,
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)



  def get_hdr_bracket(self,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_request_timeout):
    """Get the current bracket for the HDR filter
    """

    n = self._get_option("_hdrBracket",
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)

    if n in self._valid_hdr_brackets:
      return {"min_ev":  self._valid_hdr_brackets[n][0],
		"max_ev":  self._valid_hdr_brackets[n][1]}
    else:
      return n



  def set_hdr_bracket(self,
			min_ev,
			max_ev,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_request_timeout):
    """Set the bracket for the HDR filter
    """

    # Sanity-check the arguments
    assert isinstance(min_ev, int), \
		"min_ev required and should be an int"
    assert isinstance(max_ev, int), \
		"max_ev required and should be an int"
    assert (min_ev, max_ev) in self.__valid_hdr_bracket_min_max_evs, \
		"(min_ev, max_ev) should be {}".\
			format(" or ".
				join("; ".join("{}".format(f) \
					for f in \
					self.__valid_hdr_bracket_min_max_evs
					).rsplit("; ", 1))).replace(";", ",")

    return self._set_option("_hdrBracket",
				self.__valid_hdr_bracket_min_max_evs[
							(min_ev, max_ev)],
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)



  def get_stitching_mode(self,
				connect_timeout = _default_connect_timeout,
				reconnect_tries = _default_reconnect_tries,
				read_timeout = _default_request_timeout):
    """Get the camera's stitching mode - one of "auto", "static", "dynamic",
    "dynamicAuto", "dynamicSemiAuto", "dynamicSave", "dynamicLoad" or "none"
    """

    return self._get_option("_imageStitching",
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)



  def set_stitching_mode(self,
				mode,
				connect_timeout = _default_connect_timeout,
				reconnect_tries = _default_reconnect_tries,
				read_timeout = _default_request_timeout):
    """Set the camera's stitching mode - one of "auto", "static", "dynamic",
    "dynamicAuto", "dynamicSemiAuto", "dynamicSave", "dynamicLoad" or "none"
    """

    # Sanity-check the arguments
    assert mode in self._valid_stitching_modes, \
		"mode should be {}".\
			format(" or ".
				join(", ".join('"{}"'.format(f) \
					for f in self._valid_stitching_modes
					).rsplit(", ", 1)))

    return self._set_option("_imageStitching", mode,
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)



  def get_capture_mode(self,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_request_timeout):
    """Get the current capture mode - "image" or "video"
    """

    return self._get_option("captureMode",
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)



  def set_capture_mode(self,
			mode,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_request_timeout):
    """Set the camera's capture mode to "image" or "video"
    """

    # Sanity-check the arguments
    assert mode in ("image", "video"), \
		'mode should be "image" or "video"'

    return self._set_option("captureMode", mode,
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)



  def get_exposure_delay(self,
				connect_timeout = _default_connect_timeout,
				reconnect_tries = _default_reconnect_tries,
				read_timeout = _default_request_timeout):
    """Get the exposure delay (between 0s and 10s)
    """

    return self._get_option("exposureDelay",
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)



  def set_exposure_delay(self,
				delay,
				connect_timeout = _default_connect_timeout,
				reconnect_tries = _default_reconnect_tries,
				read_timeout = _default_request_timeout):
    """Set the exposure delay (between 0s and 10s)
    """

    # Sanity-check the arguments
    assert isinstance(delay, int), \
		"delay required and should be an int"
    assert 0 <= delay <= 10, \
		"delay should be >= 0 and <= 10"

    return self._set_option("exposureDelay", delay,
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)



  def start_capture(self,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_request_timeout):
    """Start capturing video
    """

    json_resp = self._execute(cmd = "camera.startCapture",
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)

    assert "state" in json_resp, \
		"malformed JSON response: missing state"
    json_resp_state = json_resp["state"]
    assert json_resp_state == "done", \
		'command returned state "{}"'.format(json_resp_state)

    return json_resp



  def stop_capture(self,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_stop_video_capture_timeout):
    """Stop capturing video
    """

    json_resp = self._execute(cmd = "camera.stopCapture",
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)

    assert "state" in json_resp, \
		"malformed JSON response: missing state"
    json_resp_state = json_resp["state"]
    assert json_resp_state == "done", \
		'command returned state "{}"'.format(json_resp_state)

    return json_resp



  def take_photo(self,
			wait_photo_taken = _default_max_wait_photo_taken,
			check_photo_taken_every = \
					_default_check_photo_taken_every,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_request_timeout):
    """Trigger taking a photo
    If wait_photo_taken > 0, wait until the photo is taken for that number of
    seconds at the most.
    If the network connection is very bad or the camera is unstable, try
    increasing the value of check_photo_taken_every to poll less often.
    """

    # Sanity-check the arguments
    assert type(wait_photo_taken) in (int, float), \
		"wait_photo_take required and should be an int or float"
    assert wait_photo_taken >= 0, \
		"wait_photo_take should be >= 0"
    assert type(check_photo_taken_every) in (int, float), \
		"check_photo_taken_every required and should be an int or float"
    assert check_photo_taken_every > 0, \
		"check_photo_taken_every should be >= 0"

    # Trigger the shot
    json_resp = self._execute(cmd = "camera.takePicture",
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)

    assert "state" in json_resp, \
		"malformed JSON response: missing state"
    state = json_resp["state"]

    if wait_photo_taken > 0:

      now = time()
      start_wait_tstamp = now
      stop_wait_tstamp = start_wait_tstamp + wait_photo_taken
      polls_count = 0

      # As long as the command is in progress, or we should keep waitinga for
      # the photo to be taken, poll the status of the command
      while state == "inProgress" and now < stop_wait_tstamp:

        # Wait before polling if needed
        polls_count += 1
        next_poll_tstamp = start_wait_tstamp + \
				check_photo_taken_every * polls_count
        wait_for = next_poll_tstamp - now

        if wait_for > 0:
          sleep(wait_for)

        # Poll the status of the command
        json_resp = \
		self.get_command_status(connect_timeout = connect_timeout,
					reconnect_tries = \
						_default_reconnect_tries,
					read_timeout = read_timeout)

        assert "state" in json_resp, \
		"malformed JSON response: missing state"
        state = json_resp["state"]

        now = time()

      if now >= stop_wait_tstamp and state != "done":
        raise TimeoutError("timeout waiting for photo to be taken")

      assert state == "done", \
		'command returned state "{}"'.format(state)

    return json_resp



  def get_storage_info(self,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_file_operations_timeout):
    """Get the total storage space and remaining space
    """

    json_resp = self._get_options({"totalSpace", "remainingSpace"},
					connect_timeout = connect_timeout,
					reconnect_tries = reconnect_tries,
					read_timeout = read_timeout)

    assert "totalSpace" in json_resp, \
		"malformed JSON response: missing totalSpace"
    assert "remainingSpace" in json_resp, \
		"malformed JSON response: missing remainingSpace"

    return {"total": json_resp["totalSpace"],
		"remaining": json_resp["remainingSpace"]}



  def get_file_list(self,
			filetype = "all",
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_file_operations_timeout):
    """List all files of file_type "all", "image" or "video"
    """

    # Sanity-check the arguments
    assert filetype in ("all", "image", "video"), \
		'filetype should be "all", "image" or "video"'

    json_resp = self._execute(cmd = "camera.listFiles",
				params = {
					"fileType": filetype,
					"entryCount": 9999999,
					"maxThumbSize": 0},
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)

    assert "state" in json_resp, \
		"malformed JSON response: missing state"
    json_resp_state = json_resp["state"]
    assert json_resp_state == "done", \
		'command returned state "{}"'.format(json_resp_state)

    assert "results" in json_resp, \
		"malformed JSON response: missing results"
    json_resp_results = json_resp["results"]

    assert "entries" in json_resp_results, \
		"malformed JSON response: missing entries in the results"
    json_resp_results_entries = json_resp_results["entries"]

    assert isinstance(json_resp_results_entries, list), \
		"malformed JSON response: entries in the results is not a list"

    assert "totalEntries" in json_resp_results, \
		"malformed JSON response: missing totalEntries in the results"
    json_resp_results_total_entries = json_resp_results["totalEntries"]

    assert len(json_resp_results_entries) == json_resp_results_total_entries, \
		"malformed JSON response: totalEntries doesn't match length " \
		"of entries in the results"

    assert all("fileUrl" in entry for entry in json_resp_results_entries), \
		"malformed JSON response: missing fileUrl in entry in the " \
		"results"

    file_urls = {entry["fileUrl"] for entry in json_resp_results_entries}
    assert all(self.__file_url_regex.match(url) for url in file_urls), \
		"malformed JSON response: fileUrl in entry in the results " \
		"doesn't match the Theta URL pattern"

    return json_resp_results_entries



  def get_last_file(self,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_file_operations_timeout):
    """Get the URL the last photo or video taken
    """

    # Get the URL of the last file created
    json_resp = self.get_state(connect_timeout = connect_timeout,
				reconnect_tries = _default_reconnect_tries,
				read_timeout = read_timeout)

    assert "_latestFileUrl" in json_resp, \
		"malformed JSON response: missing _latestFileUrl"
    last_file_url = json_resp["_latestFileUrl"]

    assert isinstance(last_file_url, str), \
		"malformed JSON response: _latestFileUrl is not a string"

    assert last_file_url != "", \
		"malformed JSON response: _latestFileUrl is an empty string"

    return last_file_url



  def delete_files(self,
			file_urls,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_file_operations_timeout):
    """Delete a set of files
    If file_urls is {"all"}, delete all files
    """

    # Sanity-check the arguments
    assert isinstance(file_urls, set) and file_urls, \
		"file_urls should be a non-empty set of non-empty string"
    assert all(isinstance(url, str) and url != "" for url in file_urls), \
		"file_urls should be a non-empty set of non-empty string"
    if file_urls != {"all"}:
      assert all(self.__file_url_regex.match(url) for url in file_urls), \
		"URL doesn't match the Theta URL pattern"

    json_resp = self._execute(cmd = "camera.delete",
				params = {
					"fileUrls": list(file_urls)},
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)

    assert "state" in json_resp, \
		"malformed JSON response: missing state"
    json_resp_state = json_resp["state"]
    assert json_resp_state == "done", \
		'command returned state "{}"'.format(json_resp_state)

    return json_resp



  def delete_file(self,
			file_url,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_file_operations_timeout):
    """Delete one file
    """

    # Sanity-check the arguments
    assert isinstance(file_url, str) and file_url != "", \
		"file_url required and should be a string"
    assert self.__file_url_regex.match(file_url), \
		"URL doesn't match the Theta URL pattern"

    return self.delete_files({file_url},
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)



  def delete_last_file(self,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_file_operations_timeout):
    """Delete the last photo or video taken
    """

    # Get the URL of the last file created
    last_file_url = self.get_last_file(connect_timeout = connect_timeout,
					reconnect_tries = reconnect_tries,
					read_timeout = read_timeout)

    return self.delete_file(last_file_url,
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)



  def get_file_metadata(self,
			file_url,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_request_timeout):
    """Get a file's metadata
    """

    # Sanity-check the arguments
    assert isinstance(file_url, str) and file_url != "", \
		"file_url required and should be a string"
    assert self.__file_url_regex.match(file_url), \
		"URL doesn't match the Theta URL pattern"

    json_resp = self._execute(cmd = "camera._getMetadata",
				params = {
					"fileUrl": file_url},
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)

    assert "state" in json_resp, \
		"malformed JSON response: missing state"
    json_resp_state = json_resp["state"]
    assert json_resp_state == "done", \
		'command returned state "{}"'.format(json_resp_state)

    assert "results" in json_resp, \
		"malformed JSON response: missing results"
    json_resp_results = json_resp["results"]

    assert "exif" in json_resp_results, \
		"malformed JSON response: missing exif in results"

    assert isinstance(json_resp_results["exif"], dict), \
		"malformed JSON response: exif in results is not a dict"

    assert "xmp" in json_resp_results, \
		"malformed JSON response: missing xmp in results"

    assert isinstance(json_resp_results["xmp"], dict), \
		"malformed JSON response: xmp in results is not a dict"

    return json_resp_results



  def download_file(self,
			file_url,
			save_dir = ".",
			save_fname = "",
			fix_timestamp = True,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_file_operations_timeout):
    """Download a file from the camera
    Save to <save_dir>/<save_fname> then fix up the file's timstamp from the
    EXIF data if fix_timestamp is asserted
    If save_fname == "", reuse the name of the file in the camera
    """

    # Sanity-check the arguments
    assert isinstance(file_url, str) and file_url != "", \
		"file_url required and should be a string"
    assert self.__file_url_regex.match(file_url), \
		"URL doesn't match the Theta URL pattern"
    assert isinstance(save_dir, str), \
		"save_dir is required and should be a string"
    assert isinstance(save_fname, str), \
		"save_fname is required and should be a string"

    # If the save filename is unsecified, use the one from the camera
    if not save_fname:
      save_fname = self.__file_url_regex.match(file_url)[4]

    fpath = os.path.join(save_dir, save_fname)

    # Stream download to avoid large memory usage
    resp = None
    try:
      resp = self._request(url = file_url,
				stream = True,
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)

      # Open the desination file for writing
      with open(fpath, "wb") as f:

        # Download chunks and write them to the file
        for chunk in resp.iter_content(chunk_size = 8192):
          if chunk:	# filter out keepalive chunks
            f.write(chunk)

    finally:
      # Close the connection if it was open
      if resp is not None:
        resp.close()

    # Should we fix the file's timestamp?
    if fix_timestamp:

      # Is the file an image?
      if file_url.endswith(".JPG"):

        datetime_regex = re.compile(r"^([0-9]{4}):([0-9]{2}):([0-9]{2})\s" \
					r"([0-9]{2}):([0-9]{2}):([0-9]{2})$")

        # Read the image's EXIF tags we need
        with exiftool.ExifToolHelper() as et:
          metadata = et.get_tags(fpath, tags = ["EXIF:DateTimeOriginal",
						"EXIF:OffsetTimeOriginal"]
					)[0]

        exif_datetime = metadata.get("EXIF:DateTimeOriginal")
        exif_tz_offset = metadata.get("EXIF:OffsetTimeOriginal")

        # Generate the date / time + timezone offset in ISO format
        m = datetime_regex.match(exif_datetime)
        exif_datetime_iso = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}{}".\
				format(int(m[1]), int(m[2]), int(m[3]),
					int(m[4]), int(m[5]), int(m[6]),
					exif_tz_offset)

      elif file_url.endswith(".MP4"):

        datetime_tz_regex = re.compile(r"^([0-9]{4}):([0-9]{2}):([0-9]{2})\s" \
					r"([0-9]{2}):([0-9]{2}):([0-9]{2})" \
					"([+-][0-9]{1,2}:[0-9]{2})$")

        # Read the image's EXIF tags we need
        with exiftool.ExifToolHelper() as et:
          metadata = et.get_tags(fpath, tags = ["QuickTime:ContentCreateDate"]
					)[0]

        exif_datetime_tz = metadata.get("QuickTime:ContentCreateDate")

        # Generate the date / time + timezone offset in ISO format
        m = datetime_tz_regex.match(exif_datetime_tz)
        exif_datetime_iso = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}{}".\
				format(int(m[1]), int(m[2]), int(m[3]),
					int(m[4]), int(m[5]), int(m[6]),
					m[7])

      # Convert the ISO date / time + timezone offset to a native datetime
      exif_datetime = datetime.fromisoformat(exif_datetime_iso)

      # Modify the file's access and modification timestamps
      os.utime(fpath, (exif_datetime.timestamp(), exif_datetime.timestamp()))



  def download_files(self,
			file_urls,
			save_dir = ".",
			fix_timestamp = True,
			connect_timeout = _default_connect_timeout,
			reconnect_tries = _default_reconnect_tries,
			read_timeout = _default_file_operations_timeout):
    """Download a set of files
    If file_urls is {"all"}, download all files
    If file_urls is {"all_images"}, download all image files
    If file_urls is {"all_videos"}, download all video files
    Save to <save_dir>/ then fix up the files' timstamps from the EXIF data if
    fix_timestamp is asserted
    """

    # Sanity-check the arguments
    assert isinstance(file_urls, set) and file_urls, \
		"file_urls should be a non-empty set of non-empty string"
    assert all(isinstance(url, str) and url != "" for url in file_urls), \
		"file_urls should be a non-empty set of non-empty string"
    if file_urls not in ({"all"}, {"all_images"}, {"all_videos"}):
      assert all(self.__file_url_regex.match(url) for url in file_urls), \
		"URL doesn't match the Theta URL pattern"

    if file_urls == {"all"}:
      all_filetype = "all"

    elif file_urls == {"all_images"}:
      all_filetype = "image"

    elif file_urls == {"all_videos"}:
      all_filetype = "video"

    else:
      all_filetype = None

    # Should we download all the files?
    if all_filetype:

      # Get the complete list of relevant file URLs
      entries = self.get_file_list(filetype = all_filetype,
					connect_timeout = connect_timeout,
					reconnect_tries = reconnect_tries,
					read_timeout = read_timeout)

      file_urls = {entry["fileUrl"] for entry in entries}

    # Download all the files
    for file_url in file_urls:
      self.download_file(file_url = file_url,
				save_dir = save_dir,
				fix_timestamp = fix_timestamp,
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)



  def download_last_file(self,
				connect_timeout = _default_connect_timeout,
				reconnect_tries = _default_reconnect_tries,
				read_timeout = \
					_default_file_operations_timeout):
    """Download the last photo or video taken
    """

    # Get the URL of the last file created
    last_file_url = self.get_last_file(connect_timeout = connect_timeout,
					reconnect_tries = \
						_default_reconnect_tries,
					read_timeout = read_timeout)

    return self.download_file(last_file_url,
				connect_timeout = connect_timeout,
				reconnect_tries = reconnect_tries,
				read_timeout = read_timeout)
