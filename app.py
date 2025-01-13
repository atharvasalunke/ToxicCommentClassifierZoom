import time
from flask import Flask, render_template
from flask_socketio import SocketIO, emit, join_room, leave_room
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.sequence import pad_sequences
import pickle
import re
import tensorflow as tf

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app)

# Load the LSTM model and tokenizer
lstm_model = tf.keras.models.load_model('lstm_model_final.h5')

with open('tokenizer.pkl', 'rb') as f:
    tokenizer = pickle.load(f)

# Define label columns
label_columns = ['toxic', 'severe_toxic', 'obscene', 'threat', 'insult', 'identity_hate']

# Track user statuses
user_status = {}
kicked_users = set()


def preprocess_text(text):
    text = re.sub(r"[^a-zA-Z\s]", "", text)
    text = text.lower().strip()
    return text


def predict_with_lstm(comment):
    processed_comment = preprocess_text(comment)
    seq = tokenizer.texts_to_sequences([processed_comment])
    padded_seq = pad_sequences(seq, maxlen=100)
    prediction = lstm_model.predict(padded_seq)
    return prediction.flatten()


def is_toxic(comment):
    lstm_prediction = predict_with_lstm(comment)
    return any(score > 0.5 for score in lstm_prediction)


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on('join')
def handle_join(data):
    username = data['username']
    room = data['room']

    if username in kicked_users:
        emit('message', {'msg': f"{username} is not allowed to join. You have been kicked by the admin."})
        return

    is_admin = username.lower() == "admin"
    user_status[username] = {
        "toxic_count": 0,
        "timeout_until": 0,
        "is_admin": is_admin
    }

    join_room(room)
    role = "admin" if is_admin else "user"
    emit('message', {'msg': f"{username} has joined the room as {role}."}, to=room)


@socketio.on('send_message')
def handle_send_message(data):
    room = data.get('room')
    message = data.get('msg')
    username = data.get('username')

    if username not in user_status:
        return

    current_time = time.time()
    if current_time < user_status[username]["timeout_until"]:
        timeout_remaining = int(user_status[username]['timeout_until'] - current_time)
        emit('message', {
            'msg': f"You are in timeout. Please wait {timeout_remaining} seconds.",
            'username': 'System'
        }, to=room)
        return

    if is_toxic(message):
        user_status[username]["toxic_count"] += 1
        if user_status[username]["toxic_count"] >= 3:
            user_status[username]["timeout_until"] = current_time + 30
            emit('message', {
                'msg': f"{username} has been placed in timeout for 30 seconds.",
                'username': 'System'
            }, to=room)
        else:
            emit('message', {
                'msg': f"{username}'s message was flagged as toxic and removed.",
                'username': 'System'
            }, to=room)
    else:
        emit('message', {
            'msg': message,
            'username': username
        }, room=room)


@socketio.on('moderate_message')
def moderate_message(data):
    admin_username = data.get('admin_username')
    target_username = data.get('target_username')
    room = data.get('room')

    if not user_status.get(admin_username, {}).get('is_admin', False):
        emit('message', {
            'msg': "Unauthorized action. Only admin can moderate messages.",
            'username': 'System'
        })
        return

    emit('message', {
        'msg': f"All messages from {target_username} were removed by the admin.",
        'username': 'System',
        'action': 'remove',
        'target_username': target_username
    }, to=room)


@socketio.on('kick_user')
def kick_user(data):
    admin_username = data.get('admin_username')
    username_to_kick = data.get('username_to_kick')
    room = data.get('room')

    if not user_status.get(admin_username, {}).get('is_admin', False):
        emit('message', {
            'msg': "Unauthorized action. Only admin can kick users.",
            'username': 'System'
        })
        return

    kicked_users.add(username_to_kick)
    if username_to_kick in user_status:
        del user_status[username_to_kick]

    emit('message', {
        'msg': f"{username_to_kick} has been kicked out by the admin.",
        'username': 'System',
        'action': 'kick',
        'target_username': username_to_kick
    }, to=room)


if __name__ == "__main__":
    socketio.run(app, debug=True)
