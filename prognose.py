import streamlit as st
import pandas as pd
from datetime import timedelta, date
from streamlit_calendar import calendar
import os

# --- KONFIGURATION & SETUP ---

# Konstanten für Dateispeicher
DATA_FILE = "klienten_sitzungen.csv"
SITZUNGS_DAUER_TAGE = 7

SITZUNGEN_TYPEN = {
    "Sprechstunde": 3,
    "Probatorik": 4,
    "Anamnese": 1,
    "KZT": 24,
    "LZT": 60,
    "RFP": 20
}

# --- HILFSFUNKTIONEN & DATENMANAGEMENT ---

def load_data():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE, parse_dates=['Datum'])
        return df.astype(
            {'Datum': 'datetime64[ns]', 'Klient': 'object', 'Sitzungsart': 'object', 'Nummer': 'Int64'}
        )
    else:
        return pd.DataFrame(columns=['Datum', 'Klient', 'Sitzungsart', 'Nummer']).astype(
            {'Datum': 'datetime64[ns]', 'Klient': 'object', 'Sitzungsart': 'object', 'Nummer': 'Int64'}
        )
def setze_basissitzungen(name: str, start_datum: date) -> pd.DataFrame:
    sitzungen_data = []
    start_timestamp = pd.Timestamp(start_datum) 
    
    for i in range(1, SITZUNGEN_TYPEN["Sprechstunde"] + 1):
        sitzungen_data.append({
            "Datum": start_timestamp + timedelta(days=(i-1) * SITZUNGS_DAUER_TAGE),
            "Klient": name,
            "Sitzungsart": "Sprechstunde",
            "Nummer": i,
        })
    return pd.DataFrame(sitzungen_data)

def generiere_folgesitzungen(klient_name: str, last_date: pd.Timestamp, sitzungs_art: str, start_nr: int, end_nr: int) -> pd.DataFrame:
    neue_sitzungen = []
    for i in range(start_nr, end_nr + 1):
        days_offset = (i - start_nr + 1) * SITZUNGS_DAUER_TAGE
        neue_sitzungen.append({
            'Datum': last_date + timedelta(days=days_offset),
            'Klient': klient_name,
            'Sitzungsart': sitzungs_art,
            "Nummer": i,
        })
    return pd.DataFrame(neue_sitzungen)

def add_sessions_callback(session_type, start_nr=None):
    if st.session_state.get('ausgewaehlter_klient') and not st.session_state.klient_termine_filtered.empty:
        klient_termine = st.session_state.klient_termine_filtered
        last_date = klient_termine["Datum"].max()
        
        if session_type == "Probatorik":
            end_nr = SITZUNGEN_TYPEN["Probatorik"]
            neue_sitzungen_df = generiere_folgesitzungen(
                st.session_state.ausgewaehlter_klient, last_date, "Probatorik", 1, end_nr
            )
            anamnese_data = [{"Datum": last_date + timedelta(days=35), "Klient": st.session_state.ausgewaehlter_klient, "Sitzungsart": "Anamnese", "Nummer": 1}]
            neue_sitzungen_df = pd.concat([neue_sitzungen_df, pd.DataFrame(anamnese_data)], ignore_index=True)
        else:
            end_nr = SITZUNGEN_TYPEN[session_type]
            neue_sitzungen_df = generiere_folgesitzungen(
                st.session_state.ausgewaehlter_klient, last_date, session_type, start_nr, end_nr
            )

        st.session_state.sitzungen = pd.concat([st.session_state.sitzungen, neue_sitzungen_df], ignore_index=True)
        st.success(f"{session_type} Sitzungen ab Nr. {start_nr} hinzugefügt!")
        st.session_state.last_button_click = None
        
        # Aktualisiere gefilterte Termine nach Hinzufügen
        st.session_state.klient_termine_filtered = st.session_state.sitzungen[
            st.session_state.sitzungen["Klient"] == st.session_state.ausgewaehlter_klient
        ]
    else:
        st.warning("Bitte wählen Sie einen gültigen Klienten aus.")

