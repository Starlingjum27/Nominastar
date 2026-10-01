# ============================================================
# NOMINA STAR v4 - Sistema Completo con Seguridad y Supabase
# ============================================================
import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime
import time

st.set_page_config(page_title="Nómina SJUM", page_icon="💼", layout="wide")
# ============================================================
# FUNCIONES AUXILIARES DE TASA BCV
# ============================================================
from tasa_bcv import obtener_tasa_bcv

def obtener_tasa_del_dia(fecha=None):
    """Obtiene la tasa BCV para una fecha dada (o la más reciente)."""
    if fecha is None:
        fecha = datetime.now().strftime("%Y-%m-%d")
    result = db.table("tasa_bcv").select("*").eq("fecha", fecha).execute().data
    if result:
        return result[0]
    # Si no hay para esa fecha, buscar la más reciente
    result = db.table("tasa_bcv").select("*").order("fecha", desc=True).limit(1).execute().data
    return result[0] if result else None

def guardar_tasa(fecha, tasa, fuente="manual", usuario="admin"):
    """Guarda o actualiza la tasa BCV del día."""
    try:
        existente = db.table("tasa_bcv").select("id").eq("fecha", fecha).execute().data
        if existente:
            db.table("tasa_bcv").update({
                "tasa_usd_bs": tasa,
                "fuente": fuente,
                "usuario": usuario
            }).eq("fecha", fecha).execute()
        else:
            db.table("tasa_bcv").insert({
                "fecha": fecha,
                "tasa_usd_bs": tasa,
                "fuente": fuente,
                "usuario": usuario
            }).execute()
        return True
    except Exception as e:
        return False

# ============================================================
# SEGURIDAD: PANTALLA DE LOGIN
# ============================================================
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("🔒 Acceso Restringido")
        st.text_input("Ingresa la contraseña del sistema de nómina", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.title("🔒 Acceso Restringido")
        st.text_input("Ingresa la contraseña del sistema de nómina", type="password", on_change=password_entered, key="password")
        st.error("😕 Contraseña incorrecta. Intenta de nuevo.")
        return False
    else:
        return True

if not check_password():
    st.stop()

# ============================================================
# CONEXIÓN A SUPABASE
# ============================================================
@st.cache_resource
def get_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

db = get_db()

def leer(tabla, order_by="id"):
    """Lee una tabla de Supabase con reintentos."""
    try:
        query = db.table(tabla).select("*")
        if order_by:
            query = query.order(order_by)
        response = query.execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"⚠️ Error al leer la tabla '{tabla}': {e}")
        return pd.DataFrame()

# Cargar configuración inicial
cfg_df = leer("config", order_by=None)
if cfg_df.empty:
    # Valores por defecto si la tabla está vacía
    defaults = {"ivss_pct": 4.0, "faov_pct": 1.0, "rpe_pct": 0.5, "cesta_ticket": 130.0}
    for k, v in defaults.items():
        try:
            db.table("config").insert({"clave": k, "valor": v}).execute()
        except Exception:
            pass
    cfg_df = leer("config", order_by=None)

if cfg_df.empty:
    cfg = {"ivss_pct": 4.0, "faov_pct": 1.0, "rpe_pct": 0.5, "cesta_ticket": 130.0}
else:
    cfg = dict(zip(cfg_df["clave"], cfg_df["valor"].astype(float)))

# ============================================================
# ENCABEZADO Y MENÚ
# ============================================================
st.title("💼 Nómina Star")
st.caption("Sistema de nómina web - Venezuela | Base de datos PostgreSQL en Supabase")

menu = st.sidebar.radio("📋 MENÚ", ["👥 Empleados", "💱 Tasa BCV", "⚙️ Configuración", "💰 Generar Nómina", "📜 Historial"])

MESES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
         "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

