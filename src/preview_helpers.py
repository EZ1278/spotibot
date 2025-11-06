
import base64
import json
from requests import post, get
import time
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

def parse_track_url(env_dict, url):
    # Pattern to extract only tracks
    spotify_pattern = r'https?://open\.spotify\.com/track/([a-zA-Z0-9]+)'
    youtube_pattern = r'(?:youtube\.com\/(?:watch\?v=|embed\/|v\/|shorts\/)|youtu\.be\/|music\.youtube\.com\/watch\?v=)([a-zA-Z0-9_-]{11})'


    # Use re.search() instead of re.match() to find it anywhere in the string
    spotify_match = re.search(spotify_pattern, url)
    youtube_match = re.search(youtube_pattern, url)

    if spotify_match:
        return {
            'valid': True,
            'type': 'spotify',
            'id': spotify_match.group(1)  # group(1) is the captured track ID
        }
    elif youtube_match:
        return {
            'valid': True,
            'type': 'youtube',
            'id': convert_youtube_to_spotify(env_dict, youtube_match.group(1))  # group(1) is the captured track ID
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

def search_spotify_song(env_dict, track, artist, offset=0):
    client_id = env_dict["spotify_id"]
    client_secret = env_dict["spotify_secret"]
    refresh_token = env_dict["spotify_user_refresh_token"]
    token = refresh_user_token(client_id=client_id, client_secret=client_secret, refresh_token=refresh_token)

    while token == False:
        print("Retrying to refresh token in 1 second")
        time.sleep(1)
        token = refresh_user_token(client_id=client_id, client_secret=client_secret, refresh_token=refresh_token)


    query = f"track:{track} artist:{artist}"
    url = "https://api.spotify.com/v1/search"
    params = {
        'q':query,
        'type': 'track',
        'limit':1
    }
    headers = {
        "Authorization": "Bearer "+token
    }

    result = get(url=url, params=params, headers=headers)
    if(result.status_code != 200):
        response = f"Could not find track: Error Code {result.status_code}"
        print(response)
        return 0

    json_result = json.loads(result.content)
    return json_result['tracks']['items'][0]['id']

def parse_youtube_title(title, channel_title):
    # Clean the title
    title = title.replace("(Official Video)", "")
    title = title.replace("(Official Music Video)", "")
    title = title.replace("[Official Video]", "")
    title = title.strip()

    # Clean the artist/channel name
    artist = channel_title.replace(" - Topic", "")
    artist = artist.replace("VEVO", "")
    artist = artist.strip()

    # If title has " - ", split it
    if " - " in title:
        parts = title.split(" - ", 1)
        # Use the split artist if it looks cleaner
        return parts[0].strip(), parts[1].strip()

    # Otherwise use channel name as artist
    return artist, title

def convert_youtube_to_spotify(env_dict, id):
    youtube_token = env_dict['youtube_token']
    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,recordingDetails&id={id}&key={youtube_token}"

    response = get(url=url)

    google_json = response.json()

    if 'items' in google_json and len(google_json['items']) > 0:
        video = google_json['items'][0]

        artist, track = parse_youtube_title(video['snippet']['title'], video['snippet']['channelTitle'])
        return search_spotify_song(env_dict, track, artist)

    print(json.dumps(google_json, indent=2))
