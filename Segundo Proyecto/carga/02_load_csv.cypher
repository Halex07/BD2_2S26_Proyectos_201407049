// =====================================================================
// 02_load_csv.cypher - Carga masiva con LOAD CSV
// Prerrequisitos:
//  1) Haber ejecutado modelo/01_schema.cypher
//  2) Copiar los CSV de datos/csv/ a la carpeta "import" del DBMS
//     (Neo4j Desktop: DBMS > ... > Open folder > Import)
// Cómo ejecutar:
//  - Neo4j Browser: ejecutar CADA bloque por separado (el prefijo ":auto" es necesario
//    para CALL { } IN TRANSACTIONS).
//  - cypher-shell -f: quitar las líneas ":auto".
// Nota: en Neo4j 5 "USING PERIODIC COMMIT" fue reemplazado por
//       CALL { ... } IN TRANSACTIONS OF n ROWS (misma idea: commits por lotes).
// Todos los nodos usan MERGE por id (idempotente: se puede re-ejecutar sin duplicar).
// =====================================================================

// ------------------------------ NODOS ---------------------------------
:auto
LOAD CSV WITH HEADERS FROM 'file:///tipos_cocina.csv' AS row
CALL {
  WITH row
  MERGE (t:TipoCocina {id: row.id})
  SET t.nombre = row.nombre, t.descripcion = row.descripcion
} IN TRANSACTIONS OF 100 ROWS;

:auto
LOAD CSV WITH HEADERS FROM 'file:///platillos.csv' AS row
CALL {
  WITH row
  MERGE (p:Platillo {id: row.id})
  SET p.nombre = row.nombre, p.precio = toFloat(row.precio), p.descripcion = row.descripcion
} IN TRANSACTIONS OF 100 ROWS;

:auto
LOAD CSV WITH HEADERS FROM 'file:///restaurantes.csv' AS row
CALL {
  WITH row
  MERGE (r:Restaurante {id: row.id})
  SET r.nombre = row.nombre, r.anio_apertura = toInteger(row.anio_apertura),
      r.rango_precios = row.rango_precios, r.descripcion = row.descripcion
} IN TRANSACTIONS OF 100 ROWS;

:auto
LOAD CSV WITH HEADERS FROM 'file:///chefs.csv' AS row
CALL {
  WITH row
  MERGE (c:Chef {id: row.id})
  SET c.nombre = row.nombre, c.fecha_nacimiento = date(row.fecha_nacimiento),
      c.nacionalidad = row.nacionalidad
} IN TRANSACTIONS OF 100 ROWS;

:auto
LOAD CSV WITH HEADERS FROM 'file:///usuarios.csv' AS row
CALL {
  WITH row
  MERGE (u:Usuario {id: row.id})
  SET u.nombre = row.nombre, u.email = row.email, u.edad = toInteger(row.edad), u.pais = row.pais
} IN TRANSACTIONS OF 250 ROWS;

// --------------------------- RELACIONES -------------------------------
// PERTENECE_A: (Restaurante)-[:PERTENECE_A]->(TipoCocina)
:auto
LOAD CSV WITH HEADERS FROM 'file:///pertenece_a.csv' AS row
CALL {
  WITH row
  MATCH (r:Restaurante {id: row.restaurante_id})
  MATCH (t:TipoCocina {id: row.tipo_id})
  MERGE (r)-[:PERTENECE_A]->(t)
} IN TRANSACTIONS OF 500 ROWS;

// OFRECE: MERGE sobre el par (restaurante, platillo) => regla 5: no se repite el platillo
:auto
LOAD CSV WITH HEADERS FROM 'file:///ofrece.csv' AS row
CALL {
  WITH row
  MATCH (r:Restaurante {id: row.restaurante_id})
  MATCH (p:Platillo {id: row.platillo_id})
  MERGE (r)-[o:OFRECE]->(p)
  SET o.precio = toFloat(row.precio), o.disponible = toBoolean(row.disponible)
} IN TRANSACTIONS OF 500 ROWS;

