-- =====================================================================
-- 03_consultas.cql
-- Las 5 consultas del negocio. Ninguna usa ALLOW FILTERING ni JOIN.
-- Ejecutar en cqlsh:  docker exec -it cass1 cqlsh
-- Cada consulta se ejecuta con TRACING ON para documentar el plan de
-- ejecucion (nodos contactados, SSTables leidas, tiempo por paso).
-- =====================================================================

USE aerolinea;
CONSISTENCY QUORUM;
TRACING ON;

-- ---------------------------------------------------------------------
-- Q1. Disponibilidad de asientos por clase (un vuelo)
-- Tabla: asientos_contadores_por_vuelo   Parametro: codigo_vuelo
-- Resultado esperado para GT0476-20261204: 3 filas (economica, ejecutiva,
-- primera) y la suma de 'ocupados' es 99 con los datos de la carga base.
-- ---------------------------------------------------------------------
SELECT clase, disponibles, ocupados
FROM asientos_contadores_por_vuelo
WHERE codigo_vuelo = 'GT0476-20261204';

-- ---------------------------------------------------------------------
-- Q2. Historial cronologico de un pasajero en un rango de fechas
-- Tabla: historial_por_pasajero   Parametros: pasajero_id, rango de fechas
-- Los UUID cambian en cada carga. Obtén uno con reservas:
--     SELECT pasajero_id FROM historial_por_pasajero LIMIT 1;
-- y reemplaza <PASAJERO_ID> (sin comillas) en la consulta de abajo.
-- ---------------------------------------------------------------------
SELECT fecha_salida, codigo_vuelo, origen, destino, fila, letra, clase,
       estado_reserva, monto, estado_pago
FROM historial_por_pasajero
WHERE pasajero_id = <PASAJERO_ID>
  AND fecha_salida >= '2026-10-01 00:00:00+0000'
  AND fecha_salida <= '2027-03-31 23:59:59+0000'
ORDER BY fecha_salida ASC;

-- ---------------------------------------------------------------------
-- Q3. Manifiesto de vuelo ordenado y enriquecido
-- Tabla: manifiesto_por_vuelo   Parametro: codigo_vuelo
-- Ordenado por asiento (fila, letra); incluye clase, estado de la
-- reserva y estado del pago. Esperado: 99 filas para GT0476-20261204.
-- ---------------------------------------------------------------------
SELECT fila, letra, nombre_pasajero, identificacion, clase,
       estado_reserva, estado_pago
FROM manifiesto_por_vuelo
WHERE codigo_vuelo = 'GT0476-20261204';

-- ---------------------------------------------------------------------
-- Q4. Porcentaje de ocupacion por ruta y rango de fechas
-- Tabla: ocupacion_por_ruta_mes   Parametros: ruta, mes, rango de fechas
-- porcentaje = confirmadas * 100 / capacidad
-- Esperado para MIA-LAX en 2026-12: vuelo GT0476-20261204,
-- capacidad 120, confirmadas 82 -> 68.33 %.
-- Si el rango cruza varios meses, se ejecuta una consulta por cada mes.
-- ---------------------------------------------------------------------
SELECT fecha_salida, codigo_vuelo, capacidad, confirmadas
FROM ocupacion_por_ruta_mes
WHERE ruta = 'MIA-LAX'
  AND mes = '2026-12'
  AND fecha_salida >= '2026-12-01 00:00:00+0000'
  AND fecha_salida <= '2026-12-31 23:59:59+0000';

-- ---------------------------------------------------------------------
-- Q5. Top N de vuelos por ingresos generados
-- Tabla: top_vuelos_por_ingresos   Parametros: periodo (mes), N
-- Clustering DESC por total_centavos: LIMIT N ya devuelve los mayores.
-- Esperado en 2026-10: 1) GT0686-20261027 con 5696148 centavos,
-- 2) GT0539-20261025 con 5569938, 3) GT0462-20261003 con 5562809.
-- Para varios meses: una consulta por mes con LIMIT N y se mezclan.
-- ---------------------------------------------------------------------
SELECT codigo_vuelo, ruta, total_centavos
FROM top_vuelos_por_ingresos
WHERE periodo = '2026-10'
LIMIT 5;

TRACING OFF;