# ============================================================
# MÓDULO 1: EMPLEADOS (Ficha completa LOTTT + Dual Moneda)
# ============================================================
if menu == "👥 Empleados":
    st.header("Gestión de Empleados")

    tab_registro, tab_lista = st.tabs(["➕ Registrar / Editar", "📋 Lista y Administración"])

    # ------------------------------------------------------------
    # PESTAÑA 1: REGISTRO
    # ------------------------------------------------------------
    with tab_registro:
        st.subheader("Ficha del Empleado")
        st.caption("Completa los campos. Los marcados con * son obligatorios.")

        with st.form("form_empleado_completo", clear_on_submit=True):
            # --- DATOS PERSONALES ---
            st.markdown("#### 👤 Datos Personales")
            col1, col2, col3 = st.columns([1, 2, 2])
            tipo_cedula = col1.selectbox("Tipo *", ["V", "E", "J", "P"])
            cedula_num = col2.text_input("Cédula * (solo números)")
            nombre = col3.text_input("Nombre completo *")

            col1, col2, col3 = st.columns(3)
            fecha_nac = col1.date_input("Fecha de nacimiento", datetime(1990, 1, 1))
            telefono = col2.text_input("Teléfono")
            email = col3.text_input("Email")

            direccion = st.text_area("Dirección", height=68)

            # --- DATOS LABORALES ---
            st.markdown("#### 💼 Datos Laborales")
            col1, col2, col3 = st.columns(3)
            cargo = col1.text_input("Cargo *")
            departamento = col2.text_input("Departamento")
            centro_costo = col3.text_input("Centro de costo")

            col1, col2, col3 = st.columns(3)
            tipo_contrato = col1.selectbox("Tipo de contrato", ["INDEFINIDO", "FIJO", "OBRA", "TEMPORADO"])
            frecuencia = col2.selectbox("Frecuencia de pago", ["Mensual", "Quincenal", "Semanal"])
            estatus_lottt = col3.selectbox("Estatus", ["ACTIVO", "SUSPENDIDO", "VACACIONES", "EGRESADO"])

            col1, col2 = st.columns(2)
            fecha_ingreso = col1.date_input("Fecha de ingreso *", datetime.now())
            fecha_egreso = col2.date_input("Fecha de egreso (si aplica)", datetime.now())

            # --- SALARIO DUAL ---
            st.markdown("#### 💵 Salario (Dual Moneda)")
            col1, col2, col3 = st.columns(3)
            salario_usd = col1.number_input("Salario mensual en USD *", min_value=0.0, step=1.0, format="%.2f")
            tipo_pago = col2.selectbox("Tipo de pago", ["BS", "USD", "MIXTO"])
            porcentaje_usd = col3.number_input("% pagado en USD (si es MIXTO)", min_value=0.0, max_value=100.0, step=1.0)

            # --- DATOS BANCARIOS ---
            st.markdown("#### 🏦 Datos Bancarios")
            col1, col2, col3 = st.columns(3)
            banco = col1.text_input("Banco")
            cuenta_bancaria = col2.text_input("Número de cuenta")
            titular_cuenta = col3.text_input("Titular de la cuenta")

            # --- BOTÓN DE GUARDAR ---
            if st.form_submit_button("💾 Guardar empleado", type="primary"):
                cedula_completa = f"{tipo_cedula}-{cedula_num.strip()}"

                if not cedula_num or not nombre or not cargo or salario_usd <= 0:
                    st.error("⚠️ Completa los campos obligatorios: cédula, nombre, cargo y salario USD.")
                else:
                    try:
                        existe = db.table("empleados").select("cedula").eq("cedula", cedula_completa).execute().data
                        if existe:
                            st.error(f"⚠️ Ya existe un empleado con la cédula {cedula_completa}")
                        else:
                            db.table("empleados").insert({
                                "cedula": cedula_completa,
                                "tipo_cedula": tipo_cedula,
                                "nombre": nombre,
                                "fecha_nacimiento": str(fecha_nac),
                                "telefono": telefono,
                                "email": email,
                                "direccion": direccion,
                                "cargo": cargo,
                                "departamento": departamento,
                                "centro_costo": centro_costo,
                                "tipo_contrato": tipo_contrato,
                                "frecuencia_pago": frecuencia,
                                "estatus_lottt": estatus_lottt,
                                "fecha_ingreso": str(fecha_ingreso),
                                "fecha_egreso": str(fecha_egreso) if estatus_lottt == "EGRESADO" else None,
                                "salario_usd": salario_usd,
                                "salario": 0,  # Se calculará en Bs al generar nómina
                                "tipo_pago": tipo_pago,
                                "porcentaje_usd": porcentaje_usd,
                                "banco": banco,
                                "cuenta_bancaria": cuenta_bancaria,
                                "titular_cuenta": titular_cuenta,
                                "activo": 1
                            }).execute()
                            st.success(f"✅ {nombre} ({cedula_completa}) guardado exitosamente.")
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al guardar: {e}")

    # ------------------------------------------------------------
    # PESTAÑA 2: LISTA Y ADMINISTRACIÓN
    # ------------------------------------------------------------
    with tab_lista:
        df = leer("empleados")

        if df.empty:
            st.info("Aún no hay empleados registrados.")
        else:
            # Buscador
            busqueda = st.text_input("🔍 Buscar por cédula, nombre o departamento:", "")
            if busqueda:
                df_filtrado = df[
                    df["cedula"].str.contains(busqueda, case=False, na=False) |
                    df["nombre"].str.contains(busqueda, case=False, na=False) |
                    df.get("departamento", pd.Series(dtype=str)).astype(str).str.contains(busqueda, case=False, na=False)
                ]
            else:
                df_filtrado = df

            if df_filtrado.empty:
                st.warning("No se encontraron empleados con esa búsqueda.")
            else:
                vista = df_filtrado.copy()
                vista["estado"] = vista["activo"].map({1: "🟢 Activo", 0: "🔴 Inactivo"})

                # Construir columnas dinámicamente
                cols = ["cedula", "nombre", "cargo"]
                if "departamento" in vista.columns:
                    cols.append("departamento")
                if "salario_usd" in vista.columns:
                    vista["salario_usd"] = vista["salario_usd"].astype(float).map("$ {:,.2f}".format)
                    cols.append("salario_usd")
                if "frecuencia_pago" in vista.columns:
                    cols.append("frecuencia_pago")
                cols.extend(["fecha_ingreso", "estado"])

                st.dataframe(vista[cols], use_container_width=True, hide_index=True)

            st.divider()

            # --- ADMINISTRAR EMPLEADO ---
            st.subheader("🛠️ Administrar Empleado")
            cedulas_lista = df["cedula"].tolist()
            empleado_sel = st.selectbox("Selecciona un empleado", cedulas_lista)
            datos_emp = df[df["cedula"] == empleado_sel].iloc[0]

            tab_edit, tab_estado, tab_hist, tab_elim = st.tabs(
                ["✏️ Editar", "🔄 Estatus", "📊 Historial Salarial", "🗑️ Eliminar"]
            )

            # --- EDITAR ---
            with tab_edit:
                with st.form("form_editar_emp"):
                    st.write(f"Editando a: **{datos_emp['nombre']}** ({datos_emp['cedula']})")

                    col1, col2, col3 = st.columns(3)
                    nuevo_nombre = col1.text_input("Nombre", value=datos_emp["nombre"])
                    nuevo_cargo = col2.text_input("Cargo", value=datos_emp.get("cargo", "") or "")
                    nuevo_depto = col3.text_input("Departamento", value=datos_emp.get("departamento", "") or "")

                    col1, col2, col3 = st.columns(3)
                    salario_actual = float(datos_emp.get("salario_usd", 0) or 0)
                    nuevo_salario_usd = col1.number_input("Salario USD", value=salario_actual, step=1.0, format="%.2f")
                    freq_actual = datos_emp.get("frecuencia_pago", "Mensual") or "Mensual"
                    opciones_freq = ["Mensual", "Quincenal", "Semanal"]
                    idx_freq = opciones_freq.index(freq_actual) if freq_actual in opciones_freq else 0
                    nueva_frecuencia = col2.selectbox("Frecuencia", opciones_freq, index=idx_freq)

                    tipo_pago_actual = datos_emp.get("tipo_pago", "BS") or "BS"
                    opciones_tipo = ["BS", "USD", "MIXTO"]
                    idx_tipo = opciones_tipo.index(tipo_pago_actual) if tipo_pago_actual in opciones_tipo else 0
                    nuevo_tipo_pago = col3.selectbox("Tipo de pago", opciones_tipo, index=idx_tipo)

                    col1, col2 = st.columns(2)
                    nuevo_telefono = col1.text_input("Teléfono", value=datos_emp.get("telefono", "") or "")
                    nuevo_email = col2.text_input("Email", value=datos_emp.get("email", "") or "")

                    motivo = st.text_input("Motivo del cambio (opcional, para auditoría)", "")

                    if st.form_submit_button("💾 Guardar cambios"):
                        try:
                            # Si cambió el salario, registrar en historial
                            if nuevo_salario_usd != salario_actual:
                                db.table("historial_salarial").insert({
                                    "cedula": empleado_sel,
                                    "salario_usd_anterior": salario_actual,
                                    "salario_usd_nuevo": nuevo_salario_usd,
                                    "motivo": motivo or "Ajuste sin motivo especificado",
                                    "usuario": "admin"
                                }).execute()

                            db.table("empleados").update({
                                "nombre": nuevo_nombre,
                                "cargo": nuevo_cargo,
                                "departamento": nuevo_depto,
                                "salario_usd": nuevo_salario_usd,
                                "frecuencia_pago": nueva_frecuencia,
                                "tipo_pago": nuevo_tipo_pago,
                                "telefono": nuevo_telefono,
                                "email": nuevo_email
                            }).eq("cedula", empleado_sel).execute()

                            st.success("✅ Empleado actualizado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al actualizar: {e}")

            # --- CAMBIAR ESTATUS ---
            with tab_estado:
                estatus_actual = datos_emp.get("estatus_lottt", "ACTIVO") or "ACTIVO"
                st.write(f"Estatus actual: **{estatus_actual}**")
                nuevo_estatus = st.selectbox(
                    "Cambiar estatus a:",
                    ["ACTIVO", "SUSPENDIDO", "VACACIONES", "EGRESADO"],
                    index=["ACTIVO", "SUSPENDIDO", "VACACIONES", "EGRESADO"].index(estatus_actual) if estatus_actual in ["ACTIVO", "SUSPENDIDO", "VACACIONES", "EGRESADO"] else 0
                )
                if st.button("🔄 Actualizar estatus"):
                    try:
                        activo = 1 if nuevo_estatus == "ACTIVO" else 0
                        db.table("empleados").update({
                            "estatus_lottt": nuevo_estatus,
                            "activo": activo
                        }).eq("cedula", empleado_sel).execute()
                        st.success(f"✅ Estatus cambiado a {nuevo_estatus}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {e}")

            # --- HISTORIAL SALARIAL ---
            with tab_hist:
                hist = leer("historial_salarial")
                if hist.empty:
                    st.info("No hay cambios salariales registrados para este empleado.")
                else:
                    hist_emp = hist[hist["cedula"] == empleado_sel].sort_values("created_at", ascending=False)
                    if hist_emp.empty:
                        st.info("Este empleado no tiene cambios salariales registrados.")
                    else:
                        for _, h in hist_emp.iterrows():
                            st.write(
                                f"📅 **{h['created_at'][:10]}** — "
                                f"${float(h['salario_usd_anterior']):,.2f} → "
                                f"**${float(h['salario_usd_nuevo']):,.2f}** — "
                                f"_{h.get('motivo', 'Sin motivo')}_"
                            )

            # --- ELIMINAR ---
            with tab_elim:
                st.warning("⚠️ Esta acción borrará al empleado permanentemente. No se puede deshacer.")
                confirmar = st.checkbox("Sí, estoy seguro de eliminar a este empleado")
                if st.button("🗑️ Eliminar Definitivamente", type="primary"):
                    if confirmar:
                        try:
                            db.table("empleados").delete().eq("cedula", empleado_sel).execute()
                            st.success(f"🗑️ {datos_emp['nombre']} eliminado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al eliminar: {e}")
                    else:
                        st.error("Debes marcar la casilla de confirmación.")
