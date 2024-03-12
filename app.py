from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import logging
from flask_mail import Mail, Message
from config import DUFFEL_ACCESS_TOKEN
from config import HOTELBEDS_API_KEY, HOTELBEDS_SECRET
import hashlib
import time


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


@app.route("/get_hotel_availability", methods=["POST"])
def get_hotel_availability():
    # Extract search parameters from the request body
    search_params = request.json
    check_in = search_params.get("checkIn")
    check_out = search_params.get("checkOut")
    adults = search_params.get("adults")
    children = search_params.get("children")
    rooms = search_params.get("rooms")
    destination_code = search_params.get("destination")

    # Endpoint for the hotel availability
    url = "https://api.test.hotelbeds.com/hotel-api/1.0/hotels"

    # Current timestamp
    timestamp = str(int(time.time()))

    # Generate the signature
    signature = hashlib.sha256(
        (HOTELBEDS_API_KEY + HOTELBEDS_SECRET + timestamp).encode()
    ).hexdigest()

    # Headers including the authentication
    headers = {
        "Api-key": HOTELBEDS_API_KEY,
        "X-Signature": signature,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # Adjusted data for the request body using dynamic parameters
    data = {
        "stay": {"checkIn": check_in, "checkOut": check_out},
        "occupancies": [{"rooms": rooms, "adults": adults, "children": children}],
        "destination": {"code": destination_code},  # Use dynamic destination code
    }

    # Make the POST request
    response = requests.post(url, headers=headers, json=data)

    # Check if the request was successful
    if response.status_code == 200:
        response_data = response.json()
        hotels_data = response_data.get("hotels", {}).get("hotels", [])

        # Process each hotel to extract and return the required information, including pricing
        hotels_info = []
        for hotel in hotels_data:
            # Directly use 'minRate' and 'currency' as they are both strings
            price_amount = hotel.get("minRate", "N/A")  # Default to "N/A" if not found
            price_currency = hotel.get(
                "currency", "N/A"
            )  # Default to "N/A" if not found

            hotel_info = {
                "name": hotel.get("name"),
                "destinationName": hotel.get("destinationName"),
                "categoryName": hotel.get("categoryName"),
                "zoneName": hotel.get("zoneName"),
                "roomsCount": len(hotel.get("rooms", [])),
                "price": price_amount,
                "currency": price_currency,
                "code": hotel.get("code"),
            }
            hotels_info.append(hotel_info)

        return jsonify(hotels_info)
    else:
        return (
            jsonify({"error": f"Failed to fetch hotels: {response.text}"}),
            response.status_code,
        )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
