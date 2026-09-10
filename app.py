import io
from datetime import date
import pandas as pd
import streamlit as st

st.set_page_config(page_title='EUKO Football Analyzer V2', page_icon='⚽', layout='wide')
COLUMNS=['Fecha','Competición','Equipo','Rival','Local/Visitante','Resultado','Goles a favor','Goles en contra','Tiros totales del equipo','Tiros totales del rival','Tiros al arco del equipo','Tiros al arco del rival','Tiros al arco del equipo en 1T','Goles equipo en 1T','Goles rival en 1T','Córneres equipo','Córneres rival','Faltas equipo','Faltas rival','Tarjetas equipo','Tarjetas rival']
ALIASES={'fecha':'Fecha','date':'Fecha','competición':'Competición','competicion':'Competición','competition':'Competición','equipo':'Equipo','team':'Equipo','rival':'Rival','opponent':'Rival','local/visitante':'Local/Visitante','venue':'Local/Visitante','resultado':'Resultado','result':'Resultado'}

def clean(df):
    df=df.copy(); df.columns=[str(c).strip() for c in df.columns]
    df=df.rename(columns={c:ALIASES.get(c.lower(),c) for c in df.columns})
    for c in COLUMNS:
        if c not in df.columns: df[c]=pd.NA
    df['Fecha']=pd.to_datetime(df['Fecha'],errors='coerce',dayfirst=True)
    for c in COLUMNS[6:]: df[c]=pd.to_numeric(df[c],errors='coerce')
    return df

def norm(x): return ' '.join(str(x).strip().lower().split())

def orient(df,team):
    if df.empty: return df[COLUMNS].copy()
    out=df.copy(); old=out.copy(); swap=out['Equipo'].map(norm).ne(norm(team))
    for l,r in [('Equipo','Rival'),('Goles a favor','Goles en contra'),('Tiros totales del equipo','Tiros totales del rival'),('Tiros al arco del equipo','Tiros al arco del rival'),('Goles equipo en 1T','Goles rival en 1T'),('Córneres equipo','Córneres rival'),('Faltas equipo','Faltas rival'),('Tarjetas equipo','Tarjetas rival')]:
        lv,rv=old[l].copy(),old[r].copy(); out.loc[swap,l]=rv[swap].values; out.loc[swap,r]=lv[swap].values
    out.loc[swap,'Rival']=old.loc[swap,'Equipo'].values; out.loc[~swap,'Rival']=old.loc[~swap,'Rival'].values; out['Equipo']=team
    venue=out['Local/Visitante'].astype(str).str.lower(); out.loc[swap & venue.eq('local'),'Local/Visitante']='Visitante'; out.loc[swap & venue.eq('visitante'),'Local/Visitante']='Local'
    return out[COLUMNS].sort_values('Fecha',ascending=False)

def groups(df,a,b,d):
    df=df[df['Fecha'].notna() & (df['Fecha']<d)].copy(); A,B=norm(a),norm(b)
    ta=df[(df.Equipo.map(norm)==A)|(df.Rival.map(norm)==A)]; tb=df[(df.Equipo.map(norm)==B)|(df.Rival.map(norm)==B)]
    hh=df[((df.Equipo.map(norm)==A)&(df.Rival.map(norm)==B))|((df.Equipo.map(norm)==B)&(df.Rival.map(norm)==A))]
    last=lambda x:x.sort_values('Fecha',ascending=False).head(5).reset_index(drop=True)
    return last(orient(ta,a)),last(orient(tb,b)),last(orient(hh,a))

st.title('⚽ EUKO Football Analyzer — V2')
st.caption('Últimos 5 • H2H • normalización • validación • promedios • exportación')
with st.sidebar:
    st.header('Configuración'); team_a=st.text_input('Equipo A','Millonarios'); team_b=st.text_input('Equipo B','Deportivo Cali'); match_date=st.date_input('Fecha del partido',date.today()); mode=st.radio('Fuente de datos',['Demo','CSV / XLSX','Pegar tabla','HTML guardado'])
df=None
if mode=='Demo':
    df=pd.read_csv('data/demo.csv'); st.info('Modo demo: datos de prueba.')
elif mode=='CSV / XLSX':
    f=st.file_uploader('Sube CSV o XLSX',type=['csv','xlsx'])
    if f: df=pd.read_excel(f) if f.name.lower().endswith('.xlsx') else pd.read_csv(f)
elif mode=='Pegar tabla':
    txt=st.text_area('Pega una tabla TSV/CSV',height=220)
    if txt.strip(): df=pd.read_csv(io.StringIO(txt),sep=None,engine='python')
else:
    f=st.file_uploader('Sube HTML guardado desde tu navegador',type=['html','htm'])
    if f:
        tables=pd.read_html(f); df=max(tables,key=lambda t:sum(k in ' '.join(map(str,t.columns)).lower() for k in ['fecha','compet','equipo','rival','tiros','corner','faltas'])) if tables else None
if df is not None:
    try:
        df=clean(df); a,b,h=groups(df,team_a,team_b,pd.Timestamp(match_date))
        tabs=st.tabs([f'{team_a} — últimos 5',f'{team_b} — últimos 5','H2H — últimos 5','Calidad'])
        for tab,frame in zip(tabs[:3],[a,b,h]):
            with tab:
                if frame.empty: st.warning('No hay suficientes partidos que coincidan.')
                else:
                    st.dataframe(frame,use_container_width=True,hide_index=True); st.write('**Promedios**'); st.dataframe(frame[COLUMNS[6:]].mean(numeric_only=True).round(2).to_frame('Promedio'),use_container_width=True)
        with tabs[3]:
            allf=pd.concat([a,b,h],ignore_index=True); missing=int(allf[COLUMNS].isna().sum().sum()); filled=int(allf[COLUMNS].notna().sum().sum()); c1,c2,c3=st.columns(3); c1.metric('Filas',len(allf)); c2.metric('Celdas con dato',filled); c3.metric('Celdas vacías',missing)
            if allf['Tiros al arco del equipo en 1T'].isna().any(): st.warning('TA del equipo en 1T faltante en algunas filas: se deja vacío y nunca se estima.')
        out=pd.concat([a.assign(Grupo='Equipo A'),b.assign(Grupo='Equipo B'),h.assign(Grupo='H2H')],ignore_index=True)
        st.download_button('⬇️ Descargar CSV',out.to_csv(index=False).encode('utf-8-sig'),'euko_v2.csv','text/csv')
        buf=io.BytesIO()
        with pd.ExcelWriter(buf,engine='openpyxl') as x: a.to_excel(x,sheet_name='Equipo_A',index=False); b.to_excel(x,sheet_name='Equipo_B',index=False); h.to_excel(x,sheet_name='H2H',index=False)
        st.download_button('⬇️ Descargar Excel',buf.getvalue(),'euko_v2.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e: st.error(f'Error procesando datos: {e}')
else: st.markdown('### Flujo V2'); st.write('Define A, B y fecha; carga datos; V2 selecciona últimos 5, normaliza H2H, valida y exporta.')
