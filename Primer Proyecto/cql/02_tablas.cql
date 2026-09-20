-- =====================================================================
-- 02_tablas.cql
-- Modelo logico basado en queries (Query-Driven Modeling)
-- Una tabla por patron de acceso. Sin JOINs y sin ALLOW FILTERING.
-- =====================================================================

USE aerolinea;

-- =====================================================================
-- A) TABLAS DE ENTIDADES (busqueda por identificador)
-- =====================================================================

-- Pasajero. Consulta: datos de un pasajero por su id.
CREATE TABLE IF NOT EXISTS pasajeros_por_id (
    pasajero_id    uuid,
    nombre         text,
    email          text,
    identificacion text,        -- pasaporte o DPI
    telefono       text,        -- text para conservar +502 y ceros iniciales
    nacionalidad   text,
    PRIMARY KEY ((pasajero_id))
);

-- Aeronave. Consulta: datos de una aeronave por su id.
CREATE TABLE IF NOT EXISTS aeronaves_por_id (
    aeronave_id  uuid,
    modelo       text,
    aerolinea    text,
    matricula    text,
    capacidad_max int,
    PRIMARY KEY ((aeronave_id))
);

-- Vuelo. Consulta: datos de un vuelo por su codigo.
-- capacidad y ruta se denormalizan aqui para no consultar Aeronave.
CREATE TABLE IF NOT EXISTS vuelos_por_codigo (
    codigo_vuelo  text,         -- identifica UN vuelo en una fecha, ej. 'GT101-20261005'
    aeronave_id   uuid,
    origen        text,
    destino       text,
    ruta          text,         -- 'GUA-MIA'
    fecha_salida  timestamp,
    fecha_llegada timestamp,
    estado        text,         -- programado | retrasado | cancelado | completado
    capacidad     int,
    PRIMARY KEY ((codigo_vuelo))
);

-- Asiento. Consulta: todos los asientos de un vuelo, ordenados.
-- fila (int) + letra (text) en vez de '12A' para que ordene 2A antes que 10A.
CREATE TABLE IF NOT EXISTS asientos_por_vuelo (
    codigo_vuelo text,
    fila         int,
    letra        text,
    clase        text,          -- economica | ejecutiva | primera
    estado       text,          -- disponible | ocupado | bloqueado
    reserva_id   uuid,          -- null si esta disponible
    PRIMARY KEY ((codigo_vuelo), fila, letra)
);

-- Reserva. Consulta: una reserva por id (base para cancelar/modificar).
CREATE TABLE IF NOT EXISTS reservas_por_id (
    reserva_id     uuid,
    pasajero_id    uuid,
    codigo_vuelo   text,
    fila           int,
    letra          text,
    clase          text,
    fecha_reserva  timestamp,
    estado         text,        -- pendiente | confirmada | cancelada
    PRIMARY KEY ((reserva_id))
);

-- Pago. Consulta: el pago de una reserva (relacion 1:1).
CREATE TABLE IF NOT EXISTS pagos_por_reserva (
    reserva_id  uuid,
    pago_id     uuid,
    monto       decimal,
    metodo      text,
    fecha_pago  timestamp,
    estado      text,           -- pendiente | pagado | reembolsado
    PRIMARY KEY ((reserva_id))
);

-- =====================================================================
-- B) TABLAS ESPECIALIZADAS PARA LAS 5 CONSULTAS DEL NEGOCIO
-- =====================================================================

-- ---------------------------------------------------------------------
-- Q1. Disponibilidad de asientos por clase (para un vuelo)
--   SELECT clase, disponibles, ocupados
--   FROM asientos_contadores_por_vuelo WHERE codigo_vuelo = ?;
-- Estrategia: tabla de contadores. Se actualiza en cada reserva/cancelacion
-- en lugar de contar filas al consultar.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS asientos_contadores_por_vuelo (
    codigo_vuelo text,
    clase        text,
    disponibles  counter,
    ocupados     counter,
    PRIMARY KEY ((codigo_vuelo), clase)
);

-- ---------------------------------------------------------------------
-- Q2. Historial cronologico de un pasajero en un rango de fechas
--   SELECT * FROM historial_por_pasajero
--   WHERE pasajero_id = ? AND fecha_salida >= ? AND fecha_salida <= ?
--   ORDER BY fecha_salida ASC;
-- Estrategia: clustering key por fecha (rango + ORDER BY) y datos de
-- reserva + vuelo + pago denormalizados en la misma fila.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS historial_por_pasajero (
    pasajero_id    uuid,
    fecha_salida   timestamp,
    reserva_id     uuid,
    codigo_vuelo   text,
    origen         text,
    destino        text,
    fila           int,
    letra          text,
    clase          text,
    fecha_reserva  timestamp,
    estado_reserva text,
    monto          decimal,
    estado_pago    text,
    PRIMARY KEY ((pasajero_id), fecha_salida, reserva_id)
) WITH CLUSTERING ORDER BY (fecha_salida DESC, reserva_id ASC);

