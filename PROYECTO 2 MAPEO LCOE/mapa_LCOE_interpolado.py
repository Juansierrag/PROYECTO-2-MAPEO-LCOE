"""
======================================================================
MAPA INTERPOLADO DE LCOE - COLOMBIA
======================================================================

Este script permite generar el mapa de cualquiera de estas columnas:

    LCOEnet
    LCOEgross

La variable se selecciona en:

    VARIABLE_MAPA = "LCOEnet"

Entrada:
    resultados_coordenadas.csv

Columnas necesarias:
    Latitud
    Longitud
    LCOEnet / LCOEgross

Salida:
    mapa_LCOEnet_interpolado.html

El script:
    1. Lee resultados_coordenadas.csv
    2. Extrae las coordenadas y la variable seleccionada
    3. Interpola mediante IDW
    4. Recorta la interpolación al territorio de Colombia
    5. Dibuja los puntos calculados
    6. Muestra la escala cromática a la derecha

No ejecuta PVGIS ni Gurobi.
======================================================================
"""

import os
import csv
import json
import requests

import numpy as np
import pandas as pd

from scipy.spatial import cKDTree

import plotly.graph_objects as go

from shapely.geometry import shape, box, Polygon, MultiPolygon
from shapely.ops import unary_union


# =====================================================================
# CONFIGURACIÓN PRINCIPAL
# =====================================================================

ARCHIVO_CSV = "resultados_coordenadas.csv"

# ============================================================
# CAMBIAR SOLO ESTA VARIABLE PARA GENERAR OTRO MAPA
# ============================================================

VARIABLE_MAPA = "LCOEnet"

# Opciones:
#
# VARIABLE_MAPA = "LCOEnet"
# VARIABLE_MAPA = "LCOEgross"


# =====================================================================
# NOMBRES AUTOMÁTICOS DE SALIDA
# =====================================================================

ARCHIVO_SALIDA = (
    f"mapa_{VARIABLE_MAPA}_interpolado.html"
)


# =====================================================================
# GEOMETRÍA DE COLOMBIA
# =====================================================================

ARCHIVO_COLOMBIA = "colombia.geojson"

URL_COLOMBIA = (
    "https://raw.githubusercontent.com/"
    "johan/world.geo.json/master/countries/COL.geo.json"
)


# =====================================================================
# LÍMITES DE VISUALIZACIÓN
# =====================================================================

LAT_MIN = -4.5
LAT_MAX = 13.5

LON_MIN = -79.5
LON_MAX = -66.5


# =====================================================================
# INTERPOLACIÓN IDW
# =====================================================================

N_GRID = 180

IDW_POWER = 2.0

N_VECINOS = 12

RADIO_MAXIMO = 2.0


# =====================================================================
# VISUALIZACIÓN
# =====================================================================

OPACIDAD = 0.85

TAMANO_PUNTOS = 5


# =====================================================================
# ESCALA DE COLORES
# =====================================================================

COLORES = [
    [0.000, "rgb(48,18,59)"],
    [0.125, "rgb(50,75,156)"],
    [0.250, "rgb(35,139,187)"],
    [0.375, "rgb(31,191,130)"],
    [0.500, "rgb(121,209,81)"],
    [0.625, "rgb(229,220,50)"],
    [0.750, "rgb(250,155,45)"],
    [0.875, "rgb(231,66,53)"],
    [1.000, "rgb(122,4,3)"],
]


# =====================================================================
# VALIDACIÓN DE CONFIGURACIÓN
# =====================================================================

VARIABLES_PERMITIDAS = [
    "LCOEnet",
    "LCOEgross"
]

if VARIABLE_MAPA not in VARIABLES_PERMITIDAS:

    raise ValueError(
        "\nVARIABLE_MAPA debe ser una de estas opciones:\n"
        f"{VARIABLES_PERMITIDAS}\n"
        f"Valor recibido: {VARIABLE_MAPA}"
    )


# =====================================================================
# COLOR
# =====================================================================

