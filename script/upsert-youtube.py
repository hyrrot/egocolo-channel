#!/usr/bin/python

import argparse
import http.client
import httplib2
import os
import random
import time

import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow

from ruamel.yaml import YAML
import sys
import json

PROJECT_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Explicitly tell the underlying HTTP transport library not to retry, since
# we are handling retry logic ourselves.
httplib2.RETRIES = 1

# Maximum number of times to retry before giving up.
MAX_RETRIES = 10

# Always retry when these exceptions are raised.
RETRIABLE_EXCEPTIONS = (
    httplib2.HttpLib2Error,
    IOError,
    http.client.NotConnected,
    http.client.IncompleteRead,
    http.client.ImproperConnectionState,
    http.client.CannotSendRequest,
    http.client.CannotSendHeader,
    http.client.ResponseNotReady,
    http.client.BadStatusLine,
)

# Always retry when an apiclient.errors.HttpError with one of these status
# codes is raised.
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

# The CLIENT_SECRETS_FILE variable specifies the name of a file that contains
# the OAuth 2.0 information for this application, including its client_id and
# client_secret. You can acquire an OAuth 2.0 client ID and client secret from
# the {{ Google Cloud Console }} at
# {{ https://cloud.google.com/console }}.
# Please ensure that you have enabled the YouTube Data API for your project.
# For more information about using OAuth2 to access the YouTube Data API, see:
#   https://developers.google.com/youtube/v3/guides/authentication
# For more information about the client_secrets.json file format, see:
#   https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
CLIENT_SECRETS_FILE = os.environ["CLIENT_SECRETS_FILE"]

# This OAuth 2.0 access scope allows an application to upload files to the
# authenticated user's YouTube channel, but doesn't allow other types of access.
SCOPES = ["https://www.googleapis.com/auth/youtube"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"

VALID_PRIVACY_STATUSES = ("public", "private", "unlisted")

yaml = YAML()

# Authorize the request and store authorization credentials.
def get_authenticated_service():
    credentials_file = os.environ["CREDENTIALS_FILE"]
    if os.path.exists(credentials_file):
        print(f"Reading {credentials_file} for cached creds")
        with open(credentials_file, "r") as f:
            json_creds = json.load(f)
            credentials = google.oauth2.credentials.Credentials(
                json_creds["token"],
                refresh_token=json_creds["refresh_token"],
                token_uri=json_creds["token_uri"],
                client_id=json_creds["client_id"],
                client_secret=json_creds["client_secret"],
                scopes=json_creds["scopes"],
            )
            print(f"Try accessing to YouTube API with the cached cred")
            youtube = build(API_SERVICE_NAME, API_VERSION, credentials=credentials)
            try:
                youtube.videos().list(part="snippet", chart="mostPopular").execute()
                print(f"Accessed video search API successfully, using the cred")
                return youtube
            except Exception as e:
                print(e)
                print(
                    f"Failed to access video search API, generating one from user flow"
                )
                os.remove(credentials_file)
                return get_authenticated_service()
    else:
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
        flow.run_console()
        credentials = flow.credentials
        with open(credentials_file, "w") as f:
            f.write(credentials.to_json())

    return build(API_SERVICE_NAME, API_VERSION, credentials=credentials)


def initialize_upload(youtube, options):

    body = options["metadata"]["video"]
    video_file_path = os.path.join(PROJECT_ROOT_DIR, options["file"])
    # Call the API's videos.insert method to create and upload the video.
    insert_request = youtube.videos().insert(
        part=",".join(list(body.keys())),
        body=body,
        # The chunksize parameter specifies the size of each chunk of data, in
        # bytes, that will be uploaded at a time. Set a higher value for
        # reliable connections as fewer chunks lead to faster uploads. Set a lower
        # value for better recovery on less reliable connections.
        #
        # Setting 'chunksize' equal to -1 in the code below means that the entire
        # file will be uploaded in a single HTTP request. (If the upload fails,
        # it will still be retried where it left off.) This is usually a best
        # practice, but if you're using Python older than 2.6 or if you're
        # running on App Engine, you should set the chunksize to something like
        # 1024 * 1024 (1 megabyte).
        media_body=MediaFileUpload(video_file_path, chunksize=-1, resumable=True),
    )

    return resumable_upload(insert_request)


# This method implements an exponential backoff strategy to resume a
# failed upload.
def resumable_upload(request):
    response = None
    error = None
    retry = 0
    while response is None:
        try:
            print("Uploading file...")
            status, response = request.next_chunk()
            if response is not None:
                if "id" in response:
                    print('Video id "%s" was successfully uploaded.' % response["id"])
                    return response
                else:
                    exit("The upload failed with an unexpected response: %s" % response)
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = "A retriable HTTP error %d occurred:\n%s" % (
                    e.resp.status,
                    e.content,
                )
            else:
                raise
        except RETRIABLE_EXCEPTIONS as e:
            error = "A retriable error occurred: %s" % e

        if error is not None:
            print(error)
            retry += 1
            if retry > MAX_RETRIES:
                exit("No longer attempting to retry.")

            max_sleep = 2**retry
            sleep_seconds = random.random() * max_sleep
            print("Sleeping %f seconds and then retrying..." % sleep_seconds)
            time.sleep(sleep_seconds)


def update_video(youtube, video_id, video_metadata):
    return (
        youtube.videos()
        .update(
            part="snippet",
            body=dict(id=video_id, snippet=video_metadata["video"]["snippet"]),
        )
        .execute()
    )


def read_author_config_yaml(author_config_yaml_filename):
    with open(author_config_yaml_filename, "r") as f:
        return yaml.load(f)


def write_author_config_yaml(author_config_yaml, author_config_yaml_filename):
    with open(author_config_yaml_filename, "w") as f:
        yaml.default_flow_style = False
        yaml.dump(author_config_yaml, f)


if __name__ == "__main__":
    author_config_yaml_filename = sys.argv[1]
    author_config_yaml = read_author_config_yaml(author_config_yaml_filename)
    youtube = get_authenticated_service()

    if author_config_yaml["id"] is None:
        try:
            response = initialize_upload(youtube, author_config_yaml)
        except HttpError as e:
            print("An HTTP error %d occurred:\n%s" % (e.resp.status, e.content))

        author_config_yaml["id"] = response["id"]
        write_author_config_yaml(author_config_yaml, author_config_yaml_filename)
    else:
        response = update_video(
            youtube, author_config_yaml["id"], author_config_yaml["metadata"]
        )
        print(response)
        print(f"Metadata of video {author_config_yaml['id']} was updated.")

    print(
        f"[YouTube Studio] https://studio.youtube.com/video/{author_config_yaml['id']}/edit"
    )
    print(f"[Video URL] https://youtu.be/{author_config_yaml['id']}")
