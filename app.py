# ============================================================
# NÓMINA STAR - Sistema de Nómina para Venezuela
# Tecnología: Python + Streamlit + SQLite (todo en un archivo)
# Sin conocimientos de programación: solo subir a GitHub y conectar
# ============================================================
import sqlite3
import streamlit as st
import pandas as pd
from datetime import datetime

# ---------- CONFIGURACIÓN DE PÁGINA ----------
st.set_page_config(
    page_title="Nómina Star",
    page_icon="💼",
    layout="wide"
)

# ---------- BASE DE DATOS (SQLite, archivo local) ----------
import os
DB = "/tmp/nomina.db"

def conectar():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    conn = conectar()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS empleados(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cedula TEXT UNIQUE,
        nombre TEXT,
        cargo TEXT,
        salario REAL,
        fecha_ingreso TEXT,
        activo INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS config(
        clave TEXT PRIMARY KEY, valor REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS nomina(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        periodo TEXT,
        cedula TEXT,
        nombre TEXT,
        cargo TEXT,
        salario_base REAL,
        cesta_ticket REAL,
        ded_ivss REAL,
        ded_faov REAL,
        ded_rpe REAL,
        total_deducciones REAL,
        total_pagar REAL)""")
    # Valores por defecto (ley venezolana, verificables en Configuración)
    defaults = {"ivss_pct": 4.0, "faov_pct": 1.0, "rpe_pct": 0.5, "cesta_ticket": 130.0}
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO config(clave, valor) VALUES(?,?)", (k, v))
    conn.commit()
    conn.close()

def get_config():
    conn = conectar()
    df = pd.read_sql("SELECT clave, valor FROM config", conn)
    conn.close()
    return dict(zip(df["clave"], df["valor"]))

def set_config(d):
    conn = conectar()
    c = conn.cursor()
    for k, v in d.items():
        c.execute("UPDATE config SET valor=? WHERE clave=?", (v, k))
    conn.commit()
    conn.close()

init_db()
cfg = get_config()

# ---------- ENCABEZADO ----------
st.title("💼 Nómina Star")
st.caption("Sistema de nómina web - Venezuela | Datos guardados automáticamente")

menu = st.sidebar.radio("📋 MENÚ", ["👥 Empleados", "⚙️ Configuración", "💰 Generar Nómina", "📜 Historial"])

MESES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
         "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

# ============================================================
# MÓDULO 1: EMPLEADOS
# ============================================================
if menu == "👥 Empleados":
    st.header("Gestión de Empleados")

    with st.expander("➕ Agregar nuevo empleado"):
        with st.form("form_empleado", clear_on_submit=True):
            col1, col2 = st.columns(2)
            cedula = col1.text_input("Cédula (V-12345678)")
            nombre = col2.text_input("Nombre completo")
            cargo = col1.text_input("Cargo")
            salario = col2.number_input("Salario mensual (Bs)", min_value=0.0, step=0.01)
            fecha = col1.date_input("Fecha de ingreso", datetime.now())
            if st.form_submit_button("💾 Guardar empleado"):
                if cedula and nombre and salario > 0:
                    try:
                        conn = conectar()
                        conn.execute("INSERT INTO empleados(cedula,nombre,cargo,salario,fecha_ingreso,activo) VALUES(?,?,?,?,?,1)",
                                     (cedula, nombre, cargo, salario, str(fecha)))
                        conn.commit(); conn.close()
                        st.success(f"✅ {nombre} guardado correctamente")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("⚠️ Ya existe un empleado con esa cédula")
                else:
                    st.error("⚠️ Completa cédula, nombre y salario")

    conn = conectar()
    df = pd.read_sql("SELECT id, cedula, nombre, cargo, salario, fecha_ingreso, activo FROM empleados ORDER BY nombre", conn)
    conn.close()

    if df.empty:
        st.info("Aún no hay empleados registrados. Usa el formulario de arriba.")
    else:
        df["estado"] = df["activo"].map({1: "🟢 Activo", 0: "🔴 Inactivo"})
        df["salario"] = df["salario"].map("{:,.2f}".format)
        st.dataframe(df[["cedula","nombre","cargo","salario","fecha_ingreso","estado"]],
                     use_container_width=True, hide_index=True)

        col_a, col_b = st.columns(2)
        con_cedula = col_a.selectbox("Empleado a cambiar estado", df["cedula"].tolist())
        if col_b.button("🔄 Activar / Desactivar"):
            conn = conectar()
            conn.execute("UPDATE empleados SET activo = 1 - activo WHERE cedula=?", (con_cedula,))
            conn.commit(); conn.close()
            st.rerun()

# ============================================================
# MÓDULO 2: CONFIGURACIÓN (tasas de deducciones)
# ============================================================
elif menu == "⚙️ Configuración":
    st.header("Configuración de Tasas y Deducciones")
    st.warning("⚖️ Verifica estos valores con tu contador. Cambian según reformas de ley.")

    with st.form("form_config"):
        ivss = st.number_input("IVSS - Seguro social (% trabajador)", value=float(cfg["ivss_pct"]), step=0.1)
        faov = st.number_input("FAOV - Vivienda (% trabajador)", value=float(cfg["faov_pct"]), step=0.1)
        rpe = st.number_input("RPE - Régimen Prestacional (% trabajador)", value=float(cfg["rpe_pct"]), step=0.1)
        cesta = st.number_input("Cesta ticket mensual (Bs)", value=float(cfg["cesta_ticket"]), step=1.0)
        if st.form_submit_button("💾 Guardar configuración"):
            set_config({"ivss_pct": ivss, "faov_pct": faov, "rpe_pct": rpe, "cesta_ticket": cesta})
            st.success("✅ Configuración guardada")
            st.rerun()

    st.info(f"""
    **Resumen actual:**
    - IVSS: {cfg['ivss_pct']}% | FAOV: {cfg['faov_pct']}% | RPE: {cfg['rpe_pct']}%
    - Cesta ticket: Bs {cfg['cesta_ticket']:,.2f}
    """)

# ============================================================
# MÓDULO 3: GENERAR NÓMINA
# ============================================================
elif menu == "💰 Generar Nómina":
    st.header("Generar Nómina del Mes")

    col1, col2 = st.columns(2)
    mes = col1.selectbox("Mes", MESES, index=datetime.now().month - 1)
    anio = col2.number_input("Año", value=datetime.now().year, step=1)
    periodo = f"{mes} {anio}"

    conn = conectar()
    emp = pd.read_sql("SELECT * FROM empleados WHERE activo=1", conn)
    conn.close()

    if emp.empty:
        st.info("No hay empleados activos para procesar nómina.")
    else:
        if st.button(f"🧮 Calcular nómina de {periodo}", type="primary"):
            # Borrar nómina previa del mismo periodo (recalculo permitido)
            conn = conectar()
            conn.execute("DELETE FROM nomina WHERE periodo=?", (periodo,))
            for _, e in emp.iterrows():
                salario = float(e["salario"])
                ded_ivss = salario * cfg["ivss_pct"] / 100
                ded_faov = salario * cfg["faov_pct"] / 100
                ded_rpe = salario * cfg["rpe_pct"] / 100
                total_ded = ded_ivss + ded_faov + ded_rpe
                total_pagar = salario + cfg["cesta_ticket"] - total_ded
                conn.execute("""INSERT INTO nomina(periodo,cedula,nombre,cargo,salario_base,cesta_ticket,
                             ded_ivss,ded_faov,ded_rpe,total_deducciones,total_pagar)
                             VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                             (periodo, e["cedula"], e["nombre"], e["cargo"], salario,
                              cfg["cesta_ticket"], ded_ivss, ded_faov, ded_rpe, total_ded, total_pagar))
            conn.commit(); conn.close()
            st.success(f"✅ Nómina de {periodo} calculada")

        # Mostrar nómina del periodo
        conn = conectar()
        nom = pd.read_sql("SELECT * FROM nomina WHERE periodo=?", conn, params=(periodo,))
        conn.close()

        if not nom.empty:
            vista = nom[["cedula","nombre","cargo","salario_base","cesta_ticket",
                         "ded_ivss","ded_faov","ded_rpe","total_deducciones","total_pagar"]].copy()
            for c in ["salario_base","cesta_ticket","ded_ivss","ded_faov","ded_rpe","total_deducciones","total_pagar"]:
                vista[c] = vista[c].map("Bs {:,.2f}".format)
            st.dataframe(vista, use_container_width=True, hide_index=True)

            total_general = nom["total_pagar"].sum()
            st.metric("💵 Total a pagar (toda la planilla)", f"Bs {total_general:,.2f}")

            # Descargar en Excel/CSV
            csv = nom.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Descargar nómina (Excel/CSV)", csv,
                               f"nomina_{mes}_{anio}.csv", "text/csv")

            # Recibo individual imprimible
            st.divider()
            st.subheader("🧾 Recibo de pago individual")
            recibo = st.selectbox("Selecciona empleado", nom["nombre"].tolist())
            r = nom[nom["nombre"] == recibo].iloc[0]
            c1, c2 = st.columns(2)
            c1.write(f"**Empleado:** {r['nombre']}\n\n**Cédula:** {r['cedula']}\n\n**Cargo:** {r['cargo']}")
            c2.write(f"**Período:** {periodo}")
            st.table(pd.DataFrame({
                "Concepto": ["Salario base","Cesta ticket","(-) IVSS","(-) FAOV","(-) RPE","**TOTAL A PAGAR**"],
                "Monto": [f"Bs {r['salario_base']:,.2f}", f"Bs {r['cesta_ticket']:,.2f}",
                          f"Bs {r['ded_ivss']:,.2f}", f"Bs {r['ded_faov']:,.2f}",
                          f"Bs {r['ded_rpe']:,.2f}", f"**Bs {r['total_pagar']:,.2f}**"]
            }))
            st.button("🖨️ Imprimir recibo (Ctrl+P en el navegador)")

# ============================================================
# MÓDULO 4: HISTORIAL
# ============================================================
elif menu == "📜 Historial":
    st.header("Historial de Nóminas Procesadas")
    conn = conectar()
    periodos = pd.read_sql("SELECT DISTINCT periodo FROM nomina ORDER BY id DESC", conn)
    conn.close()

    if periodos.empty:
        st.info("No hay nóminas registradas aún.")
    else:
        sel = st.selectbox("Período", periodos["periodo"].tolist())
        conn = conectar()
        hist = pd.read_sql("SELECT * FROM nomina WHERE periodo=?", conn, params=(sel,))
        conn.close()
        st.dataframe(hist, use_container_width=True, hide_index=True)
        csv = hist.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Descargar", csv, f"nomina_{sel}.csv", "text/csv")
