// =====================================================================
// 03_consultas_negocio.cypher - Las 5 consultas obligatorias
// Parámetros (Neo4j Browser):  :param userId => 'U0001';
// =====================================================================

// ---------------------------------------------------------------------
// Q1. Recomendación social (amigos directos e indirectos, hasta 3 grados)
// Propósito : recomendar restaurantes que los amigos (1..3 grados) calificaron >= 4
//             y que el usuario NO ha visitado.
// Prioridad : 1) cantidad de amigos coincidentes  2) calificación promedio de esos amigos.
// Parámetro : $userId
// ---------------------------------------------------------------------
MATCH (yo:Usuario {id: $userId})
MATCH camino = (yo)-[:ES_AMIGO_DE*1..3]-(amigo:Usuario)      // sin dirección: amistad simétrica
WHERE amigo <> yo
WITH yo, amigo, min(length(camino)) AS grado                   // grado más corto a cada amigo
MATCH (amigo)-[c:CALIFICÓ]->(r:Restaurante)
WHERE c.puntuacion >= 4
  AND NOT EXISTS { (yo)-[:VISITÓ]->(r) }                       // excluye lo ya visitado
WITH r,
     count(DISTINCT amigo)               AS amigos_coincidentes,
     round(avg(c.puntuacion), 2)         AS promedio_amigos,
     min(grado)                          AS grado_mas_cercano,
     collect(DISTINCT amigo.nombre)[..3] AS ejemplo_amigos
RETURN r.id AS id, r.nombre AS restaurante, r.rango_precios AS precio,
       amigos_coincidentes, promedio_amigos, grado_mas_cercano, ejemplo_amigos
ORDER BY amigos_coincidentes DESC, promedio_amigos DESC
LIMIT 10;

// ---------------------------------------------------------------------
// Q1b (extra - calidad de recomendaciones): por CHEFS COMPARTIDOS
// Propósito : recomendar restaurantes donde trabajan chefs que también trabajan en
//             restaurantes que el usuario calificó >= 4; solo cocinas que le gustan (LE_GUSTA >= 3).
// ---------------------------------------------------------------------
MATCH (yo:Usuario {id: $userId})-[k:CALIFICÓ]->(r1:Restaurante)
WHERE k.puntuacion >= 4
MATCH (r1)<-[:TRABAJA_EN]-(chef:Chef)-[:TRABAJA_EN]->(r2:Restaurante)
WHERE r2 <> r1
  AND NOT EXISTS { (yo)-[:VISITÓ]->(r2) }
  AND EXISTS { (yo)-[g:LE_GUSTA]->(:TipoCocina)<-[:PERTENECE_A]-(r2) WHERE g.nivel_interes >= 3 }
RETURN r2.nombre AS recomendado,
       collect(DISTINCT chef.nombre)  AS chefs_compartidos,
       collect(DISTINCT r1.nombre)[..3] AS porque_calificaste_bien,
       count(DISTINCT chef)           AS n_chefs
ORDER BY n_chefs DESC
LIMIT 10;

// ---------------------------------------------------------------------
// Q2. Chefs de alto impacto
// Propósito : chefs cuyos restaurantes tienen calificación promedio > 4 y que preparan
//             platillos ofrecidos en al menos 3 restaurantes distintos.
// Criterio  : promedio de los promedios de los restaurantes donde trabaja el chef.
//             (variante estricta: sustituir por  min(prom_rest) > 4  = TODOS sus restaurantes > 4)
// ---------------------------------------------------------------------
MATCH (c:Chef)-[:TRABAJA_EN]->(r:Restaurante)<-[k:CALIFICÓ]-()
WITH c, r, avg(k.puntuacion) AS prom_rest
WITH c, collect(r.nombre) AS restaurantes, avg(prom_rest) AS prom_restaurantes
WHERE prom_restaurantes > 4
MATCH (c)-[:PREPARA]->(p:Platillo)<-[:OFRECE]-(r2:Restaurante)
WITH c, restaurantes, prom_restaurantes, p, count(DISTINCT r2) AS restaurantes_que_lo_ofrecen
WHERE restaurantes_que_lo_ofrecen >= 3
RETURN c.id AS id, c.nombre AS chef, restaurantes,
       round(prom_restaurantes, 2) AS prom_restaurantes,
       count(p) AS platillos_difundidos,
       collect(p.nombre)[..3] AS ejemplos_platillos