-- ---------------------------------------------------------------------
-- Q3. Manifiesto de vuelo ordenado y enriquecido
--   SELECT * FROM manifiesto_por_vuelo WHERE codigo_vuelo = ?;
-- Estrategia: clustering (fila, letra) da el orden por asiento; se
-- denormalizan Pasajero + Asiento + Reserva + Pago en una sola tabla.
-- Tambien sirve para propagar la cancelacion de un vuelo (regla 6).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS manifiesto_por_vuelo (
    codigo_vuelo    text,
    fila            int,
    letra           text,
    reserva_id      uuid,
    pasajero_id     uuid,
    nombre_pasajero text,
    identificacion  text,
    clase           text,
    estado_reserva  text,
    estado_pago     text,
    PRIMARY KEY ((codigo_vuelo), fila, letra)
);

-- ---------------------------------------------------------------------
-- Q4. Porcentaje de ocupacion por ruta y rango de fechas
--   SELECT fecha_salida, codigo_vuelo, capacidad, confirmadas
--   FROM ocupacion_por_ruta_mes
--   WHERE ruta = ? AND mes = ?
--     AND fecha_salida >= ? AND fecha_salida <= ?;
--   porcentaje = confirmadas / capacidad * 100
-- Estrategia: bucketing (ruta, mes) para evitar particiones gigantes, y
-- un contador de reservas confirmadas. 'capacidad' va como clustering
-- column porque una tabla de counters no admite otras columnas normales;
-- asi una sola consulta trae contador y capacidad.
-- Si el rango cruza varios meses, se consulta cada 'mes' y se unen.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ocupacion_por_ruta_mes (
    ruta         text,          -- 'GUA-MIA'
    mes          text,          -- 'YYYY-MM'
    fecha_salida timestamp,
    codigo_vuelo text,
    capacidad    int,
    confirmadas  counter,
    PRIMARY KEY ((ruta, mes), fecha_salida, codigo_vuelo, capacidad)
);

-- ---------------------------------------------------------------------
-- Q5. Top N de vuelos por ingresos generados
--   SELECT codigo_vuelo, ruta, total_centavos
--   FROM top_vuelos_por_ingresos WHERE periodo = ? LIMIT N;
-- Estrategia: total_centavos como clustering key en orden DESC, de modo
-- que LIMIT N ya devuelve los mayores sin ordenar en el cliente.
-- Un counter no puede ser parte de la llave, por eso el acumulado vive en
-- ingresos_por_vuelo y esta tabla se reescribe (delete + insert) cuando
-- cambia el total de un vuelo.
-- Para un rango que cruza varios 'periodo', se consulta cada uno con
-- LIMIT N y se mezclan. Es correcto porque cada vuelo esta en un solo periodo.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ingresos_por_vuelo (
    codigo_vuelo    text,
    total_centavos  counter,    -- suma de pagos 'pagado', en centavos
    PRIMARY KEY ((codigo_vuelo))
);

CREATE TABLE IF NOT EXISTS top_vuelos_por_ingresos (
    periodo        text,        -- 'YYYY-MM' del mes de salida del vuelo
    total_centavos bigint,
    codigo_vuelo   text,
    ruta           text,
    PRIMARY KEY ((periodo), total_centavos, codigo_vuelo)
) WITH CLUSTERING ORDER BY (total_centavos DESC, codigo_vuelo ASC);

-- =====================================================================
-- NOTAS DE OPERACION
--  * TTL (reservas pendientes que expiran): usar
--      INSERT ... USING TTL 900
--    en TODAS las tablas donde se escriba esa reserva pendiente
--    (reservas_por_id, historial_por_pasajero, manifiesto_por_vuelo).
--    Al confirmarla, se reescribe sin TTL. Los counters no admiten TTL.
--  * Los counters se actualizan solo con UPDATE ... SET c = c + n y en
--    batches de tipo COUNTER (no se pueden mezclar con tablas normales).
--  * Regla 2 (un asiento, un pasajero): UPDATE asientos_por_vuelo
--      SET estado='ocupado', reserva_id=? WHERE ... IF estado='disponible';
-- =====================================================================