// TRABAJA_EN: (Chef)-[:TRABAJA_EN]->(Restaurante)
:auto
LOAD CSV WITH HEADERS FROM 'file:///trabaja_en.csv' AS row
CALL {
  WITH row
  MATCH (c:Chef {id: row.chef_id})
  MATCH (r:Restaurante {id: row.restaurante_id})
  MERGE (c)-[t:TRABAJA_EN]->(r)
  SET t.fecha_inicio = date(row.fecha_inicio), t.puesto = row.puesto
} IN TRANSACTIONS OF 500 ROWS;

// PREPARA: (Chef)-[:PREPARA]->(Platillo)
:auto
LOAD CSV WITH HEADERS FROM 'file:///prepara.csv' AS row
CALL {
  WITH row
  MATCH (c:Chef {id: row.chef_id})
  MATCH (p:Platillo {id: row.platillo_id})
  MERGE (c)-[pr:PREPARA]->(p)
  SET pr.estilo = row.estilo, pr.especialidad = toBoolean(row.especialidad)
} IN TRANSACTIONS OF 500 ROWS;

// LE_GUSTA: (Usuario)-[:LE_GUSTA {nivel_interes 1-5}]->(TipoCocina)
:auto
LOAD CSV WITH HEADERS FROM 'file:///le_gusta.csv' AS row
WITH row WHERE toInteger(row.nivel_interes) IN [1,2,3,4,5]
CALL {
  WITH row
  MATCH (u:Usuario {id: row.usuario_id})
  MATCH (t:TipoCocina {id: row.tipo_id})
  MERGE (u)-[g:LE_GUSTA]->(t)
  SET g.nivel_interes = toInteger(row.nivel_interes)
} IN TRANSACTIONS OF 500 ROWS;

// ES_AMIGO_DE: se guarda en UNA sola dirección y se consulta SIN dirección
//   (u)-[:ES_AMIGO_DE]-(v)   => evita duplicar aristas y es simétrica en las consultas
:auto
LOAD CSV WITH HEADERS FROM 'file:///amistades.csv' AS row
CALL {
  WITH row
  MATCH (u:Usuario {id: row.usuario_id})
  MATCH (v:Usuario {id: row.amigo_id})
  MERGE (u)-[a:ES_AMIGO_DE]->(v)
  SET a.fecha_amistad = date(row.fecha_amistad)
} IN TRANSACTIONS OF 500 ROWS;

// VISITÓ: un usuario puede visitar varias veces un restaurante.
//   La clave de MERGE incluye fecha_visita => re-ejecutar no duplica.
:auto
LOAD CSV WITH HEADERS FROM 'file:///visito.csv' AS row
CALL {
  WITH row
  MATCH (u:Usuario {id: row.usuario_id})
  MATCH (r:Restaurante {id: row.restaurante_id})
  MERGE (u)-[v:VISITÓ {fecha_visita: date(row.fecha_visita)}]->(r)
  SET v.consumo = toFloat(row.consumo), v.con_reserva = toBoolean(row.con_reserva)
} IN TRANSACTIONS OF 500 ROWS;

// CALIFICÓ: una calificación por (usuario, restaurante); regla 4: puntuación 1-5
:auto
LOAD CSV WITH HEADERS FROM 'file:///califico.csv' AS row
WITH row WHERE toInteger(row.puntuacion) IN [1,2,3,4,5]
CALL {
  WITH row
  MATCH (u:Usuario {id: row.usuario_id})
  MATCH (r:Restaurante {id: row.restaurante_id})
  MERGE (u)-[c:CALIFICÓ]->(r)
  SET c.puntuacion = toInteger(row.puntuacion), c.fecha = date(row.fecha), c.comentario = row.comentario
} IN TRANSACTIONS OF 500 ROWS;
