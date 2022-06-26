# egocolo-channel

Automated management script for [Egocolo Channel （絵心ちゃんねる）](https://www.youtube.com/channel/UCJHSKslmbic8IGMMp9F3FGA), Hyrrot's YouTube channel.

## Requirement
* author.sh
    * ffmpeg
* upsert-youtube.py
    * Software
        * Pyenv
        * Poetry
        * jq
    * GCP
        * Register "YouTube Data API v3" in Google Cloud Console, obtain OAuth 2.0 Client ID, and download client_secret.json

## Usage

```
pyenv install $(cat .python-version)
poetry install
export CLIENT_SECRETS_FILE=(path to client-secret.json)
export CREDENTIALS_FILE=/tmp/creds.json
poetry run script/upsert-youtube.py <path-to->
```

