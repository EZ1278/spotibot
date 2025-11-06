from dotenv import load_dotenv
import os
import json
from datetime import datetime
from requests import get

DATA_DEST = "/app/data"
SRC_DEST = "/app/src"


def get_data_filepath():
    return DATA_DEST


def get_source_filepath():
    return SRC_DEST

def is_integer(input_string):
    try:
        int(input_string)
        return True
    except ValueError:
        return False


def load_env_vars():
    load_dotenv(f"{get_source_filepath()}/.env")

    env_dict = {
        "telegram_token": os.getenv("telegram_token"),
        "telegram_bot_username": os.getenv("telegram_bot_username"),
        "spotify_id": os.getenv("spotify_id"),
        "spotify_secret": os.getenv("spotify_secret"),
        "spotify_user_code": os.getenv("spotify_user_code"),
        "spotify_user_token": os.getenv("spotify_user_token"),
        "spotify_user_refresh_token": os.getenv("spotify_user_refresh_token"),
        "youtube_token": os.getenv("youtube_token")
    }

    return env_dict


def save_env(env_vars):
    with open(f"{get_source_filepath()}/.env", "w") as f:
        for key, value in env_vars.items():
            if isinstance(value, list):
                value = json.dumps(value)
            f.write(f"{key}={value}\n")


def create_logs():
    file_name = f"{get_data_filepath()}/output.log"

    with open(file_name, "w") as f:
        pass


def add_to_logs(text):
    file_name = f"{get_data_filepath()}/output.log"
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