def convert_kzt_to_lzt_callback(start_kzt_nr):
    klient_termine = st.session_state.klient_termine_filtered
    
    # Filtert KZT-Sitzungen bis zur Umwandlungsnummer
    kzt_sitzungen_behalten = klient_termine[(klient_termine["Sitzungsart"] == "KZT") & (klient_termine["Nummer"] < start_kzt_nr)]
    
    if kzt_sitzungen_behalten.empty:
        last_date = klient_termine["Datum"].max()
    else:
        last_date = kzt_sitzungen_behalten["Datum"].max()
        
    neue_sitzungen = generiere_folgesitzungen(
        klient_name=st.session_state.ausgewaehlter_klient,
        last_date=last_date,
        sitzungs_art="LZT",
        start_nr=start_kzt_nr,
        end_nr=SITZUNGEN_TYPEN["LZT"]
    )
    
    # Entfernt alte KZT-Sitzungen und fügt LZT hinzu
    klient_termine_bereinigt = klient_termine[~((klient_termine["Sitzungsart"] == "KZT") & (klient_termine["Nummer"] >= start_kzt_nr))]
    st.session_state.sitzungen = pd.concat([klient_termine_bereinigt, neue_sitzungen], ignore_index=True)
    st.success(f"KZT ab Sitzung {start_kzt_nr} in LZT umgewandelt.")
    st.session_state.last_button_click = None
    
    # Aktualisiere gefilterte Termine nach Hinzufügen
    st.session_state.klient_termine_filtered = st.session_state.sitzungen[
        st.session_state.sitzungen["Klient"] == st.session_state.ausgewaehlter_klient
    ]
    
def get_index(termine, date):
    termine = termine.reset_index(drop=True)
    date = pd.to_datetime(date)
    idx = termine[termine["Datum"] == date].index[0]
    return idx

def hole_klienten_termine(klient):
    klienten_termine = st.session_state.sitzungen[st.session_state.sitzungen["Klient"] == klient].reset_index(drop=True)
    return klienten_termine
    
def verschiebe_termin_callback(date, client):
    klienten_termine = hole_klienten_termine(client)
    date = pd.to_datetime(date)
    
    idx = get_index(klienten_termine, date)
    
    last_date = klienten_termine["Datum"].max()
    neue_daten = klienten_termine["Datum"].tolist()
    neue_daten.append(last_date + timedelta(days=7))
    del neue_daten[idx]
    
    klienten_termine["Datum"] = neue_daten
    update_klient_termine_in_session(client, klienten_termine)
    return klienten_termine

def count_value_in_quarter(df, date, spalte, wert):
    """
    Zählt, wie oft ein bestimmter Wert in einer Spalte
    im selben Quartal wie 'date' vorkommt.

    df      : DataFrame mit einer 'Datum'-Spalte
    date    : Datum (str oder Timestamp)
    spalte  : Spaltenname, in der der Wert gesucht wird (z. B. 'Sitzungsart')
    wert    : Gesuchter Wert (z. B. 'PTG')
    """
    date = pd.to_datetime(date)
    quartal = date.to_period("Q")

    # Alle Zeilen, deren Datum im selben Quartal liegt
    gleiche_quartal = df[pd.to_datetime(df["Datum"]).dt.to_period("Q") == quartal]

    # Anzahl der Zeilen mit dem gewünschten Wert
    anzahl = (gleiche_quartal[spalte] == wert).sum()

    return anzahl

def markiere_ptg(date, client):
    klienten_termine = hole_klienten_termine(client)
    
    date = pd.to_datetime(date)
    n_ptg = count_value_in_quarter(klienten_termine, date, "Sitzungsart", "PTG") + 1
    idx = get_index(klienten_termine, date)
    
    last_date = klienten_termine["Datum"].max()
    neue_daten = klienten_termine["Datum"].tolist()
    neue_daten.append(last_date + timedelta(days=7))
    
    new_row = {"Klient": client, "Sitzungsart": "PTG", "Nummer": n_ptg}
    top = klienten_termine.iloc[:idx]
    bottom = klienten_termine.iloc[idx:]
    
    klienten_termine = pd.concat([top, pd.DataFrame([new_row]), bottom], ignore_index=True)
    klienten_termine["Datum"] = neue_daten
    update_klient_termine_in_session(client, klienten_termine)
    return klienten_termine

