#!/bin/bash
# Transcode a single video into a directory containing a m3u8 playlist, fragmented MP4 media segments and init.mp4 header file, then set panoramic XMP tags in the header file
#
# Useful to split a large 360 video file into small streamable chunks

SRC=$1
DST=$2
SEGMENT_TYPE=$3

if [ ! "${SRC}" ] || [ ! "${DST}" ]; then
  echo "Usage: $0 <source video file> <destination directory> [mpegts|fmp4]"
  exit
fi

if [ ! "${SEGMENT_TYPE}" ]; then
  SEGMENT_TYPE="mpegts"
else
  if [ ${SEGMENT_TYPE} != "mpegts" ] && [ ${SEGMENT_TYPE} != "fmp4" ]; then
    echo 'Error: if the segment type is specified, it must be "mpegts" or "fmp4". Default: mpegts'
    exit
  fi
fi

# Determine the source video's nominal framerate
FPS_FRACTIONAL=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 ${SRC})
FPS=$(awk -v v=${FPS_FRACTIONAL} 'BEGIN { split(v,a,"/"); if (a[2]) printf "%.0f\n", a[1] / a[2]; else print a[1] }')

if [ ! "${FPS}" ]; then
  echo "Error: cannot determine source video's framerate"
  exit
fi

OUTFILE=${DST}/${DST}.m3u8

# Map the output video streams
VAR_STREAM_MAPPING="-var_stream_map v:0"

# If the video has audio, add it to ouput streams
if [ "$(ffprobe -v error -select_streams a ${SRC} -show_entries stream=index)" ]; then
  VAR_STREAM_MAPPING="${VAR_STREAM_MAPPING},a:0"
fi

# Does the video have subtitles?
if [ "$(ffprobe -v error -select_streams s ${SRC} -show_entries stream=index)" ]; then

  # Add the subtitles to the output streams
  VAR_STREAM_MAPPING="${VAR_STREAM_MAPPING},s:0,sgroup:subtitle"

  # If the video has MPEG-TS segments, rename the video proper so the master playlist has the name we want
  if [ ${SEGMENT_TYPE} == "mpegts" ]; then
    MASTER_PLAYLIST="-master_pl_name ${DST}.m3u8"
    OUTFILE=${DST}/video.m3u8
  fi
fi

# Transcode the video
let KEYINT_MIN=FPS*2

mkdir -p ${DST}
ffmpeg -i ${SRC} -c:v libx264 -crf 23 -b:v 0 -pix_fmt yuv420p -g ${KEYINT_MIN} -keyint_min ${KEYINT_MIN} -sc_threshold 0 -c:a aac -b:a 128k -start_number 0 -hls_time 10 -hls_list_size 0 -async 1 -hls_segment_type ${SEGMENT_TYPE} ${VAR_STREAM_MAPPING} ${MASTER_PLAYLIST} -muxdelay 0 -muxpreload 0 -f hls ${OUTFILE}

# Set the destination video's XMP tags in init.mp4 if the segment type is fragmented MP4 (fmp4)
if [ ${SEGMENT_TYPE} = "fmp4" ]; then
  printf '\x00\x00\x00\x08mdat' >> ${DST}/init.mp4
  exiftool -overwrite_original \
		-XMP-GPano:UsePanoramaViewer=true \
		-XMP-GPano:ProjectionType=equirectangular \
		-XMP-GPano:PoseHeadingDegrees=0.0 \
		-XMP-GPano:PosePitchDegrees=0.0 \
		-XMP-GPano:PoseRollDegrees=0.0 \
		-XMP-GPano:InitialViewHeadingDegrees=0.0 \
		-XMP-GPano:InitialViewPitchDegrees=0.0 \
		-XMP-GPano:InitialViewRollDegrees=0.0 \
		-XMP-GSpherical:Spherical=true \
		-XMP-GSpherical:Stitched=true \
		-XMP-GSpherical:ProjectionType=equirectangular \
		${DST}/init.mp4
  truncate -s -8 ${DST}/init.mp4
fi