def color_interpolado(
    valor,
    minimo,
    maximo
):

    if maximo == minimo:

        return COLORES[
            len(COLORES) // 2
        ][1]

    t = (
        float(valor) - minimo
    ) / (
        maximo - minimo
    )

    t = max(
        0.0,
        min(
            1.0,
            t
        )
    )

    for i in range(
        len(COLORES) - 1
    ):

        p1 = COLORES[i][0]
        c1 = COLORES[i][1]

        p2 = COLORES[i + 1][0]
        c2 = COLORES[i + 1][1]

        if p1 <= t <= p2:

            rgb1 = tuple(
                int(x)
                for x in (
                    c1
                    .replace("rgb(", "")
                    .replace(")", "")
                    .split(",")
                )
            )

            rgb2 = tuple(
                int(x)
                for x in (
                    c2
                    .replace("rgb(", "")
                    .replace(")", "")
                    .split(",")
                )
            )

            if p2 == p1:

                proporcion = 0.0

            else:

                proporcion = (
                    t - p1
                ) / (
                    p2 - p1
                )

            r = int(
                rgb1[0]
                +
                proporcion
                *
                (
                    rgb2[0]
                    -
                    rgb1[0]
                )
            )

            g = int(
                rgb1[1]
                +
                proporcion
                *
                (
                    rgb2[1]
                    -
                    rgb1[1]
                )
            )

            b = int(
                rgb1[2]
                +
                proporcion
                *
                (
                    rgb2[2]
                    -
                    rgb1[2]
                )
            )

            return (
                f"rgb({r},{g},{b})"
            )

    return COLORES[-1][1]


# =====================================================================
# CARGAR GEOMETRÍA DE COLOMBIA
# =====================================================================

def cargar_colombia():

    print(
        "\n"
        + "=" * 70
    )

    print(
        "1. CARGANDO GEOMETRÍA DE COLOMBIA"
    )

    print(
        "=" * 70
    )

    if not os.path.exists(
        ARCHIVO_COLOMBIA
    ):

        print(
            "\nNo existe el archivo:"
        )

        print(
            ARCHIVO_COLOMBIA
        )

        print(
            "\nDescargando geometría..."
        )

        respuesta = requests.get(
            URL_COLOMBIA,
            timeout=30
        )

        respuesta.raise_for_status()

        with open(
            ARCHIVO_COLOMBIA,
            "wb"
        ) as archivo:

            archivo.write(
                respuesta.content
            )

        print(
            "GeoJSON descargado correctamente."
        )

    else:

        print(
            "\nGeoJSON local encontrado."
        )

    with open(
        ARCHIVO_COLOMBIA,
        "r",
        encoding="utf-8"
    ) as archivo:

        geojson = json.load(
            archivo
        )

    tipo = geojson.get(
        "type"
    )

    if tipo in [
        "Polygon",
        "MultiPolygon"
    ]:

        colombia = shape(
            geojson
        )

    elif tipo == "Feature":

        colombia = shape(
            geojson["geometry"]
        )

    elif tipo == "FeatureCollection":

        geometrias = []

        for feature in geojson.get(
            "features",
            []
        ):

            geometria = feature.get(
                "geometry"
            )

            if geometria is None:
                continue

            try:

                geom = shape(
                    geometria
                )

                if not geom.is_empty:

                    geometrias.append(
                        geom
                    )

            except Exception:
                continue

        if not geometrias:

            raise ValueError(
                "No se encontraron geometrías válidas."
            )

        colombia = unary_union(
            geometrias
        )

    else:

        raise ValueError(
            f"Tipo GeoJSON no soportado: {tipo}"
        )

    if not colombia.is_valid:

        colombia = colombia.buffer(
            0
        )

    if colombia.is_empty:

        raise ValueError(
            "La geometría de Colombia está vacía."
        )

    minx, miny, maxx, maxy = (
        colombia.bounds
    )

    print(
        f"\nLongitud: {minx:.4f} → {maxx:.4f}"
    )

    print(
        f"Latitud:   {miny:.4f} → {maxy:.4f}"
    )

    return colombia


