import io
from datetime import date
import pandas as pd
import streamlit as st
from euko.schema import COLUMNS, clean_columns, coerce_types
from euko.normalize import normalize_matches, select_last5, normalize_h2h
from euko.validate import quality_report

st.set_page_config(page_title="EUKO Football Analyzer V2", page_icon="⚽", layout="wide")
st.title("⚽ EUKO Football Analyzer — V2")
st.caption("Ingestión • últimos 5 • H2H • validación • promedios • exportación")

with st.sidebar:
    st.header("Configuración")
    team_a = st.text_input("Equipo A", "Millonarios")
    team_b = st.text_input("Equipo B", "Deportivo Cali")
    match_date = st.date_input("Fecha del partido", date.today())
    source_mode = st.radio("Fuente", ["Demo","CSV / XLSX","Pegar tabla","HTML guardado"])

def parse_upload(f):
    return pd.read_excel(f) if f.name.lower().endswith(".xlsx") else pd.read_csv(f)

def parse_paste(text):
    return pd.read_csv(io.StringIO(text), sep=None, engine="python")

def parse_html(f):
    tables = pd.read_html(f)
    if not tables: raise ValueError("No se encontró ninguna tabla.")
    def score(t):
        s = " ".join(map(str,t.columns)).lower()
        return sum(k in s for k in ["fecha","compet","equipo","rival","tiros","corner","faltas"])
    return max(tables, key=score)

df_raw = None
if source_mode == "Demo":
    df_raw = pd.read_csv("data/demo.csv")
    st.info("Modo demo: datos sintéticos para probar el flujo.")
elif source_mode == "CSV / XLSX":
    f = st.file_uploader("Sube CSV o XLSX", type=["csv","xlsx"])
    if f:
        try: df_raw = parse_upload(f)
        except Exception as e: st.error(str(e))
elif source_mode == "Pegar tabla":
    txt = st.text_area("Pega una tabla TSV/CSV", height=220)
    if txt.strip():
        try: df_raw = parse_paste(txt)
        except Exception as e: st.error(str(e))
else:
    f = st.file_uploader("Sube HTML guardado desde tu navegador", type=["html","htm"])
    if f:
        try: df_raw = parse_html(f)
        except Exception as e: st.error(str(e))

if df_raw is None:
    st.markdown("### Flujo V2")
    st.write("1) Define A, B y fecha. 2) Carga datos. 3) V2 filtra partidos anteriores, toma últimos 5, normaliza H2H y valida. 4) Exporta CSV/XLSX.")
else:
    try:
        df = coerce_types(clean_columns(df_raw))
        r = normalize_matches(df, team_a, team_b, pd.Timestamp(match_date))
        a = select_last5(r["team_a"], pd.Timestamp(match_date))
        b = select_last5(r["team_b"], pd.Timestamp(match_date))
        h = normalize_h2h(r["h2h"], team_a, team_b, pd.Timestamp(match_date))
        tabs = st.tabs([f"{team_a} — últimos 5",f"{team_b} — últimos 5","H2H — últimos 5","Calidad"])
        for tab, frame in zip(tabs[:3],[a,b,h]):
            with tab:
                if frame.empty: st.warning("No hay datos suficientes.")
                else:
                    st.dataframe(frame[COLUMNS], use_container_width=True, hide_index=True)
                    nums = frame[COLUMNS[6:]].apply(pd.to_numeric,errors="coerce")
                    st.write("**Promedios**")
                    st.dataframe(nums.mean().round(2).to_frame("Promedio"), use_container_width=True)
        with tabs[3]:
            q = quality_report([a,b,h], COLUMNS)
            st.metric("Filas",q["rows"]); st.metric("Celdas con dato",q["filled"]); st.metric("Celdas vacías",q["blank"])
            for w in q["warnings"]: st.warning(w)
            if not q["warnings"]: st.success("Sin alertas críticas.")
        out = pd.concat([a.assign(Grupo="Equipo A"),b.assign(Grupo="Equipo B"),h.assign(Grupo="H2H")],ignore_index=True)
        st.download_button("⬇️ CSV",out.to_csv(index=False).encode("utf-8-sig"),"euko_v2.csv","text/csv")
        buf=io.BytesIO()
        with pd.ExcelWriter(buf,engine="openpyxl") as x:
            a.to_excel(x,sheet_name="Equipo_A",index=False); b.to_excel(x,sheet_name="Equipo_B",index=False); h.to_excel(x,sheet_name="H2H",index=False)
        st.download_button("⬇️ Excel",buf.getvalue(),"euko_v2.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.caption("Regla crítica: Tiros al arco del equipo en 1T nunca se inventan ni estiman; si no están verificables, quedan vacíos.")
    except Exception as e:
        st.error(f"Error procesando datos: {e}")
