from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import logging
from flask_mail import Mail, Message
from config import DUFFEL_ACCESS_TOKEN
from config import SKYSCANNER_API_KEY
import urllib.parse


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


@app.route("/search_hotels", methods=["POST"])
def search_hotels():
    data = request.json
    checkin = data["checkin"]
    checkout = data["checkout"]
    adults = data["adults"]
    rooms = data["rooms"]
    entity_id = data.get("entity_id", "27539733")  # Example entity ID, consider making this dynamic
    mediaPartnerId = "yourMediaPartnerIdHere"  # Replace with your actual Media Partner ID

    # Construct the referral URL
    base_url = "https://skyscanner.net/g/referrals/v1/hotels/day-view"
    params = {
        "entity_id": entity_id,
        "checkin": checkin,
        "checkout": checkout,
        "adults": adults,
        "rooms": rooms,
        "mediaPartnerId": mediaPartnerId,
    }
    referral_url = f"{base_url}?{urllib.parse.urlencode(params)}"

    # Log the referral URL for debugging
    logging.info(f"Generated referral URL: {referral_url}")

    # Print the referral URL to the console (server side)
    print(f"Generated referral URL: {referral_url}")

    # Return the referral URL to the frontend
    return jsonify({"referral_url": referral_url})


def generate_hotels_day_view_url(entity_id, checkin, checkout, adults, rooms, market="US", locale="en-US", currency="USD"):
    base_url = "https://skyscanner.net/g/referrals/v1/hotels/day-view"
    params = {
        "entity_id": entity_id,
        "checkin": checkin,
        "checkout": checkout,
        "adults": adults,
        "rooms": rooms,
        "market": market,
        "locale": locale,
        "currency": currency
    }
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    return url


if __name__ == "__main__":
    app.run(debug=True, port=5000)
