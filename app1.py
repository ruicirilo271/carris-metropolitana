from flask import Flask, render_template, request, jsonify
import requests
import math
from datetime import datetime, timedelta
import zipfile
import io
import csv
import time
import json
import os

app = Flask(__name__, static_folder="static", template_folder="templates")

BASE_API = "https://api.carrismetropolitana.pt/v1"
HEADERS = {"User-Agent": "Mozilla/5.0"}

stops_cache = {"timestamp": 0, "data": []}

# 🔹 Carregar mapeamento existente (se existir)
VEHICLE_MAP_PATH = "vehicle_map.json"
if os.path.exists(VEHICLE_MAP_PATH):
    with open(VEHICLE_MAP_PATH, "r", encoding="utf-8") as f:
        VEHICLE_MAP = json.load(f)
else:
    VEHICLE_MAP = {}

# ----------------------------------------
# Função Haversine
# ----------------------------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

@app.route("/")
def index():
    return render_template("index.html")

# ----------------------------------------
# 🔹 Endpoint que descobre o número real da camioneta
# ----------------------------------------
@app.route("/api/update_vehicle_map")
def update_vehicle_map():
    """
    Descobre o número real da camioneta (quando só há um veículo ativo numa paragem)
    e atualiza o ficheiro vehicle_map.json.
    """
    try:
        rv = requests.get(f"{BASE_API}/vehicles", headers=HEADERS, timeout=30)
        rs = requests.get(f"{BASE_API}/stops", headers=HEADERS, timeout=30)
        if rv.status_code != 200 or rs.status_code != 200:
            return jsonify({"error": "Falha ao obter dados da API Carris Metropolitana"}), 500

        vehicles = rv.json()
        stops = rs.json()

        # 🔹 Agrupar veículos por paragem
        stop_vehicle_map = {}
        for v in vehicles:
            stop_id = v.get("stop_id")
            if not stop_id:
                continue
            stop_vehicle_map.setdefault(stop_id, []).append(v)

        discovered = {}
        for stop in stops:
            sid = stop.get("id")
            if sid in stop_vehicle_map and len(stop_vehicle_map[sid]) == 1:
                v = stop_vehicle_map[sid][0]
                vid = v.get("id")
                route = v.get("route_id")
                
                # 🔹 Aqui é onde poderás introduzir uma heurística
                # Exemplo: usa o nome da paragem se tiver número
                real_number = None
                name = stop.get("name", "")
                for token in name.split():
                    if token.isdigit() and len(token) == 4:
                        real_number = token
                        break

                # 🔹 Se não tiver número no nome, usa apenas o route_id
                if not real_number:
                    real_number = route or "desconhecido"

                if vid:
                    discovered[vid] = {
                        "real_number": real_number,
                        "stop": name,
                        "route": route
                    }

        # 🔹 Atualizar o ficheiro vehicle_map.json
        VEHICLE_MAP.update(discovered)
        with open(VEHICLE_MAP_PATH, "w", encoding="utf-8") as f:
            json.dump(VEHICLE_MAP, f, ensure_ascii=False, indent=2)

        return jsonify({
            "message": "Mapeamento atualizado com sucesso ✅",
            "new_entries": discovered,
            "total_registos": len(VEHICLE_MAP)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)

