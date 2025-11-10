from shutil import Error
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import preview_helpers as prev
import functions as func
import spotify_helpers as spot
from datetime import timedelta
from time import sleep

env_dict = func.load_env_vars()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This will link the ranking to whatever chat the '/start' command was sent in #
    env_dict['chat_id'] = update.effective_chat.id
    env_dict['thread_id'] = update.effective_message.message_thread_id

    func.save_env(env_vars=env_dict)

    await context.bot.send_message(
                chat_id=env_dict['chat_id'],
                message_thread_id=env_dict['thread_id'],
                text='Hello, to start a playlist ranking, please use the command "/start_ranking" followed by a link to the playlist'
            )
    await context.bot.send_message(
                chat_id=env_dict['chat_id'],
                message_thread_id=env_dict['thread_id'],
                text='Example: "/start_ranking https://open.spotify.com/playlist/playlist_id"'
            )

async def send_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type: str = update.message.chat.type
    chat_id:   str = update.effective_chat.id
    chat_thread_id = update.effective_message.message_thread_id
    chat_text: str = update.message.text

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
    audio_file = f"{func.get_data_dir()}/{track['name']}.mp3"
    func.download_url(audio_file, track['preview_url'])
    await context.bot.send_audio(
        chat_id=chat_id,
        filename=filename,
        audio=audio_file,
        message_thread_id=chat_thread_id,
    )
    func.delete_file(audio_file)

    func.add_to_logs(f"Successfully Sent Preview of {filename}")

async def start_ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type: str = update.message.chat.type
    chat_text: str = update.message.text
    user_id: str = update.message.from_user.id

    # Only allow a specific user to start rankings #
    if user_id != env_dict['admin_id']:
        return

    # Parse spotify link for playlist ID, then get playlist information #
    playlist_id = chat_text.split('/playlist/')[1].split('?')[0]
    json_result = spot.get_playlist(env_dict, playlist_id)
    env_dict["current_ranking"]=json_result['name']
    func.save_env(env_dict)

    if not func.check_ranking(json_result['name']):
        func.create_calibration_round(env_dict=env_dict, playlist_id=playlist_id, playlist_name=json_result['name'])

    # Send poll for first ranking #
    await create_poll(context)
    sleep(5)
    await create_poll(context)

async def create_poll(context: ContextTypes.DEFAULT_TYPE):
    ranking_data = func.open_ranking(env_dict['current_ranking'])
    current_round = ranking_data['current_round']

    # Check if there are songs left in this round #
    if ranking_data[f'round_{current_round}']['songs_remaining'] == 0:
        ranking_data = func.create_next_round(ranking_data)
        current_round = ranking_data['current_round']

    options = []
    ids = []
    playlist_name = ranking_data['playlist_name']
    current_round_data = ranking_data[f'round_{current_round}']
    current_ranking = current_round_data['current_ranking']

    # Increment the current ranking for the next poll #
    ranking_data[f'round_{current_round}']['current_ranking'] += 2
    ranking_data[f'round_{current_round}']['songs_remaining'] -= 2
    func.save_choice(ranking_data)

    options.append(f"{current_round_data['matchups']['tracks'][current_ranking]} by: {current_round_data['matchups']['artists'][current_ranking]}")
    ids.append(current_round_data['matchups']['id'][current_ranking])
    options.append(f"{current_round_data['matchups']['tracks'][current_ranking+1]} by: {current_round_data['matchups']['artists'][current_ranking+1]}")
    ids.append(current_round_data['matchups']['id'][current_ranking+1])

    message = await context.bot.send_poll(
            chat_id=env_dict['chat_id'],
            message_thread_id=env_dict['thread_id'],
            question=f"{playlist_name} round: {current_round} ranking",
            options=options,
            is_anonymous=False
        )

    # Function call to close poll, and update ranking #
    if isinstance(context, Application):
        job_queue = context.job_queue
    else:
        job_queue = context.application.job_queue

    job_queue.run_once(
            close_poll,
            when=timedelta(minutes=1440),
            data={
                'chat_id': env_dict['chat_id'],
                'thread_id': env_dict['thread_id'],
                'message_id': message.message_id,
                'poll_id': message.poll.id,
                'current_round': current_round
            },
            name=f"close_poll_{message.poll.id}"
        )

    # Create JSON as a reference to each poll #
    poll = {
        message.poll.id: {
            'ids':ids,
            'message_id':message.message_id
        }
    }
    print('saving poll')
    func.save_poll_id(poll)

    # Send previews of song with spotify links #
    for id in ids:
        track = prev.get_song_preview(env_dict, id)
        filename=f"{track['name']} by {track['artist']}"
        audio_file = f"{func.get_data_dir()}/{track['name']}.mp3"
        func.download_url(audio_file, track['preview_url'])
        await context.bot.send_audio(
            chat_id=env_dict['chat_id'],
            filename=filename,
            audio=audio_file,
            message_thread_id=env_dict['thread_id'],
            caption=spot.get_song_url(env_dict, id)
        )
        func.delete_file(audio_file)

async def close_poll(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    open_polls = func.get_open_polls()
    try:
        # Stop the poll #
        ranking_poll = await context.bot.stop_poll(
            chat_id=job_data['chat_id'],
            message_id=job_data['message_id']
        )

        # Determine Winner #
        results = ranking_poll.options

        ids = open_polls.pop(ranking_poll.id)['ids']
        func.delete_poll_id(open_polls)
        if results[0].voter_count > results[1].voter_count:
            func.write_results(ids[0], ids[1], env_dict, job_data['current_round'])
        elif results[0].voter_count < results[1].voter_count:
            func.write_results(ids[1], ids[0], env_dict, job_data['current_round'])

        # Create else statement to handle a tie #


        # Create another poll #
        await create_poll(context)

    except Exception as e:
        print(f"Error closing poll: {e}")
        await create_poll(context)

async def startup(context:ContextTypes.DEFAULT_TYPE):

    ranking_data = func.open_ranking(env_dict['current_ranking'])
    open_polls = func.get_open_polls()
    if not open_polls or not ranking_data:
        # no current ranking
        return
    current_round = ranking_data['current_round']


    print(open_polls.items())
    for poll_id, poll_data in list(open_polls.items()):
    # Stop and Log all polls that exist before startup #
        try:
            # Stop the poll #

            ranking_poll = await context.bot.stop_poll(
                chat_id=env_dict['chat_id'],
                message_id=poll_data['message_id']
            )

            # Determine Winner #
            results = ranking_poll.options

            ids = poll_data['ids']
            if results[0].voter_count > results[1].voter_count:
                func.write_results(ids[0], ids[1], env_dict, current_round)
            elif results[0].voter_count < results[1].voter_count:
                func.write_results(ids[1], ids[0], env_dict, current_round)

            # Create else statement to handle a tie #

        except Exception as e:
            print(f"Error closing poll: {e}")

    open_polls.clear()
    func.delete_poll_id(open_polls)

    # Create new polls #
    # Create another poll #
    await create_poll(context)
    sleep(5)
    await create_poll(context)

async def post_init(application: Application):
    print("Running startup tasks...")
    # Create a context-like object to pass to startup
    await startup(application)

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    func.add_to_logs(f'Update: {update} caused error {context.error}')


if __name__ == '__main__':
    print('Starting Bot..')
    app = Application.builder().token(env_dict['telegram_token']).post_init(post_init).build()

    # Commands
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('start_ranking', start_ranking))
    app.add_handler(CommandHandler('send_preview', send_preview))
    # Add command for user to sent preview #

    # Errors
    app.add_error_handler(error)

    print('Polling..')
    app.run_polling(poll_interval=3)
