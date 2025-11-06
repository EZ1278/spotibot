from shutil import Error
import preview_helpers as prev
import functions as func
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import json

env_dict = func.load_env_vars()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Hello World!')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type: str = update.message.chat.type
    chat_id:   str = update.effective_chat.id
    chat_thread_id = update.effective_message.message_thread_id
    chat_text: str = update.message.text

    # Confirm that if the message was sent in a group, that the user was talking to spotibot #
    if (chat_type == 'group' or chat_type == 'supergroup') and env_dict['telegram_bot_username'] not in chat_text:
        return

    # Confirm that the user send a spotify link #
    link = prev.parse_track_url(env_dict, chat_text)
    if not link['valid']:
        func.add_to_logs(f'User = {update.message.chat.id} in {chat_type}: {chat_text}')
        await update.message.reply_text("Not a valid spotify song link. Please send a link to a specific song from spotify")
        return

    # use track ID to get song preview #
    if link['valid']:
        track = prev.get_song_preview(env_dict, link['id'])


    # if there is no preview, send a message saying there is no preview #
    if track is None:
        func.add_to_logs(f'User = {update.message.chat.id} in {chat_type}: {chat_text}')
        await update.message.reply_text("Sorry, there is no preview available for this track")
        return

    # Send audio file to chat where message was sent #
    filename=f"{track['name']} by {track['artist']}"
    audio_file = f"{func.get_data_filepath()}/{track['name']}.mp3"
    func.download_url(audio_file, track['preview_url'])
    await context.bot.send_audio(
        chat_id=chat_id,
        filename=filename,
        audio=audio_file,
        message_thread_id=chat_thread_id,
    )
    func.delete_file(audio_file)

    func.add_to_logs(f"Successfully Sent Preview of {filename}")

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    func.add_to_logs(f'Update: {update} caused error {context.error}')


if __name__ == '__main__':
    print('Starting Bot..')
    app = Application.builder().token(env_dict['telegram_token']).build()

    # Commands
    app.add_handler(CommandHandler('start', start_command))
    # Add command for user to sent preview #

    # Messages
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    # Errors
    app.add_error_handler(error)

    print('Polling..')
    app.run_polling(poll_interval=3)
