import streamlit as st
import pandas as pd
from datetime import date, time, datetime, timedelta
from streamlit_calendar import calendar
import os
import streamlit.components.v1 as components
import locale

# Setze deutsche Locale für Datumsformatierung
try:
    locale.setlocale(locale.LC_TIME, 'de_DE.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'de_DE')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, 'German')
        except locale.Error:
            pass  # Fallback auf Systemstandard

# =============================================================================
# KONFIGURATION & KONSTANTEN
# =============================================================================

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

CHECKLISTE_TEMPLATE = {
    "Formale Aufnahme & Start": [
        "Abrechnungsschein oder Überweisung vorhanden",
        "Abrechnungsschein/Überweisung (optional)",
        "Sprechstundenprotokoll ausgefüllt",
        "PTV 10 ausgefüllt",
        "PTV 11 ausgefüllt",
        "Aktendeckblatt angelegt",
        "Terminliste erstellt",
        "PiA-Einverständniserklärung unterschrieben",
        "Patienteninfo & Einverständnis Tonaufzeichnungen",
        "Datenschutzerklärung unterschrieben",
        "Einverständnis Tonbandaufzeichnungen",
        "Informationsblatt ePA übergeben",
        "Patientenerklärung ePA unterschrieben",
        "Eintrag von Daten in ePA (optional)",
        "Lebensfragebogen ausgegeben",
        "Lebensfragebogen zurück",
        "Konsiliarbericht + rosa Überweisung mitgegeben",
        "Konsiliarbericht + rosa Überweisung zurück",
        "Therapievertrag abgeschlossen",
    ],
    "PT-Verfahren": [
        "PTV 1 eingereicht",
        "PTV 2 eingereicht",
        "Gutachterbericht"
    ],
    "Abschlüsse": [
        "Therapieende dokumentiert",
    ],
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

EBM_HONORAR = {
    'Sprechstunde': 46.8,
    'Probatorik': 35.15,
    'Anamnese': 35.05,
    'KZT': 46.65,
    'LZT': 46.65,
    'RFP': 46.65,
    'PTG': 38.2
}

WOCHENTAGE = {
    "Montag": 0,
    "Dienstag": 1,
    "Mittwoch": 2,
    "Donnerstag": 3,
    "Freitag": 4,
}

# =============================================================================
# DATENMANAGEMENT
# =============================================================================

def load_data():
    """Lädt Daten aus CSV-Datei oder erstellt leeren DataFrame."""
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE, parse_dates=['Datum'])
        return df.astype({
            'Datum': 'datetime64[ns]',
            'Klient': 'object',
            'Sitzungsart': 'object',
            'Nummer': 'Int64'
        })
    return pd.DataFrame(columns=['Datum', 'Klient', 'Sitzungsart', 'Nummer']).astype({
        'Datum': 'datetime64[ns]',
        'Klient': 'object',
        'Sitzungsart': 'object',
        'Nummer': 'Int64'
    })


def setze_basissitzungen(name: str, start_datum: date) -> pd.DataFrame:
    """Erstellt initiale Sprechstunden für neuen Klienten."""
    sitzungen_data = []
    start_timestamp = pd.Timestamp(start_datum)
    
    for i in range(1, SITZUNGEN_TYPEN["Sprechstunde"] + 1):
        sitzungen_data.append({
            "Datum": start_timestamp + timedelta(days=(i - 1) * SITZUNGS_DAUER_TAGE),
            "Klient": name,
            "Sitzungsart": "Sprechstunde",
            "Nummer": i,
        })
    return pd.DataFrame(sitzungen_data)


def generiere_folgesitzungen(
    klient_name: str,
    last_date: pd.Timestamp,
    sitzungs_art: str,
    start_nr: int,
    end_nr: int
) -> pd.DataFrame:
    """Generiert Folgesitzungen für einen Klienten."""
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


def hole_klienten_termine(klient: str) -> pd.DataFrame:
    """Gibt alle Termine eines Klienten zurück."""
    return st.session_state.sitzungen[
        st.session_state.sitzungen["Klient"] == klient
    ].reset_index(drop=True)


def update_klient_termine_in_session(client: str, klienten_termine: pd.DataFrame):
    """Aktualisiert Termine eines Klienten im Session State."""
    st.session_state.sitzungen = st.session_state.sitzungen[
        st.session_state.sitzungen["Klient"] != client
    ].copy()
    st.session_state.sitzungen = pd.concat(
        [st.session_state.sitzungen, klienten_termine],
        ignore_index=True
    )


# =============================================================================
# TERMINOPERATIONEN
# =============================================================================

def get_index(termine: pd.DataFrame, date: pd.Timestamp) -> int:
    """Findet Index eines Termins an gegebenem Datum."""
    termine = termine.reset_index(drop=True)
    date = pd.to_datetime(date)
    termine["Datum"] = pd.to_datetime(termine["Datum"])
    
    matching_rows = termine[termine["Datum"].dt.date == date.date()]
    
    if matching_rows.empty:
        print(f"Kein Termin gefunden für Datum {date} – übersprungen.")
        return None
    
    return matching_rows.index[0]


def count_value_in_quarter(df: pd.DataFrame, date: pd.Timestamp, spalte: str, wert: str) -> int:
    """Zählt wie oft ein Wert in einer Spalte im selben Quartal vorkommt."""
    date = pd.to_datetime(date)
    quartal = date.to_period("Q")
    
    gleiche_quartal = df[pd.to_datetime(df["Datum"]).dt.to_period("Q") == quartal]
    return (gleiche_quartal[spalte] == wert).sum()


def verschiebe_termin_callback(date: pd.Timestamp, client: str) -> pd.DataFrame:
    """Verschiebt einen Termin und alle nachfolgenden um eine Woche."""
    klienten_termine = hole_klienten_termine(client)
    date = pd.to_datetime(date)
    
    idx = get_index(klienten_termine, date)
    if idx is None:
        return klienten_termine
        
    last_date = klienten_termine["Datum"].max()
    neue_daten = klienten_termine["Datum"].tolist()
    neue_daten.append(last_date + timedelta(days=7))
    del neue_daten[idx]
    
    klienten_termine["Datum"] = neue_daten
    update_klient_termine_in_session(client, klienten_termine)
    return klienten_termine


def markiere_ptg(date: pd.Timestamp, client: str) -> pd.DataFrame:
    """Markiert einen Termin als PTG."""
    klienten_termine = hole_klienten_termine(client)
    date = pd.to_datetime(date)
    
    n_ptg = count_value_in_quarter(klienten_termine, date, "Sitzungsart", "PTG") + 1
    idx = get_index(klienten_termine, date)
    
    if idx is None:
        return klienten_termine
    
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


def loesche_termine(date: pd.Timestamp, client: str) -> pd.DataFrame:
    """Löscht alle Termine ab gegebenem Datum."""
    klienten_termine = hole_klienten_termine(client)
    date = pd.to_datetime(date)
    
    idx = get_index(klienten_termine, date)
    if idx is None:
        return klienten_termine
    
    klienten_termine = klienten_termine[:idx]
    update_klient_termine_in_session(client, klienten_termine)
    return klienten_termine


def loesche_urlaub(start: pd.Timestamp, ende: pd.Timestamp, klient: str) -> pd.DataFrame:
    """Verschiebt Termine im Urlaubszeitraum."""
    termine = st.session_state.sitzungen.copy()
    termine = termine[termine["Sitzungsart"] != "Supervision"]
    
    if klient != "Alle":
        termine = termine[termine["Klient"] == klient]
        
    urlaub_start = pd.to_datetime(start)
    urlaub_ende = pd.to_datetime(ende)
    
    urlaub_termine = termine[
        (termine["Datum"] >= urlaub_start) &
        (termine["Datum"] <= urlaub_ende)
    ]
    
    for _, row in urlaub_termine.iterrows():
        verschiebe_termin_callback(row["Datum"], row["Klient"])
    
    return urlaub_termine


def verschiebe_alle(date: pd.Timestamp, client: str, diff_days: int) -> pd.DataFrame:
    """Verschiebt alle Termine ab Datum um diff_days."""
    klienten_termine = hole_klienten_termine(client)
    date = pd.to_datetime(date)
    
    idx = get_index(klienten_termine, date)
    if idx is None:
        return klienten_termine
        
    differenz = pd.Timedelta(days=diff_days)
    klienten_termine.loc[klienten_termine.index >= idx, "Datum"] += differenz
    
    update_klient_termine_in_session(client, klienten_termine)
    return klienten_termine


def loesche_sup_termin(date: pd.Timestamp, title: str):
    """Löscht einen Supervisionstermin."""
    termine = st.session_state.sitzungen.copy()
    date = pd.to_datetime(date)
    
    mask = (termine["Sitzungsart"] == "Supervision") & (termine["Datum"] == date)
    termine = termine.drop(termine[mask].index).reset_index(drop=True)
    st.session_state.sitzungen = termine


# =============================================================================
# SITZUNGS-CALLBACKS
# =============================================================================

def add_sessions_callback(session_type: str, start_nr: int = None):
    """Fügt neue Sitzungen für ausgewählten Klienten hinzu."""
    if not st.session_state.get('ausgewaehlter_klient') or st.session_state.klient_termine_filtered.empty:
        st.warning("Bitte wählen Sie einen gültigen Klienten aus.")
        return
        
    klient_termine = st.session_state.klient_termine_filtered
    last_date = klient_termine["Datum"].max()
    
    if session_type == "Probatorik":
        end_nr = SITZUNGEN_TYPEN["Probatorik"]
        neue_sitzungen_df = generiere_folgesitzungen(
            st.session_state.ausgewaehlter_klient, last_date, "Probatorik", 1, end_nr
        )
        anamnese_data = [{
            "Datum": last_date + timedelta(days=35),
            "Klient": st.session_state.ausgewaehlter_klient,
            "Sitzungsart": "Anamnese",
            "Nummer": 1
        }]
        neue_sitzungen_df = pd.concat([neue_sitzungen_df, pd.DataFrame(anamnese_data)], ignore_index=True)
    else:
        end_nr = SITZUNGEN_TYPEN[session_type]
        neue_sitzungen_df = generiere_folgesitzungen(
            st.session_state.ausgewaehlter_klient, last_date, session_type, start_nr, end_nr
        )

    st.session_state.sitzungen = pd.concat([st.session_state.sitzungen, neue_sitzungen_df], ignore_index=True)
    st.success(f"{session_type} Sitzungen ab Nr. {start_nr} hinzugefügt!")
    st.session_state.last_button_click = None
    
    # Aktualisiere gefilterte Termine
    st.session_state.klient_termine_filtered = st.session_state.sitzungen[
        st.session_state.sitzungen["Klient"] == st.session_state.ausgewaehlter_klient
    ]


def convert_kzt_to_lzt_callback(start_kzt_nr: int):
    """Wandelt KZT ab bestimmter Nummer in LZT um."""
    klient_termine = st.session_state.klient_termine_filtered
    
    # Filtert KZT-Sitzungen bis zur Umwandlungsnummer
    kzt_sitzungen_behalten = klient_termine[
        (klient_termine["Sitzungsart"] == "KZT") &
        (klient_termine["Nummer"] < start_kzt_nr)
    ]
    
    last_date = kzt_sitzungen_behalten["Datum"].max() if not kzt_sitzungen_behalten.empty else klient_termine["Datum"].max()
        
    neue_sitzungen = generiere_folgesitzungen(
        klient_name=st.session_state.ausgewaehlter_klient,
        last_date=last_date,
        sitzungs_art="LZT",
        start_nr=start_kzt_nr,
        end_nr=SITZUNGEN_TYPEN["LZT"]
    )
    
    # Entfernt alte KZT-Sitzungen und fügt LZT hinzu
    klient_termine_bereinigt = klient_termine[
        ~((klient_termine["Sitzungsart"] == "KZT") & (klient_termine["Nummer"] >= start_kzt_nr))
    ]
    st.session_state.sitzungen = pd.concat([klient_termine_bereinigt, neue_sitzungen], ignore_index=True)
    st.success(f"KZT ab Sitzung {start_kzt_nr} in LZT umgewandelt.")
    st.session_state.last_button_click = None
    
    # Aktualisiere gefilterte Termine
    st.session_state.klient_termine_filtered = st.session_state.sitzungen[
        st.session_state.sitzungen["Klient"] == st.session_state.ausgewaehlter_klient
    ]


# =============================================================================
# UI-HILFSFUNKTIONEN
# =============================================================================

def get_calendar_events(df: pd.DataFrame) -> list:
    """Konvertiert DataFrame in Kalender-Events."""
    events = []
    for _, row in df.iterrows():
        if row["Sitzungsart"] != "Supervision":
            events.append({
                "title": f"{row['Klient']} - {row['Sitzungsart']} {row['Nummer']}",
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


def wochentag_auswahl() -> int:
    """Zeigt Auswahl für Wochentag und gibt entsprechenden Index zurück."""
    st.warning("Ab diesem Termin werden alle Termine auf den folgenden Wochentag verschoben")
    
    ausgewaehlter_name = st.radio(
        "Wählen Sie den gewünschten Wochentag für die neuen Termine:",
        options=list(WOCHENTAGE.keys()),
        index=1
    )
    
    return WOCHENTAGE[ausgewaehlter_name]


def abbruch_button(key: str = "abbrechen"):
    """Zeigt Abbrechen-Button und setzt State zurück."""
    if st.button("Abbrechen", key=key):
        st.session_state.last_button_click = None
        st.session_state.selected_event = None
        st.rerun()


def init_session_state():
    """Initialisiert Session State Variablen."""
    if 'ausgewaehlter_klient' not in st.session_state:
        st.session_state.ausgewaehlter_klient = None
    if 'last_button_click' not in st.session_state:
        st.session_state.last_button_click = None
    if 'sitzungen' not in st.session_state:
        st.session_state.sitzungen = pd.DataFrame(
            columns=['Datum', 'Klient', 'Sitzungsart', 'Nummer', 'Art Supervision', 'Stundenanzahl']
        )
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False
    if 'klient_termine_filtered' not in st.session_state:
        st.session_state.klient_termine_filtered = pd.DataFrame()


# =============================================================================
# HAUPTANWENDUNG
# =============================================================================

st.set_page_config(page_title="IPP Ambulanzverwaltungstool", layout="wide")
st.subheader("IPP Ambulanzverwaltungstool")

init_session_state()

clients = st.session_state.sitzungen["Klient"].dropna().unique()

# =============================================================================
# SIDEBAR - Datenmanagement
# =============================================================================

with st.sidebar:
    st.error("Programm arbeitet ausschließlich offline! Bitte am Ende der Sitzung immer aktuellen Datensatz herunterladen und bei der nächsten Sitzung hochladen, um weiterzuarbeiten!")
    st.subheader("Datenquelle auswählen")

    if st.button("Neuen Datensatz beginnen"):
        st.session_state.sitzungen = pd.DataFrame(
            columns=['Datum', 'Klient', 'Sitzungsart', 'Nummer']
        ).astype({
            'Datum': 'datetime64[ns]',
            'Klient': 'object',
            'Sitzungsart': 'object',
            'Nummer': 'Int64'
        })
        st.session_state.ausgewaehlter_klient = ""
        st.session_state.klient_termine_filtered = pd.DataFrame()
        st.session_state.last_button_click = None
        st.session_state.data_loaded = True

    uploaded_file = st.file_uploader("CSV-Datei hochladen", type="csv")
    if uploaded_file is not None and not st.session_state.data_loaded:
        df = pd.read_csv(uploaded_file, parse_dates=['Datum'])
        st.session_state.sitzungen = df.astype({
            'Datum': 'datetime64[ns]',
            'Klient': 'object',
            'Sitzungsart': 'object',
            'Nummer': 'Int64'
        })
        
        # Standardmäßig ersten Klienten auswählen
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

    # CSV Download
    st.subheader("Daten sichern")
    if not st.session_state.sitzungen.empty:
        csv = st.session_state.sitzungen.to_csv(index=False).encode('utf-8')
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"ipp_ambulanzdaten_{timestamp}.csv"

        st.download_button(
            label="Daten als CSV herunterladen",
            data=csv,
            file_name=filename,
            mime="text/csv"
        )

# =============================================================================
# TABS
# =============================================================================

tabs = st.tabs(["Kalender", "Abwesenheiten", "Klientenverwaltung", "Quartalsprognose", "Supervision", "Anleitung"])

# TAB 5: Anleitung
with tabs[5]:
    with st.expander("1. Datenverwaltung (Seitenleiste)"):
        st.markdown("""
Die Datenverwaltung bildet die Grundlage der gesamten Anwendung.  
Da das Tool ausschließlich offline arbeitet, sollte zu Beginn einer Sitzung immer ein aktueller Datensatz geladen und am Ende gespeichert werden.

### Funktionen:

**• Neuen Datensatz beginnen**  
Erstellt eine komplett leere Datenbasis. Alle zuvor geladenen Daten werden verworfen.

**• CSV-Datei hochladen**  
Lädt vorhandene Daten.  
Die Datei muss mindestens enthalten:  
*Datum*, *Klient*, *Sitzungsart*, *Nummer*.

Wenn Daten vorhanden sind, wird automatisch der erste Klient vorausgewählt.

**• CSV herunterladen**  
Speichert alle aktuellen Daten als CSV-Datei mit Zeitstempel.  
Dies sollte immer am Ende der Sitzung erfolgen.
""")
    
    with st.expander("2. Kalender"):
        st.markdown("""
Der Kalender zeigt alle geplanten Sitzungen und Supervisionen übersichtlich an.  
Ein Klick auf einen Termin öffnet die verfügbaren Aktionen.

### Therapietermine:

**• Terminausfall**  
Löscht den Termin und verschiebt alle folgenden Termine um eine Woche.

**• PTG markieren**  
Trägt den Termin als PTG ein (maximal drei pro Quartal).  
Ist das Limit erreicht, erfolgt eine Warnung.

**• Ab hier verschieben**  
Verschiebt alle Termine ab dem gewählten Datum auf einen anderen Wochentag.

**• Therapieende**  
Löscht alle zukünftigen Termine einschließlich des ausgewählten.

### Supervision:

**• Supervisionstermin löschen**  
Entfernt den gewählten Supervisionseintrag.
""")
    
    with st.expander("3. Abwesenheiten"):
        st.markdown("""
Hier werden Urlaube oder Abwesenheiten abgebildet.  
Termine im gewählten Zeitraum werden automatisch um eine Woche verschoben.

### Vorgehen:

1. Datumsbereich auswählen.  
2. Klient festlegen (*Alle* verschiebt sämtliche Termine).  
3. Bestätigen.  
4. Die betroffenen Termine werden angezeigt.  

Diese Funktion erleichtert die Planung bei Urlaub, Krankheit oder anderen Ausfällen.
""")
    
    with st.expander("4. Klientenverwaltung"):
        st.markdown("""
Hier lassen sich neue Klienten anlegen und bestehende Behandlungen verwalten.

### Neuen Klienten hinzufügen:

- Kürzel (2 Buchstaben) eingeben.  
- Datum der ersten Sitzung wählen.  
- Es werden automatisch **3 Sprechstunden** im Wochenrhythmus angelegt.

### Bestehende Klienten verwalten:

Angezeigt werden:

- Startdatum  
- geplantes Enddatum  
- Anzahl der geplanten Sitzungen  
- aktuelle Therapiephase  
- vollständige Terminliste  

Je nach aktueller Phase stehen verschiedene Erweiterungen zur Verfügung:

**• Probatorik + Anamnese hinzufügen**  
**• KZT beginnen**  
**• LZT beginnen**  
**• RFP beginnen**  
**• KZT in LZT umwandeln**

Alle erweiterten Behandlungsphasen werden automatisch vollständig berechnet und angelegt.
""")
    
    with st.expander("5. Quartalsprognose"):
        st.markdown("""
Die Quartalsprognose bietet eine Schätzung der im Quartal geplanten Sitzungen sowie der voraussichtlichen EBM-Abrechnung.

### Funktionen:

- Quartal auswählen  
- interne oder externe Abrechnung wählen  
- automatische Berechnung:  
  - Anzahl der Sitzungen  
  - 10/12-Korrektur  
  - Honorar pro Sitzungsart  
  - Gesamtsumme  

Die Prognose eignet sich für Berichte, Abrechnungen und eigene Planung.
""")
    
    with st.expander("6. Supervision"):
        st.markdown("""
Dieser Bereich dient der Verwaltung von Supervisionen.

### Supervisionssitzung hinzufügen:

- Datum wählen  
- Art auswählen: Einzel (E-SV) oder Gruppe (G-SV)  
- Anzahl der Stunden eingeben  
- Die Sitzung erscheint anschließend im Kalender

### SOLL vs. IST Übersicht:

- Stichtag auswählen  
- Die Anwendung berechnet automatisch:  
  - erforderliche Supervisionsstunden (SOLL)  
  - tatsächlich geleistete Stunden (IST)  
  - Differenz zwischen beiden Werten

Dies ermöglicht eine präzise Dokumentation des Supervisionsstandes.
""")
    
    with st.expander("Hinweise zur Bedienung"):
        st.markdown("""
- Änderungen werden sofort übernommen und in die aktuelle Sitzung geschrieben.  
- Viele Aktionen führen automatisch zu einem Neustart der Oberfläche (z. B. nach Terminverschiebungen).  
- Standardwerte der Sitzungsarten:  
  - **Sprechstunde:** 3  
  - **Probatorik:** 4  
  - **Anamnese:** 1  
  - **KZT:** 24  
  - **LZT:** 60  
  - **RFP:** 20  

Die Anleitung soll helfen, das Tool klar, sicher und effizient zu nutzen.
""")

# TAB 0: Kalender
with tabs[0]:
    calendar_options = {
        "editable": True,
        "selectable": True,
        "initialView": "dayGridWeek",
        "height": 400,
        "headerToolbar": {
            "left": "today prev,next",
            "center": "",
            "right": "title",
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
    
        # Header anzeigen
        st.write(f"**{title} am {start}**")
    
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
            with st.form("sup_loeschen_form"):
                st.warning("Dieser Supervisionstermin wird gelöscht!")
                if st.form_submit_button("Bestätigen"):
                    loesche_sup_termin(start, title)
                    st.session_state.last_button_click = None
                    st.session_state.selected_event = None
                    st.rerun()
            abbruch_button("sup")
    
        elif action == "Terminausfall":
            with st.form("terminausfall"):
                st.warning("Dieser Termin wird gelöscht und alle Termine um eine Woche verschoben")
                if st.form_submit_button("Bestätigen"):
                    verschiebe_termin_callback(start, klient_id)
                    st.session_state.last_button_click = None
                    st.session_state.selected_event = None
                    st.rerun()
            abbruch_button("terminausfall")
    
        elif action == "PTG":
            with st.form("ptg"):
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
                st.warning("Alle zukünftigen Termine inklusive des ausgewählten Termins werden gelöscht!")
                if st.form_submit_button("Bestätigen"):
                    loesche_termine(start, klient_id)
                    st.session_state.last_button_click = None
                    st.session_state.selected_event = None
                    st.rerun()
            abbruch_button("ende")

# TAB 1: Abwesenheiten
with tabs[1]:
    clients = st.session_state.sitzungen["Klient"].dropna().unique()
    
    if clients.size > 0:
        valid_clients = [c for c in clients if c]

        with st.form("urlaub"):
            start_date_default = date.today()
            end_date_default = date.today() + timedelta(days=14)

            u_dates = st.date_input(
                "Wählen Sie einen Datumsbereich für die Abwesenheit aus",
                value=(start_date_default, end_date_default),
                help="Wählen Sie das Start- und Enddatum aus",
                format="DD.MM.YYYY"
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
                    st.success("Die folgenden Termine wurden erfolgreich verschoben:")
                    urlaub_termine["Datum_formatiert"] = urlaub_termine["Datum"].dt.strftime("%d.%m.%Y")
                    
                    st.dataframe(
                        urlaub_termine[["Datum_formatiert", "Klient", "Sitzungsart", "Nummer"]]
                    )
                else:
                    st.info("Keine Termine für den gewählten Zeitraum gefunden.")
                
                if st.button("OK, aktualisieren"):
                    st.rerun()

        abbruch_button("urlaub")
    else:
        st.info("Füge einen Klienten hinzu, um Abwesenheiten zu verwalten")

# TAB 2: Klientenverwaltung
with tabs[2]:
    kv_choice = st.radio(
        "Was möchtest du machen?",
        options=["Neuen Klienten hinzufügen", "Bestehenden Klienten verwalten"]
    )

    if kv_choice == "Neuen Klienten hinzufügen":
        with st.form("eingabemaske_klient"):
            name = st.text_input("Kürzel des Klienten", max_chars=3, help="Bitte gib die Initialen des Klienten ein")
            start_datum_input = st.date_input("Datum der ersten Sitzung", format="DD.MM.YYYY")
            submitted = st.form_submit_button("Hinzufügen")
            clients = st.session_state.sitzungen["Klient"].dropna().unique()

            if submitted:
                if name in clients:
                    st.warning(f"'{name}' existiert bereits! Bitte wähle ein anderes Kürzel.")
                if name.isdigit():
                    st.warning(f"'{name}' ist kein zulässiges Kürzel! Bitte wähle ein anderes Kürzel mit mindestens einem Buchstaben, zum Beispiel 'K{name}'.")
                elif not re.match("^[A-Za-z0-9äöüÄÖÜß]+$", name):
                    st.warning(f"'{name}' ist kein zulässiges Kürzel! Bitte verwende nur die Buchstaben von A-Z und die Zahlen von 0-9.")
                elif name and start_datum_input:
                    p_sitzungen = setze_basissitzungen(name, start_datum_input)
                    st.session_state.sitzungen = pd.concat(
                        [st.session_state.sitzungen, p_sitzungen],
                        ignore_index=True
                    )
                    st.success(f"Klient {name} mit Basissitzungen hinzugefügt!")
                    st.rerun()

    elif kv_choice == "Bestehenden Klienten verwalten":
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

            cola, colb = st.columns([0.3, 0.7])

            if st.session_state.ausgewaehlter_klient:
                klient_termine = st.session_state.klient_termine_filtered

                if not klient_termine.empty:
                    current_therapy = klient_termine["Sitzungsart"].iloc[-1]
                    uebersicht_klient = pd.DataFrame({
                        "Startdatum": [klient_termine["Datum"].min().strftime("%d.%m.%Y")],
                        "Voraussichtliches Enddatum": [klient_termine["Datum"].max().strftime("%d.%m.%Y")],
                        "Anzahl Termine": [len(klient_termine)],
                        "Aktuelle Therapie": [current_therapy]
                    }).T

                    has_prob = klient_termine['Sitzungsart'].isin(["Probatorik", "Anamnese"]).any()

                    # Buttons in 4 Spalten ÜBER den Tabellen
                    if current_therapy in ["Sprechstunde"]:
                        btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)
                        with btn_col1:
                            if st.button("Probatorik/Anamnese", disabled=has_prob, key="btn_prob"):
                                st.session_state.last_button_click = "Probatorik"
                        with btn_col2:
                            if st.button("KZT beginnen", key="btn_kzt"):
                                st.session_state.last_button_click = "KZT"
                        with btn_col3:
                            if st.button("LZT beginnen", key="btn_lzt"):
                                st.session_state.last_button_click = "LZT"
                        with btn_col4:
                            if st.button("RFP beginnen", key="btn_rfp"):
                                st.session_state.last_button_click = "RFP"

                    elif current_therapy in ["Anamnese"]:
                        btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)
                        with btn_col1:
                            st.button("Probatorik abgeschlossen", disabled=True, key="btn_prob_done")
                        with btn_col2:
                            if st.button("KZT beginnen", key="btn_kzt_anam"):
                                st.session_state.last_button_click = "KZT"
                        with btn_col3:
                            if st.button("LZT beginnen", key="btn_lzt_anam"):
                                st.session_state.last_button_click = "LZT"

                    elif current_therapy in ["KZT"]:
                        btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)
                        with btn_col1:
                            if st.button("Umwandlung", key="btn_umw"):
                                st.session_state.last_button_click = "Umwandlung"

                    elif current_therapy in ["LZT"]:
                        btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)
                        with btn_col1:
                            if st.button("RFP beginnen", key="btn_rfp_lzt"):
                                st.session_state.last_button_click = "RFP"

                    elif current_therapy in ["PTG"]:
                        btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)
                        with btn_col1:
                            if st.button("Probatorik/Anamnese", disabled=has_prob, key="btn_prob_ptg"):
                                st.session_state.last_button_click = "Probatorik"
                        with btn_col2:
                            if st.button("KZT beginnen", key="btn_kzt_ptg"):
                                st.session_state.last_button_click = "KZT"
                        with btn_col3:
                            if st.button("LZT beginnen", key="btn_lzt_ptg"):
                                st.session_state.last_button_click = "LZT"
                        with btn_col4:
                            if st.button("RFP beginnen", key="btn_rfp_ptg"):
                                st.session_state.last_button_click = "RFP"

                    # DYNAMISCHE MASKEN - über volle Breite
                    if st.session_state.last_button_click == "Probatorik":
                        with st.form("prob_confirm"):
                            st.subheader("Probatorik/Anamnese hinzufügen")
                            st.warning("Probatorik (4) und Anamnese (1) werden automatisch hinzugefügt.")
                            if st.form_submit_button("Bestätigen"):
                                add_sessions_callback("Probatorik")
                                st.session_state.last_button_click = None
                                st.rerun()
                        abbruch_button("probatorik")

                    elif st.session_state.last_button_click == "KZT":
                        with st.form("kzt_eingabe"):
                            st.subheader("KZT-Sitzungen hinzufügen")
                            if current_therapy == "Sprechstunde":
                                start_kzt = st.number_input(
                                    "Mit welcher KZT-Sitzung soll gestartet werden?",
                                    min_value=1, max_value=24, value=1
                                )
                            else:
                                start_kzt = 1
                                st.warning("KZT (1 und 2; 24 Sitzungen) wird hinzugefügt.")
                            if st.form_submit_button("KZT-Sitzungen hinzufügen"):
                                add_sessions_callback("KZT", start_kzt)
                                st.session_state.last_button_click = None
                                st.rerun()
                        abbruch_button("kzt")

                    elif st.session_state.last_button_click == "LZT":
                        with st.form("lzt_eingabe"):
                            st.subheader("LZT-Sitzungen hinzufügen")
                            if current_therapy == "Sprechstunde":
                                start_lzt = st.number_input(
                                    "Mit welcher LZT-Sitzung soll gestartet werden?",
                                    min_value=1, max_value=60, value=1
                                )
                            else:
                                start_lzt = 1
                                st.warning("LZT (60 Sitzungen) wird hinzugefügt.")
                            if st.form_submit_button("LZT-Sitzungen hinzufügen"):
                                add_sessions_callback("LZT", start_lzt)
                                st.session_state.last_button_click = None
                                st.rerun()
                        abbruch_button("lzt")

                    elif st.session_state.last_button_click == "RFP":
                        with st.form("rfp_eingabe"):
                            st.subheader("RFP-Sitzungen hinzufügen")
                            if current_therapy == "Sprechstunde":
                                start_rfp = st.number_input(
                                    "Mit welcher RFP-Sitzung soll gestartet werden?",
                                    min_value=1, max_value=20, value=1
                                )
                            else:
                                start_rfp = 1
                                st.warning("RFP (20 Sitzungen) wird hinzugefügt.")
                            if st.form_submit_button("RFP-Sitzungen hinzufügen"):
                                add_sessions_callback("RFP", start_rfp)
                                st.session_state.last_button_click = None
                                st.rerun()
                        abbruch_button("rfp")

                    elif st.session_state.last_button_click == "Umwandlung":
                        with st.form("umwandlung_eingabe"):
                            st.subheader("KZT in LZT umwandeln")
                            kzt_sitzungen = klient_termine[klient_termine["Sitzungsart"] == "KZT"]
                            start_kzt = min(kzt_sitzungen["Nummer"])
                            start_umwandlung = st.number_input(
                                f"Ab welcher KZT-Sitzung (von {start_kzt} bis 24) soll die Therapie umgewandelt werden?",
                                min_value=start_kzt, max_value=24
                            )
                            if st.form_submit_button("Umwandlung bestätigen"):
                                convert_kzt_to_lzt_callback(start_umwandlung)
                                st.session_state.last_button_click = None
                                st.rerun()
                        abbruch_button("umwandlung")

                    # Jetzt die zwei Spalten für die Tabellen
                    with cola:
                        st.dataframe(uebersicht_klient, hide_index=False)

                    with colb:
                        klient_termine["Datum_formatiert"] = klient_termine["Datum"].dt.strftime("%d.%m.%Y")
                        st.dataframe(
                            klient_termine[["Datum_formatiert", "Sitzungsart", "Nummer"]],
                            hide_index=True
                        )
                else:
                    st.info("Keine Termine für diesen Klienten gefunden.")
        else:
            st.info("Füge zuerst einen Klienten hinzu, um die Übersicht zu sehen.")

# TAB 3: Quartalsprognose
with tabs[3]:
    clients = st.session_state.sitzungen["Klient"].dropna().unique()

    if clients.size > 0:
        with st.form("qp"):
            ext = st.radio(
                "In externer Praxis oder im IPP?",
                options=["extern", "intern"]
            )
        
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
                    prognose['EBM Honorar'] = prognose['Sitzungsart'].map(EBM_HONORAR) - 3
                else:
                    prognose['EBM Honorar'] = prognose['Sitzungsart'].map(EBM_HONORAR)
        
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

# TAB 4: Supervision
with tabs[4]:
    clients = st.session_state.sitzungen["Klient"].dropna().unique()
    sv_choice = st.radio(
        "Was möchtest du machen?",
        options=["Supervisionssitzung hinzufügen", "Supervisions SOLL vs. IST vergleichen"]
    )
    
    if sv_choice == "Supervisionssitzung hinzufügen":
        with st.form("sup_add"):
            sup_date = st.date_input("Datum Supervision", format="DD.MM.YYYY")
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
                
    elif sv_choice == "Supervisions SOLL vs. IST vergleichen":
        supervisionen = st.session_state.sitzungen[st.session_state.sitzungen["Sitzungsart"] == "Supervision"]
        
        if supervisionen.size > 0:
            st.subheader("Supervisionsübersicht (IST vs SOLL)")
            with st.form("sup_ov"):
                due_day = st.date_input(
                    "Bitte wähle einen Stichtag aus.",
                    format="DD.MM.YYYY",
                    help="Bitte gib den Stichtag ein, zu dem Supervisions SOLL und IST verglichen werden sollen"
                )
                if st.form_submit_button("Bestätigen"):
                    subset = st.session_state.sitzungen[st.session_state.sitzungen["Datum"] <= pd.Timestamp(due_day)]
                    subset_sitzungen = subset[subset["Sitzungsart"] != "Supervision"].shape[0]
                    subset_sup = subset[subset["Sitzungsart"] == "Supervision"]
                    due_day_de = due_day.strftime("%d. %B %Y")
                    verb = "wurden" if due_day <= date.today() else "werden"
                    st.write(f"Bis zum {due_day_de} {verb} {subset_sitzungen} Sitzungen Psychotherapie absolviert. Daraus ergibt sich der folgende Supervisionsbedarf.")
        
                    vergleich = pd.DataFrame(
                        columns=["SOLL", "IST", "Differenz"],
                        index=["Gesamt-SUP", "E-SV", "G-SV"]
                    )
                    vergleich["SOLL"] = [
                        subset_sitzungen / 4,
                        subset_sitzungen / 12,
                        subset_sitzungen / 6
                    ]
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

# =============================================================================
# POPUP-WARNUNG BEIM SCHLIESSEN
# =============================================================================

components.html(
    """
    <script>
    window.addEventListener("beforeunload", function (e) {
        var confirmationMessage = "Möchtest du die Datei noch herunterladen, bevor du das Fenster schließt?";
        e.preventDefault();
        e.returnValue = confirmationMessage;
        return confirmationMessage;
    });
    </script>
    """,
    height=0,
)
