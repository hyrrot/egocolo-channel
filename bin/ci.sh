if [[ "$1" == "test" ]]; then
    BLACK_OPTION="--check"
else
    BLACK_OPTION=""
fi
poetry run black ${BLACK_OPTION} $(dirname $0)/../script