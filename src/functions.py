from dotenv import load_dotenv
import os
import json
from datetime import datetime
from requests import get
import spotify_helpers as spot
import pandas as pd
import shutil

DATA_DEST = "/app/data"
SRC_DEST = "/app/src"


def get_data_dir():
    return DATA_DEST

def get_src_dir():
    return SRC_DEST

def is_integer(input_string):
    try:
        int(input_string)
        return True
    except ValueError:
        return False


def load_env_vars():
    load_dotenv(f"{get_src_dir()}/.env")

    env_dict = {
        "telegram_token": os.getenv("telegram_token"),
        "telegram_bot_username": os.getenv("telegram_bot_username"),
        "spotify_id": os.getenv("spotify_id"),
        "spotify_secret": os.getenv("spotify_secret"),
        "spotify_user_code": os.getenv("spotify_user_code"),
        "spotify_user_token": os.getenv("spotify_user_token"),
        "spotify_user_refresh_token": os.getenv("spotify_user_refresh_token"),
        "redirect_uri" : "http://127.0.0.1:5500",
        "youtube_token": os.getenv("youtube_token"),
        "chat_id": os.getenv("chat_id"),
        "thread_id":os.getenv("thread_id"),
        "admin_id":int(os.getenv("admin_id")),
        "current_ranking":os.getenv("current_ranking"),
        "open_poll_time":int(os.getenv("open_poll_time")),
        "open_poll_amount":int(os.getenv("open_poll_amount"))
    }

    return env_dict


def save_env(env_vars):
    with open(f"{get_src_dir()}/.env", "w") as f:
        for key, value in env_vars.items():
            if isinstance(value, list):
                value = json.dumps(value)
            f.write(f"{key}={value}\n")


def create_logs():
    file_name = f"{get_data_dir()}/output.log"

    with open(file_name, "w") as f:
        pass


def add_to_logs(text):
    file_name = f"{get_data_dir()}/output.log"
    if not os.path.exists(file_name):
        create_logs()

    with open(file_name, "a") as f:
        f.write("\n")
        f.write(f"Date: {datetime.now().date()}\n")
        f.write(text)
        f.write("\n")

def download_url(filename, url):
    try:
        response = get(url)
        with open(filename, 'wb') as f:
            f.write(response.content)
        add_to_logs(f"Downloaded to {filename}")
        return True
    except:
        add_to_logs(f"Download to {filename} failed")
        return False

def delete_file(filename):
    if os.path.exists(filename):
        os.remove(filename)
    else:
        add_to_logs(f"{filename} doesn't exist")


def select_matchup(database):
    current_round = database['current_round']
    current_ranking = database[f'round_{current_round}']['current_ranking']

    ids = [database[f'round_{current_round}']['matchups']['id'][current_ranking],
           database[f'round_{current_round}']['matchups']['id'][current_ranking+1]]

    return ids

def prev_power_of_two(value):
    return 2**(value.bit_length()-1)

def create_next_round(database):
    current_round = database['current_round']
    # Creating template for the next round, writing the previous rounds winners to the to the matchups #
    # of the next round #
    template = {f"round_{current_round+2}":{
        "songs_remaining": 0,
        "current_ranking": 0,
        "losers":{"tracks": [], "artists": [], "album": [], "id": [], "added_by": []},
        "winners":{"tracks": [], "artists": [], "album": [], "id": [], "added_by": []},
        "matchups":{"tracks": [], "artists": [], "album": [], "id": [], "added_by": []}
    }}

    # Write the template to the existing ranking #
    database.update(template)

    # Update the current round of the ranking #
    database['current_round']=database['current_round']+1
    save_choice(database=database)
    return database

