from flask import Flask, render_template, request, jsonify
import requests
import math
import time
from datetime import datetime, timedelta
import zipfile, io, csv

app = Flask(__name__, static_folder="static", template_folder="templates")

BASE_API = "https://api.carrismetropolitana.pt/v1"
HEADERS = {"User-Agent": "Mozilla/5.0"}

stops_cache = {"timestamp":0, "data":[]}

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2-lat1)
    dlambda = math.radians(lon2-lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R*c

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/nearby_stops")
def nearby_stops():
    try:
        lat=float(request.args.get("lat"))
        lon=float(request.args.get("lon"))
        line=request.args.get("line","").strip()
    except:
        return jsonify({"error":"Parâmetros inválidos"}),400
    global stops_cache
    now=time.time()
    if not stops_cache["data"] or now - stops_cache["timestamp"] > 600:
        r=requests.get(f"{BASE_API}/stops", headers=HEADERS, timeout=30)
        if r.status_code != 200:
            return jsonify({"error":"Erro a obter paragens"}),500
        stops_cache["data"]=r.json()
        stops_cache["timestamp"]=now
    stops=stops_cache["data"]
    candidates=[]
    for s in stops:
        lines=s.get("lines") or []
        if line=="" or any(line.lower() in str(li).lower() for li in lines):
            d=haversine(lat,lon,float(s.get("lat")),float(s.get("lon")))
            candidates.append({
                "id":s.get("id"),
                "name":s.get("name"),
                "lat":float(s.get("lat")),
                "lon":float(s.get("lon")),
                "distance_m":int(d),
                "lines":lines
            })
    candidates.sort(key=lambda x:x["distance_m"])
    return jsonify(candidates[:7])

@app.route("/api/arrival")
def arrival():
    stop_id=request.args.get("stop_id")
    line=request.args.get("line","").strip()
    if not stop_id:
        return jsonify({"error":"stop_id é obrigatório"}),400
    rv=requests.get(f"{BASE_API}/vehicles", headers=HEADERS, timeout=30)
    vehicles=rv.json() if rv.status_code==200 else []
    rs=requests.get(f"{BASE_API}/stops/{stop_id}", headers=HEADERS, timeout=30)
    if rs.status_code!=200:
        return jsonify({"error":"Paragem não encontrada"}),404
    stop=rs.json()
    stop_lat, stop_lon=float(stop.get("lat")),float(stop.get("lon"))
    matches=[]
    for v in vehicles:
        trip=v.get("trip_id","")
        pattern=v.get("pattern_id","")
        route=v.get("route_id","")
        if line=="" or any(line.lower() in str(x).lower() for x in [trip,pattern,route]):
            veh_lat=v.get("lat") or stop_lat
            veh_lon=v.get("lon") or stop_lon
            speed=v.get("speed") or 0.0
            speed_m_s=speed*1000/3600 if speed>40 else float(speed)
            dist=haversine(stop_lat,stop_lon,veh_lat,veh_lon)
            if speed_m_s>0.5:
                eta_seconds=dist/speed_m_s
                matches.append({
                    "vehicle_id":v.get("id"),
                    "distance_m":int(dist),
                    "eta_minutes":round(eta_seconds/60,1),
                    "lat":veh_lat,
                    "lon":veh_lon
                })
    matches.sort(key=lambda x:x["distance_m"])
    if matches:
        return jsonify({"type":"realtime","stop":stop,"vehicles":matches[:5]})
    # fallback GTFS
    try:
        g=requests.get(f"{BASE_API}/gtfs", headers=HEADERS, timeout=60)
        if g.status_code==200:
            z=zipfile.ZipFile(io.BytesIO(g.content))
            stop_times=[]
            with z.open("stop_times.txt") as f:
                reader=csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
                for row in reader:
                    if row.get("stop_id")==stop_id:
                        stop_times.append(row)
            now=datetime.now()
            results=[]
            for st in stop_times:
                arrival=st.get("arrival_time")
                try:
                    h,m,s=[int(x) for x in arrival.split(":")]
                    arr_dt=now.replace(hour=h%24, minute=m, second=s, microsecond=0)
                    if h>=24: arr_dt+=timedelta(days=1)
                    if arr_dt<now: continue
                    diff=(arr_dt-now).total_seconds()
                    results.append(int(diff))
                except: continue
            results.sort()
            if results:
                sched=[{"eta_seconds":r,"eta_minutes":round(r/60,1)} for r in results[:5]]
                return jsonify({"type":"schedule","stop":stop,"scheduled":sched})
    except:
        pass
    return jsonify({"type":"none","stop":stop,"message":"Sem dados em tempo real. Tenta mais tarde."})

if __name__=="__main__":
    app.run(debug=True, port=5000)



