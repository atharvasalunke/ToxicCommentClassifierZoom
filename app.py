from flask import Flask, request, jsonify

app = Flask(__name__)

# Replace this with the token you set in your Zoom webhook app
ZOOM_VERIFICATION_TOKEN = "1CFUWxvzTtOVvc3bHx6g5Q"

@app.route("/zoom-webhook", methods=["POST"])
def zoom_webhook():
    """
    Endpoint to receive and log Zoom chat messages via webhook.
    """
    # Verify Zoom webhook token
    if request.headers.get("Authorization") != ZOOM_VERIFICATION_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    # Log the incoming payload
    data = request.json
    print("Received data:", data)

    # Parse the message content
    try:
        message = data["payload"]["object"]["message"]["content"]
        user = data["payload"]["object"]["participant"]["user_name"]
        print(f"Message from {user}: {message}")
    except KeyError as e:
        print(f"Missing expected field: {e}")
        return jsonify({"error": "Invalid data"}), 400

    # Send a response back to Zoom
    return jsonify({"status": "Message received and logged"}), 200

if __name__ == "__main__":
    app.run(debug=True)
