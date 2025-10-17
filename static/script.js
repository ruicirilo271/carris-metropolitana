const status = document.getElementById("status");
const stopsList = document.getElementById("stopsList");
const findBtn = document.getElementById("findBtn");
const lineInput = document.getElementById("line");
const arrivalBox = document.getElementById("arrivalBox");
const arrivalInfo = document.getElementById("arrivalInfo");
const refreshBtn = document.getElementById("refreshArrival");

let chosenStop = null;
let map, stopMarker;
let vehicleMarkers = [];
let vehicleLines = [];
let vehicleTargets = [];

// --- Status Helper ---
function setStatus(t){ status.innerText = t; }

// --- Inicializa o mapa ---
function initMap(lat, lon){
  if(!map){
    map = L.map("map").setView([lat, lon],16);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution:"&copy; OpenStreetMap contributors"
    }).addTo(map);
  } else {
    map.setView([lat, lon],16);
  }
}

// --- Atualiza marcador da paragem ---
function updateStopMarker(lat, lon){
  if(stopMarker) stopMarker.remove();
  stopMarker = L.circleMarker([lat, lon],{
    radius:10,
    color:"#0ff",
    fillColor:"#0ff",
    fillOpacity:1,
    className:"neon-marker"
  }).addTo(map);
}

// --- Atualiza veículos no mapa ---
function updateVehiclesOnMap(vehicles){
  // remove antigos
  vehicleMarkers.forEach(m=>m.remove());
  vehicleLines.forEach(l=>l.remove());
  vehicleMarkers=[]; vehicleLines=[];

  vehicles.forEach(v=>{
    let m=L.circleMarker([v.lat,v.lon],{
      radius:8,color:"#0ff",fillColor:"#0ff",fillOpacity:1,className:"neon-marker"
    }).addTo(map);
    vehicleMarkers.push(m);

    // linha neon
    let line=L.polyline([[v.lat,v.lon],[chosenStop.lat,chosenStop.lon]],{
      color:"#0ff",weight:2,opacity:0.7,dashArray:"4 4"
    }).addTo(map);
    vehicleLines.push(line);
  });
}

// --- Animação dos veículos ---
function animateVehicles(vehicles){
  if(!map || !stopMarker) return;
  vehicleTargets = vehicles.map((v,i)=>{
    const marker = vehicleMarkers[i];
    return {
      marker: marker,
      targetLat: chosenStop.lat,
      targetLon: chosenStop.lon,
      speed: 0.00005 + Math.random()*0.00003
    };
  });
  requestAnimationFrame(stepAnimation);
}

function stepAnimation(){
  let moving=false;
  vehicleTargets.forEach((obj,i)=>{
    const lat=obj.marker.getLatLng().lat;
    const lon=obj.marker.getLatLng().lng;
    const dLat=obj.targetLat-lat;
    const dLon=obj.targetLon-lon;
    const dist=Math.sqrt(dLat*dLat+dLon*dLon);
    if(dist>0.00005){
      moving=true;
      obj.marker.setLatLng([lat + dLat*obj.speed*20, lon + dLon*obj.speed*20]);
      // Atualiza linha
      vehicleLines[i].setLatLngs([[lat + dLat*obj.speed*20, lon + dLon*obj.speed*20],[obj.targetLat,obj.targetLon]]);
    }
  });
  if(moving) requestAnimationFrame(stepAnimation);
}

// --- Escolher paragem ---
function chooseStop(s){
  chosenStop=s;
  arrivalBox.style.display="block";
  arrivalInfo.innerText="A obter estimativa...";
  initMap(s.lat,s.lon);
  updateStopMarker(s.lat,s.lon);
  fetchArrival();
}

// --- Fetch de chegada ---
async function fetchArrival(){
  if(!chosenStop) return;
  const line=lineInput.value.trim();
  arrivalInfo.innerText="A pedir chegada...";
  const r=await fetch(`/api/arrival?stop_id=${encodeURIComponent(chosenStop.id)}&line=${encodeURIComponent(line)}`);
  if(!r.ok){ arrivalInfo.innerText="Erro a obter chegada"; return; }
  const j=await r.json();
  if(j.type==="realtime"){
    arrivalInfo.innerHTML=`<p>Dados em tempo real — veículos próximos:</p>`+
      j.vehicles.map(v=>`<div>Veículo ${v.vehicle_id} — ${v.distance_m} m — ETA ${v.eta_minutes} min</div>`).join("");
    updateVehiclesOnMap(j.vehicles);
    animateVehicles(j.vehicles);
  } else if(j.type==="schedule"){
    arrivalInfo.innerHTML=`<p>Sem veículo em tempo real. Próximos horários (programados):</p>`+
      j.scheduled.map(s=>`<div>ETA ${s.eta_minutes} min</div>`).join("");
  } else {
    arrivalInfo.innerText=j.message||"Sem dados disponíveis";
  }
}

// --- Buscar paragens próximas ---
findBtn.onclick=async ()=>{
  setStatus("A obter a tua localização...");
  arrivalBox.style.display="none";
  stopsList.innerHTML="";
  if(!navigator.geolocation){ setStatus("Geolocation não suportada"); return; }
  navigator.geolocation.getCurrentPosition(async (pos)=>{
    const lat=pos.coords.latitude;
    const lon=pos.coords.longitude;
    const line=lineInput.value.trim();
    setStatus("A procurar paragens próximas...");
    const url=`/api/nearby_stops?lat=${lat}&lon=${lon}&line=${encodeURIComponent(line)}`;
    const r=await fetch(url);
    if(!r.ok){ setStatus("Erro a obter paragens"); return; }
    const stops=await r.json();
    if(!stops.length){ setStatus("Nenhuma paragem encontrada para essa linha nas proximidades."); return; }
    setStatus(`Encontradas ${stops.length} paragens.`);
    stopsList.innerHTML="";
    stops.forEach(s=>{
      const li=document.createElement("li");
      li.innerHTML=`<b>${s.name}</b> — ${s.distance_m} m — linhas: ${s.lines ? s.lines.join(", ") : "—" } <button data-id="${s.id}">Escolher</button>`;
      li.querySelector("button").onclick=()=>chooseStop(s);
      stopsList.appendChild(li);
    });
  }, (err)=>{ setStatus("Não foi possível obter localização: "+err.message); }, {enableHighAccuracy:true,timeout:10000});
}

// --- Atualizar chegada ---
refreshBtn.onclick=fetchArrival;

