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
        offers_response = response.json()

        offers_data = offers_response.get("data", {}).get("offers", [])

        offers_details = []
        for offer in offers_data[:4]:  # Assuming you still want to limit to the first 4 offers
            slices_details = []
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
                    "destination_iata_code": first_segment["destination"].get("iata_code"),
                    "operating_carrier_name": first_segment["operating_carrier"].get("name")
                }
                slices_details.append(slice_details)
            offers_details.append({"slices": slices_details})

        return jsonify(offers_details)
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
