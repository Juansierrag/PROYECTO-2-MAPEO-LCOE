# 1. Pon aquí tus 12 valores de (T + D + PR + R + Cv_negociado) en COP/kWh
# Estos son valores de ejemplo, debes reemplazarlos con los tuyos de enero a diciembre.
valores_mensuales = [
    700.9069, # Mes 1: septiembre
    694.5416, # Mes 2: octubre
    678.8596, # Mes 3: noviembre
    656.538, # Mes 4: diciembre
    605.4569, # Mes 5: enero
    685.9857, # Mes 6: febrero
    671.5034, # Mes 7: marzo
    677.3741, # Mes 8: abril
    701.6864, # Mes 9: mayo
    718.3759, # Mes 10: junio
    738.3181, # Mes 11: julio
    721.4679  # Mes 12: agosto
]

# 2. Definir los días de cada mes 
# ATENCIÓN: El modelo original de Gurobi que tienes usa 8760 horas (T = range(1, 8761)).
# Por lo tanto, usaremos 28 días para febrero para que la suma cuadre exacto en 8760.
dias_por_mes = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

nombre_archivo = 'psi_colombia.inc'
hora_actual = 1

print("Generando el archivo de cargos de red mensuales (con 4 decimales)...")

# 3. Crear el archivo .inc
with open(nombre_archivo, 'w', encoding='utf-8') as f:
    for mes in range(12):
        valor_del_mes = valores_mensuales[mes]
        horas_del_mes = dias_por_mes[mes] * 24
        
        # Escribe el mismo valor para todas las horas de ese mes con 4 decimales
        for _ in range(horas_del_mes):
            f.write(f"t{hora_actual} {valor_del_mes:.4f}\n")
            hora_actual += 1

print(f"¡Listo! Se ha creado el archivo '{nombre_archivo}' exitosamente con {hora_actual - 1} horas.")