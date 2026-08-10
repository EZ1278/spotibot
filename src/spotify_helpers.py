
import base64
import json
from requests import post, get
import time
import pandas as pd
import functions as func

###################################################
# USER INFORMATION
#
#
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
    func.add_to_logs(f"[INFO] {result.status_code}")
    func.add_to_logs(f"{result.reason}")
    if(result.status_code != 200):
        return False

    json_result = json.loads(result.content)["access_token"]
    return json_result

#############################################################################
# PLAYLIST
#
#
#
#
#############################################################################
def add_to_playlist(playlist_id, client_id, client_secret, refresh_token, song_uris):
    token = refresh_user_token(client_id=client_id, client_secret=client_secret, refresh_token=refresh_token)
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    headers = {
        "Authorization": "Bearer "+token,
        "Content-Type": "application/json"
    }
    data = {
        "uris": song_uris
    }

    result = post(url=url, headers=headers, data=json.dumps(data))

    if(result.status_code != 201):
        response = f"Could not add to playlist\nError Code {result.status_code}"
        print(response)
        print(result.text)
        return False

    return True

def get_songs_in_playlist(env_dict, playlist_id):
    client_id = env_dict["spotify_id"]
    client_secret = env_dict["spotify_secret"]
    refresh_token = env_dict["spotify_user_refresh_token"]
    token = refresh_user_token(client_id=client_id, client_secret=client_secret, refresh_token=refresh_token)

    while token == False:
        print("Retrying to refresh token in 1 second")
        time.sleep(1)
        token = refresh_user_token(client_id=client_id, client_secret=client_secret, refresh_token=refresh_token)


    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"

    headers = {
        "Authorization": "Bearer "+token
    }

    result = get(url, headers=headers)
    json_result = json.loads(result.content)
    iteration = 0
    data = []

    while True:
        for item in json_result['items']:
            iteration = iteration + 1
            data.append({
                'Track': item.get('track').get('name'),
                'Artist': item.get('track').get('artists')[0].get('name'),
                'Album': item.get('track').get('album').get('name'),
                'id': item.get('track').get('id'),
                'added_by': item.get('added_by').get('id')
            })

        if json_result['next'] == None:
            break

        result = get(json_result['next'], headers=headers)
        json_result = json.loads(result.content)

    df = pd.DataFrame(data)
    return df

def get_playlist(env_dict, playlist_id):
    client_id = env_dict["spotify_id"]
    client_secret = env_dict["spotify_secret"]
    refresh_token = env_dict["spotify_user_refresh_token"]
    token = refresh_user_token(client_id=client_id, client_secret=client_secret, refresh_token=refresh_token)

    url = f'https://api.spotify.com/v1/playlists/{playlist_id}'
    headers = {
        "Authorization": f"Bearer {token}"
    }

    result = get(url, headers=headers)
    json_result = json.loads(result.content)
    return json_result



#############################################################################
# SPOTIFY SEARCH
#
#
#
#
#############################################################################
def search_spotify_song(env_dict, track, artist=None, offset=0):
    client_id = env_dict["spotify_id"]
    client_secret = env_dict["spotify_secret"]
    refresh_token = env_dict["spotify_user_refresh_token"]
    token = refresh_user_token(client_id=client_id, client_secret=client_secret, refresh_token=refresh_token)

    while token == False:
        print("Retrying to refresh token in 1 second")
        time.sleep(1)
        token = refresh_user_token(client_id=client_id, client_secret=client_secret, refresh_token=refresh_token)


    query = f"track:{track} "

    if artist:
        query += f"artist:{artist}"
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
    # try a search of just the song title if nothing could be found
    if len(json_result['tracks']['items']) == 0 and artist:
        return search_spotify_song(env_dict, track)
    elif len(json_result['tracks']['items']) == 0:
        return False

    return json_result['tracks']['items'][0]['id']

def get_song_url(env_dict, song_id):
    client_id = env_dict["spotify_id"]
    client_secret = env_dict["spotify_secret"]
    refresh_token = env_dict["spotify_user_refresh_token"]
    token = refresh_user_token(client_id=client_id, client_secret=client_secret, refresh_token=refresh_token)
    print('successfully refreshed token')

    url = f'https://api.spotify.com/v1/tracks/{song_id}'
    headers = {
        "Authorization": f"Bearer {token}"
    }

    result = get(url, headers=headers)
    print(result)
    json_result = json.loads(result.content)
    print('successfully found url')
    print(json_result['external_urls']['spotify'])
    return json_result['external_urls']['spotify']
