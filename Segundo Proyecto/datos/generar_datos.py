#!/usr/bin/env python3
"""
generar_datos.py - Genera los archivos CSV del Sistema de Recomendación de Restaurantes (Neo4j).

Uso:  python generar_datos.py        (solo usa la librería estándar de Python 3.8+)
Salida: carpeta ./csv  ->  1 CSV por tipo de nodo y 1 CSV por tipo de relación.

Cantidades: 500 usuarios, 200 restaurantes, 100 chefs, 50 platillos, 15 tipos de cocina.
La semilla es fija (SEED) para que los datos sean reproducibles.
Los datos tienen sesgos intencionales (calidad, reservas, consumo, gustos) para que
las 5 consultas de negocio devuelvan resultados interesantes.
"""
import csv, os, random, unicodedata
from datetime import date, timedelta

SEED = 42
random.seed(SEED)
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "csv")
os.makedirs(OUT, exist_ok=True)
HOY = date(2026, 10, 13)

N_USU, N_REST, N_CHEF = 500, 200, 100


def slug(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower().replace(" ", "").replace("'", "")


def rand_date(a, b):
    return a + timedelta(days=random.randint(0, (b - a).days))


def clip(x, lo, hi):
    return max(lo, min(hi, x))


def write(name, header, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"{name:<24}{len(rows):>7} filas")


NOMBRES = ["Ana", "Luis", "María", "Carlos", "Sofía", "Jorge", "Lucía", "Pedro", "Valeria", "Diego",
           "Camila", "Andrés", "Daniela", "Mateo", "Isabella", "Javier", "Gabriela", "Fernando", "Paola",
           "Ricardo", "Mónica", "Sergio", "Karla", "Héctor", "Andrea", "Raúl", "Natalia", "Oscar",
           "Fabiola", "Pablo"]
APELLIDOS = ["López", "García", "Martínez", "Hernández", "Pérez", "González", "Rodríguez", "Morales",
             "Ramírez", "Cruz", "Flores", "Castillo", "Mendoza", "Ortiz", "Vásquez", "Ruiz", "Aguilar",
             "Reyes", "Torres", "Díaz", "Gómez", "Álvarez", "Méndez", "Estrada", "Barrios", "Chávez",
             "Santos", "Fuentes", "Herrera", "Sandoval"]
PAISES = ["Guatemala", "México", "El Salvador", "Honduras", "Costa Rica", "Colombia", "España", "Estados Unidos"]
PAISES_W = [45, 15, 8, 6, 6, 8, 6, 6]

# ---------------------------------------------------------------- TipoCocina (15)
TIPOS_BASE = [
    ("Guatemalteca", "Cocina tradicional guatemalteca: pepián, kak'ik, tamales"),
    ("Mexicana", "Antojitos, moles y tacos de todo México"),
    ("Italiana", "Pastas, pizzas y risottos"),
    ("Japonesa", "Sushi, ramen y tempura"),
    ("China", "Cocina cantonesa y sichuanesa"),
    ("Peruana", "Ceviches y cocina nikkei"),
    ("Mediterránea", "Platos del Mediterráneo: Grecia, Líbano y España"),
    ("India", "Currys, tandoor y especias"),
    ("Francesa", "Cocina clásica y de bistró"),
    ("Americana", "Hamburguesas, BBQ y comida casual"),
    ("Vegetariana", "Platos sin carne, opciones veganas"),
    ("Mariscos", "Pescados y mariscos frescos"),
    ("Parrilla y Carnes", "Cortes y asados a la brasa"),
    ("Fusión", "Mezcla creativa de tradiciones culinarias"),
    ("Postres y Panadería", "Repostería, panes y dulces"),
]
tipos = [(f"T{i + 1:02d}", n, d) for i, (n, d) in enumerate(TIPOS_BASE)]
write("tipos_cocina.csv", ["id", "nombre", "descripcion"], tipos)
TIPO_IDS = [t[0] for t in tipos]

# ---------------------------------------------------------------- Platillo (50)
PLATILLOS_N = ["Pepián de pollo", "Kak'ik", "Jocón", "Tamales colorados", "Chiles rellenos", "Tacos al pastor",
               "Enchiladas verdes", "Mole poblano", "Ceviche clásico", "Lomo saltado", "Pizza margherita",
               "Lasaña boloñesa", "Risotto de hongos", "Pasta carbonara", "Sushi variado", "Ramen tonkotsu",
               "Tempura de camarón", "Chow mein", "Pato pekinés", "Curry de pollo", "Biryani",
               "Paella valenciana", "Hummus con pita", "Falafel", "Moussaka", "Coq au vin", "Crepas dulces",
               "Hamburguesa clásica", "Alitas BBQ", "Costillas ahumadas", "Ensalada César", "Bowl vegano",
               "Curry de garbanzos", "Tofu salteado", "Cóctel de camarones", "Filete de pescado",
               "Pulpo a la parrilla", "Paella de mariscos", "Churrasco", "Lomito al carbón", "Picanha",
               "Chuletas de cerdo", "Tiramisú", "Flan de vainilla", "Pastel tres leches",
               "Brownie con helado", "Croissant de almendra", "Tartar de atún", "Sopa de tomate",
               "Tacos de camarón"]
assert len(PLATILLOS_N) == 50
platillos = [(f"P{i + 1:02d}", n, round(random.uniform(6, 28), 2),
              f"{n}, receta de la casa preparada con ingredientes frescos")
             for i, n in enumerate(PLATILLOS_N)]
write("platillos.csv", ["id", "nombre", "precio", "descripcion"], platillos)
PLAT_PRECIO = {p[0]: p[2] for p in platillos}

# ---------------------------------------------------------------- Restaurante (200)
RANGOS = ["$", "$$", "$$$", "$$$$"]
PRECIO_MULT = {"$": 0.7, "$$": 1.0, "$$$": 1.5, "$$$$": 2.2}   # multiplicador del precio del platillo
CONSUMO_MEDIO = {"$": 15, "$$": 35, "$$$": 65, "$$$$": 120}   # consumo "esperado" por categoría (USD)
PROB_RESERVA = {"$": 0.12, "$$": 0.28, "$$$": 0.45, "$$$$": 0.62}
PREF = ["La Casona", "El Fogón", "Casa", "Rincón", "Sabores de", "Taller", "Mesa", "Cocina de", "El Patio",
        "Bistró", "Fuego y", "Terraza", "Mercado", "La Cantina", "Hacienda", "El Establo", "Villa", "Punto",
        "Taberna", "El Jardín"]
SUF = ["Antigua", "Zona 10", "del Mar", "Maya", "Verde", "Dorado", "del Lago", "Norte", "Sur", "Central",
       "del Chef", "Andino", "Urbano", "Tradicional", "Moderno"]
combos = random.sample([(a, b) for a in PREF for b in SUF], N_REST)
restaurantes, R = [], {}
for i, (a, b) in enumerate(combos):
    rid = f"R{i + 1:03d}"
    rango = random.choices(RANGOS, [25, 40, 25, 10])[0]
    R[rid] = dict(
        rango=rango,
        calidad=random.uniform(2.6, 4.8),                                # calidad latente (genera calificaciones)
        bias=random.uniform(0.9, 1.1) if random.random() < 0.75 else random.uniform(0.55, 1.6),
        p_res=clip(PROB_RESERVA[rango] + random.gauss(0, 0.12), 0.03, 0.9),
        tipos=random.sample(TIPO_IDS, random.choices([1, 2, 3], [50, 35, 15])[0]),
        menu=random.sample([p[0] for p in platillos], random.randint(5, 10)),
    )
    restaurantes.append((rid, f"{a} {b}", random.randint(1985, 2024), rango,
                         f"Restaurante de cocina variada ubicado en {b}"))
write("restaurantes.csv", ["id", "nombre", "anio_apertura", "rango_precios", "descripcion"], restaurantes)
REST_IDS = list(R)

pertenece = [(rid, t) for rid, d in R.items() for t in d["tipos"]]
write("pertenece_a.csv", ["restaurante_id", "tipo_id"], pertenece)

ofrece = []
for rid, d in R.items():
    for pid in d["menu"]:
        precio = round(PLAT_PRECIO[pid] * PRECIO_MULT[d["rango"]] * random.uniform(0.9, 1.2), 2)
        ofrece.append((rid, pid, precio, "true" if random.random() < 0.9 else "false"))
write("ofrece.csv", ["restaurante_id", "platillo_id", "precio", "disponible"], ofrece)

# ---------------------------------------------------------------- Chef (100)
NACION = ["Guatemala", "México", "Italia", "Japón", "Perú", "España", "Francia", "India", "Colombia", "Líbano"]
vistos, chefs = set(), []
while len(chefs) < N_CHEF:
    n = f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)} {random.choice(APELLIDOS)}"
    if n in vistos:
        continue
    vistos.add(n)
    chefs.append((f"C{len(chefs) + 1:03d}", n, rand_date(date(1955, 1, 1), date(1998, 12, 31)).isoformat(),
                  random.choice(NACION)))