def loesche_termine(date, client):
    klienten_termine = hole_klienten_termine(client)
    
    date = pd.to_datetime(date)
    idx = get_index(klienten_termine, date)
    
    klienten_termine = klienten_termine[:idx]
    update_klient_termine_in_session(client, klienten_termine)
    return klienten_termine

def update_klient_termine_in_session(client, klienten_termine):
    st.session_state.sitzungen = st.session_state.sitzungen[
        st.session_state.sitzungen["Klient"] != client
    ].copy()
    st.session_state.sitzungen = pd.concat(
        [st.session_state.sitzungen, klienten_termine],
        ignore_index=True
    )

def verschiebe_alle(date, client, diff_days):
    klienten_termine = hole_klienten_termine(client)
    # Datum in Timestamp umwandeln
    date = pd.to_datetime(date)
    
    # Index des ausgefallenen Termins
    idx = get_index(klienten_termine, date)
    differenz = pd.Timedelta(days=diff_days)

    klienten_termine.loc[klienten_termine.index >= idx, "Datum"] += differenz
    
    update_klient_termine_in_session(client, klienten_termine)    
    return klienten_termine

def get_calendar_events(df):
    events = []
    for _, row in df.iterrows():
        if row["Sitzungsart"]!="Supervision":
            events.append({
                "title": f"{row['Klient']} - {row['Sitzungsart']} {row['Nummer']}",  # Trenne Werte mit Pipe
                "start": row['Datum'].strftime("%Y-%m-%d"),
                "allDay": True
            })
        else:
            events.append({
                "title": f"{row['Stundenanzahl']} h {row['Art Supervision']}",
                "start": row['Datum'].strftime("%Y-%m-%d"),
                "allDay": True,
                "color": "red",
            })
    return events
    
def loesche_sup_termin(date, title):
    termine = st.session_state.sitzungen.copy()
    date = pd.to_datetime(date)
    anzahl = int(float(title.split(" h ")[0].strip()))
    type = title.split(" h ")[1].strip()

    # Maske für Supervisionstermine am gesuchten Datum
    mask = (termine["Sitzungsart"] == "Supervision") & (termine["Datum"] == date)
    
    # Index der zu löschenden Zeilen
    index_to_drop = termine[mask].index
    
    # Zeilen löschen
    termine = termine.drop(index_to_drop)
    
    # Index zurücksetzen
    termine = termine.reset_index(drop=True)
    
    # Aktualisieren des Session State
    st.session_state.sitzungen = termine

   

def wochentag_auswahl():
    st.subheader("Wochentag auswählen")

    # Dictionary, das den angezeigten Namen den zugehörigen Zahlenwerten zuordnet
    wochentage = {
        "Montag": 0,
        "Dienstag": 1,
        "Mittwoch": 2,
        "Donnerstag": 3,
        "Freitag": 4,
    }

    # Streamlit Radio-Button Widget
    # Der Benutzer sieht die Schlüssel ("Montag", "Dienstag", etc.)
    # Der zurückgegebene Wert ist der Schlüssel selbst ("Montag")
    ausgewaehlter_name = st.radio(
        "Wählen Sie den gewünschten Wochentag für die neuen Termine:",
        options=list(wochentage.keys()),
        index=1 # Standardmäßig ist Montag vorausgewählt
    )
    
    ausgewaehlte_zahl = wochentage[ausgewaehlter_name]
    
    return ausgewaehlte_zahl
   

# --- STREAMLIT ANWENDUNG ---

st.set_page_config(page_title="IPP Ambulanzverwaltungstool", layout="wide")
st.title("IPP Ambulanzverwaltungstool")

# Initialisiere den Zustand für die Benutzerinteraktion
if 'last_button_click' not in st.session_state:
    st.session_state.last_button_click = None
if 'sitzungen' not in st.session_state:
    st.session_state.sitzungen = pd.DataFrame(
        columns=['Datum', 'Klient', 'Sitzungsart', 'Nummer', 'Art Supervision', 'Stundenanzahl'])

