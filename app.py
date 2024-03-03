from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import logging
from config import DUFFEL_ACCESS_TOKEN

app = Flask(__name__)
CORS(app)


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
        offers_data = response.json().get("data", {}).get("offers", [])

        filtered_offers = []
        for offer in offers_data:
            # Check if 'services' key exists and has at least one item
            if "services" in offer and offer["services"]:
                first_service = offer["services"][0]
                # Further checks can be added here for nested keys
                if "segments" in first_service and first_service["segments"]:
                    first_segment = first_service["segments"][0]
                    if (
                        "operating_carrier" in first_segment
                        and first_segment["operating_carrier"]
                    ):
                        airline_name = first_segment["operating_carrier"].get(
                            "name", "Unknown Airline"
                        )
                        filtered_offers.append(
                            {
                                "total_amount": offer.get("total_amount", "Unknown"),
                                "total_currency": offer.get(
                                    "total_currency", "Unknown"
                                ),
                                "airline": airline_name,
                            }
                        )

        print(filtered_offers)  # Print the filtered offers
        return jsonify(filtered_offers)
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred: {http_err} - {response.text}")
        return jsonify({"error": "Failed to fetch flight offers"}), 500
    except Exception as err:
        logging.error(f"An error occurred: {err}")
        return jsonify({"error": "An unexpected error occurred"}), 500


@app.route("/get_flight_offers", methods=["POST"])
def get_flight_offers():
    return fetch_flight_offers()


@app.route("/")
def hello_world():
    return "Hello, Cross-Origin World!"


if __name__ == "__main__":
    app.run(debug=True, port=5000)
