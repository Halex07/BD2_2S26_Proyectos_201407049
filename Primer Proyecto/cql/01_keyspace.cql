-- =====================================================================
-- 01_keyspace.cql
-- Keyspace del sistema de reservas y boletos aereos
-- =====================================================================
-- NetworkTopologyStrategy: es la estrategia recomendada para produccion
-- porque conoce datacenters y racks, y permite crecer a varios DC sin
-- rehacer el keyspace. 'dc1' debe coincidir con CASSANDRA_DC del compose.
--
-- RF = 3 con 3 nodos: cada dato queda en los 3 nodos.
--   QUORUM = floor(3/2) + 1 = 2  -> tolera 1 nodo caido
--   ONE    = 1                   -> tolera 2 nodos caidos
--   ALL    = 3                   -> no tolera ninguno caido
-- =====================================================================

CREATE KEYSPACE IF NOT EXISTS aerolinea
WITH replication = {
    'class': 'NetworkTopologyStrategy',
    'dc1': 3
}
AND durable_writes = true;
