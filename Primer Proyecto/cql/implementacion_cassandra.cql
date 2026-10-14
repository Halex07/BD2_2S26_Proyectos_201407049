-- =========================================================================
-- Tarea #2 - Bases de Datos 2
-- Sistema de Recomendaciones (E-commerce) implementado en Apache Cassandra
-- Autor: Henry García - Carné 201407049
-- =========================================================================

-- -------------------------------------------------------------------------
-- 1. CREACIÓN DEL KEYSPACE
-- -------------------------------------------------------------------------
CREATE KEYSPACE IF NOT EXISTS sistema_recomendaciones
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE sistema_recomendaciones;

-- -------------------------------------------------------------------------
-- 2. MODELADO DE TABLAS (diseño "query-first", típico de Cassandra)
-- -------------------------------------------------------------------------

-- Tabla de usuarios
CREATE TABLE IF NOT EXISTS usuarios (
    usuario_id   UUID PRIMARY KEY,
    nombre       TEXT,
    email        TEXT,
    edad         INT,
    ciudad       TEXT
);

-- Tabla de catálogo de productos
CREATE TABLE IF NOT EXISTS productos (
    producto_id  UUID PRIMARY KEY,
    nombre       TEXT,
    categoria    TEXT,
    precio       DECIMAL,
    descripcion  TEXT
);

-- Historial de interacciones por usuario (consulta: "dame el historial de X usuario")
CREATE TABLE IF NOT EXISTS interacciones_por_usuario (
    usuario_id         UUID,
    fecha_interaccion  TIMESTAMP,
    producto_id        UUID,
    producto_nombre    TEXT,
    tipo_interaccion   TEXT,   -- 'vista', 'compra', 'calificacion', 'carrito'
    calificacion        INT,
    PRIMARY KEY (usuario_id, fecha_interaccion, producto_id)
) WITH CLUSTERING ORDER BY (fecha_interaccion DESC);

-- Recomendaciones ya calculadas por usuario (consulta: "dame las recomendaciones de X usuario")
CREATE TABLE IF NOT EXISTS recomendaciones_por_usuario (
    usuario_id       UUID,
    score            DECIMAL,
    producto_id      UUID,
    producto_nombre  TEXT,
    categoria        TEXT,
    motivo           TEXT,   -- ej. 'comprado_por_usuarios_similares', 'misma_categoria'
    PRIMARY KEY (usuario_id, score, producto_id)
) WITH CLUSTERING ORDER BY (score DESC);

-- Productos por categoría, con contador de veces recomendado
-- (consulta: "productos más recomendados en la categoría Y")
CREATE TABLE IF NOT EXISTS productos_por_categoria (
    categoria         TEXT,
    veces_recomendado INT,
    producto_id       UUID,
    nombre            TEXT,
    precio            DECIMAL,
    PRIMARY KEY (categoria, veces_recomendado, producto_id)
) WITH CLUSTERING ORDER BY (veces_recomendado DESC);


-- -------------------------------------------------------------------------
-- 3. INSERCIÓN DE DATOS (usuarios y productos base)
-- -------------------------------------------------------------------------

-- 5 usuarios
INSERT INTO usuarios (usuario_id, nombre, email, edad, ciudad) VALUES (11111111-1111-1111-1111-111111111111, 'Henry García', 'henry.garcia@usac.edu.gt', 27, 'Guatemala');
INSERT INTO usuarios (usuario_id, nombre, email, edad, ciudad) VALUES (22222222-2222-2222-2222-222222222222, 'María López', 'maria.lopez@mail.com', 24, 'Antigua Guatemala');
INSERT INTO usuarios (usuario_id, nombre, email, edad, ciudad) VALUES (33333333-3333-3333-3333-333333333333, 'Carlos Pérez', 'carlos.perez@mail.com', 31, 'Quetzaltenango');
INSERT INTO usuarios (usuario_id, nombre, email, edad, ciudad) VALUES (44444444-4444-4444-4444-444444444444, 'Ana Ramírez', 'ana.ramirez@mail.com', 29, 'Escuintla');
INSERT INTO usuarios (usuario_id, nombre, email, edad, ciudad) VALUES (55555555-5555-5555-5555-555555555555, 'Luis Morales', 'luis.morales@mail.com', 35, 'Guatemala');

