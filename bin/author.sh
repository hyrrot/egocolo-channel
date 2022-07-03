#!/bin/bash -x
set -ue
set -o pipefail
FFMPEG=ffmpeg
FFPROBE=ffprobe
JQ=jq
BC=bc


PROJ_DIR=$(dirname $0)/..
SRC_DIR=${PROJ_DIR}/src
SRC_VIDEO_DIR=${SRC_DIR}/videos
SRC_SOUND_DIR=${SRC_DIR}/sounds
BUILD_DIR=${PROJ_DIR}/build

SOUND_FILE="${SRC_SOUND_DIR}/日曜の午後_loop.wav"

VIDEO_NAME=$1
VIDEO_FILE=${SRC_VIDEO_DIR}/${VIDEO_NAME}


# Get duration
VIDEO_DURATION=$($FFPROBE -v quiet -show_format -print_format json ${VIDEO_FILE}.mov | $JQ -r '.format.duration')
SOUND_DURATION=$($FFPROBE -v quiet -show_format -print_format json ${SOUND_FILE} | $JQ -r '.format.duration')

VIDEO_SPEED_UP=$(echo "scale=5; $SOUND_DURATION / $VIDEO_DURATION" | $BC)

# Change speed of video
INTERMEDIATE_FILE_1=${BUILD_DIR}/${VIDEO_NAME}.intermediate.mov

ffmpeg -i ${VIDEO_FILE}.mov \
-filter:v "setpts=${VIDEO_SPEED_UP}*PTS" \
${INTERMEDIATE_FILE_1}

INTERMEDIATE_FILE_2=${BUILD_DIR}/${VIDEO_NAME}.intermediate.2.mov

ffmpeg -i ${INTERMEDIATE_FILE_1} -i ${SOUND_FILE} -c copy -shortest ${INTERMEDIATE_FILE_2}


# https://trac.ffmpeg.org/wiki/Encode/YouTube
# Try upscaling with "-vf scale=iw*2:ih*2:flags=neighbor" option
ffmpeg -i ${INTERMEDIATE_FILE_2} \
-movflags +faststart \
-vf scale=iw*2:ih*2:flags=neighbor \
-c:v libx264 \
-profile:v high \
-level:v 4.0 \
-b_strategy 2 \
-bf 2 \
-flags cgop \
-coder ac \
-pix_fmt \
yuv420p -crf 23 -maxrate 5M -bufsize 10M -c:a aac -ac 2 -ar 48000 -b:a 384k ${BUILD_DIR}/${VIDEO_NAME}.mp4


rm ${INTERMEDIATE_FILE_1}
rm ${INTERMEDIATE_FILE_2}
