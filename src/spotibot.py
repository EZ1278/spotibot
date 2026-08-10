from shutil import Error
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, PollHandler
import preview_helpers as prev
import functions as func
import spotify_helpers as spot
from datetime import timedelta, datetime
from time import sleep

env_dict = func.load_env_vars()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type: str = update.message.chat.type
    chat_text: str = update.message.text

    # Confirm that if the message was sent in a group, that the user was talking to spotibot #
    if (chat_type == 'group' or chat_type == 'supergroup') and env_dict['telegram_bot_username'] not in chat_text:
        return

    # Confirm that the user send a spotify link #
    spotify_link = prev.parse_track_url(env_dict, chat_text)
    if spotify_link['valid']:
        await send_preview(context, update=update)
        return


    await update.message.reply_text("Not a valid chat command. Please @ me with a spotify/youtube link")

async def send_message(context: ContextTypes.DEFAULT_TYPE, message):
    await context.bot.sendMessage(
        chat_id=env_dict['chat_id'],
        message_thread_id=env_dict['thread_id'],
        text=message
    )

####################################################################################
# PREVIEW SENDING FUNCTIONALITY
#
#
####################################################################################
async def send_preview(context: ContextTypes.DEFAULT_TYPE, update=None, id=None):

    if id:
        chat_type: str = "group"
        chat_id:   str = env_dict['chat_id']
        chat_thread_id = env_dict['thread_id']
        chat_text: str = spot.get_song_url(env_dict, id)
    else:
        chat_type: str = update.message.chat.type
        chat_id:   str = update.effective_chat.id
        chat_thread_id = update.effective_message.message_thread_id
        chat_text: str = update.message.text

    # Confirm that the user send a spotify link #
    link = prev.parse_track_url(env_dict, chat_text)
    print(link['valid'])
    if (not link['valid'] or not link['id']) and update:
        func.add_to_logs(f'[{datetime.now()}] [ERROR] User = {update.effective_user.id} ({update.effective_user.username}) in {chat_type}: {chat_text} did not send a valid link')
        await send_message(context, "Not a valid spotify song link. Please send a link to a specific song from spotify")
        return

    # use track ID to get song preview #
    track = prev.get_song_preview(env_dict, link['id'])

    # if there is no preview, send a message saying there is no preview #
    if track['preview_url'] is None:
        message = f"Sorry, there is no preview available for {track['name']} by: {track['artist']}"
        await send_message(context, message)
        return

    # Send audio file to chat where message was sent #
    filename=f"{track['name']} by {track['artist']}"
    audio_file = f"{func.get_data_dir()}/{track['name']}.mp3"

    complete = func.download_url(audio_file, track['preview_url'])
    if not complete:
        await send_message(context, f"Sorry, there is no preview available for {filename}")
        return
    await context.bot.send_audio(
        chat_id=chat_id,
        filename=filename,
        audio=audio_file,
        message_thread_id=chat_thread_id,
    )
    response = f"[{datetime.now()}] [SUCCESS] Succesfully sent preview of {filename}"
    func.add_to_logs(response)
    func.delete_file(audio_file)

####################################################################################
# UTILITY FUNCTIONS
#
#
####################################################################################
async def post_init(application: Application):
    print("[INFO] Running startup tasks...")

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #func.add_to_logs(f'[{datetime.now()}] [ERROR] {update} caused error {context.error}')
    print(f'[{datetime.now()}] [ERROR] {update} caused error {context.error}')



if __name__ == '__main__':
    print('Starting Bot..')
    app = Application.builder().token(env_dict['telegram_token']).post_init(post_init).build()

    # Message handler to do specific tasks depending on the message #
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    # Errors
    app.add_error_handler(error)

    print('[INFO] Polling..')
    app.run_polling(poll_interval=3)