-- 6 productos
INSERT INTO productos (producto_id, nombre, categoria, precio, descripcion) VALUES (aaaaaaaa-0000-0000-0000-000000000001, 'Laptop Gamer X15', 'Electrónica', 6999.99, 'Laptop con GPU dedicada para gaming y diseño');
INSERT INTO productos (producto_id, nombre, categoria, precio, descripcion) VALUES (aaaaaaaa-0000-0000-0000-000000000002, 'Audífonos Bluetooth Pro', 'Electrónica', 349.50, 'Audífonos inalámbricos con cancelación de ruido');
INSERT INTO productos (producto_id, nombre, categoria, precio, descripcion) VALUES (aaaaaaaa-0000-0000-0000-000000000003, 'Camiseta Deportiva DryFit', 'Ropa', 129.00, 'Camiseta transpirable para entrenamiento');
INSERT INTO productos (producto_id, nombre, categoria, precio, descripcion) VALUES (aaaaaaaa-0000-0000-0000-000000000004, 'Tenis Running Air', 'Ropa', 549.00, 'Tenis para correr con amortiguación');
INSERT INTO productos (producto_id, nombre, categoria, precio, descripcion) VALUES (aaaaaaaa-0000-0000-0000-000000000005, 'Cafetera Automática', 'Hogar', 899.00, 'Cafetera programable de 12 tazas');
INSERT INTO productos (producto_id, nombre, categoria, precio, descripcion) VALUES (aaaaaaaa-0000-0000-0000-000000000006, 'Set de Sartenes Antiadherentes', 'Hogar', 459.00, 'Set de 3 sartenes antiadherentes');

