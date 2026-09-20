CONSISTENCY QUORUM;
TRACING ON;

-- Q1
SELECT clase, disponibles, ocupados
FROM asientos_contadores_por_vuelo
WHERE codigo_vuelo = 'GT0476-20261204';

-- Q2
SELECT fecha_salida, codigo_vuelo, origen, destino, fila, letra, clase,
       estado_reserva, monto, estado_pago
FROM historial_por_pasajero
WHERE pasajero_id = 44590c5d-8844-4c23-b78a-2d22850234b7
  AND fecha_salida >= '2026-10-01 00:00:00+0000'
  AND fecha_salida <= '2027-03-31 23:59:59+0000'
ORDER BY fecha_salida ASC;

-- Q3
SELECT fila, letra, nombre_pasajero, identificacion, clase,
       estado_reserva, estado_pago
FROM manifiesto_por_vuelo
WHERE codigo_vuelo = 'GT0476-20261204';

-- Q4
SELECT fecha_salida, codigo_vuelo, capacidad, confirmadas
FROM ocupacion_por_ruta_mes
WHERE ruta = 'MIA-LAX' AND mes = '2026-12'
  AND fecha_salida >= '2026-12-01 00:00:00+0000'
  AND fecha_salida <= '2026-12-31 23:59:59+0000';

-- Q5
SELECT codigo_vuelo, ruta, total_centavos
FROM top_vuelos_por_ingresos
WHERE periodo = '2026-10'
LIMIT 5;