# =====================================================================
# DETECTAR SEPARADOR
# =====================================================================

def detectar_separador(
    archivo
):

    with open(
        archivo,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        muestra = f.read(
            10000
        )

    try:

        dialecto = csv.Sniffer().sniff(
            muestra,
            delimiters=",;"
        )

        return dialecto.delimiter

    except csv.Error:

        primera_linea = (
            muestra.splitlines()[0]
        )

        if ";" in primera_linea:

            return ";"

        return ","


# =====================================================================
# NORMALIZAR COLUMNA
# =====================================================================

def normalizar_nombre_columna(
    nombre
):

    return (
        str(nombre)
        .strip()
        .replace(
            "\ufeff",
            ""
        )
    )


# =====================================================================
# CONVERTIR A NÚMERO
# =====================================================================

def convertir_numero(
    valor
):

    if valor is None:

        return np.nan

    texto = str(
        valor
    ).strip()

    if texto == "":

        return np.nan

    texto = texto.replace(
        "\xa0",
        ""
    )

    # Decimal con coma
    if (
        "," in texto
        and
        "." not in texto
    ):

        texto = texto.replace(
            ",",
            "."
        )

    # Formato 1.234,56
    elif (
        "," in texto
        and
        "." in texto
    ):

        if (
            texto.rfind(",")
            >
            texto.rfind(".")
        ):

            texto = texto.replace(
                ".",
                ""
            )

            texto = texto.replace(
                ",",
                "."
            )

    try:

        return float(
            texto
        )

    except ValueError:

        return np.nan


# =====================================================================
# CARGAR DATOS
# =====================================================================

def cargar_datos():

    print(
        "\n"
        + "=" * 70
    )

    print(
        "2. CARGANDO RESULTADOS"
    )

    print(
        "=" * 70
    )

    print(
        f"\nVariable seleccionada: {VARIABLE_MAPA}"
    )

    if not os.path.exists(
        ARCHIVO_CSV
    ):

        raise FileNotFoundError(
            f"No se encontró:\n"
            f"{os.path.abspath(ARCHIVO_CSV)}"
        )

    separador = detectar_separador(
        ARCHIVO_CSV
    )

    print(
        f"Separador detectado: "
        f"{repr(separador)}"
    )

    filas = []

    filas_defectuosas = 0

    encabezado = None

    indice_latitud = None
    indice_longitud = None
    indice_variable = None

    with open(
        ARCHIVO_CSV,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as archivo:

        lector = csv.reader(
            archivo,
            delimiter=separador
        )

        for numero_fila, fila in enumerate(
            lector,
            start=1
        ):

            if not fila:
                continue

            # ---------------------------------------------------------
            # ENCABEZADO
            # ---------------------------------------------------------

            if encabezado is None:

                encabezado = [
                    normalizar_nombre_columna(
                        x
                    )
                    for x in fila
                ]

                print(
                    "\nColumnas detectadas:"
                )

                print(
                    encabezado
                )

                nombres = {
                    nombre.lower(): indice
                    for indice, nombre
                    in enumerate(encabezado)
                }

                indice_latitud = nombres.get(
                    "latitud"
                )

                indice_longitud = nombres.get(
                    "longitud"
                )

                indice_variable = nombres.get(
                    VARIABLE_MAPA.lower()
                )

                if indice_latitud is None:

                    raise ValueError(
                        "No se encontró la columna "
                        "'Latitud'."
                    )

                if indice_longitud is None:

                    raise ValueError(
                        "No se encontró la columna "
                        "'Longitud'."
                    )

                if indice_variable is None:

                    raise ValueError(
                        f"No se encontró la columna "
                        f"'{VARIABLE_MAPA}'.\n\n"
                        "Columnas disponibles:\n"
                        f"{encabezado}"
                    )

                continue

            # ---------------------------------------------------------
            # DATOS
            # ---------------------------------------------------------

            indice_maximo = max(
                indice_latitud,
                indice_longitud,
                indice_variable
            )

            if len(fila) <= indice_maximo:

                filas_defectuosas += 1
                continue

            filas.append(
                {
                    "Latitud":
                        convertir_numero(
                            fila[
                                indice_latitud
                            ]
                        ),

                    "Longitud":
                        convertir_numero(
                            fila[
                                indice_longitud
                            ]
                        ),

                    VARIABLE_MAPA:
                        convertir_numero(
                            fila[
                                indice_variable
                            ]
                        )
                }
            )

    if not filas:

        raise ValueError(
            "No se encontraron datos válidos."
        )

    df = pd.DataFrame(
        filas
    )

    print(
        f"\nFilas leídas: {len(df)}"
    )

    if filas_defectuosas > 0:

        print(
            "Filas con estructura insuficiente "
            f"ignoradas: {filas_defectuosas}"
        )

    # ---------------------------------------------------------------
    # Eliminar NaN
    # ---------------------------------------------------------------

    df = df.dropna(
        subset=[
            "Latitud",
            "Longitud",
            VARIABLE_MAPA
        ]
    ).copy()

    # ---------------------------------------------------------------
    # Eliminar infinitos
    # ---------------------------------------------------------------

    df = df[
        np.isfinite(
            df["Latitud"]
        )
        &
        np.isfinite(
            df["Longitud"]
        )
        &
        np.isfinite(
            df[VARIABLE_MAPA]
        )
    ].copy()

    # ---------------------------------------------------------------
    # Coordenadas válidas
    # ---------------------------------------------------------------

    df = df[
        (df["Latitud"] >= -90)
        &
        (df["Latitud"] <= 90)
        &
        (df["Longitud"] >= -180)
        &
        (df["Longitud"] <= 180)
    ].copy()

    # ---------------------------------------------------------------
    # Eliminar duplicados
    # ---------------------------------------------------------------

    duplicados = df.duplicated(
        subset=[
            "Latitud",
            "Longitud"
        ]
    ).sum()

    if duplicados > 0:

        print(
            f"Duplicados eliminados: "
            f"{duplicados}"
        )

        df = df.drop_duplicates(
            subset=[
                "Latitud",
                "Longitud"
            ]
        )

    df = df.reset_index(
        drop=True
    )

    # ---------------------------------------------------------------
    # Validación
    # ---------------------------------------------------------------

    if len(df) < 3:

        raise ValueError(
            "\nSe necesitan al menos 3 puntos válidos.\n"
            f"Solo se encontraron {len(df)}."
        )

    # ---------------------------------------------------------------
    # Resumen
    # ---------------------------------------------------------------

    print(
        f"\nPUNTOS VÁLIDOS: {len(df)}"
    )

    print(
        f"\nRango de {VARIABLE_MAPA}:"
    )

    print(
        f"Mínimo: "
        f"{df[VARIABLE_MAPA].min():.6f}"
    )

    print(
        f"Máximo: "
        f"{df[VARIABLE_MAPA].max():.6f}"
    )

    print(
        f"Promedio: "
        f"{df[VARIABLE_MAPA].mean():.6f}"
    )

    print(
        "\nPrimeros puntos:"
    )

    print(
        df.head(10).to_string(
            index=False
        )
    )

    return df


# =====================================================================
# INTERPOLADOR IDW
# =====================================================================

class InterpoladorIDW:

    def __init__(
        self,
        df
    ):

        self.latitudes = (
            df["Latitud"].to_numpy(
                dtype=float
            )
        )

        self.longitudes = (
            df["Longitud"].to_numpy(
                dtype=float
            )
        )

        self.valores = (
            df[VARIABLE_MAPA].to_numpy(
                dtype=float
            )
        )

        puntos = np.column_stack(
            (
                self.latitudes,
                self.longitudes
            )
        )

        self.tree = cKDTree(
            puntos
        )

    def calcular(
        self,
        lat,
        lon
    ):

        k = min(
            N_VECINOS,
            len(self.valores)
        )

        distancia, indices = (
            self.tree.query(
                [
                    lat,
                    lon
                ],
                k=k
            )
        )

        distancia = np.atleast_1d(
            distancia
        )

        indices = np.atleast_1d(
            indices
        )

        # Punto exacto
        if np.any(
            distancia < 1e-12
        ):

            indice = np.argmin(
                distancia
            )

            return float(
                self.valores[
                    indices[indice]
                ]
            )

        # Radio máximo
        if RADIO_MAXIMO is not None:

            if (
                np.min(distancia)
                >
                RADIO_MAXIMO
            ):

                return np.nan

        # IDW
        pesos = (
            1.0
            /
            np.power(
                distancia,
                IDW_POWER
            )
        )

        suma = np.sum(
            pesos
        )

        if suma <= 0:

            return np.nan

        return float(
            np.sum(
                pesos
                *
                self.valores[
                    indices
                ]
            )
            /
            suma
        )


# =====================================================================
# GEOMETRÍA → COORDENADAS
# =====================================================================

def geometria_a_coordenadas(
    geometria
):

    if geometria.is_empty:

        return [], []

    if isinstance(
        geometria,
        Polygon
    ):

        lats = []
        lons = []

        for lon, lat in (
            geometria.exterior.coords
        ):

            lons.append(
                lon
            )

            lats.append(
                lat
            )

        for interior in (
            geometria.interiors
        ):

            lons.append(
                None
            )

            lats.append(
                None
            )

            for lon, lat in (
                interior.coords
            ):

                lons.append(
                    lon
                )

                lats.append(
                    lat
                )

        return lats, lons

    if isinstance(
        geometria,
        MultiPolygon
    ):

        lats = []
        lons = []

        for poligono in (
            geometria.geoms
        ):

            lats_p, lons_p = (
                geometria_a_coordenadas(
                    poligono
                )
            )

            if lats_p:

                if lats:

                    lats.append(
                        None
                    )

                    lons.append(
                        None
                    )

                lats.extend(
                    lats_p
                )

                lons.extend(
                    lons_p
                )

        return lats, lons

    if hasattr(
        geometria,
        "geoms"
    ):

        lats = []
        lons = []

        for geom in (
            geometria.geoms
        ):

            lats_g, lons_g = (
                geometria_a_coordenadas(
                    geom
                )
            )

            if lats_g:

                if lats:

                    lats.append(
                        None
                    )

                    lons.append(
                        None
                    )

                lats.extend(
                    lats_g
                )

                lons.extend(
                    lons_g
                )

        return lats, lons

    return [], []


# =====================================================================
# CREAR MALLA
# =====================================================================

def crear_malla(
    colombia,
    interpolador
):

    print(
        "\n"
        + "=" * 70
    )

    print(
        "3. CREANDO MALLA DE INTERPOLACIÓN"
    )

    print(
        "=" * 70
    )

    minx, miny, maxx, maxy = (
        colombia.bounds
    )

    lon_min = max(
        minx,
        LON_MIN
    )

    lon_max = min(
        maxx,
        LON_MAX
    )

    lat_min = max(
        miny,
        LAT_MIN
    )

    lat_max = min(
        maxy,
        LAT_MAX
    )

    longitudes = np.linspace(
        lon_min,
        lon_max,
        N_GRID + 1
    )

    latitudes = np.linspace(
        lat_min,
        lat_max,
        N_GRID + 1
    )

    celdas = []
    valores = []

    total = (
        N_GRID
        *
        N_GRID
    )

    contador = 0

    print(
        f"\nCeldas totales: {total}"
    )

    for i in range(
        N_GRID
    ):

        for j in range(
            N_GRID
        ):

            x1 = longitudes[j]
            x2 = longitudes[j + 1]

            y1 = latitudes[i]
            y2 = latitudes[i + 1]

            celda = box(
                x1,
                y1,
                x2,
                y2
            )

            if not celda.intersects(
                colombia
            ):

                continue

            recorte = (
                celda.intersection(
                    colombia
                )
            )

            if recorte.is_empty:

                continue

            centro = (
                recorte.centroid
            )

            valor = (
                interpolador.calcular(
                    centro.y,
                    centro.x
                )
            )

            if not np.isfinite(
                valor
            ):

                continue

            celdas.append(
                recorte
            )

            valores.append(
                valor
            )

            contador += 1

    print(
        f"Celdas interpoladas: "
        f"{contador}"
    )

    if not valores:

        raise ValueError(
            "No se generaron valores interpolados."
        )

    valores = np.asarray(
        valores,
        dtype=float
    )

    return (
        celdas,
        valores
    )


# =====================================================================
# CREAR MAPA
# =====================================================================

def crear_mapa(
    df,
    colombia,
    celdas,
    valores
):

    print(
        "\n"
        + "=" * 70
    )

    print(
        "4. CONSTRUYENDO MAPA"
    )

    print(
        "=" * 70
    )

    minimo = float(
        np.nanmin(
            valores
        )
    )

    maximo = float(
        np.nanmax(
            valores
        )
    )

    fig = go.Figure()

    # ---------------------------------------------------------------
    # INTERPOLACIÓN
    # ---------------------------------------------------------------

    print(
        "\nDibujando interpolación..."
    )

    for celda, valor in zip(
        celdas,
        valores
    ):

        lats, lons = (
            geometria_a_coordenadas(
                celda
            )
        )

        if not lats:
            continue

        color = (
            color_interpolado(
                valor,
                minimo,
                maximo
            )
        )

        fig.add_trace(
            go.Scattergeo(
                lon=lons,
                lat=lats,
                mode="lines",
                fill="toself",
                fillcolor=color,
                line=dict(
                    width=0
                ),
                opacity=OPACIDAD,
                hovertemplate=(
                    f"<b>{VARIABLE_MAPA}</b>: "
                    f"{valor:.6f}"
                    "<extra></extra>"
                ),
                showlegend=False
            )
        )

    # ---------------------------------------------------------------
    # FRONTERA
    # ---------------------------------------------------------------

    lat_col, lon_col = (
        geometria_a_coordenadas(
            colombia
        )
    )

    fig.add_trace(
        go.Scattergeo(
            lon=lon_col,
            lat=lat_col,
            mode="lines",
            line=dict(
                width=2,
                color="black"
            ),
            hoverinfo="skip",
            showlegend=False
        )
    )

    # ---------------------------------------------------------------
    # PUNTOS CALCULADOS
    # ---------------------------------------------------------------

    hover = []

    for _, fila in df.iterrows():

        hover.append(
            "<b>Punto Gurobi</b><br>"
            f"Latitud: "
            f"{fila['Latitud']:.5f}<br>"
            f"Longitud: "
            f"{fila['Longitud']:.5f}<br>"
            f"{VARIABLE_MAPA}: "
            f"{fila[VARIABLE_MAPA]:.6f}"
        )

    fig.add_trace(
        go.Scattergeo(
            lon=df["Longitud"],
            lat=df["Latitud"],
            mode="markers",
            marker=dict(
                size=TAMANO_PUNTOS,
                color="black",
                line=dict(
                    width=0.5,
                    color="white"
                )
            ),
            text=hover,
            hovertemplate=(
                "%{text}"
                "<extra></extra>"
            ),
            name="Puntos Gurobi"
        )
    )

    # ---------------------------------------------------------------
    # ESCALA DE COLOR
    # ---------------------------------------------------------------

    fig.add_trace(
        go.Scattergeo(
            lon=[
                -100,
                -100
            ],
            lat=[
                -30,
                -30
            ],
            mode="markers",
            marker=dict(
                size=0.1,
                color=[
                    minimo,
                    maximo
                ],
                cmin=minimo,
                cmax=maximo,
                colorscale=COLORES,
                showscale=True,
                colorbar=dict(
                    title=dict(
                        text=VARIABLE_MAPA,
                        side="right"
                    ),
                    thickness=22,
                    len=0.70,
                    x=1.02,
                    y=0.50,
                    outlinewidth=1,
                    ticks="outside"
                )
            ),
            hoverinfo="skip",
            showlegend=False
        )
    )

    # ---------------------------------------------------------------
    # CENTRO DE COLOMBIA
    # ---------------------------------------------------------------

    minx, miny, maxx, maxy = (
        colombia.bounds
    )

    centro_lon = (
        minx + maxx
    ) / 2

    centro_lat = (
        miny + maxy
    ) / 2

    # ---------------------------------------------------------------
    # VISTA GEOGRÁFICA
    # ---------------------------------------------------------------

    fig.update_geos(
        projection_type="mercator",

        center=dict(
            lat=centro_lat,
            lon=centro_lon
        ),

        projection_scale=7.0,

        showland=True,

        landcolor="rgb(245,245,245)",

        showcoastlines=True,

        coastlinecolor="black",

        coastlinewidth=1.2,

        showcountries=False,

        showframe=False,

        bgcolor="white"
    )

    # ---------------------------------------------------------------
    # DISEÑO
    # ---------------------------------------------------------------

    fig.update_layout(

        title=dict(
            text=(
                f"{VARIABLE_MAPA} interpolado — Colombia"
            ),
            x=0.47,
            xanchor="center",
            font=dict(
                size=22
            )
        ),

        width=1100,

        height=800,

        margin=dict(
            l=20,
            r=120,
            t=70,
            b=20
        ),

        paper_bgcolor="white",

        plot_bgcolor="white",

        showlegend=False
    )

    return fig


# =====================================================================
# MAIN
# =====================================================================

def main():

    print(
        "\n"
        + "=" * 70
    )

    print(
        "MAPA INTERPOLADO DE COLOMBIA"
    )

    print(
        "=" * 70
    )

    print(
        f"\nVARIABLE: {VARIABLE_MAPA}"
    )

    print(
        f"SALIDA:   {ARCHIVO_SALIDA}"
    )

    # ---------------------------------------------------------------
    # 1. Datos
    # ---------------------------------------------------------------

    df = cargar_datos()

    # ---------------------------------------------------------------
    # 2. Colombia
    # ---------------------------------------------------------------

    colombia = (
        cargar_colombia()
    )

    # ---------------------------------------------------------------
    # 3. IDW
    # ---------------------------------------------------------------

    print(
        "\n"
        + "=" * 70
    )

    print(
        "PREPARANDO INTERPOLADOR IDW"
    )

    print(
        "=" * 70
    )

    interpolador = (
        InterpoladorIDW(
            df
        )
    )

    print(
        f"\nPuntos: {len(df)}"
    )

    print(
        f"Variable: {VARIABLE_MAPA}"
    )

    print(
        f"Potencia IDW: {IDW_POWER}"
    )

    print(
        f"Vecinos: {N_VECINOS}"
    )

    print(
        f"Radio máximo: {RADIO_MAXIMO}"
    )

    # ---------------------------------------------------------------
    # 4. Malla
    # ---------------------------------------------------------------

    celdas, valores = (
        crear_malla(
            colombia,
            interpolador
        )
    )

    # ---------------------------------------------------------------
    # 5. Mapa
    # ---------------------------------------------------------------

    figura = crear_mapa(
        df,
        colombia,
        celdas,
        valores
    )

    # ---------------------------------------------------------------
    # 6. Guardar
    # ---------------------------------------------------------------

    figura.write_html(
        ARCHIVO_SALIDA
    )

    print(
        "\n"
        + "=" * 70
    )

    print(
        "PROCESO COMPLETADO"
    )

    print(
        "=" * 70
    )

    print(
        "\nMapa generado:"
    )

    print(
        os.path.abspath(
            ARCHIVO_SALIDA
        )
    )

    print(
        "\nVariable representada:"
    )

    print(
        VARIABLE_MAPA
    )

    print(
        "\n" + "=" * 70
    )


# =====================================================================
# EJECUCIÓN
# =====================================================================

if __name__ == "__main__":

    main()