def create_calibration_round(env_dict, playlist_id, playlist_name):

    # Get Data from the playlist that the user selected #
    print("Downloading spotify data")
    initial_data = spot.get_songs_in_playlist(env_dict=env_dict, playlist_id=playlist_id)
    print("Download complete")
    initial_data = initial_data.sort_values(by='Track')

    # Remove tracks without a valid ID #
    initial_data = initial_data[initial_data['id'].notna() & (initial_data['id'] != '')]
    # Remove duplicate tracks by the same artist #
    initial_data = initial_data.drop_duplicates(subset=["Track", "Artist"], keep='first')

    # Creating Calibration Round #
    offset_val = len(initial_data)-prev_power_of_two(len(initial_data))
    skip_amount = len(initial_data)-(2*offset_val)
    # Songs that get a first round bye #
    skip_db = initial_data.sample(n=skip_amount).sort_values(by="Track")
    # Songs that do not get a first round by #
    initial_data = initial_data[~initial_data['id'].isin(skip_db['id'])]
    # Create .json for new ranking #
    ranking_header = {
        "playlist_name": playlist_name,
        "current_round": 0,
    }
    round_0 = {"round_0":{
    "songs_remaining": len(initial_data),
    "current_ranking": 0,
    "losers": {"tracks":[],
            "artists":[],
            "album":[],
            "id":[],
            "added_by":[]},
    "winners": {"tracks":skip_db['Track'].tolist(),
            "artists":skip_db['Artist'].tolist(),
            "album":skip_db['Album'].tolist(),
            "id":skip_db['id'].tolist(),
            "added_by":skip_db['added_by'].tolist()},
    "matchups": {"tracks":initial_data['Track'].tolist(),
            "artists":initial_data['Artist'].tolist(),
            "album":initial_data['Album'].tolist(),
            "id":initial_data['id'].tolist(),
            "added_by":initial_data['added_by'].tolist()}
    }}
    round_1 = {"round_1":{
    "songs_remaining": len(skip_db),
    "current_ranking": 0,
    "losers": {"tracks":[],
            "artists":[],
            "album":[],
            "id":[],
            "added_by":[]},
    "winners": {"tracks":[],
            "artists":[],
            "album":[],
            "id":[],
            "added_by":[]},
    "matchups": {"tracks":skip_db['Track'].tolist(),
            "artists":skip_db['Artist'].tolist(),
            "album":skip_db['Album'].tolist(),
            "id":skip_db['id'].tolist(),
            "added_by":skip_db['added_by'].tolist()}
    }}
    ranking_header.update(round_0)
    ranking_header.update(round_1)
    save_choice(database=ranking_header)
    return ranking_header

def save_choice(database):
    filepath = f"{get_data_dir()}/rankings/{database['playlist_name']}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(database, f, indent=2)

def check_ranking(playlist_name):
    if os.path.exists(f"{get_data_dir()}/rankings/{playlist_name}.json"):
        return True
    return False

def read_ranking_user_input(input, database):
    current_round = database['current_round']
    current_ranking = int(database[f'round_{current_round}']['current_ranking'])
    matchups = []
    for i in range(2):
        matchups.append(database[f'round_{current_round}']['matchups']['id'][current_ranking+i])

    round_data = database[f'round_{current_round}']
    matchups = round_data['matchups']

    # Check if user input is an integer
    if not is_integer(input):
        return 'restart'

    # Check if user input is a valid option #
    if int(input) not in [1, 2]:
        return 'restart'

    winner_index = 0 if int(input) == 1 else 1
    loser_index = 1 - winner_index

    fields = ['tracks', 'artists', 'album', 'id', 'added_by']

    round_data = database[f'round_{current_round}']
    matchups = round_data['matchups']

    for field in fields:
        round_data['winners'][field].append(matchups[field][winner_index+round_data['current_ranking']])

    for field in fields:
        round_data['losers'][field].append(matchups[field][loser_index+round_data['current_ranking']])

    round_data['current_ranking'] += 2
    round_data["songs_remaining"] -= 2

    database[f'round_{current_round}']=round_data

    save_choice(database=database)
    return database

