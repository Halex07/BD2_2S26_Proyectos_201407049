#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reglas_negocio.py
------------------
Demuestra dos reglas de negocio del enunciado que no se cubren con el
modelo de tablas por si solas:

  Regla 2 (un asiento, un pasajero a la vez):
      Se usa un Lightweight Transaction (LWT), es decir un
      UPDATE ... IF estado = 'disponible'. Si dos reservas intentan
      tomar el mismo asiento al mismo tiempo, solo una gana; la otra
      recibe [applied] = False y debe reintentar con otro asiento.

  TTL (reservas pendientes que expiran solas):
      Una reserva 'pendiente' se escribe con TTL. Si el pasajero no paga
      a tiempo, Cassandra borra la fila sola y el asiento debe liberarse.
      Se demuestra con un TTL corto (unos segundos) para no esperar los
      15 minutos reales de produccion.

Uso (dentro del contenedor Python, con las tablas ya creadas):
    python python/reglas_negocio.py --demo-lwt
    python python/reglas_negocio.py --demo-ttl
"""
import argparse
import os
import time
import uuid
from datetime import datetime, timezone

from cassandra import ConsistencyLevel
from cassandra.cluster import Cluster, ExecutionProfile, EXEC_PROFILE_DEFAULT
from cassandra.policies import DCAwareRoundRobinPolicy, TokenAwarePolicy

KEYSPACE = "aerolinea"
DC_LOCAL = "dc1"
HOSTS = os.environ.get("CASSANDRA_HOSTS", "cass1,cass2,cass3").split(",")
TTL_DEMO_SEGUNDOS = 8          # en produccion serian 900 (15 min)


def conectar():
    perfil = ExecutionProfile(
        load_balancing_policy=TokenAwarePolicy(DCAwareRoundRobinPolicy(local_dc=DC_LOCAL)),
        consistency_level=ConsistencyLevel.QUORUM, request_timeout=15)
    cluster = Cluster(HOSTS, execution_profiles={EXEC_PROFILE_DEFAULT: perfil})
    return cluster, cluster.connect(KEYSPACE)


# =====================================================================
# Regla 2: LWT para evitar que dos pasajeros tomen el mismo asiento
# =====================================================================
def intentar_reservar_asiento(session, codigo_vuelo, fila, letra, reserva_id):
    """UPDATE condicional. Devuelve True si el asiento quedo reservado."""
    fila_r = session.execute(
        "UPDATE asientos_por_vuelo SET estado = 'ocupado', reserva_id = %s "
        "WHERE codigo_vuelo = %s AND fila = %s AND letra = %s "
        "IF estado = 'disponible'",
        (reserva_id, codigo_vuelo, fila, letra)
    ).one()
    return fila_r.applied


def demo_lwt(session, codigo_vuelo):
    print("Regla 2: un asiento no puede quedar en manos de dos pasajeros\n")

    # Se deja un asiento en 'disponible' para la prueba
    session.execute(
        "UPDATE asientos_por_vuelo SET estado = 'disponible', reserva_id = null "
        "WHERE codigo_vuelo = %s AND fila = 99 AND letra = 'Z'", (codigo_vuelo,))
    print("  Asiento de prueba: %s fila 99 letra Z -> disponible\n" % codigo_vuelo)

    id_a, id_b = uuid.uuid4(), uuid.uuid4()
    print("  Pasajero A intenta tomar el asiento (reserva %s)" % id_a)
    ok_a = intentar_reservar_asiento(session, codigo_vuelo, 99, "Z", id_a)
    print("    -> %s" % ("CONFIRMADO" if ok_a else "RECHAZADO (alguien mas lo tomo)"))

    print("  Pasajero B intenta tomar el MISMO asiento (reserva %s)" % id_b)
    ok_b = intentar_reservar_asiento(session, codigo_vuelo, 99, "Z", id_b)
    print("    -> %s" % ("CONFIRMADO" if ok_b else "RECHAZADO (alguien mas lo tomo)"))

    estado = session.execute(
        "SELECT estado, reserva_id FROM asientos_por_vuelo "
        "WHERE codigo_vuelo = %s AND fila = 99 AND letra = 'Z'", (codigo_vuelo,)).one()
    print("\n  Estado final del asiento: %s, reserva_id = %s" % (estado.estado, estado.reserva_id))

    assert ok_a and not ok_b, "Los dos intentos NO deberian tener exito al mismo tiempo"
    assert estado.reserva_id == id_a
    print("  OK: solo una de las dos reservas tuvo exito; el asiento quedo con la reserva de A.")

    # Se limpia el asiento de prueba para no dejar basura en los datos
    session.execute(
        "UPDATE asientos_por_vuelo SET estado = 'disponible', reserva_id = null "
        "WHERE codigo_vuelo = %s AND fila = 99 AND letra = 'Z'", (codigo_vuelo,))


# =====================================================================
# TTL: una reserva pendiente que expira sola si no se confirma a tiempo
# =====================================================================
def demo_ttl(session, codigo_vuelo):
    print("TTL: una reserva pendiente que caduca si no se confirma a tiempo\n")
    print("  (TTL de demostracion: %d segundos; en produccion serian 900 = 15 min)\n" %
          TTL_DEMO_SEGUNDOS)

    rid = uuid.uuid4()
    pasajero_id = session.execute("SELECT pasajero_id FROM pasajeros_por_id LIMIT 1").one().pasajero_id
    ahora = datetime.now(timezone.utc)

    # La reserva pendiente se escribe en las 2 tablas que la muestran al usuario,
    # con el mismo TTL, para que ambas copias caduquen juntas.
    session.execute(
        "INSERT INTO reservas_por_id (reserva_id, pasajero_id, codigo_vuelo, fila, letra, "
        "clase, fecha_reserva, estado) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) USING TTL %s",
        (rid, pasajero_id, codigo_vuelo, 98, "Y", "economica", ahora, "pendiente", TTL_DEMO_SEGUNDOS))
    session.execute(
        "UPDATE asientos_por_vuelo SET estado = 'bloqueado', reserva_id = %s "
        "WHERE codigo_vuelo = %s AND fila = 98 AND letra = 'Y'", (rid, codigo_vuelo))

    print("  Reserva %s creada como 'pendiente' con TTL." % rid)
    fila = session.execute(
        "SELECT estado, TTL(estado) AS ttl_restante FROM reservas_por_id WHERE reserva_id = %s",
        (rid,)).one()
    print("  Recien creada -> estado=%s, TTL restante=%s s" % (fila.estado, fila.ttl_restante))

    espera = TTL_DEMO_SEGUNDOS + 2
    print("  Esperando %d s a que el TTL expire..." % espera)
    time.sleep(espera)

    fila = session.execute(
        "SELECT estado FROM reservas_por_id WHERE reserva_id = %s", (rid,)).one()
    print("  Tras esperar -> %s" % ("la fila ya NO existe (expiro sola)" if fila is None else fila))
    assert fila is None, "La reserva deberia haber expirado"
    print("  OK: la reserva pendiente desaparecio sola por TTL, sin borrarla a mano.")

    # El asiento se libera al expirar la reserva (regla de negocio, se aplica en la app)
    session.execute(
        "UPDATE asientos_por_vuelo SET estado = 'disponible', reserva_id = null "
        "WHERE codigo_vuelo = %s AND fila = 98 AND letra = 'Y'", (codigo_vuelo,))
    print("  Asiento fila 98 letra Y liberado manualmente (en produccion: un job periodico")
    print("  revisa asientos 'bloqueado' sin reserva viva y los vuelve a 'disponible').")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vuelo", default=None, help="codigo de vuelo a usar (por defecto, el primero)")
    ap.add_argument("--demo-lwt", action="store_true")
    ap.add_argument("--demo-ttl", action="store_true")
    args = ap.parse_args()
    if not args.demo_lwt and not args.demo_ttl:
        ap.error("indica --demo-lwt, --demo-ttl, o ambos")

    cluster, s = conectar()
    try:
        codigo = args.vuelo or s.execute(
            "SELECT codigo_vuelo FROM vuelos_por_codigo LIMIT 1").one().codigo_vuelo
        if args.demo_lwt:
            demo_lwt(s, codigo)
            print()
        if args.demo_ttl:
            demo_ttl(s, codigo)
    finally:
        cluster.shutdown()


if __name__ == "__main__":
    main()