ORDER BY prom_restaurantes DESC, platillos_difundidos DESC;

// ---------------------------------------------------------------------
// Q3. Restaurantes infravalorados
// Propósito : tasa de visitas con reserva > promedio general Y calificación promedio
//             < promedio general de la plataforma. (mínimo 5 visitas para evitar ruido)
// ---------------------------------------------------------------------
MATCH ()-[v:VISITÓ]->()
WITH avg(CASE WHEN v.con_reserva THEN 1.0 ELSE 0.0 END) AS tasa_global
MATCH ()-[k0:CALIFICÓ]->()
WITH tasa_global, avg(k0.puntuacion) AS prom_global
MATCH (r:Restaurante)<-[v2:VISITÓ]-()
WITH r, tasa_global, prom_global,
     avg(CASE WHEN v2.con_reserva THEN 1.0 ELSE 0.0 END) AS tasa_reserva,
     count(v2) AS visitas
WHERE visitas >= 5
MATCH (r)<-[k:CALIFICÓ]-()
WITH r, tasa_global, prom_global, tasa_reserva, visitas, avg(k.puntuacion) AS prom_rest, count(k) AS n_calif
WHERE tasa_reserva > tasa_global AND prom_rest < prom_global
RETURN r.id AS id, r.nombre AS restaurante, r.rango_precios AS precio, visitas,
       round(tasa_reserva, 2) AS tasa_reserva, round(tasa_global, 2) AS tasa_reserva_global,
       round(prom_rest, 2) AS calificacion, round(prom_global, 2) AS calificacion_global
ORDER BY (tasa_reserva - tasa_global) DESC;

// ---------------------------------------------------------------------
// Q4. Rango de precios declarado vs consumo real
// Propósito : comparar el consumo promedio registrado en VISITÓ con el consumo esperado
//             de su categoría. Esperado (USD): $=15, $$=35, $$$=65, $$$$=120.
//             Se listan primero los de mayor diferencia absoluta.
// ---------------------------------------------------------------------
MATCH (r:Restaurante)<-[v:VISITÓ]-()
WITH r, avg(v.consumo) AS consumo_real, count(v) AS visitas
WITH r, consumo_real, visitas,
     CASE r.rango_precios WHEN '$' THEN 15.0 WHEN '$$' THEN 35.0 WHEN '$$$' THEN 65.0 ELSE 120.0 END AS esperado
RETURN r.id AS id, r.nombre AS restaurante, r.rango_precios AS rango, visitas,
       round(consumo_real, 2) AS consumo_real, esperado,
       round(consumo_real - esperado, 2) AS diferencia,
       round(100.0 * (consumo_real - esperado) / esperado, 1) AS diferencia_pct,
       CASE WHEN consumo_real > esperado THEN 'Gasto mayor al esperado' ELSE 'Gasto menor al esperado' END AS lectura
ORDER BY abs(consumo_real - esperado) DESC
LIMIT 15;

// ---------------------------------------------------------------------
// Q5. Cocina favorita declarada vs cocina realmente visitada
// Propósito : por usuario, favorita = LE_GUSTA con mayor nivel_interes; real = tipo de cocina
//             más frecuente en VISITÓ -> PERTENECE_A. Empates se resuelven por nombre.
//             Devuelve solo los usuarios donde NO coinciden.
// ---------------------------------------------------------------------
MATCH (u:Usuario)-[g:LE_GUSTA]->(t:TipoCocina)
WITH u, t, g ORDER BY u.id, g.nivel_interes DESC, t.nombre
WITH u, collect({tipo: t.nombre, nivel: g.nivel_interes})[0] AS favorita
MATCH (u)-[:VISITÓ]->(:Restaurante)-[:PERTENECE_A]->(tv:TipoCocina)
WITH u, favorita, tv.nombre AS tipo, count(*) AS visitas ORDER BY u.id, visitas DESC, tipo
WITH u, favorita, collect({tipo: tipo, visitas: visitas})[0] AS real
WHERE favorita.tipo <> real.tipo
RETURN u.id AS id, u.nombre AS usuario,
       favorita.tipo AS cocina_favorita, favorita.nivel AS nivel_interes,
       real.tipo AS cocina_mas_visitada, real.visitas AS visitas_a_esa_cocina
ORDER BY visitas_a_esa_cocina DESC
LIMIT 20;
