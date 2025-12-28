from shutil import Error
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, PollHandler
import preview_helpers as prev
import functions as func
import spotify_helpers as spot
from datetime import timedelta, datetime
from time import sleep

env_dict = func.load_env_vars()
poll_tracking = {
    'number_polls':0
}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id: str = update.message.from_user.id

    if user_id != env_dict['admin_id']:
        return

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

async def send_preview_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_preview(context, update=update)

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
# PLAYLIST RANKING FUNCTIONALITY
#
#
####################################################################################
async def change_ranking_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id: str = update.message.from_user.id
    chat_text: str = update.message.text.split()[1]

    if user_id != env_dict['admin_id']:
        response = f"[{datetime.now()}] [INFO] Non-admin user ({user_id})tried to change ranking amount"
        func.add_to_logs(response)
        return

    env_dict["open_poll_amount"]=int(chat_text)
    func.save_env(env_dict)
    response = f"[{datetime.now()}] [SUCCESS] Updated total polls to {chat_text}"

async def change_ranking_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id: str = update.message.from_user.id
    chat_text: str = update.message.text.split()[1]

    if user_id != env_dict['admin_id']:
        response = f"[{datetime.now()}] [INFO] Non-admin user ({user_id}) tried to change poll open time"
        func.add_to_logs(response)
        return

    env_dict["open_poll_time"]=int(chat_text)
    func.save_env(env_dict)
    response = f"[{datetime.now()}] [SUCCESS] Updated poll open time to {chat_text}"

async def start_ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_text: str = update.message.text
    user_id: str = update.message.from_user.id

    # Only allow a specific user to start rankings #
    if user_id != env_dict['admin_id']:
        response = f"[{datetime.now()}] [INFO] Non-admin user ({user_id}) tried start a ranking"
        func.add_to_logs(response)
        return

    # Parse spotify link for playlist ID, then get playlist information #
    playlist_id = chat_text.split('/playlist/')[1].split('?')[0]
    json_result = spot.get_playlist(env_dict, playlist_id)
    env_dict["current_ranking"]=json_result['name']
    func.save_env(env_dict)

    if not func.check_ranking(json_result['name']):
        func.create_calibration_round(env_dict=env_dict, playlist_id=playlist_id, playlist_name=json_result['name'])

    # Send poll for first ranking #
    response = f"[{datetime.now()}] [INFO] Sending initial rankings for {json_result['name']}"
    func.add_to_logs(response)
    for i in range(env_dict['open_poll_amount']):
        await create_poll(context, update)
        sleep(30)

async def create_poll(context: ContextTypes.DEFAULT_TYPE, update: Update = None):

    ranking_data = func.open_ranking(env_dict['current_ranking'])
    current_round = ranking_data['current_round']

    # Check if there are songs left in this round #
    if ranking_data[f'round_{current_round}']['songs_remaining'] == 0:
        response = f"[{datetime.now()}] [INFO] Moving ranking to next round"
        func.add_to_logs(response)
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

    options.append(f"{current_round_data['matchups']['tracks'][current_ranking]} by: {current_round_data['matchups']['artists'][current_ranking]}")
    ids.append(current_round_data['matchups']['id'][current_ranking])
    options.append(f"{current_round_data['matchups']['tracks'][current_ranking+1]} by: {current_round_data['matchups']['artists'][current_ranking+1]}")
    ids.append(current_round_data['matchups']['id'][current_ranking+1])

    response = f"[{datetime.now()}] [INFO] Sending poll for {options[0]} vs {options[1]}"
    func.add_to_logs(response)
    message = await context.bot.send_poll(
            chat_id=env_dict['chat_id'],
            message_thread_id=env_dict['thread_id'],
            question=f"{playlist_name} round: {current_round} ranking",
            options=options,
            is_anonymous=False
        )
    response = f"[{datetime.now()}] [SUCCESS] Poll sucessfully sent!"
    func.add_to_logs(response)

    # Function call to close poll, and update ranking #
    if isinstance(context, Application):
        job_queue = context.job_queue
    else:
        job_queue = context.application.job_queue

    response = f"[{datetime.now()}] [INFO] Queuing job to close poll for {options[0]} vs {options[1]}"
    func.add_to_logs(response)
    job_queue.run_once(
            close_poll,
            when=timedelta(hours=env_dict['open_poll_time']),
            data={
                'chat_id': env_dict['chat_id'],
                'thread_id': env_dict['thread_id'],
                'message_id': message.message_id,
                'poll_id': message.poll.id,
                'current_round': current_round
            },
            name=f"close_poll_{message.poll.id}"
        )
    response = f"[{datetime.now()}] [SUCCESS] Job Queued Successfully"
    func.add_to_logs(response)

    # Create JSON as a reference to each poll #
    poll = {
        message.poll.id: {
            'ids':ids,
            'message_id':message.message_id,
            'start_date': str(datetime.now()),
            'current_round': current_round
        }
    }

    func.save_poll_id(poll)
    poll_tracking['number_polls'] += 1
    response = f"[{datetime.now()}] [INFO] set open polls to {poll_tracking['number_polls']}"
    func.add_to_logs(response)

    # Send previews of song with spotify links #
    for id in ids:
        await send_preview(context, update=update, id=id)

    func.save_choice(ranking_data)

