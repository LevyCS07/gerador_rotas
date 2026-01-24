import streamlit as st
import folium
from streamlit_folium import st_folium
import json, requests
from shapely.geometry import Point, shape
from math import sqrt
import streamlit as st

# Configuração Gemini
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# Carregar bairros
with open("BAIRROS_MANAUS.geojson", encoding="utf-8") as f:
    bairros_geo = json.load(f)

BAIRROS = [{"nome": feat["properties"].get("NOME") or feat["properties"].get("bairro"),
            "shape": shape(feat["geometry"])} for feat in bairros_geo["features"]]

CAP_MIN = {15: 11, 22: 16, 32: 23, 44: 32}

def bairro_de_ponto(coord):
    p = Point(coord[1], coord[0])
    for b in BAIRROS:
        if b["shape"].contains(p):
            return b["nome"]
    return "DESCONHECIDO"

def dist(a, b): return sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)

def criar_rotas(pontos, destino, capacidade):
    minimo = CAP_MIN[capacidade]
    for p in pontos:
        p["bairro"] = bairro_de_ponto(p["coord"])
        p["usado"] = False
    rotas, rota_id = [], 1
    while any(not p["usado"] for p in pontos):
        candidatos = [p for p in pontos if not p["usado"]]
        start = max(candidatos, key=lambda p: dist(p["coord"], destino))
        rota = {"id": f"Rota {rota_id}", "pontos": [start], "destino": destino,
                "capacidade": capacidade, "bairro_base": start["bairro"]}
        start["usado"] = True
        while True:
            livres = [p for p in pontos if not p["usado"]]
            if not livres or len(rota["pontos"]) >= capacidade: break
            melhor = min(livres, key=lambda p: dist(rota["pontos"][-1]["coord"], p["coord"]))
            rota["pontos"].append(melhor); melhor["usado"] = True
        rotas.append(rota); rota_id += 1
    return rotas

def chamar_gemini(pontos, capacidade, destino, rotas_algoritmo):
    prompt = f"""
    Você é um planejador de rotas. Avalie as rotas calculadas pelo algoritmo:
    Rotas: {rotas_algoritmo}
    Pontos: {pontos}
    Capacidade: {capacidade}
    Destino: {destino}
    Sugira melhorias ou confirme se estão adequadas.
    """
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    res = requests.post(GEMINI_URL,
        headers={"X-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
        json=body)
    data = res.json()
    try:
       if "candidates" in data and len(data["candidates"]) > 0:
    parts = data["candidates"][0].get("content", {}).get("parts", [])
    if parts and "text" in parts[0]:
        return parts[0]["text"]
return f"Erro na resposta do Gemini: {data}"


# ---------------- UI ----------------
st.title("RotaSmart AI 🚐")
pontos_txt = st.text_area("Colaboradores (COLAB;LAT;LON)")
capacidade = st.selectbox("Capacidade", [15,22,32,44])
destino_txt = st.text_input("Destino (LAT,LON)")

if st.button("Simular"):
    pontos = []
    for linha in pontos_txt.splitlines():
        partes = linha.split(";")
        if len(partes) >= 3:
            pontos.append({"nome": partes[0], "coord": [float(partes[1]), float(partes[2])]})
    destino = [float(x) for x in destino_txt.split(",")]
    rotas = criar_rotas(pontos, destino, capacidade)
    for r in rotas:
        for p in r["pontos"]: p.pop("usado", None)
    analise = chamar_gemini(pontos, capacidade, destino, rotas)

    st.subheader("Análise Gemini")
    st.write(analise)

    st.subheader("Mapa das Rotas")
    m = folium.Map(location=destino, zoom_start=12)
    colors = ["red","blue","green","purple","orange","brown","pink","cyan"]
    for idx, rota in enumerate(rotas):
        coords = [p["coord"] for p in rota["pontos"]] + [rota["destino"]]
        folium.PolyLine(coords, color=colors[idx%len(colors)], weight=4).add_to(m)
        for p in rota["pontos"]:
            folium.Marker(p["coord"], popup=p["nome"]).add_to(m)
    st_folium(m, width=700, height=500)


