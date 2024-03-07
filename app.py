from flask import Flask, request, jsonify, redirect, session, url_for
from flask_cors import CORS
import requests
import logging
from flask_mail import Mail, Message
from config import DUFFEL_ACCESS_TOKEN, LUFTHANSA_API_KEY, LUFTHANSA_API_SECRET
import json

app = Flask(__name__)
CORS(app)

# Flask-Mail configuration
app.config["MAIL_SERVER"] = "smtp.gmail.com"  # The mail server
app.config["MAIL_PORT"] = 587  # The mail server port
app.config["MAIL_USE_TLS"] = True  # Use TLS
app.config["MAIL_USERNAME"] = "joshsparkes6@gmail.com"  # Your email username
app.config["MAIL_PASSWORD"] = "1Time4UrM"  # Your email password
app.config["MAIL_DEFAULT_SENDER"] = "joshsparkes6@gmail.com"  # Default sender

mail = Mail(app)  # Initialize Flask-Mail


def fetch_flight_offers():
    url = "https://api.duffel.com/air/offer_requests"
    headers = {
        "Authorization": f"Bearer {DUFFEL_ACCESS_TOKEN}",
        "Duffel-Version": "v1",
        "Content-Type": "application/json",
    }
    payload = request.json
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        offers_response = response.json()

        offers_data = offers_response.get("data", {}).get("offers", [])

        offers_details = []
        for offer in offers_data[
            :4
        ]:  # Assuming you still want to limit to the first 4 offers
            slices_details = []
            passenger_ids = [
                passenger["id"] for passenger in offer.get("passengers", [])
            ]
            for slice in offer["slices"]:
                # Assuming each slice has at least one segment
                first_segment = slice["segments"][0]
                slice_details = {
                    "total_amount": offer.get("total_amount"),
                    "base_currency": offer.get("base_currency"),
                    "departing_at": first_segment.get("departing_at"),
                    "arriving_at": first_segment.get("arriving_at"),
                    "stops": len(first_segment.get("stops", [])),
                    "duration": slice.get("duration"),
                    "origin_iata_code": first_segment["origin"].get("iata_code"),
                    "destination_iata_code": first_segment["destination"].get(
                        "iata_code"
                    ),
                    "operating_carrier_name": first_segment["operating_carrier"].get(
                        "name"
                    ),
                }
                slices_details.append(slice_details)
            offers_details.append(
                {
                    "id": offer["id"],
                    "slices": slices_details,
                    "passenger_ids": passenger_ids,
                }
            )

        return jsonify(offers_details)
    except requests.exceptions.HTTPError as http_err:
        error_response = response.json()
        logging.error(f"HTTP error occurred: {http_err} - {error_response}")

        error_messages = [
            error["message"] for error in error_response.get("errors", [])
        ]

        return jsonify({"errors": error_messages}), response.status_code
    except Exception as err:
        logging.error(f"An error occurred: {err}")
        return jsonify({"error": "An unexpected error occurred"}), 500


@app.route("/get_flight_offers", methods=["POST"])
def get_flight_offers():
    return fetch_flight_offers()


@app.route("/")
def hello_world():
    return "Hello, Cross-Origin World!"


@app.route("/create_order", methods=["POST"])
def create_order():
    url = "https://api.duffel.com/air/orders"
    headers = {
        "Authorization": f"Bearer {DUFFEL_ACCESS_TOKEN}",
        "Duffel-Version": "v1",
        "Content-Type": "application/json",
    }
    payload = (
        request.json
    )  # This should include the selected offer ID and passenger details

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        order_response = response.json()
        return jsonify(order_response), 200
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred: {http_err} - {response.text}")
        return jsonify({"error": "Failed to create order"}), response.status_code
    except Exception as err:
        logging.error(f"An error occurred: {err}")
        return jsonify({"error": "An unexpected error occurred"}), 500


@app.route("/duffel-webhook", methods=["POST"])
def duffel_webhook():
    data = request.json
    if data.get("object") and data["object"].get("id"):
        order_id = data["object"]["id"]
        order_details = fetch_order_details(order_id)
        for passenger in order_details.get("passengers", []):
            passenger_email = passenger.get("email")
            if passenger_email:
                send_booking_confirmation_email(passenger_email)
    return jsonify({"message": "Webhook received"}), 200


def fetch_order_details(order_id):
    url = f"https://api.duffel.com/air/orders/{order_id}"
    headers = {
        "Authorization": f"Bearer {DUFFEL_ACCESS_TOKEN}",
        "Duffel-Version": "v1",
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        return {}


def send_booking_confirmation_email(email):
    msg = Message(
        "Booking Confirmation", sender="joshsparkes6@gmail.com", recipients=[email]
    )
    msg.body = "Your booking has been confirmed."
    mail.send(msg)


@app.route("/oauth/callback")
def oauth_callback():
    # Retrieve the authorization code from the query string
    auth_code = request.args.get("code")

    if not auth_code:
        return "Authorization code not found in the request", 400

    # Exchange the authorization code for an access token
    token_url = "https://api.lufthansa.com/v1/oauth/token"
    client_id = "YOUR_CLIENT_ID"
    client_secret = "YOUR_CLIENT_SECRET"
    redirect_uri = "https://api-ai-client-be.onrender.com/oauth/callback"

    payload = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }

    try:
        response = requests.post(token_url, data=payload)
        response.raise_for_status()
        token_data = response.json()

        # Here you would typically save the token to the session or a database
        # For example: session['access_token'] = token_data['access_token']

        # Redirect or respond as necessary for your application flow
        return "Authorization successful. Access token obtained."
    except requests.exceptions.HTTPError as err:
        return f"Failed to obtain access token: {err}", 500


def get_lufthansa_token():
    token_url = "https://api.lufthansa.com/v1/oauth/token"
    payload = {
        "client_id": LUFTHANSA_API_KEY,
        "client_secret": LUFTHANSA_API_SECRET,
        "grant_type": "client_credentials",
    }
    response = requests.post(token_url, data=payload)
    if response.status_code == 200:
        token_data = response.json()
        return token_data["access_token"]
    else:
        logging.error(f"Failed to obtain Lufthansa access token: {response.text}")
        return None


def fetch_best_fares(origin, destination, departure_date, return_date, cabin_class="ECONOMY"):
    access_token = get_lufthansa_token()
    if not access_token:
        print("Failed to obtain access token. Cannot fetch fares.")
        return

    url = "https://api.lufthansa.com/v1/offers/faresbestprice/bestfares"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    params = {
        "origin": origin,
        "destination": destination,
        "departureDate": departure_date,
        "returnDate": return_date,
        "cabinClass": cabin_class,
        "duration": "P0Y0M7D",  # Example duration of 7 days
        "viewBy": "DAY"  # Can be DAY or MONTH
    }
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        offers = response.json()
        print(json.dumps(offers, indent=4))  # Pretty print the JSON response
    else:
        logging.error(f"Failed to fetch best fares. Status Code: {response.status_code}")
        print(response.text)

# Example usage
fetch_best_fares("FRA", "JFK", "2023-12-01", "2023-12-08")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