-- -------------------------------------------------------------------------
-- 4. INSERCIÓN DE >20 REGISTROS EN interacciones_por_usuario
-- -------------------------------------------------------------------------
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (11111111-1111-1111-1111-111111111111, '2026-09-01 10:00:00', aaaaaaaa-0000-0000-0000-000000000001, 'Laptop Gamer X15', 'vista', null);
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (11111111-1111-1111-1111-111111111111, '2026-09-02 11:00:00', aaaaaaaa-0000-0000-0000-000000000001, 'Laptop Gamer X15', 'compra', 5);
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (11111111-1111-1111-1111-111111111111, '2026-09-03 09:15:00', aaaaaaaa-0000-0000-0000-000000000002, 'Audífonos Bluetooth Pro', 'vista', null);
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (11111111-1111-1111-1111-111111111111, '2026-09-03 09:20:00', aaaaaaaa-0000-0000-0000-000000000002, 'Audífonos Bluetooth Pro', 'carrito', null);
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (11111111-1111-1111-1111-111111111111, '2026-09-05 18:40:00', aaaaaaaa-0000-0000-0000-000000000002, 'Audífonos Bluetooth Pro', 'compra', 4);
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (22222222-2222-2222-2222-222222222222, '2026-09-01 08:00:00', aaaaaaaa-0000-0000-0000-000000000003, 'Camiseta Deportiva DryFit', 'vista', null);
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (22222222-2222-2222-2222-222222222222, '2026-09-01 08:05:00', aaaaaaaa-0000-0000-0000-000000000003, 'Camiseta Deportiva DryFit', 'compra', 5);
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (22222222-2222-2222-2222-222222222222, '2026-09-02 12:30:00', aaaaaaaa-0000-0000-0000-000000000004, 'Tenis Running Air', 'vista', null);
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (22222222-2222-2222-2222-222222222222, '2026-09-04 17:00:00', aaaaaaaa-0000-0000-0000-000000000004, 'Tenis Running Air', 'compra', 5);
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (22222222-2222-2222-2222-222222222222, '2026-09-06 20:00:00', aaaaaaaa-0000-0000-0000-000000000003, 'Camiseta Deportiva DryFit', 'calificacion', 4);
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (33333333-3333-3333-3333-333333333333, '2026-09-01 07:45:00', aaaaaaaa-0000-0000-0000-000000000005, 'Cafetera Automática', 'vista', null);
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (33333333-3333-3333-3333-333333333333, '2026-09-01 07:50:00', aaaaaaaa-0000-0000-0000-000000000005, 'Cafetera Automática', 'carrito', null);
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (33333333-3333-3333-3333-333333333333, '2026-09-02 19:10:00', aaaaaaaa-0000-0000-0000-000000000005, 'Cafetera Automática', 'compra', 5);
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (33333333-3333-3333-3333-333333333333, '2026-09-03 21:00:00', aaaaaaaa-0000-0000-0000-000000000006, 'Set de Sartenes Antiadherentes', 'vista', null);
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (33333333-3333-3333-3333-333333333333, '2026-09-05 15:00:00', aaaaaaaa-0000-0000-0000-000000000006, 'Set de Sartenes Antiadherentes', 'compra', 3);
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (44444444-4444-4444-4444-444444444444, '2026-09-01 13:00:00', aaaaaaaa-0000-0000-0000-000000000001, 'Laptop Gamer X15', 'vista', null);
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (44444444-4444-4444-4444-444444444444, '2026-09-02 14:00:00', aaaaaaaa-0000-0000-0000-000000000002, 'Audífonos Bluetooth Pro', 'vista', null);
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (44444444-4444-4444-4444-444444444444, '2026-09-02 14:10:00', aaaaaaaa-0000-0000-0000-000000000002, 'Audífonos Bluetooth Pro', 'compra', 5);
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (44444444-4444-4444-4444-444444444444, '2026-09-07 16:30:00', aaaaaaaa-0000-0000-0000-000000000006, 'Set de Sartenes Antiadherentes', 'vista', null);
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (55555555-5555-5555-5555-555555555555, '2026-09-01 09:00:00', aaaaaaaa-0000-0000-0000-000000000004, 'Tenis Running Air', 'vista', null);
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (55555555-5555-5555-5555-555555555555, '2026-09-02 09:30:00', aaaaaaaa-0000-0000-0000-000000000004, 'Tenis Running Air', 'compra', 4);
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (55555555-5555-5555-5555-555555555555, '2026-09-03 10:00:00', aaaaaaaa-0000-0000-0000-000000000003, 'Camiseta Deportiva DryFit', 'vista', null);
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion) VALUES (55555555-5555-5555-5555-555555555555, '2026-09-04 11:00:00', aaaaaaaa-0000-0000-0000-000000000005, 'Cafetera Automática', 'vista', null);
-- (24 registros insertados en esta tabla, cumpliendo el mínimo de 20)

-- -------------------------------------------------------------------------
-- 5. RECOMENDACIONES PRE-CALCULADAS POR USUARIO
-- -------------------------------------------------------------------------
INSERT INTO recomendaciones_por_usuario (usuario_id, score, producto_id, producto_nombre, categoria, motivo) VALUES (11111111-1111-1111-1111-111111111111, 0.92, aaaaaaaa-0000-0000-0000-000000000006, 'Set de Sartenes Antiadherentes', 'Hogar', 'comprado_por_usuarios_similares');
INSERT INTO recomendaciones_por_usuario (usuario_id, score, producto_id, producto_nombre, categoria, motivo) VALUES (11111111-1111-1111-1111-111111111111, 0.85, aaaaaaaa-0000-0000-0000-000000000004, 'Tenis Running Air', 'Ropa', 'tendencia_general');
INSERT INTO recomendaciones_por_usuario (usuario_id, score, producto_id, producto_nombre, categoria, motivo) VALUES (22222222-2222-2222-2222-222222222222, 0.95, aaaaaaaa-0000-0000-0000-000000000002, 'Audífonos Bluetooth Pro', 'Electrónica', 'misma_categoria_de_interes');
INSERT INTO recomendaciones_por_usuario (usuario_id, score, producto_id, producto_nombre, categoria, motivo) VALUES (33333333-3333-3333-3333-333333333333, 0.88, aaaaaaaa-0000-0000-0000-000000000001, 'Laptop Gamer X15', 'Electrónica', 'tendencia_general');
INSERT INTO recomendaciones_por_usuario (usuario_id, score, producto_id, producto_nombre, categoria, motivo) VALUES (44444444-4444-4444-4444-444444444444, 0.90, aaaaaaaa-0000-0000-0000-000000000001, 'Laptop Gamer X15', 'Electrónica', 'comprado_por_usuarios_similares');

