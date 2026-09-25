# ============================================================
# NOMINA STAR v3 - Datos persistentes en Supabase (PostgreSQL)
# ============================================================
import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime

st.set_page_config(page_title="Nómina Star", page_icon="💼", layout="wide")

@st.cache_resource
def get_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

db = get_db()

def leer(tabla):
    return pd.DataFrame(db.table(tabla).select("*").order("id").execute().data)

# Configuración por defecto (Venezuela) si la tabla está vacía
cfg_df = leer("config")
if cfg_df.empty:
    for k, v in {"ivss_pct": 4.0, "faov_pct": 1.0, "rpe_pct": 0.5, "cesta_ticket": 130.0}.items():
        db.table("config").insert({"clave": k, "valor": v}).execute()
    cfg_df = leer("config")
cfg = dict(zip(cfg_df["clave"], cfg_df["valor"].astype(float)))

# ---------- ENCABEZADO ----------
st.title("💼 Nómina Star")
st.caption("Sistema de nómina web - Venezuela | Base de datos PostgreSQL en Supabase")

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
                    existe = db.table("empleados").select("cedula").eq("cedula", cedula).execute().data
                    if existe:
                        st.error("⚠️ Ya existe un empleado con esa cédula")
                    else:
                        db.table("empleados").insert({
                            "cedula": cedula, "nombre": nombre, "cargo": cargo,
                            "salario": salario, "fecha_ingreso": str(fecha), "activo": 1}).execute()
                        st.success(f"✅ {nombre} guardado permanentemente")
                        st.rerun()
                else:
                    st.error("⚠️ Completa cédula, nombre y salario")

    df = leer("empleados")

    if df.empty:
        st.info("Aún no hay empleados registrados.")
    else:
        vista = df.copy()
        vista["estado"] = vista["activo"].map({1: "🟢 Activo", 0: "🔴 Inactivo"})
        vista["salario"] = vista["salario"].astype(float).map("{:,.2f}".format)
        st.dataframe(vista[["cedula","nombre","cargo","salario","fecha_ingreso","estado"]],
                     use_container_width=True, hide_index=True)

        col_a, col_b = st.columns(2)
        con_cedula = col_a.selectbox("Empleado a cambiar estado", vista["cedula"].tolist())
        if col_b.button("🔄 Activar / Desactivar"):
            fila = df[df["cedula"] == con_cedula].iloc[0]
            db.table("empleados").update({"activo": 1 - int(fila["activo"])}).eq("cedula", con_cedula).execute()
            st.rerun()

# ============================================================
# MÓDULO 2: CONFIGURACIÓN
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
            for k, v in {"ivss_pct": ivss, "faov_pct": faov, "rpe_pct": rpe, "cesta_ticket": cesta}.items():
                db.table("config").update({"valor": v}).eq("clave", k).execute()
            st.success("✅ Configuración guardada")
            st.rerun()

    st.info(f"**Resumen actual:** IVSS: {cfg['ivss_pct']}% | FAOV: {cfg['faov_pct']}% | "
            f"RPE: {cfg['rpe_pct']}% | Cesta ticket: Bs {cfg['cesta_ticket']:,.2f}")

# ============================================================
# MÓDULO 3: GENERAR NÓMINA
# ============================================================
elif menu == "💰 Generar Nómina":
    st.header("Generar Nómina del Mes")

    col1, col2 = st.columns(2)
    mes = col1.selectbox("Mes", MESES, index=datetime.now().month - 1)
    anio = col2.number_input("Año", value=datetime.now().year, step=1)
    periodo = f"{mes} {anio}"

    emp = leer("empleados")
    emp = emp[emp["activo"] == 1]

    if emp.empty:
        st.info("No hay empleados activos para procesar nómina.")
    else:
        if st.button(f"🧮 Calcular nómina de {periodo}", type="primary"):
            db.table("nomina").delete().eq("periodo", periodo).execute()  # permite recalcular
            for _, e in emp.iterrows():
                salario = float(e["salario"])
                ded_ivss = salario * cfg["ivss_pct"] / 100
                ded_faov = salario * cfg["faov_pct"] / 100
                ded_rpe = salario * cfg["rpe_pct"] / 100
                total_ded = ded_ivss + ded_faov + ded_rpe
                db.table("nomina").insert({
                    "periodo": periodo, "cedula": e["cedula"], "nombre": e["nombre"],
                    "cargo": e["cargo"], "salario_base": salario,
                    "cesta_ticket": cfg["cesta_ticket"], "ded_ivss": ded_ivss,
                    "ded_faov": ded_faov, "ded_rpe": ded_rpe,
                    "total_deducciones": total_ded,
                    "total_pagar": salario + cfg["cesta_ticket"] - total_ded}).execute()
            st.success(f"✅ Nómina de {periodo} calculada y guardada permanentemente")

        nom = pd.DataFrame(db.table("nomina").select("*").eq("periodo", periodo).execute().data)

        if not nom.empty:
            vista = nom[["cedula","nombre","cargo","salario_base","cesta_ticket",
                         "ded_ivss","ded_faov","ded_rpe","total_deducciones","total_pagar"]].copy()
            for c in vista.columns[3:]:
                vista[c] = vista[c].astype(float).map("Bs {:,.2f}".format)
            st.dataframe(vista, use_container_width=True, hide_index=True)

            st.metric("💵 Total a pagar (toda la planilla)",
                      f"Bs {nom['total_pagar'].astype(float).sum():,.2f}")

            csv = nom.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Descargar nómina (Excel/CSV)", csv,
                               f"nomina_{mes}_{anio}.csv", "text/csv")

            st.divider()
            st.subheader("🧾 Recibo de pago individual")
            recibo = st.selectbox("Selecciona empleado", nom["nombre"].tolist())
            r = nom[nom["nombre"] == recibo].iloc[0]
            st.write(f"**Empleado:** {r['nombre']} | **Cédula:** {r['cedula']} | **Cargo:** {r['cargo']} | **Período:** {periodo}")
            st.table(pd.DataFrame({
                "Concepto": ["Salario base","Cesta ticket","(-) IVSS","(-) FAOV","(-) RPE","TOTAL A PAGAR"],
                "Monto": [f"Bs {float(r['salario_base']):,.2f}", f"Bs {float(r['cesta_ticket']):,.2f}",
                          f"Bs {float(r['ded_ivss']):,.2f}", f"Bs {float(r['ded_faov']):,.2f}",
                          f"Bs {float(r['ded_rpe']):,.2f}", f"Bs {float(r['total_pagar']):,.2f}"]
            }))
            st.caption("🖨️ Para imprimir: Ctrl+P en el navegador")

# ============================================================
# MÓDULO 4: HISTORIAL
# ============================================================
elif menu == "📜 Historial":
    st.header("Historial de Nóminas Procesadas")
    nom = leer("nomina")

    if nom.empty:
        st.info("No hay nóminas registradas aún.")
    else:
        periodos = nom["periodo"].unique()[::-1]
        sel = st.selectbox("Período", periodos)
        hist = nom[nom["periodo"] == sel]
        st.dataframe(hist, use_container_width=True, hide_index=True)
        csv = hist.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Descargar", csv, f"nomina_{sel}.csv", "text/csv")
        st.caption("💡 En Supabase > Table Editor puedes ver y editar todas las tablas directamente")
