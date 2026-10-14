// =====================================================================
// 05_validacion.cypher - Validación de integridad tras la carga
// =====================================================================

// V1. Conteo de nodos (esperado: 500 / 200 / 100 / 50 / 15)
MATCH (n) RETURN labels(n)[0] AS etiqueta, count(*) AS total ORDER BY total DESC;

// V2. Conteo de relaciones por tipo
MATCH ()-[r]->() RETURN type(r) AS relacion, count(*) AS total ORDER BY total DESC;

// V3. Puntuaciones fuera de rango 1-5 (esperado: 0)
MATCH ()-[c:CALIFICÓ]->() WHERE NOT c.puntuacion IN [1,2,3,4,5] RETURN count(c) AS fuera_de_rango;

// V4. Niveles de interés fuera de rango 1-5 (esperado: 0)
MATCH ()-[g:LE_GUSTA]->() WHERE NOT g.nivel_interes IN [1,2,3,4,5] RETURN count(g) AS fuera_de_rango;

// V5. Restaurantes que ofrecen un mismo platillo más de una vez (esperado: 0)
MATCH (r:Restaurante)-[o:OFRECE]->(p:Platillo)
WITH r, p, count(o) AS veces WHERE veces > 1 RETURN count(*) AS duplicados;

// V6. Amistades duplicadas en sentido inverso (esperado: 0)
MATCH (a:Usuario)-[:ES_AMIGO_DE]->(b:Usuario) WHERE EXISTS { (b)-[:ES_AMIGO_DE]->(a) } RETURN count(*) AS duplicados;

// V7. Usuarios sin amigos / restaurantes sin tipo de cocina / sin platillos (esperado: 0)
MATCH (u:Usuario) WHERE NOT (u)-[:ES_AMIGO_DE]-() RETURN count(u) AS usuarios_sin_amigos;
MATCH (r:Restaurante) WHERE NOT (r)-[:PERTENECE_A]->() RETURN count(r) AS restaurantes_sin_tipo;
MATCH (r:Restaurante) WHERE NOT (r)-[:OFRECE]->() RETURN count(r) AS restaurantes_sin_platillos;

// V8. Calificaciones sin visita previa (informativo; el generador siempre califica lo visitado)
MATCH (u:Usuario)-[:CALIFICÓ]->(r:Restaurante) WHERE NOT EXISTS { (u)-[:VISITÓ]->(r) } RETURN count(*) AS calificaciones_sin_visita;

// V9. Muestra del esquema
CALL db.schema.visualization();