clients = st.session_state.sitzungen["Klient"].dropna().unique()

# --- SIDEBAR ---
with st.sidebar:
    st.subheader("Datenquelle auswählen")

    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False

    if st.button("Neuen Datensatz beginnen"):
        st.session_state.sitzungen = pd.DataFrame(
            columns=['Datum', 'Klient', 'Sitzungsart', 'Nummer']
        ).astype(
            {'Datum': 'datetime64[ns]', 'Klient': 'object', 'Sitzungsart': 'object', 'Nummer': 'Int64'}
        )
        st.session_state.ausgewaehlter_klient = ""
        st.session_state.klient_termine_filtered = pd.DataFrame()
        st.session_state.last_button_click = None
        st.session_state.data_loaded = True

    uploaded_file = st.file_uploader("CSV-Datei hochladen", type="csv")
    if uploaded_file is not None and not st.session_state.data_loaded:
        df = pd.read_csv(uploaded_file, parse_dates=['Datum'])
        st.session_state.sitzungen = df.astype(
            {'Datum': 'datetime64[ns]', 'Klient': 'object', 'Sitzungsart': 'object', 'Nummer': 'Int64'}
        )
        
        # Standardmäßig ersten Klienten auswählen, falls vorhanden
        clients = st.session_state.sitzungen["Klient"].dropna().unique()
        if len(clients) > 0:
            st.session_state.ausgewaehlter_klient = clients[0]
            st.session_state.klient_termine_filtered = st.session_state.sitzungen[
                st.session_state.sitzungen['Klient'] == clients[0]
            ]
        else:
            st.session_state.ausgewaehlter_klient = ""
            st.session_state.klient_termine_filtered = pd.DataFrame()
            
        st.session_state.last_button_click = None
        st.session_state.data_loaded = True
        st.success("CSV-Datei erfolgreich geladen!")

    # --- CSV Download ---
    st.subheader("Daten sichern")
    if 'sitzungen' in st.session_state and not st.session_state.sitzungen.empty:
        csv = st.session_state.sitzungen.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Daten als CSV herunterladen",
            data=csv,
            file_name="ipp_ambulanzdaten.csv",
            mime="text/csv"
        )




tabs = st.tabs(["Kalender", "Klientenverwaltung", "Quartalsprognose", "Supervision", "Test"])

with tabs[4]:
    st.write(st.session_state.sitzungen)

