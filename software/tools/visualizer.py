import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# Configurazione della pagina
st.set_page_config(page_title="Analizzatore CSV Pressione", layout="wide")

st.title("📊 Analizzatore CSV Pressione")
st.markdown("Carica il log CSV generato dall'ESP32 per visualizzare il grafico e calcolare la resistenza.")

# --- BARRA LATERALE PER IMPOSTAZIONI ---
with st.sidebar:
    st.header("Impostazioni")
    vol_ref = st.number_input("Volume di riferimento (Litri)", min_value=0.01, value=1.0, step=0.1)
    # Ora la soglia è regolabile dall'utente, con 0.4 come valore di default!
    threshold = st.number_input("Soglia di Pressione (Pa)", min_value=0.01, value=0.40, step=0.1)

# --- CARICAMENTO FILE NATIVO ---
uploaded_file = st.file_uploader("Trascina qui il file CSV o clicca per esplorare", type=['csv'])

if uploaded_file is not None:
    try:
        # Lettura del file
        df = pd.read_csv(uploaded_file)
        
        # Controllo formato
        if 'Timestamp_s' not in df.columns or 'Pressione_Pa' not in df.columns:
            st.error("Il file CSV non ha il formato corretto. Mancano le colonne 'Timestamp_s' o 'Pressione_Pa'.")
        else:
            st.success("File caricato con successo!")

            # --- ALGORITMO DI RICERCA SEZIONI ---
            # Trova dove la pressione supera la soglia dinamica
            mask = df['Pressione_Pa'].abs() > threshold
            
            # Crea un ID univoco per ogni blocco
            blocks = (mask != mask.shift()).cumsum()
            
            # Estrae solo le sezioni in cui la condizione è True
            sections = [group for _, group in df[mask].groupby(blocks)]

            # --- CALCOLO METRICHE ---
            results = []
            for idx, sec in enumerate(sections):
                t_start = sec['Timestamp_s'].iloc[0]
                t_end = sec['Timestamp_s'].iloc[-1]
                duration = t_end - t_start
                avg_p = sec['Pressione_Pa'].mean()
                
                # Formula Resistenza
                resistance = (abs(avg_p) * duration * 1000) / vol_ref
                
                results.append({
                    "Sezione": f"#{idx + 1}",
                    "Inizio (s)": round(t_start, 3),
                    "Fine (s)": round(t_end, 3),
                    "Durata (s)": round(duration, 3),
                    "P. Media (Pa)": round(avg_p, 3),
                    "Resistenza": round(resistance, 2)
                })

            # --- VISUALIZZAZIONE TABELLA ---
            st.subheader(f"📋 Sezioni Rilevate (|P| > {threshold} Pa)")
            if len(results) > 0:
                results_df = pd.DataFrame(results)
                # Mostra la tabella a tutto schermo
                st.dataframe(results_df, use_container_width=True, hide_index=True)
            else:
                st.info(f"Nessuna sezione supera la soglia di {threshold} Pa.")

            # --- VISUALIZZAZIONE GRAFICO ---
            st.subheader("📈 Grafico Totale")
            
            # Creazione figura Matplotlib
            fig, ax = plt.subplots(figsize=(12, 5))
            
            # Disegna la linea principale
            ax.plot(df['Timestamp_s'], df['Pressione_Pa'], color='#1f77b4', linewidth=1.5, label="Pressione (Pa)")
            
            # Evidenzia le sezioni attive con un rettangolo rosso trasparente
            for sec in sections:
                ax.axvspan(sec['Timestamp_s'].iloc[0], sec['Timestamp_s'].iloc[-1], color='red', alpha=0.2)
            
            # Disegna le linee di soglia (si adattano automaticamente al valore scelto)
            ax.axhline(threshold, color='green', linestyle='--', alpha=0.6, label=f"+{threshold} Pa")
            ax.axhline(-threshold, color='green', linestyle='--', alpha=0.6, label=f"-{threshold} Pa")
            
            # Estetica
            ax.set_xlabel("Tempo (secondi)")
            ax.set_ylabel("Pressione (Pascal)")
            ax.grid(True, linestyle=':', alpha=0.7)
            ax.legend(loc="upper right")
            
            # Mostra il grafico nell'app
            st.pyplot(fig)

    except Exception as e:
        st.error(f"Si è verificato un errore durante la lettura: {e}")