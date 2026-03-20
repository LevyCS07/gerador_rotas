import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
import openrouteservice
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

st.set_page_config(layout="wide", page_title="Otimização de Rotas com ORS")

# -----------------------------
# Funções auxiliares
# -----------------------------
def calcular_matriz(coords, client):
    """Calcula matriz de tempo usando ORS"""
    matrix = client.distance_matrix(coords, profile='driving-car', metrics=["duration"])["durations"]
    return matrix

def otimizar_rotas(matrix, num_vehicles, vehicle_capacities, demands, max_time=4800):
    """Resolve VRP com capacidade e tempo máximo"""
    depot = 0
    manager = pywrapcp.RoutingIndexManager(len(matrix), num_vehicles, depot)
    routing = pywrapcp.RoutingModel(manager)

    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(matrix[from_node][to_node])

    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Capacidade
    def demand_callback(from_index):
        return demands[manager.IndexToNode(from_index)]
    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithCapacity(demand_callback_index, 0, vehicle_capacities, True, "Capacity")

    # Tempo máximo
    routing.AddDimension(transit_callback_index, 0, max_time, True, "Time")

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC

    solution = routing.SolveWithParameters(search_parameters)
    rotas = []
    if solution:
        for v in range(num_vehicles):
            index = routing.Start(v)
            plan = []
            while not routing.IsEnd(index):
                plan.append(manager.IndexToNode(index))
                index = solution.Value(routing.NextVar(index))
            plan.append(manager.IndexToNode(index))
            rotas.append(plan)
    return rotas

# -----------------------------
# Upload de dados
# -----------------------------
st.sidebar.header("📂 Upload")
xlsx = st.sidebar.file_uploader("Colaboradores", type=["xlsx"])

# Entrada de capacidades heterogêneas
capacities_input = st.sidebar.text_input("Capacidades dos veículos (separadas por vírgula)", "10,20,15")
vehicle_capacities = [int(x.strip()) for x in capacities_input.split(",") if x.strip().isdigit()]
num_vehicles = len(vehicle_capacities)

max_time = st.sidebar.number_input("Tempo máximo (minutos)", min_value=10, value=80)

if xlsx:
    colaboradores = pd.read_excel(xlsx)
    st.write("### Dados carregados")
    st.dataframe(colaboradores)

    # Coordenadas no formato ORS (lon, lat)
    coords = [(float(row["LONG"]), float(row["LAT"])) for _, row in colaboradores.iterrows()]
    coords.insert(0, coords[0])  # depot = primeiro ponto

    # Usa a chave guardada em Secrets
    client = openrouteservice.Client(key=st.secrets["ORS_API_KEY"])
    matrix = calcular_matriz(coords, client)

    # Demanda: cada colaborador = 1
    demands = [0] + [1] * (len(coords) - 1)

    if st.sidebar.button("🚀 Otimizar distribuição"):
        rotas = otimizar_rotas(matrix, num_vehicles, vehicle_capacities, demands, max_time*60)
        st.write("### Rotas otimizadas")
        for i, rota in enumerate(rotas):
            st.write(f"Veículo {i+1} (capacidade {vehicle_capacities[i]}): {rota}")

        # Mapa
        m = folium.Map(location=[-3.119, -60.021], zoom_start=12)
        cluster = MarkerCluster().add_to(m)
        for _, row in colaboradores.iterrows():
            folium.Marker(
                location=[row["LAT"], row["LONG"]],
                popup=row["COLABORADORES"],
                icon=folium.Icon(color="blue")
            ).add_to(cluster)
        st_folium(m, width=1200, height=700)