write("chefs.csv", ["id", "nombre", "fecha_nacimiento", "nacionalidad"], chefs)

PUESTOS = ["Chef Ejecutivo", "Chef de Cocina", "Sous Chef", "Chef de Partida", "Chef Pastelero"]
ESTILOS = ["Tradicional", "Moderno", "Fusión", "Rústico", "Gourmet", "Casero"]
trabaja, prepara = [], []
for c in chefs:
    k = random.choices([1, 2, 3, 4], [35, 35, 20, 10])[0]
    rs = random.sample(REST_IDS, k)
    for rid in rs:
        trabaja.append((c[0], rid, rand_date(date(2005, 1, 1), date(2025, 6, 30)).isoformat(),
                        random.choice(PUESTOS)))
    # un chef prepara platillos que aparecen en los menús de sus restaurantes
    pool = sorted({p for rid in rs for p in R[rid]["menu"]})
    for pid in random.sample(pool, min(len(pool), random.randint(3, 6))):
        prepara.append((c[0], pid, random.choice(ESTILOS), "true" if random.random() < 0.35 else "false"))
write("trabaja_en.csv", ["chef_id", "restaurante_id", "fecha_inicio", "puesto"], trabaja)
write("prepara.csv", ["chef_id", "platillo_id", "estilo", "especialidad"], prepara)