with tabs[0]:
    st.header("Kalenderübersicht")
    clients = st.session_state.sitzungen["Klient"].dropna().unique()
    
    if clients.size > 0:
        st.header("Kalender")
        
        calendar_options = {
            "editable": True,
            "selectable": True,
            "headerToolbar": {
                "left": "today prev,next",
                "center": "title",
                "right": "list,dayGridDay,dayGridWeek,dayGridMonth",
            },
            "firstDay": 1,
            "locale": "de",
        }
        
        calendar_events = get_calendar_events(st.session_state.sitzungen)
        
        clnd = calendar(
            events=calendar_events,
            options=calendar_options,
            key="my_calendar",
            callbacks="eventClick"
        )
        
        # Prüfen, ob ein Termin geklickt wurde
        if clnd and "callback" in clnd and clnd["callback"] == "eventClick":
            st.session_state.selected_event = clnd["eventClick"]["event"]

        if "selected_event" in st.session_state and st.session_state.selected_event:
            event_obj = st.session_state.selected_event
            title = event_obj["title"]
            start = event_obj["start"]

            if "E-SV" in title or "G-SV" in title:             
                st.header(f"{title} am {start}")
                
                with st.form("sup_loeschen"):
                    st.subheader("Supervisionstermin löschen")
                    st.warning("Dieser Supervisionstermin wird gelöscht!")
                    if st.form_submit_button("Bestätigen"):
                        loesche_sup_termin(start, title)
                        st.rerun()
            else:
                klient_id = title.split(" - ")[0].strip()
                
                # Header nur anzeigen, wenn noch keine Aktion läuft
                if st.session_state.get("last_button_click") is None:
                    st.header(f"{title} am {start}")

                    col1, col2, col3, col4 = st.columns(4)
                    if col1.button("Terminausfall"):
                        st.session_state.last_button_click = "Terminausfall"
                    if col2.button("PTG markieren"):
                        st.session_state.last_button_click = "PTG"
                    if col3.button("Ab hier verschieben"):
                        st.session_state.last_button_click = "Verschieben"
                    if col4.button("Therapieende"):
                        st.session_state.last_button_click = "Ende"

                # Aktionen ausführen
                if st.session_state.get("last_button_click") == "Terminausfall":
                    with st.form("terminausfall"):
                        st.subheader("Termin ist ausgefallen")
                        st.warning("Dieser Termin wird gelöscht und alle Termine um eine Woche verschoben")
                        if st.form_submit_button("Bestätigen"):
                            verschiebe_termin_callback(start, klient_id)
                            st.rerun()

                elif st.session_state.get("last_button_click") == "PTG":
                    with st.form("ptg"):
                        st.subheader("Termin als PTG markieren")
                        n_ptg = count_value_in_quarter(
                            st.session_state.sitzungen[st.session_state.sitzungen["Klient"] == klient_id],
                            start, "Sitzungsart", "PTG"
                        )
                        if n_ptg >= 3:
                            st.warning("Dieses Quartal haben schon 3 PTG stattgefunden. Eine Abrechnung als PTG ist nicht möglich!")
                            st.form_submit_button("Bestätigen", disabled=True)
                        else:
                            st.warning("Dieser Termin wird als PTG eingetragen. Die bisherigen Termine werden verschoben.")
                        if st.form_submit_button("Bestätigen"):
                            markiere_ptg(start, klient_id)
                            st.rerun()

                elif st.session_state.get("last_button_click") == "Verschieben":
                    with st.form("verschieben"):
                        new_day = wochentag_auswahl()
                        diff_tage = new_day - pd.to_datetime(start).weekday()
                        if st.form_submit_button("Bestätigen"):
                            verschiebe_alle(start, klient_id, diff_tage)
                            st.rerun()

                elif st.session_state.get("last_button_click") == "Ende":
                    with st.form("ende"):
                        st.subheader("Therapie ab diesem Termin beenden")
                        st.warning("Alle zukünftigen Termine inklusive des ausgewählten Termins werden gelöscht!")
                        if st.form_submit_button("Bestätigen"):
                            loesche_termine(start, klient_id)
                            st.rerun()
                            
        else:
            st.info("Füge zuerst einen Klienten hinzu, um die Übersicht zu sehen.")



