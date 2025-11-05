
import base64
import json
from requests import post, get
import re
import functions as func

###################################################
# USER INFORMATION
###################################################
def refresh_user_token(client_id, client_secret, refresh_token):
    auth_string = client_id +":"+client_secret
    auth_bytes = auth_string.encode("utf-8")
    auth_base64 = str(base64.b64encode(auth_bytes), "utf-8")

    url = "https://accounts.spotify.com/api/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": "Basic "+auth_base64,
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }

    result = post(url, headers=headers, data=data)
    if(result.status_code != 200):
        response = f"Could not refresh token\nError Code: {result.status_code}"
        func.add_to_logs(f"{response}+\n+{result.reason}\n{result.text}")
        return False

    json_result = json.loads(result.content)["access_token"]

    return json_result

#############################################################################
# SEARCH
#############################################################################

def parse_spotify_track_url(url):
    # Pattern to extract only tracks
    pattern = r'https?://open\.spotify\.com/track/([a-zA-Z0-9]+)'

    # Use re.search() instead of re.match() to find it anywhere in the string
    match = re.search(pattern, url)

    if match:
        return {
            'valid': True,
            'type': 'track',
            'id': match.group(1),  # group(1) is the captured track ID
            'full_url': match.group(0)  # group(0) is the entire matched URL
        }
    return {'valid': False}

def get_song_preview(env_dict, song_id):

    # Search Spotify for a preview url #
    client_id = env_dict["spotify_id"]
    client_secret = env_dict["spotify_secret"]
    refresh_token = env_dict["spotify_user_refresh_token"]
    token = refresh_user_token(client_id=client_id, client_secret=client_secret, refresh_token=refresh_token)

    url = f"https://api.spotify.com/v1/tracks/{song_id}"
    headers = {
        "Authorization": "Bearer "+token
    }

    result = get(url, headers=headers)
    if(result.status_code != 200):
        response = f"Could not find song\nError Code {result.status_code}"
        func.add_to_logs(response)
        return None

    track = json.loads(result.content)
    artist = track['artists'][0]['name']
    if track['preview_url'] is not None:
        return {
            'name': track['name'],
            'artist': artist,
            'preview_url': track['preview_url']
        }

    song_isrc = track['external_ids']['isrc']

    # Search Apple Music for a preview url #
    url = "https://itunes.apple.com/search"
    params = {
        "term": song_isrc,
        "entity": "song",
        "limit": 1
    }

    response = get(url, params=params)
    data = response.json()

    if data['resultCount'] > 0:
        track = data['results'][0]
        return {
            'name': track['trackName'],
            'artist': artist,
            'preview_url': track.get('previewUrl')
        }

    # Search Music Brainz for a preview url #
    url = f"https://api.deezer.com/track/isrc:{song_isrc}"
    try:
        response = get(url)
        data = response.json()

        if 'id' in data and 'preview' in data:
            return {
                'name': data['title'],
                'artist': artist,
                'preview_url': data['preview']
            }
    except:
        pass

    return None