# ---------------------------------------------------------------- Usuario (500)
usuarios, U = [], {}
for i in range(N_USU):
    uid = f"U{i + 1:04d}"
    nom, ap = random.choice(NOMBRES), random.choice(APELLIDOS)
    pais = random.choices(PAISES, PAISES_W)[0]
    usuarios.append((uid, f"{nom} {ap}", f"{slug(nom)}.{slug(ap)}{i + 1}@correo.com",
                     random.randint(18, 70), pais))
    U[uid] = {"pais": pais}
write("usuarios.csv", ["id", "nombre", "email", "edad", "pais"], usuarios)
USER_IDS = list(U)

# ---------------------------------------------------------------- LE_GUSTA
le_gusta = []
for uid in USER_IDS:
    gustos = random.sample(TIPO_IDS, random.randint(2, 4))
    niveles = [random.randint(1, 5) for _ in gustos]
    niveles[0] = random.randint(4, 5)            # al menos un favorito claro
    U[uid]["gustos"] = dict(zip(gustos, niveles))
    for t, n in zip(gustos, niveles):
        le_gusta.append((uid, t, n))
write("le_gusta.csv", ["usuario_id", "tipo_id", "nivel_interes"], le_gusta)

# ---------------------------------------------------------------- ES_AMIGO_DE (grafo conexo, ~2100 aristas)
por_pais = {}
for uid in USER_IDS:
    por_pais.setdefault(U[uid]["pais"], []).append(uid)
aristas = set()


def add_edge(a, b):
    if a != b and (a, b) not in aristas and (b, a) not in aristas:
        aristas.add((a, b))


for i in range(1, N_USU):                         # árbol base: garantiza que todos están conectados
    add_edge(USER_IDS[i], USER_IDS[random.randrange(0, i)])
while len(aristas) < 2100:
    a = random.choice(USER_IDS)
    b = random.choice(por_pais[U[a]["pais"]]) if random.random() < 0.5 else random.choice(USER_IDS)
    add_edge(a, b)
amistades = [(a, b, rand_date(date(2018, 1, 1), date(2026, 9, 30)).isoformat()) for a, b in sorted(aristas)]
write("amistades.csv", ["usuario_id", "amigo_id", "fecha_amistad"], amistades)

# ---------------------------------------------------------------- VISITÓ y CALIFICÓ
rest_por_tipo = {t: [] for t in TIPO_IDS}
for rid, d in R.items():
    for t in d["tipos"]:
        rest_por_tipo[t].append(rid)
COMENT = {1: ["Mala experiencia", "No volvería", "Servicio muy lento"],
          2: ["Regular, esperaba más", "Comida sin sabor", "Precio alto para lo que ofrecen"],
          3: ["Aceptable", "Cumple, nada especial", "Buen lugar pero irregular"],
          4: ["Muy buena comida", "Recomendado", "Excelente servicio"],
          5: ["¡Espectacular!", "Volveré pronto", "Una de las mejores experiencias"]}
visitas, califico = [], []
for uid in USER_IDS:
    gustos = U[uid]["gustos"]
    fav = max(gustos, key=gustos.get)
    k = random.randint(6, 14)
    visitados = set()
    while len(visitados) < k:
        x = random.random()
        pool = (rest_por_tipo[fav] if x < 0.5 else
                rest_por_tipo[random.choice(list(gustos))] if x < 0.75 else REST_IDS)
        visitados.add(random.choice(pool))
    for rid in sorted(visitados):
        d = R[rid]
        fechas = set()
        for _ in range(random.choice([1, 1, 2])):
            f = rand_date(date(2023, 1, 1), date(2026, 10, 1))
            if f in fechas:
                continue
            fechas.add(f)
            consumo = round(CONSUMO_MEDIO[d["rango"]] * d["bias"] * random.lognormvariate(0, 0.2), 2)
            visitas.append((uid, rid, f.isoformat(), consumo, "true" if random.random() < d["p_res"] else "false"))
        if random.random() < 0.7:
            p = int(clip(round(random.gauss(d["calidad"], 0.8)), 1, 5))
            fc = min(HOY, max(fechas) + timedelta(days=random.randint(0, 5)))
            califico.append((uid, rid, p, fc.isoformat(), random.choice(COMENT[p])))
write("visito.csv", ["usuario_id", "restaurante_id", "fecha_visita", "consumo", "con_reserva"], visitas)
write("califico.csv", ["usuario_id", "restaurante_id", "puntuacion", "fecha", "comentario"], califico)
print("\nListo. Copia la carpeta csv/ a la carpeta 'import' de tu DBMS de Neo4j.")
