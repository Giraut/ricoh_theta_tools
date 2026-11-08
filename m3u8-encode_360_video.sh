#!/bin/bash
# Transcode a single video into a directory containing a m3u8 playlist, fragmented MP4 media segments and init.mp4 header file, then set panoramic XMP tags in the header file
#
# Useful to split a large 360 video file into small streamable chunks

SRC=$1
DST=$2

if [ ! "${SRC}" ] || [ ! "${DST}" ]; then
  echo "Usage: $0 <source video file> <destination directory>"
  exit
fi

# Determine the source video's nominal framerate
FPS_FRACTIONAL=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 ${SRC})
FPS=$(awk -v v=${FPS_FRACTIONAL} 'BEGIN { split(v,a,"/"); if (a[2]) printf "%.0f\n", a[1] / a[2]; else print a[1] }')

if [ ! "${FPS}" ]; then
  echo "Error: cannot determine source video's framerate"
  exit
fi

# Transcode the video
let KEYINT_MIN=FPS*2

mkdir -p ${DST}

ffmpeg -i ${SRC} -c:v libx264 -crf 23 -b:v 0 -pix_fmt yuv420p -g ${KEYINT_MIN} -keyint_min ${KEYINT_MIN} -sc_threshold 0 -c:a aac -b:a 128k -start_number 0 -hls_time 10 -hls_list_size 0 -async 1 -hls_segment_type fmp4 -f hls ${DST}/${DST}.m3u8

# Set the destination video's XMP tags in init.mp4
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