with tabs[1]:
    st.header("Klientenverwaltung")    
    st.subheader("Neuen Klienten hinzufügen")
    with st.form("eingabemaske_klient"):
        name = st.text_input("Name des Klienten", max_chars=2)
        start_datum_input = st.date_input("Datum der ersten Sitzung", format="DD/MM/YYYY") 
        submitted = st.form_submit_button("Hinzufügen")
        clients = st.session_state.sitzungen["Klient"].dropna().unique()
        
        if submitted:
            if name in st.session_state.sitzungen["Klient"].dropna().unique():
                st.warning(f"'{name}' existiert bereits! Bitte wähle ein anderes Kürzel.")
            elif name and start_datum_input:
                p_sitzungen = setze_basissitzungen(name, start_datum_input) 
                st.session_state.sitzungen = pd.concat([st.session_state.sitzungen, p_sitzungen], ignore_index=True)
                
                st.success(f"Klient {name} mit Basissitzungen hinzugefügt!")
                st.rerun()
    
    if 'ausgewaehlter_klient' not in st.session_state:
        st.session_state.ausgewaehlter_klient = ""
    if 'klient_termine_filtered' not in st.session_state:
        st.session_state.klient_termine_filtered = pd.DataFrame()
    
    if clients.size > 0:
        st.subheader("Bestehende Klienten verwalten")
        valid_clients = [c for c in clients if c] 
        
        def select_client_callback():
            selected_client = st.session_state.auswahl_klient_box
            if selected_client:
                st.session_state.ausgewaehlter_klient = selected_client
                st.session_state.klient_termine_filtered = st.session_state.sitzungen[
                    st.session_state.sitzungen['Klient'] == selected_client
                ]
            else:
                st.session_state.ausgewaehlter_klient = ""
                st.session_state.klient_termine_filtered = pd.DataFrame()
            st.session_state.last_button_click = None

    
        auswahl_klient_box = st.selectbox(
            "Wähle einen Klienten aus", 
            [""] + valid_clients, 
            key="auswahl_klient_box", 
            on_change=select_client_callback
        )
    
        if st.session_state.ausgewaehlter_klient:
            klient_termine = st.session_state.klient_termine_filtered
            st.header(f"Übersicht für {st.session_state.ausgewaehlter_klient}")
    
            if not klient_termine.empty:
                current_therapy = klient_termine["Sitzungsart"].iloc[-1]
                uebersicht_klient = pd.DataFrame({
                    "Startdatum": [klient_termine["Datum"].min().strftime("%d.%m.%Y")],
                    "Voraussichtliches Enddatum": [klient_termine["Datum"].max().strftime("%d.%m.%Y")],
                    "Anzahl Termine": [len(klient_termine)],
                    "Aktuelle Therapie": [current_therapy]
                }).T 
                st.write(uebersicht_klient)
                st.subheader(f"Terminliste für {st.session_state.ausgewaehlter_klient}")
                st.write(klient_termine)
            else:
                st.info("Keine Termine für diesen Klienten gefunden.")
                current_therapy = None
    
            st.subheader("Nächste Schritte planen")
            
            col1, col2, col3, col4 = st.columns(4)
            
            has_prob = klient_termine['Sitzungsart'].isin(["Probatorik", "Anamnese"]).any()
            has_kzt = klient_termine['Sitzungsart'].isin(["KZT"]).any()
            has_lzt = klient_termine['Sitzungsart'].isin(["LZT"]).any()
            has_rfp = klient_termine['Sitzungsart'].isin(["RFP"]).any()
            
            with col1:
                if current_therapy in ["Sprechstunde"]:
                    if st.button("Probatorik/Anamnese beginnen", disabled=has_prob):
                        st.session_state.last_button_click = "Probatorik"
            
            if current_therapy in ["Sprechstunde"]:
                with col2:
                    if st.button("KZT beginnen"):
                        st.session_state.last_button_click = "KZT"
                with col3:
                    if st.button("LZT beginnen"):
                        st.session_state.last_button_click = "LZT"
                with col4:
                    if st.button("RFP beginnen"):
                        st.session_state.last_button_click = "RFP"
    
            elif current_therapy in ["Anamnese"]:
                with col1:
                    st.button("Probatorik abgeschlossen", disabled=True)
                with col2:
                    if st.button("KZT beginnen"):
                        st.session_state.last_button_click = "KZT"
                with col3:
                    if st.button("LZT beginnen"):
                        st.session_state.last_button_click = "LZT"
            
            elif current_therapy in ["KZT"]:
                if st.button("Umwandlung"):
                    st.session_state.last_button_click = "Umwandlung"
                    
            elif current_therapy in ["LZT"]:
                if st.button("RFP beginnen"):
                    st.session_state.last_button_click = "RFP"
            
            elif current_therapy in ["PTG"]:
                with col1:
                    if st.button("Probatorik/Anamnese beginnen", disabled=has_prob):
                            st.session_state.last_button_click = "Probatorik"
                with col2:
                    if st.button("KZT beginnen"):
                        st.session_state.last_button_click = "KZT"
                with col3:
                    if st.button("LZT beginnen"):
                        st.session_state.last_button_click = "LZT"
                with col4:
                    if st.button("RFP beginnen"):
                        st.session_state.last_button_click = "RFP"
    
            # --- DYNAMISCHE EINGABEMASKEN ---
            
            if st.session_state.last_button_click == "Probatorik":
                with st.form("prob_confirm"):
                    st.subheader("Probatorik/Anamnese hinzufügen")
                    st.warning("Probatorik (4) und Anamnese (1) werden automatisch hinzugefügt.")
                    if st.form_submit_button("Bestätigen"):
                        add_sessions_callback("Probatorik")
                        st.rerun()
            
            elif st.session_state.last_button_click == "KZT":
                with st.form("kzt_eingabe"):
                    st.subheader("KZT-Sitzungen hinzufügen")
                    if current_therapy == "Sprechstunde":
                        start_kzt = st.number_input("Mit welcher KZT-Sitzung soll gestartet werden?", min_value=1, max_value=24, value=1)
                    else:
                        start_kzt = 1
                        st.warning("KZT (1 und 2; 24 Sitzungen) wird hinzugefügt.")
                    if st.form_submit_button("KZT-Sitzungen hinzufügen"):
                        add_sessions_callback("KZT", start_kzt)
                        st.rerun()
            
            elif st.session_state.last_button_click == "LZT":
                with st.form("lzt_eingabe"):
                    st.subheader("LZT-Sitzungen hinzufügen")
                    if current_therapy == "Sprechstunde":
                        start_lzt = st.number_input("Mit welcher LZT-Sitzung soll gestartet werden?", min_value=1, max_value=60, value=1)
                    else:
                        start_lzt = 1
                        st.warning("LZT (60 Sitzungen) wird hinzugefügt.")
                    if st.form_submit_button("LZT-Sitzungen hinzufügen"):
                        add_sessions_callback("LZT", start_lzt)
                        st.rerun()
            
            elif st.session_state.last_button_click == "RFP":
                with st.form("rfp_eingabe"):
                    st.subheader("RFP-Sitzungen hinzufügen")
                    if current_therapy == "Sprechstunde":
                        start_rfp = st.number_input("Mit welcher RFP-Sitzung soll gestartet werden?", min_value=1, max_value=20, value=1)
                    else:
                        start_rfp = 1
                        st.warning("RFP (20 Sitzungen) wird hinzugefügt.")
                    if st.form_submit_button("RFP-Sitzungen hinzufügen"):
                        add_sessions_callback("RFP", start_rfp)
                        st.rerun()
            
            elif st.session_state.last_button_click == "Umwandlung":
                with st.form("umwandlung_eingabe"):
                    st.subheader("KZT in LZT umwandeln")
                    # Holen Sie die aktuelle Anzahl an KZT-Sitzungen als Max-Wert
                    kzt_sitzungen = klient_termine[klient_termine["Sitzungsart"] == "KZT"]
                    start_kzt = min(kzt_sitzungen["Nummer"])
                    start_umwandlung = st.number_input(f"Ab welcher KZT-Sitzung (von {start_kzt} bis 24) soll die Therapie in eine LZT umgewandelt werden?", min_value=start_kzt, max_value=24)
                    if st.form_submit_button("Umwandlung bestätigen"):
                        convert_kzt_to_lzt_callback(start_umwandlung)
                        st.rerun()
    
    else:
        st.info("Füge zuerst einen Klienten hinzu, um die Übersicht zu sehen.")