async def close_poll(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    open_polls = func.get_open_polls()
    poll_tracking['number_polls'] -= 1
    response = f"[{datetime.now()}] [INFO] set open polls to {poll_tracking['number_polls']}"
    func.add_to_logs(response)
    try:
        # Stop the poll #
        ranking_poll = await context.bot.stop_poll(
            chat_id=job_data['chat_id'],
            message_id=job_data['message_id']
        )

        response = f"[{datetime.now()}] [SUCCESS] Successfully closed poll {job_data['poll_id']}"
        func.add_to_logs(response)

        # Determine Winner #
        results = ranking_poll.options

        ids = open_polls.pop(ranking_poll.id)['ids']
        func.delete_poll_id(open_polls)
        if results[0].voter_count > results[1].voter_count:
            func.write_results(ids[0], ids[1], env_dict, job_data['current_round'])
        elif results[0].voter_count < results[1].voter_count:
            func.write_results(ids[1], ids[0], env_dict, job_data['current_round'])
        else:
            print('tie')
            func.write_tie(ids, env_dict, job_data['current_round'])

    except Exception as e:
        response = f"[{datetime.now()}] [ERROR] Problem closing poll\n\t{e}"
        func.add_to_logs(response)

    # Only create a new poll if there is space for a new poll #
    # IE: calibration > current
    if env_dict['open_poll_amount'] > poll_tracking['number_polls']:
        for i in range(env_dict['open_poll_amount']-poll_tracking['number_polls']):
            await create_poll(context)
            sleep(300) # sleep for 5 min to allow for adequate time between polls

####################################################################################
# UTILITY FUNCTIONS
#
#
####################################################################################
async def startup(context:ContextTypes.DEFAULT_TYPE):
    response = f"[{datetime.now()}] [INFO] Running Startup tasks.."
    func.add_to_logs(response)
    ranking_data = func.open_ranking(env_dict['current_ranking'])
    open_polls = func.get_open_polls()
    if open_polls == False or ranking_data == False:
        # no open polls #
        func.add_to_logs(f"[{datetime.now()}] [INFO] No open polls, starting bot")
        return
    func.add_to_logs(f"[{datetime.now()}] [INFO] Setting open polls to {len(open_polls)}")
    poll_tracking['number_polls'] = len(open_polls)
    current_schedule = 5 # minutes

    if len(open_polls) == 0:
        while poll_tracking['number_polls'] < env_dict['open_poll_amount']:
            await create_poll(context)
            sleep(current_schedule*60) # wait 5 minutes inbetween poll creation
        return

    for poll_id, poll_data in list(open_polls.items()):
    # Stop and Log all polls that exist before startup #
        start_date = datetime.fromisoformat(poll_data['start_date'])
        total_time_open = (datetime.now()-start_date).total_seconds() / 3600
        response = f"[{datetime.now()}] [INFO] Poll {poll_id} has been open for {total_time_open} hours starting at {start_date}"
        func.add_to_logs(response)
        if total_time_open > env_dict['open_poll_time']:
            if isinstance(context, Application):
                job_queue = context.job_queue
            else:
                job_queue = context.application.job_queue

            job_queue.run_once(
                    close_poll,
                    when=timedelta(minutes=current_schedule),
                    data={
                        'chat_id': env_dict['chat_id'],
                        'thread_id': env_dict['thread_id'],
                        'message_id': poll_data['message_id'],
                        'poll_id': poll_id,
                        'current_round': poll_data['current_round']
                    },
                    name=f"close_poll_{poll_id}"
                )
            response = f"[{datetime.now()}] [INFO] Poll {poll_id} queued to close in {current_schedule} minutes"
            func.add_to_logs(response)
            current_schedule += 5

        else:
            # Restoring the timer on polls that already exist #
            time_remaining = env_dict['open_poll_time'] - total_time_open + (current_schedule/60)
            context.job_queue.run_once(
                            close_poll,
                            when=timedelta(hours=time_remaining),
                            data={
                                'chat_id': env_dict['chat_id'],
                                'thread_id': env_dict['thread_id'],
                                'message_id': poll_data['message_id'],
                                'poll_id': poll_id,
                                'current_round': poll_data['current_round'],
                                'startup':False
                            },
                            name=f"close_poll_{poll_id}"
                        )
            response = f"[{datetime.now()}] [INFO] Poll {poll_id} queued to close in {time_remaining} hours"
            func.add_to_logs(response)
        sleep(5)

async def post_init(application: Application):
    print("[INFO] Running startup tasks...")
    # Create a context-like object to pass to startup #
    await startup(application)

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    func.add_to_logs(f'[{datetime.now()}] [ERROR] {update} caused error {context.error}')
    print(f'[{datetime.now()}] [ERROR] {update} caused error {context.error}')



if __name__ == '__main__':
    print('Starting Bot..')
    app = Application.builder().token(env_dict['telegram_token']).post_init(post_init).build()

    # Commands
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('start_ranking', start_ranking))
    app.add_handler(CommandHandler('send_preview', send_preview_command))
    app.add_handler(CommandHandler('change_ranking_amount', change_ranking_amount))
    app.add_handler(CommandHandler('change_ranking_time', change_ranking_time))

    # Message handler to do specific tasks depending on the message #
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    # Poll handler #

    # Errors
    app.add_error_handler(error)

    print('[INFO] Polling..')
    app.run_polling(poll_interval=3)