def has_folders(directory_path):
    try:
        items = os.listdir(directory_path)
        for item in items:
            if os.path.isdir(os.path.join(directory_path, item)):
                return True
        return False
    except OSError:
        return False

def open_ranking(playlist_name):
    filepath = f'{get_data_dir()}/rankings/{playlist_name}.json'
    if not os.path.exists(filepath):
        return False

    with open(filepath, 'r') as file:
        data_dict = json.load(file)
    return data_dict

def save_poll_id(poll_id):
    filepath = f"{get_data_dir()}/rankings/open_polls.json"
    if not os.path.exists(filepath):
        open_polls=poll_id

    else:
        with open(filepath, 'r') as file:
            open_polls = json.load(file)
        open_polls.update(poll_id)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(open_polls, f, indent=2)

def get_open_polls():
    filepath = f"{get_data_dir()}/rankings/open_polls.json"
    if not os.path.exists(filepath):
        return False
    with open(filepath, 'r') as file:
        open_polls = json.load(file)

    return open_polls

def delete_poll_id(open_polls):
    filepath = f"{get_data_dir()}/rankings/open_polls.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(open_polls, f, indent=2)

def write_results(winner_id, loser_id, env_dict, current_round):
    ranking_data = open_ranking(env_dict['current_ranking'])
    winner_index = ranking_data[f'round_{current_round}']['matchups']['id'].index(winner_id)
    loser_index = ranking_data[f'round_{current_round}']['matchups']['id'].index(loser_id)

    # Write to current round winners #
    ranking_data[f'round_{current_round}']['winners']['tracks'].append(ranking_data[f'round_{current_round}']['matchups']['tracks'][winner_index])
    ranking_data[f'round_{current_round}']['winners']['artists'].append(ranking_data[f'round_{current_round}']['matchups']['artists'][winner_index])
    ranking_data[f'round_{current_round}']['winners']['album'].append(ranking_data[f'round_{current_round}']['matchups']['album'][winner_index])
    ranking_data[f'round_{current_round}']['winners']['id'].append(ranking_data[f'round_{current_round}']['matchups']['id'][winner_index])
    ranking_data[f'round_{current_round}']['winners']['added_by'].append(ranking_data[f'round_{current_round}']['matchups']['added_by'][winner_index])

    # write to next round matchups #
    ranking_data[f'round_{current_round+1}']['matchups']['tracks'].append(ranking_data[f'round_{current_round}']['matchups']['tracks'][winner_index])
    ranking_data[f'round_{current_round+1}']['matchups']['artists'].append(ranking_data[f'round_{current_round}']['matchups']['artists'][winner_index])
    ranking_data[f'round_{current_round+1}']['matchups']['album'].append(ranking_data[f'round_{current_round}']['matchups']['album'][winner_index])
    ranking_data[f'round_{current_round+1}']['matchups']['id'].append(ranking_data[f'round_{current_round}']['matchups']['id'][winner_index])
    ranking_data[f'round_{current_round+1}']['matchups']['added_by'].append(ranking_data[f'round_{current_round}']['matchups']['added_by'][winner_index])
    ranking_data[f'round_{current_round+1}']['songs_remaining'] += 1

    # Write Loser #
    ranking_data[f'round_{current_round}']['losers']['tracks'].append(ranking_data[f'round_{current_round}']['matchups']['tracks'][loser_index])
    ranking_data[f'round_{current_round}']['losers']['artists'].append(ranking_data[f'round_{current_round}']['matchups']['artists'][loser_index])
    ranking_data[f'round_{current_round}']['losers']['album'].append(ranking_data[f'round_{current_round}']['matchups']['album'][loser_index])
    ranking_data[f'round_{current_round}']['losers']['id'].append(ranking_data[f'round_{current_round}']['matchups']['id'][loser_index])
    ranking_data[f'round_{current_round}']['losers']['added_by'].append(ranking_data[f'round_{current_round}']['matchups']['added_by'][loser_index])

    save_choice(ranking_data)