with tabs[2]:
    st.header("Quartalsprognose")
    clients = st.session_state.sitzungen["Klient"].dropna().unique()
    if clients.size > 0:
        with st.form("qp"):
            options = ["extern", "intern"]
            ext = st.radio(
                "In externer Praxis oder im IPP?",
                options
            )
            sitzung_mapping = {
                'Sprechstunde': 46.8,
                'Probatorik': 35.15,
            'Anamnese': 35.05,
                'KZT': 46.65,
                'LZT': 46.65,
                'RFP': 46.65,
                'PTG': 38.2
            }
            
            quartale = st.session_state.sitzungen["Datum"].dt.to_period('Q').unique()
            quartaljahre = st.session_state.sitzungen["Datum"].dt.to_period('Q')
            
            element = st.selectbox("Bitte wähle das Quartal aus",
                quartale)
            
            if st.form_submit_button("Bestätigen"):
                st.subheader(element)
                quartals_termine = st.session_state.sitzungen[quartaljahre == element]
                prognose = quartals_termine["Sitzungsart"].value_counts().reset_index()
                prognose.columns = ["Sitzungsart", "Anzahl"]
                prognose["Schätzung (10/12)"] = (prognose["Anzahl"]*10/12).round()
                if ext == "extern":
                    prognose['EBM Honorar'] = prognose['Sitzungsart'].map(sitzung_mapping)-3
                else:
                    prognose['EBM Honorar'] = prognose['Sitzungsart'].map(sitzung_mapping)
                
                prognose['Entgelt'] = prognose["Schätzung (10/12)"] * prognose['EBM Honorar']
                summe_anzahl = prognose["Anzahl"].sum()
                summe_schaetzung = prognose["Schätzung (10/12)"].sum()
                summe_entgelt = prognose["Entgelt"].sum()
                
                # Erstellen Sie ein Dictionary mit den Werten für die neue Zeile
                # Der Schlüssel ist der Spaltenname, der Wert ist der entsprechende Wert
                neue_zeile_werte = {
                    "Sitzungsart": "",
                    "Anzahl": summe_anzahl,
                    "Schätzung (10/12)": summe_schaetzung,
                    "EBM Honorar": "",  # Bleibt leer
                    "Entgelt": summe_entgelt
                }
                prognose.loc['Gesamt'] = neue_zeile_werte
                
                st.write(prognose)
    else:
        st.info("Füge zuerst einen Klienten hinzu, um die Übersicht zu sehen.") 
    
    
    
