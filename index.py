import os
import re
import random
import pytz

import iso8601
from flask import Flask, request, jsonify, render_template
import dialogflow
import pusher

from utility import *


app = Flask(__name__)

# initialize Pusher
pusher_client = pusher.Pusher(
    app_id=os.getenv('PUSHER_APP_ID'),
    key=os.getenv('PUSHER_KEY'),
    secret=os.getenv('PUSHER_SECRET'),
    cluster=os.getenv('PUSHER_CLUSTER'),
    ssl=True)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/webhook', methods=['POST'])
def webhook():
    api_data = request.get_json(silent=True)
    print(api_data)

    intent_name = api_data['queryResult']['intent']['displayName']
    session_id = api_data['session'].split("/")[-1]
    # session_id = '771146823'

    try:
        data = read_pickle(session_id)
    except Exception:
        data = {}

    timezone = data.get('timezone', 'Etc/Greenwich')
    tz = pytz.timezone(timezone)

    if intent_name == "user":
        user = api_data['queryResult']['parameters'].get('email')
        response = "Thanks. How much time will you need? 15min, 30min, or 1hour?"

        data = {
            'user': user
        }

    elif intent_name == "time_amount":
        amount = api_data['queryResult']['parameters']['duration']['amount']
        unit = api_data['queryResult']['parameters']['duration']['unit']

        future_events, timezone = get_events(data.get('user'))

        if unit == "hour":
            amount = amount * 60

        available_durations = get_availables(future_events, amount, 24*60, 60, timezone)

        data['availables'] = available_durations
        data['recommend'] = available_durations[0][0][0]
        data['timezone'] = timezone
        data['amount'] = amount
        data['unit'] = unit
        timezone = data.get('timezone', '+00:00')
        write_pickle(session_id, data)

        # available_durations = data['availables']

        response = "The soonest I can get you a meeting is %s (%s)" % (
            available_durations[0][0][0].strftime("%A %b %d at %I:%M %p"), timezone)
        response += ";select1"

    elif intent_name == "agree":
        try:
            user = data['user']
            recommend_datetime = data['recommend']
            add_event(user, recommend_datetime.isoformat(),
                      (recommend_datetime + datetime.timedelta(minutes=15)).isoformat())

            response = "Great, you're all set! I've sent an invitation to %s" % user
        except KeyError:
            response = "Hey there! I'll help you book a meeting with $USER. But first where should I sent the invitation to?"

    elif intent_name == "other_time":
        availabes = data['availables']
        available_days = ','.join([day_available[0][0].strftime("%A %b %d") for day_available in availabes])

        response = "Sure, Which day would be better?;select2;" + available_days

    elif intent_name == "timezone":
        timezone = api_data['queryResult']['queryText'].replace(";timezone", '').strip()

        data['timezone'] = timezone
        data['availables'] = converted(data['availables'], timezone)
        data['recommend'] = converted(data['recommend'], timezone)

        response = "The soonest I can get you a meeting is %s (%s)" % (
            data['availables'][0][0][0].strftime("%A %b %d at %I:%M %p"), timezone)
        response += ";select1"

    elif intent_name == "want_day":

        day_string = api_data['queryResult']['queryText']

        current_year = datetime.datetime.now(tz).year
        data['want_day'] = datetime.datetime.strptime(day_string + ' %s' % current_year, '%A %b %d %Y').date()

        write_pickle(session_id, data)
        response = "Would morning or afternoon be more convenient for you?"

    elif intent_name == "morning_afternoon":
        start_time = iso8601.parse_date(api_data['queryResult']['parameters']['time-period']['startTime']).time()
        end_time = iso8601.parse_date(api_data['queryResult']['parameters']['time-period']['endTime']).time()

        want_day = data['want_day']
        availables = data['availables']

        want_duration = (tz.localize(datetime.datetime.combine(want_day, start_time)),
                         tz.localize(datetime.datetime.combine(want_day, end_time)))

        day_availables = [x for x in availables if x[0][0].date()==want_duration[0].date()][0]

        want_availables = []
        for day_available in day_availables:
            want_available = want_duration

            if day_available[1] <= want_available[0] or day_available[0] >= want_available[1]:
                continue

            if check_include(want_available, day_available[0]):
                want_available = (day_available[0], want_duration[1])

            if check_include(want_available, day_available[1]):
                want_available = (want_duration[0], day_available[1])

            want_availables.append(want_available)

        want_availables = [x for x in want_availables if get_diff_minute(x[0], x[1])]

        if len(want_availables) > 0:
            available_times = [
                (x[0] + datetime.timedelta(minutes=random.randint(0, int(get_diff_minute(x[0], x[1])) - 15)))
                for x in want_availables for i in range(0, 3)]

            response = "Here's what I have available in the morning %s, %s, %s." % tuple(
                [x.strftime("%I:%M %p") for x in sorted(random.sample(available_times, 3))])

        else:
            response = "Not morning available in this day. How about afternoon?"

    elif intent_name == "want_time":
        want_time = iso8601.parse_date(api_data['queryResult']['parameters']['time']).time()

        data['want_time'] = want_time
        amount = int(data['amount'])
        unit = data['unit'].capitalize()
        data['recommend'] = tz.localize(datetime.datetime.combine(data['want_day'], data['want_time']))
        response = "Ok, to confirm, you will have a %s %ss meetings with %s on %s. Book or cancel?" % (
            amount, unit, data['user'],
            data['recommend'].strftime("%A %b %d at %I:%M %p"))

    elif intent_name == "exit":
        response = 'I\'m sorry. It didn\'t work out. Just say "I want to book a meeting" if you change your mind'

        data = {}

    else:
        response = ''

    write_pickle(session_id, data)

    print(response)
    reply = {"fulfillmentText": response}
    
    return jsonify(reply)


def detect_intent_texts(project_id, session_id, text, language_code):
    session_client = dialogflow.SessionsClient()
    session = session_client.session_path(project_id, session_id)
    
    if text:
        text_input = dialogflow.types.TextInput(
            text=text, language_code=language_code)
        query_input = dialogflow.types.QueryInput(text=text_input)
        response = session_client.detect_intent(
            session=session, query_input=query_input)
        
        return response.query_result.fulfillment_text


@app.route('/send_message', methods=['POST'])
def send_message():
    try:
        socketId = request.form['socketId']
    except KeyError:
        socketId = ''

    message = request.form['message']
    print(message)
    project_id = os.getenv('DIALOGFLOW_PROJECT_ID')
    fulfillment_text = detect_intent_texts(project_id, str(socketId).replace(".", ''), message, 'en')
    response_text = {"message":  fulfillment_text}

    pusher_client.trigger(
        'Calendar_Bot',
        'new_message', 
        {
            'human_message': message, 
            'bot_message': fulfillment_text,
        },
        socketId
    )
                        
    return jsonify(response_text)


# run Flask app
if __name__ == "__main__":
    app.run()
