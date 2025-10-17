from flask import Flask, render_template, request, jsonify
import requests
import math
import json
import time

app = Flask(__name__)

BASE_API = "https://api.carrismetropolitana.pt/v1"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Carrega vehicle_map.json
with open("vehicle_map.json", "r", encoding="utf-8") as f:
    vehicle_map = json.load(f)

def get_vehicle_id(vehicle_number):
    """Procura o vehicle_id no JSON pelo real_number"""
    for entry in vehicle_map.values():
        if entry["real_number"] == vehicle_number:
            return entry["route"]
    return None

def distance(lat1, lon1, lat2, lon2):
    """Calcula distância em km entre dois pontos"""
    R = 6371
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def geocode_osm(query):
    """Obtém lat/lon de uma rua/paragem usando OpenStreetMap Nominatim"""
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query + ", Portugal",
        "format": "json",
        "limit": 1
    }
    try:
        r = requests.get(url, params=params, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code == 200:
            data = r.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
    except:
        pass
    return None, None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/stops")
def stops():
    vehicle_number = request.args.get("vehicle")
    user_lat = float(request.args.get("lat"))
    user_lon = float(request.args.get("lon"))

    vehicle_id = get_vehicle_id(vehicle_number)
    if not vehicle_id:
        return jsonify({"error": "Camioneta não encontrada no mapeamento"}), 404

    stops_list = []

    # Primeiro, tentamos buscar todas as paragens da API
    url = f"{BASE_API}/vehicles/{vehicle_id}/stops"
    r = requests.get(url, headers=HEADERS)
    api_stops = r.json().get("stops", []) if r.status_code == 200 else []

    if api_stops:
        for stop in api_stops:
            stop_lat = stop.get("latitude")
            stop_lon = stop.get("longitude")
            dist = distance(user_lat, user_lon, stop_lat, stop_lon) if stop_lat and stop_lon else None
            stops_list.append({
                "id": stop.get("id"),
                "name": stop.get("name"),
                "lat": stop_lat,
                "lon": stop_lon,
                "distance_km": round(dist,2) if dist else None
            })
    else:
        # Fallback usando vehicle_map + geocodificação OSM
        for key, entry in vehicle_map.items():
            if entry["real_number"] == vehicle_number:
                stop_name = entry["stop"]
                stop_lat, stop_lon = geocode_osm(stop_name)
                time.sleep(1)
                dist = distance(user_lat, user_lon, stop_lat, stop_lon) if stop_lat and stop_lon else None
                stops_list.append({
                    "id": key,
                    "name": stop_name,
                    "lat": stop_lat,
                    "lon": stop_lon,
                    "distance_km": round(dist,2) if dist else None
                })

    # Ordena por distância
    stops_list.sort(key=lambda x: x["distance_km"] if x["distance_km"] is not None else float('inf'))
    return jsonify(stops_list)

@app.route("/arrival")
def arrival():
    vehicle_number = request.args.get("vehicle")
    stop_id = request.args.get("stop_id")

    vehicle_id = get_vehicle_id(vehicle_number)
    if not vehicle_id:
        return jsonify({"error": "Camioneta não encontrada"}), 404

    url = f"{BASE_API}/vehicles/{vehicle_id}/stops/{stop_id}/arrivals"
    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        return jsonify({"arrivals": [{"vehicle": vehicle_number, "estimated_arrival_minutes": "Sem dados de chegada"}]})

    data = r.json()
    arrivals = data.get("arrivals", [])
    if not arrivals:
        arrivals = [{"vehicle": vehicle_number, "estimated_arrival_minutes": "Sem dados de chegada"}]

    return jsonify({"arrivals": arrivals})

if __name__ == "__main__":
    app.run(debug=True)