-- -------------------------------------------------------------------------
-- 5b. CONTADOR DE PRODUCTOS RECOMENDADOS POR CATEGORÍA
-- -------------------------------------------------------------------------
INSERT INTO productos_por_categoria (categoria, veces_recomendado, producto_id, nombre, precio) VALUES ('Electrónica', 12, aaaaaaaa-0000-0000-0000-000000000001, 'Laptop Gamer X15', 6999.99);
INSERT INTO productos_por_categoria (categoria, veces_recomendado, producto_id, nombre, precio) VALUES ('Electrónica', 9, aaaaaaaa-0000-0000-0000-000000000002, 'Audífonos Bluetooth Pro', 349.50);
INSERT INTO productos_por_categoria (categoria, veces_recomendado, producto_id, nombre, precio) VALUES ('Ropa', 7, aaaaaaaa-0000-0000-0000-000000000004, 'Tenis Running Air', 549.00);
INSERT INTO productos_por_categoria (categoria, veces_recomendado, producto_id, nombre, precio) VALUES ('Ropa', 4, aaaaaaaa-0000-0000-0000-000000000003, 'Camiseta Deportiva DryFit', 129.00);
INSERT INTO productos_por_categoria (categoria, veces_recomendado, producto_id, nombre, precio) VALUES ('Hogar', 6, aaaaaaaa-0000-0000-0000-000000000006, 'Set de Sartenes Antiadherentes', 459.00);

-- -------------------------------------------------------------------------
-- 6. OPERACIONES CRUD
-- -------------------------------------------------------------------------

-- CREATE (ya ilustrado arriba). Ejemplo adicional:
INSERT INTO interacciones_por_usuario (usuario_id, fecha_interaccion, producto_id, producto_nombre, tipo_interaccion, calificacion)
VALUES (11111111-1111-1111-1111-111111111111, '2026-09-08 12:00:00', aaaaaaaa-0000-0000-0000-000000000005, 'Cafetera Automática', 'vista', null);

-- READ
SELECT * FROM usuarios WHERE usuario_id = 11111111-1111-1111-1111-111111111111;
SELECT * FROM interacciones_por_usuario WHERE usuario_id = 11111111-1111-1111-1111-111111111111;

-- UPDATE (Cassandra: UPDATE actúa como upsert; se debe incluir toda la clave primaria)
UPDATE recomendaciones_por_usuario
SET motivo = 'reajustado_por_nueva_compra'
WHERE usuario_id = 11111111-1111-1111-1111-111111111111 AND score = 0.92 AND producto_id = aaaaaaaa-0000-0000-0000-000000000006;

-- DELETE
DELETE FROM interacciones_por_usuario
WHERE usuario_id = 11111111-1111-1111-1111-111111111111 AND fecha_interaccion = '2026-09-08 12:00:00' AND producto_id = aaaaaaaa-0000-0000-0000-000000000005;

-- -------------------------------------------------------------------------
-- 7. TRES CONSULTAS RELEVANTES DEL CASO DE USO
-- -------------------------------------------------------------------------

-- Consulta 1: Recomendaciones activas de un usuario, de mayor a menor score
SELECT producto_nombre, categoria, score, motivo
FROM recomendaciones_por_usuario
WHERE usuario_id = 22222222-2222-2222-2222-222222222222;

-- Consulta 2: Historial de interacciones recientes de un usuario
SELECT fecha_interaccion, producto_nombre, tipo_interaccion, calificacion
FROM interacciones_por_usuario
WHERE usuario_id = 11111111-1111-1111-1111-111111111111;

-- Consulta 3: Productos más recomendados dentro de una categoría específica
SELECT nombre, veces_recomendado, precio
FROM productos_por_categoria
WHERE categoria = 'Electrónica';