with tabs[3]:
    st.header("Supervision")
    clients = st.session_state.sitzungen["Klient"].dropna().unique()
    if clients.size > 0:
        with st.form("sup_add"):
            sup_date = st.date_input("Datum Supervision", format="DD/MM/YYYY")
            sup_type = st.radio("Einzel-/Gruppensupervision?", options=["E-SV", "G-SV"])
            sup_stunden = st.number_input(
                "Anzahl Stunden",
                min_value = 1,
                max_value = 10,
                step = 1,
                format = "%d"
            )
            if st.form_submit_button("Hinzufügen"):
                sup_sitzung = pd.DataFrame({
                    "Datum": [pd.Timestamp(sup_date)],
                    "Sitzungsart": ["Supervision"],
                    "Art Supervision": [sup_type],
                    "Stundenanzahl": [sup_stunden]
                })
                
                st.session_state.sitzungen = pd.concat([st.session_state.sitzungen,sup_sitzung], ignore_index = True)
                st.rerun()
        supervisionen = st.session_state.sitzungen[st.session_state.sitzungen["Sitzungsart"] == "Supervision"]
        if supervisionen.size>0:
            st.subheader("Supervisionsübersicht (IST vs SOLL)")
            with st.form("sup_ov"):
                due_day = st.date_input("Bitte wähle einen Stichtag aus.", format="DD/MM/YYYY")
                if st.form_submit_button("Bestätigen"):
                    subset = st.session_state.sitzungen[st.session_state.sitzungen["Datum"]<pd.Timestamp(due_day)]
                    subset_sitzungen = subset[subset["Sitzungsart"]!="Supervision"].shape[0]
                    subset_sup = subset[subset["Sitzungsart"]=="Supervision"]

                    st.write(f"Bis zum {due_day} wurden/werden {subset_sitzungen} Sitzungen Psychotherapie absolviert. Daraus ergibt sich der folgende Superivisionsbedarf.")
                    vergleich = pd.DataFrame(columns=["SOLL", "IST", "Differenz"], index = ["Gesamt-SUP", "E-SV", "G-SV"])
                    vergleich["SOLL"] = [subset_sitzungen/4, subset_sitzungen/12, subset_sitzungen/6]
                    vergleich["SOLL"] = vergleich["SOLL"].round(1)
                    
                    vergleich["IST"] = [
                        subset_sup["Stundenanzahl"].sum(),
                        subset_sup[subset_sup["Art Supervision"] == "E-SV"]["Stundenanzahl"].sum(),
                        subset_sup[subset_sup["Art Supervision"] == "G-SV"]["Stundenanzahl"].sum()
                    ]
                    
                    vergleich["Differenz"] = vergleich["IST"]-vergleich["SOLL"]
                    st.write(vergleich)
        else:
            st.info("Füge eine erste Supervisionssitzung hinzu, um die Supervisionsübersicht zu öffnen.")       
           
    else:
        st.info("Füge zuerst einen Klienten hinzu, um die Übersicht zu sehen.")
