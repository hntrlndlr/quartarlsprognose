import streamlit as st
import pandas as pd
from datetime import date, time, datetime, timedelta
from streamlit_calendar import calendar
import os
import streamlit.components.v1 as components

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

HILFE = {
    "Kalender": """
**Kalender**
- Termine per Klick bearbeiten.
- Supervisionstermine können gelöscht werden
- 'PTG markieren' max. 3x pro Quartal.
- 'Ab hier verschieben' = alle Termine ab dem ausgewählten auf neuen Wochentag.
- 'Therapieende' = löscht alle Termine ab gewähltem Datum.
""",
    "Abwesenheiten": """
**Abwesenheiten**
- Wähle Zeitraum und Klient, um Termine automatisch zu verschieben.
- Wähle "Alle" für Abwesenheiten des Therapeuten (dann werden alle Kliententermine in dem Zeitraum verschoben)
""",
    "Klienten": """
**Klientenverwaltung**
- Neue Klienten mit Kürzel + Datum hinzufügen (es werden standardmäßig drei Sprechstunden hinzugefügt)
- Übersicht eines Klienten zeigt aktuelle Therapiephase.
- Bei Auswahl eines Klienten können Probatotorik/KZT/LZT/RFP hinzugefügt werden
- Wenn der Klient in der KZT ist, kann eine Umwandlung erfolgen
- Wenn der Klient in der LZT ist, kann eine RFP begonnen werden)
""",
    "Quartalsprognose": """
**Quartalsprognose**
- Zeigt Übersicht geplanter Sitzungen für alle Klienten.
- Schätzung basiert auf 10/12 Formel (Korrektur für Krank/Urlaub)
- Filter nach Quartal möglich.
""",
    "Supervision": """
**Supervision**
- Hier werden Supervisionstermine verwaltet.
- Supervisionstermine können hinzugefügt werden (Stundenanzahl und Supervisionsart)
- Bis zu einem Stichtag kann dann das SOLL und IST von Supervisionen verglichen werden
""",
    "Anleitung": """
**Allgemeine Anleitung**
- Nutze die Tabs, um die verschiedenen Funktionen zu steuern.
- Hilfe-Expander geben kurze Erklärungen.
- Für detaillierte Infos siehe Dokumentation oder Sidebar-Hilfe.
"""
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
    
    # Datumsspalte sicher in datetime konvertieren (nur einmal)
    termine["Datum"] = pd.to_datetime(termine["Datum"])
    
    # Robust vergleichen: nur Datumsteil, nicht Uhrzeit
    matching_rows = termine[termine["Datum"].dt.date == date.date()]
    
    if matching_rows.empty:
        print(f"Kein Termin gefunden für Datum {date} – übersprungen.")
        return None
    
    return matching_rows.index[0]

def hole_klienten_termine(klient):
    klienten_termine = st.session_state.sitzungen[st.session_state.sitzungen["Klient"] == klient].reset_index(drop=True)
    return klienten_termine
    
def verschiebe_termin_callback(date, client):
    klienten_termine = hole_klienten_termine(client)
    date = pd.to_datetime(date)
    
    idx = get_index(klienten_termine, date)
    
    if idx is None:
        return klienten_termine  # nichts zu löschen
        
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

    if idx is None:
        return klienten_termine  # nichts zu löschen
    
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

    if idx is None:
        return klienten_termine  # nichts zu löschen
    
    klienten_termine = klienten_termine[:idx]
    update_klient_termine_in_session(client, klienten_termine)
    return klienten_termine

def loesche_urlaub(start, ende, klient):
    termine = st.session_state.sitzungen.copy()
    termine = termine[termine["Sitzungsart"]!="Supervision"]
    if klient != "Alle":
        termine = termine[termine["Klient"]==klient]
        
    urlaub_start = pd.to_datetime(start)
    urlaub_ende = pd.to_datetime(ende)
    
    urlaub_termine = termine[
        (termine["Datum"]>=urlaub_start) &
        (termine["Datum"]<=urlaub_ende)
    ]
    
    for _, row in urlaub_termine.iterrows():
        verschiebe_termin_callback(row["Datum"], row["Klient"])
    
    return urlaub_termine
    
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

def abbruch_button(key="abbrechen"):
    if st.button("Abbrechen", key=key):
        st.session_state.last_button_click = None
        st.session_state.selected_event = None
        st.rerun()

# --- STREAMLIT ANWENDUNG ---

st.set_page_config(page_title="IPP Ambulanzverwaltungstool", layout="wide")
st.title("IPP Ambulanzverwaltungstool")

# Initialisiere den Zustand für die Benutzerinteraktion
if 'ausgewaehlter_klient' not in st.session_state:
    st.session_state.ausgewaehlter_klient = None 
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
        # Get the current date and time
        now = datetime.now()
        
        # Format the timestamp into a string suitable for a filename (e.g., "2025-11-13_13-31-00")
        timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
        
        # Define the base filename and extension
        base_filename = "ipp_ambulanzdaten"
        file_extension = ".csv"
        
        # Construct the full filename
        filename = f"{base_filename}_{timestamp}{file_extension}"

        st.download_button(
            label="Daten als CSV herunterladen",
            data=csv,
            file_name=filename,
            mime="text/csv"
        )




tabs = st.tabs(["Kalender", "Abwesenheiten", "Klientenverwaltung", "Quartalsprognose", "Supervision", "Anleitung"])

with tabs[5]:
    st.markdown("""
        ## Anleitung zur Nutzung des IPP Ambulanzverwaltungstools
        
        Diese Anwendung dient der Verwaltung von Klientensitzungen, Urlaubszeiträumen und Supervisionsterminen in der psychotherapeutischen Ambulanz.  
        Sie ist in mehrere Tabs unterteilt, die jeweils eine bestimmte Funktion abbilden.
        
        ---
        
        ### **1. Kalender**
        Im Kalender werden alle Termine übersichtlich angezeigt.  
        Ein Klick auf einen Termin öffnet die möglichen Aktionen.
        
        **Verfügbare Aktionen für Therapietermine:**
        - **Terminausfall:** Der gewählte Termin entfällt; alle folgenden Termine werden automatisch um eine Woche verschoben.  
        - **PTG markieren:** Der Termin wird als PTG (Psychotherapeutische Gesprächseinheit) gekennzeichnet. Es können maximal drei PTG pro Quartal eingetragen werden.  
        - **Ab hier verschieben:** Alle zukünftigen Termine werden auf einen anderen Wochentag verlegt.  
        - **Therapieende:** Alle Termine ab dem gewählten Datum werden gelöscht.
        
        **Für Supervisionstermine:**  
        - Durch Klick kann der jeweilige Termin gelöscht werden.
        
        ---
        
        ### **2. Abwesenheiten**
        In diesem Tab können Urlaubszeiträume angegeben werden.  
        Während des gewählten Zeitraums liegende Termine werden automatisch um eine Woche nach hinten verschoben.
        
        **Vorgehen:**
        1. Urlaubsstart und -ende auswählen.  
        2. Klient auswählen (oder „Alle“, um alle Termine zu verschieben).  
        3. Mit *Bestätigen* ausführen.  
        4. Anschließend werden die verschobenen Termine angezeigt.
        
        ---
        
        ### **3. Klientenverwaltung**
        Hier können neue Klienten angelegt und bestehende verwaltet werden.
        
        **Neuen Klienten hinzufügen:**
        1. Kürzel eingeben (zwei Buchstaben).  
        2. Datum der ersten Sitzung auswählen.  
        3. *Hinzufügen* klicken.  
           → Es werden automatisch drei Sprechstunden mit wöchentlichem Abstand angelegt.
        
        **Bestehende Klienten:**
        - Auswahl eines Klienten zeigt alle Termine und eine Übersicht (Startdatum, geplantes Enddatum, Sitzungsanzahl, aktuelle Therapiephase).  
        - Weitere Sitzungsphasen (Probatorik, KZT, LZT usw.) können in den folgenden Tabs ergänzt werden.
        
        ---
        
        ### **4. Quartalsprognose**
        Hier wird die erwartete Verteilung der Sitzungsarten pro Quartal angezeigt.  
        Die Prognose basiert auf den geplanten Terminen und dient der Vorbereitung für Abrechnungszeiträume.
        
        ---
        
        ### **5. Supervision**
        Supervisionstermine (Einzel- oder Gruppensupervision) können hier eingetragen und im Kalender angezeigt oder gelöscht werden.
        
        ---
        
        ### **6. Datenverwaltung (Seitenleiste)**
        In der linken Seitenleiste befinden sich die Optionen zum Laden, Erstellen und Speichern von Daten.
        
        - **Neuen Datensatz beginnen:**  
          Erstellt eine leere Datenbasis, um neue Klienten einzutragen.
        
        - **CSV-Datei hochladen:**  
          Lädt bestehende Termindaten in die Anwendung.  
          Die Datei muss Spalten mit *Datum*, *Klient*, *Sitzungsart* und *Nummer* enthalten.
        
        - **CSV-Datei herunterladen:**  
          Speichert alle aktuellen Daten als `ipp_ambulanzdaten.csv`.
        
        ---
        
        ### **Hinweise zur Bedienung**
        - Änderungen (z. B. Terminausfälle, PTG, Urlaube) werden direkt in der Sitzung gespeichert.  
        - Nach bestimmten Aktionen (z. B. Hinzufügen, Löschen) wird die Seite automatisch neu geladen, um den aktuellen Stand anzuzeigen.  
        - Das System unterscheidet Sitzungsarten automatisch nach ihrer vorgesehenen Anzahl:
          - Sprechstunde: 3  
          - Probatorik: 4 (+ 1 Anamnese)  
          - Anamnese: 1  
          - KZT: 24  
          - LZT: 60  
          - RFP: 20  
        
        ---
        
        Diese Anleitung fasst die Kernfunktionen des Tools zusammen und hilft, die Anwendung sicher und effizient zu bedienen.
    """)
    
with tabs[0]:
    st.header("Kalenderübersicht")
    with st.expander("Hilfe anzeigen"):
        st.markdown(HILFE["Kalender"])                   
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
    
        klient_id = title.split(" - ")[0].strip()
        is_supervision = "E-SV" in title or "G-SV" in title
    
        # Header immer anzeigen
        st.header(f"{title} am {start}")
    
        # Falls noch keine Aktion läuft
        if st.session_state.get("last_button_click") is None:
            if is_supervision:
                if st.button("Supervisionstermin löschen"):
                    st.session_state.last_button_click = "sup_loeschen"
            else:
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
        action = st.session_state.get("last_button_click")
    
        if action == "sup_loeschen":
            st.subheader("Supervisionstermin löschen")
            st.warning("Dieser Supervisionstermin wird gelöscht!")
    
            with st.form("sup_loeschen_form"):
                if st.form_submit_button("Bestätigen"):
                    loesche_sup_termin(start, title)
                    st.session_state.last_button_click = None
                    st.session_state.selected_event = None
                    st.rerun()
    
            abbruch_button("sup")
    
        elif action == "Terminausfall":
            with st.form("terminausfall"):
                st.subheader("Termin ist ausgefallen")
                st.warning("Dieser Termin wird gelöscht und alle Termine um eine Woche verschoben")
                if st.form_submit_button("Bestätigen"):
                    verschiebe_termin_callback(start, klient_id)
                    st.session_state.last_button_click = None
                    st.session_state.selected_event = None
                    st.rerun()
            abbruch_button("terminausfall")
    
        elif action == "PTG":
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
                        st.session_state.last_button_click = None
                        st.session_state.selected_event = None
                        st.rerun()
            abbruch_button("ptg")
    
        elif action == "Verschieben":
            with st.form("verschieben"):
                new_day = wochentag_auswahl()
                diff_tage = new_day - pd.to_datetime(start).weekday()
                if st.form_submit_button("Bestätigen"):
                    verschiebe_alle(start, klient_id, diff_tage)
                    st.session_state.last_button_click = None
                    st.session_state.selected_event = None
                    st.rerun()
            abbruch_button("verschieben")
    
        elif action == "Ende":
            with st.form("ende"):
                st.subheader("Therapie ab diesem Termin beenden")
                st.warning("Alle zukünftigen Termine inklusive des ausgewählten Termins werden gelöscht!")
                if st.form_submit_button("Bestätigen"):
                    loesche_termine(start, klient_id)
                    st.session_state.last_button_click = None
                    st.session_state.selected_event = None
                    st.rerun()
            abbruch_button("ende")
            
with tabs[1]:
    st.header("Urlaubsverwaltung")
    with st.expander("Hilfe anzeigen"):
        st.markdown(HILFE["Abwesenheiten"])     
    clients = st.session_state.sitzungen["Klient"].dropna().unique()
    
    if clients.size > 0:
        valid_clients = [c for c in clients if c]

        with st.form("urlaub"):
            st.subheader("Termine wegen Urlaub verschieben")
            
            start_date_default = date.today()
            end_date_default = date.today() + timedelta(days=14)

            u_dates = st.date_input(
                "Wählen Sie einen Datumsbereich für die Abwesenheit aus",
                value=(start_date_default, end_date_default),
                help="Wählen Sie das Start- und Enddatum aus",
                format = "DD/MM/YYYY"
            )
            
            u_klient = st.selectbox(
                "Wähle einen Klienten aus", 
                ["Alle"] + valid_clients, 
                key="auswahl_klient_box_urlaub"
            )

            submitted = st.form_submit_button("Bestätigen")
        
        if submitted:
            if len(u_dates) == 2:
                u_start = pd.to_datetime(u_dates[0])
                u_end = pd.to_datetime(u_dates[1])
            
                # Termine verschieben
                urlaub_termine = loesche_urlaub(u_start, u_end, u_klient)
    
                # Zeige die verschobenen Termine als Tabelle
                if not urlaub_termine.empty:
                    # Erfolgsmeldung mit Zeilenumbruch
                    st.success("Die folgenden Termine wurden erfolgreich verschoben:")
                    st.dataframe(
                        urlaub_termine[["Datum", "Klient", "Sitzungsart", "Nummer"]],
                        column_config={
                            "Datum": st.column_config.DatetimeColumn(
                                "Datum",
                                format="DD.MM.YYYY",
                                time_format=""
                            )
                        }
                    )
                else:
                    st.info("Keine Termine für den gewählten Zeitraum gefunden.")
                
                if st.button("OK, aktualisieren"):
                    st.rerun()

        abbruch_button("urlaub")
        
    else:
        st.info("Füge einen Klienten hinzu, um Abwesenheiten zu verwalten")

with tabs[2]:
    st.header("Klientenverwaltung")
    with st.expander("Hilfe anzeigen"):
        st.markdown(HILFE["Klienten"])     
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
    
        if "last_button_click" not in st.session_state:
            st.session_state.last_button_click = None
        
        if "ausgewaehlter_klient" not in st.session_state:
            st.session_state.ausgewaehlter_klient = None
        
        # Dynamische Anzeige nur, wenn ein Klient ausgewählt ist
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
                st.dataframe(
                    klient_termine[["Datum", "Klient", "Sitzungsart", "Nummer"]],
                    st.dataframe(
                        urlaub_termine[["Datum", "Klient", "Sitzungsart", "Nummer"]],
                        column_config={
                            "Datum": st.column_config.DatetimeColumn(
                                "Datum",
                                format="DD.MM.YYYY",
                                time_format=""
                            )
                        }
                    )
                )
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
                        st.session_state.last_button_click = None  # Zurücksetzen
                        st.rerun()
                abbruch_button("probatorik")
            
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
                        st.session_state.last_button_click = None  # Zurücksetzen
                        st.rerun()
                abbruch_button("kzt")
            
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
                        st.session_state.last_button_click = None  # Zurücksetzen
                        st.rerun()
                abbruch_button("lzt")
            
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
                        st.session_state.last_button_click = None  # Zurücksetzen
                        st.rerun()
                abbruch_button("rfp")
            
            elif st.session_state.last_button_click == "Umwandlung":
                with st.form("umwandlung_eingabe"):
                    st.subheader("KZT in LZT umwandeln")
                    # Holen Sie die aktuelle Anzahl an KZT-Sitzungen als Max-Wert
                    kzt_sitzungen = klient_termine[klient_termine["Sitzungsart"] == "KZT"]
                    start_kzt = min(kzt_sitzungen["Nummer"])
                    start_umwandlung = st.number_input(f"Ab welcher KZT-Sitzung (von {start_kzt} bis 24) soll die Therapie in eine LZT umgewandelt werden?", min_value=start_kzt, max_value=24)
                    if st.form_submit_button("Umwandlung bestätigen"):
                        convert_kzt_to_lzt_callback(start_umwandlung)
                        st.session_state.last_button_click = None  # Zurücksetzen
                        st.rerun()
                abbruch_button("umwandlung")
    
    else:
        st.info("Füge zuerst einen Klienten hinzu, um die Übersicht zu sehen.")

with tabs[3]:
    st.header("Quartalsprognose")
    with st.expander("Hilfe anzeigen"):
        st.markdown(HILFE["Quartalsprognose"])     
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
        
            element = st.selectbox(
                "Bitte wähle das Quartal aus",
                quartale
            )
        
            if st.form_submit_button("Bestätigen"):
                st.subheader(element)
                quartals_termine = st.session_state.sitzungen[quartaljahre == element]
                quartals_termine = quartals_termine[quartals_termine["Sitzungsart"] != "Supervision"]
        
                prognose = quartals_termine["Sitzungsart"].value_counts().reset_index()
                prognose.columns = ["Sitzungsart", "Anzahl"]
                prognose["Schätzung (10/12)"] = (prognose["Anzahl"] * 10 / 12).round()
        
                if ext == "extern":
                    prognose['EBM Honorar'] = prognose['Sitzungsart'].map(sitzung_mapping) - 3
                else:
                    prognose['EBM Honorar'] = prognose['Sitzungsart'].map(sitzung_mapping)
        
                prognose['Entgelt'] = prognose["Schätzung (10/12)"] * prognose['EBM Honorar']
        
                summe_anzahl = prognose["Anzahl"].sum()
                summe_schaetzung = prognose["Schätzung (10/12)"].sum()
                summe_entgelt = prognose["Entgelt"].sum()
        
                neue_zeile_werte = {
                    "Sitzungsart": "",
                    "Anzahl": summe_anzahl,
                    "Schätzung (10/12)": summe_schaetzung,
                    "EBM Honorar": "",
                    "Entgelt": summe_entgelt
                }
                prognose.loc['Gesamt'] = neue_zeile_werte
        
                st.dataframe(prognose)
    else: 
        st.info("Füge zuerst einen Klienten hinzu, um die Quartalsprognose zu bestimmen")

with tabs[4]:
    st.header("Supervision")
    with st.expander("Hilfe anzeigen"):
        st.markdown(HILFE["Supervision"])     
    clients = st.session_state.sitzungen["Klient"].dropna().unique()     

    with st.form("sup_add"):
        sup_date = st.date_input("Datum Supervision", format="DD/MM/YYYY")
        sup_type = st.radio("Einzel-/Gruppensupervision?", options=["E-SV", "G-SV"])
        sup_stunden = st.number_input(
            "Anzahl Stunden",
            min_value=1,
            max_value=10,
            step=1,
            format="%d"
        )
        if st.form_submit_button("Hinzufügen"):
            sup_sitzung = pd.DataFrame({
                "Datum": [pd.Timestamp(sup_date)],
                "Sitzungsart": ["Supervision"],
                "Art Supervision": [sup_type],
                "Stundenanzahl": [sup_stunden]
            })
            
            st.session_state.sitzungen = pd.concat([st.session_state.sitzungen, sup_sitzung], ignore_index=True)
            st.rerun()

    supervisionen = st.session_state.sitzungen[st.session_state.sitzungen["Sitzungsart"] == "Supervision"]
    
    if supervisionen.size > 0:
        st.subheader("Supervisionsübersicht (IST vs SOLL)")
        with st.form("sup_ov"):
            due_day = st.date_input("Bitte wähle einen Stichtag aus.", format="DD/MM/YYYY")
            if st.form_submit_button("Bestätigen"):
                subset = st.session_state.sitzungen[st.session_state.sitzungen["Datum"] <= pd.Timestamp(due_day)]
                subset_sitzungen = subset[subset["Sitzungsart"] != "Supervision"].shape[0]
                subset_sup = subset[subset["Sitzungsart"] == "Supervision"]
    
                st.write(f"Bis zum {due_day} wurden/werden {subset_sitzungen} Sitzungen Psychotherapie absolviert. Daraus ergibt sich der folgende Supervisionsbedarf.")
    
                vergleich = pd.DataFrame(columns=["SOLL", "IST", "Differenz"], index=["Gesamt-SUP", "E-SV", "G-SV"])
                vergleich["SOLL"] = [subset_sitzungen / 4, subset_sitzungen / 12, subset_sitzungen / 6]
                vergleich["SOLL"] = vergleich["SOLL"].round(1)
    
                vergleich["IST"] = [
                    subset_sup["Stundenanzahl"].sum(),
                    subset_sup[subset_sup["Art Supervision"] == "E-SV"]["Stundenanzahl"].sum(),
                    subset_sup[subset_sup["Art Supervision"] == "G-SV"]["Stundenanzahl"].sum()
                ]
    
                vergleich["Differenz"] = vergleich["IST"] - vergleich["SOLL"]
                st.write(vergleich)
    else:
        st.info("Füge eine erste Supervisionssitzung hinzu, um die Supervisionsübersicht zu öffnen.")



# --- POPUP-WARNUNG BEIM SCHLIEßEN DES FENSTERS ---
components.html(
    """
    <script>
    window.addEventListener("beforeunload", function (e) {
        var confirmationMessage = "Möchtest du die Datei noch herunterladen, bevor du das Fenster schließt?";
        e.preventDefault();
        e.returnValue = confirmationMessage; // Für ältere Browser
        return confirmationMessage;
    });
    </script>
    """,
    height=0,
)