# ============================================================
# MÓDULO: TASA BCV
# ============================================================
elif menu == "💱 Tasa BCV":
    st.header("💱 Gestión de la Tasa BCV")
    st.caption("La tasa oficial del Banco Central de Venezuela se usa para convertir salarios USD a Bs.")
    
    # --- CARGA AUTOMÁTICA ---
    st.subheader("🤖 Carga Automática")
    if st.button("🔄 Obtener tasa del BCV ahora", type="primary"):
        with st.spinner("Consultando bcv.org.ve..."):
            resultado = obtener_tasa_bcv()
            if resultado:
                exito = guardar_tasa(resultado["fecha"], resultado["tasa"], "automatica", "sistema")
                if exito:
                    st.success(f"✅ Tasa obtenida: **{resultado['tasa']:.2f} Bs/USD** (Fecha: {resultado['fecha']})")
                    st.rerun()
                else:
                    st.error("❌ Error al guardar la tasa en Supabase.")
            else:
                st.warning("⚠️ No se pudo obtener la tasa automáticamente. El sitio del BCV puede estar caído o cambió su estructura.")
                st.info("💡 Usa la carga manual de abajo.")
    
    st.divider()
    
    # --- CARGA MANUAL ---
    st.subheader("✍️ Carga Manual")
    st.info("Usa esta opción si la carga automática falla o si necesitas corregir un valor.")
    
    with st.form("form_tasa_manual"):
        fecha_manual = st.date_input("Fecha de la tasa", datetime.now())
        tasa_manual = st.number_input("Tasa USD → Bs", min_value=0.0, step=0.01, format="%.2f")
        if st.form_submit_button("💾 Guardar tasa manual"):
            if tasa_manual > 0:
                exito = guardar_tasa(str(fecha_manual), tasa_manual, "manual", "admin")
                if exito:
                    st.success(f"✅ Tasa guardada: **{tasa_manual:.2f} Bs/USD** para el {fecha_manual}")
                    st.rerun()
                else:
                    st.error("❌ Error al guardar.")
            else:
                st.error("⚠️ La tasa debe ser mayor a 0.")
    
    st.divider()
    
    # --- HISTORIAL ---
    st.subheader("📜 Historial de Tasas")
    tasas = leer("tasa_bcv")
    if tasas.empty:
        st.info("No hay tasas registradas aún.")
    else:
        tasas = tasas.sort_values("fecha", ascending=False)
        for _, t in tasas.iterrows():
            fuente_icono = "🤖" if t["fuente"] == "automatica" else "✍️"
            st.write(f"{fuente_icono} **{t['fecha']}** → **{float(t['tasa_usd_bs']):,.2f} Bs/USD** ({t['fuente']})")
        
        csv = tasas.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Descargar historial (CSV)", csv, "tasa_bcv_historial.csv", "text/csv")   
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
            try:
                for k, v in {"ivss_pct": ivss, "faov_pct": faov, "rpe_pct": rpe, "cesta_ticket": cesta}.items():
                    db.table("config").update({"valor": v}).eq("clave", k).execute()
                st.success("✅ Configuración guardada")
                st.rerun()
            except Exception:
                st.error("❌ Error al guardar la configuración. Revisa los permisos de Supabase.")

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
    if not emp.empty:
        emp = emp[emp["activo"] == 1]

    if emp.empty:
        st.info("No hay empleados activos para procesar nómina.")
    else:
        if st.button(f"🧮 Calcular nómina de {periodo}", type="primary"):
            try:
                db.table("nomina").delete().eq("periodo", periodo).execute()
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
            except Exception:
                st.error("❌ Error al guardar la nómina. Revisa los permisos de Supabase.")

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
