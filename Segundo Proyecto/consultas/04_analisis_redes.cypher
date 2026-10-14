// =====================================================================
// 04_analisis_redes.cypher - Análisis de redes
// Parámetros: :param origen => 'U0001'; :param destino => 'U0250';
// =====================================================================

// ---------------------------------------------------------------------
// A1. Ruta más corta entre dos usuarios (grados de separación)
// ---------------------------------------------------------------------
MATCH (a:Usuario {id: $origen}), (b:Usuario {id: $destino})
MATCH ruta = shortestPath((a)-[:ES_AMIGO_DE*..10]-(b))
RETURN [n IN nodes(ruta) | n.nombre] AS ruta_de_amigos, length(ruta) AS grados_de_separacion;

// A1b. Todas las rutas más cortas (alternativas)
MATCH (a:Usuario {id: $origen}), (b:Usuario {id: $destino})
MATCH rutas = allShortestPaths((a)-[:ES_AMIGO_DE*..10]-(b))
RETURN [n IN nodes(rutas) | n.id] AS ruta_ids, length(rutas) AS grados
LIMIT 10;

// A1c. Distribución de grados de separación desde un usuario hacia toda la red
MATCH (a:Usuario {id: $origen}), (b:Usuario)
WHERE a <> b
MATCH ruta = shortestPath((a)-[:ES_AMIGO_DE*..10]-(b))
RETURN length(ruta) AS grados, count(*) AS usuarios
ORDER BY grados;

// ---------------------------------------------------------------------
// A2. Restaurantes altamente conectados
// Definición: puntaje = (# chefs que trabajan en el restaurante)
//                     + (# platillos DESTACADOS)
// Platillo destacado = platillo ofrecido y DISPONIBLE en el restaurante que además
//                      es preparado por un chef que trabaja en ese mismo restaurante
//                      (platillo "de autor").
// ---------------------------------------------------------------------
MATCH (r:Restaurante)
OPTIONAL MATCH (c:Chef)-[:TRABAJA_EN]->(r)
WITH r, count(DISTINCT c) AS chefs
OPTIONAL MATCH (r)-[:OFRECE {disponible: true}]->(p:Platillo)<-[:PREPARA]-(c2:Chef)-[:TRABAJA_EN]->(r)
WITH r, chefs, count(DISTINCT p) AS platillos_destacados
OPTIONAL MATCH (r)<-[k:CALIFICÓ]-()
RETURN r.id AS id, r.nombre AS restaurante, chefs, platillos_destacados,
       chefs + platillos_destacados AS puntaje_conectividad,
       round(avg(k.puntuacion), 2) AS calificacion
ORDER BY puntaje_conectividad DESC, calificacion DESC
LIMIT 10;

// A2b. Centralidad de grado simple (todas las relaciones que tocan al restaurante)
MATCH (r:Restaurante)
RETURN r.nombre AS restaurante, COUNT { (r)--() } AS grado_total
ORDER BY grado_total DESC
LIMIT 10;
