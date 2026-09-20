"""Rich Theta web API client class

   Default parameters
"""

### Parameters
_default_connect_timeout = 5 #s
_default_reconnect_tries = 1

_default_request_timeout = 5 #s
_default_stop_video_capture_timeout = 10 #s
_default_file_operations_timeout = 15 #s

_default_check_photo_taken_every = 1 #s
_default_max_wait_photo_taken = (60 + 10 + 5) #s
				# max shutter speed +
				# max timer duration +
				# max stitching time
_default_max_wait_rebooted = 60 #s

# By default, use mpv with the mpv360 extension for live preview
# https://github.com/kasper93/mpv360
_default_live_preview_viewer_command = "mpv --script-opts=mpv360-enabled=yes " \
					"--demuxer=lavf " \
					"--demuxer-lavf-format=mjpeg " \
					"--cache=no " \
					"--untimed " \
					"--video-sync=display-desync " \
					"--demuxer-lavf-o=fflags=+nobuffer " \
					"--demuxer-readahead-secs=0 " \
					"--demuxer-lavf-probesize=300000 " \
					"--demuxer-lavf-analyzeduration=0 " \
					"-"
