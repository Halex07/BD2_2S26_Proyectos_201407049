// =====================================================================
// 01_schema.cypher - Esquema del grafo (constraints e índices)
// Proyecto 2 - Sistemas de Bases de Datos 2 - Neo4j 5.x
// Ejecutar UNA VEZ, antes de cargar datos.
// =====================================================================
// Etiquetas de nodos : Usuario, Restaurante, TipoCocina, Chef, Platillo
// Relaciones         : CALIFICÓ, VISITÓ, ES_AMIGO_DE, PERTENECE_A,
//                      OFRECE, PREPARA, TRABAJA_EN, LE_GUSTA
// ---------------------------------------------------------------------

// --- Unicidad (garantiza integridad y habilita MERGE eficiente) -------
CREATE CONSTRAINT usuario_id      IF NOT EXISTS FOR (n:Usuario)     REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT usuario_email   IF NOT EXISTS FOR (n:Usuario)     REQUIRE n.email IS UNIQUE;
CREATE CONSTRAINT restaurante_id  IF NOT EXISTS FOR (n:Restaurante) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT tipococina_id   IF NOT EXISTS FOR (n:TipoCocina)  REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT chef_id         IF NOT EXISTS FOR (n:Chef)        REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT platillo_id     IF NOT EXISTS FOR (n:Platillo)    REQUIRE n.id IS UNIQUE;

// --- Índices de apoyo a las consultas ---------------------------------
CREATE INDEX restaurante_nombre IF NOT EXISTS FOR (n:Restaurante) ON (n.nombre);
CREATE INDEX restaurante_rango  IF NOT EXISTS FOR (n:Restaurante) ON (n.rango_precios);
CREATE INDEX usuario_nombre     IF NOT EXISTS FOR (n:Usuario)     ON (n.nombre);
CREATE INDEX tipococina_nombre  IF NOT EXISTS FOR (n:TipoCocina)  ON (n.nombre);

// Índice sobre propiedad de relación (requiere Neo4j >= 5.7; si falla, omitirlo)
CREATE INDEX calificacion_puntuacion IF NOT EXISTS FOR ()-[r:CALIFICÓ]-() ON (r.puntuacion);

// Nota sobre integridad de dominios (puntuación 1-5, niveles 1-5):
// los constraints de existencia/tipo de propiedad son de Neo4j Enterprise, por lo que
// en Community la regla se valida en la carga (WHERE ... IN [1,2,3,4,5]) y en
// consultas/05_validacion.cypher.
SHOW CONSTRAINTS;
SHOW INDEXES;
