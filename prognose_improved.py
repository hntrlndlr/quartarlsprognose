"""
Ambulanzverwaltungstool für psychotherapeutische Praxis
Verbesserte Version mit SQLite-Datenbank, optimierter Struktur und Fehlerbehandlung
"""

import streamlit as st
import pandas as pd
from datetime import date, time, datetime, timedelta
from streamlit_calendar import calendar
import os
import re
import sqlite3
from contextlib import contextmanager
import streamlit.components.v1 as components
import locale
from typing import Optional, List, Dict, Tuple

# =============================================================================
# LOCALE SETUP
# =============================================================================

def setup_locale():
    """Setzt deutsche Locale mit Fallback-Optionen."""
    locale_options = ['de_DE.UTF-8', 'de_DE', 'German']
    for loc in locale_options:
        try:
            locale.setlocale(locale.LC_TIME, loc)
            return
        except locale.Error:
            continue
    # Fallback auf Systemstandard wenn keine deutsche Locale verfügbar

setup_locale()

# =============================================================================
# KONFIGURATION & KONSTANTEN
# =============================================================================

DB_FILE = "klienten_sitzungen.db"
SITZUNGS_DAUER_TAGE = 7

SITZUNGEN_TYPEN = {
    "Sprechstunde": 3,
    "Probatorik": 4,
    "Anamnese": 1,
    "KZT": 24,
    "LZT": 60,
    "RFP": 20,
    "PTG": 1  # PTG für Konsistenz hinzugefügt
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

HILFE = {
    "Kalender": """
**Kalender**
- Termine per Klick bearbeiten
- Supervisionstermine können gelöscht werden
- 'PTG markieren' max. 3x pro Quartal
- 'Ab hier verschieben' = alle Termine ab dem ausgewählten auf neuen Wochentag
- 'Therapieende' = löscht alle Termine ab gewähltem Datum
""",
    "Abwesenheiten": """
**Abwesenheiten**
- Wähle Zeitraum und Klient, um Termine automatisch zu verschieben
- Wähle "Alle" für Abwesenheiten des Therapeuten (dann werden alle Kliententermine in dem Zeitraum verschoben)
""",
    "Klienten": """
**Klientenverwaltung**
- Neue Klienten mit Kürzel + Datum hinzufügen (es werden standardmäßig drei Sprechstunden hinzugefügt)
- Übersicht eines Klienten zeigt aktuelle Therapiephase
- Bei Auswahl eines Klienten können Probatorik/KZT/LZT/RFP hinzugefügt werden
- Wenn der Klient in der KZT ist, kann eine Umwandlung erfolgen
- Wenn der Klient in der LZT ist, kann eine RFP begonnen werden
""",
    "Quartalsprognose": """
**Quartalsprognose**
- Zeigt Übersicht geplanter Sitzungen für alle Klienten
- Schätzung basiert auf 10/12 Formel (Korrektur für Krank/Urlaub)
- Filter nach Quartal möglich
""",
    "Supervision": """
**Supervision**
- Hier werden Supervisionstermine verwaltet
- Supervisionstermine können hinzugefügt werden (Stundenanzahl und Supervisionsart)
- Bis zu einem Stichtag kann dann das SOLL und IST von Supervisionen verglichen werden
""",
    "Anleitung": """
**Allgemeine Anleitung**
- Nutze die Tabs, um die verschiedenen Funktionen zu steuern
- Hilfe-Expander geben kurze Erklärungen
- Für detaillierte Infos siehe Dokumentation oder Sidebar-Hilfe
"""
}

# =============================================================================
# DATENBANK-MANAGEMENT
# =============================================================================

@contextmanager
def get_db_connection():
    """Context Manager für sichere Datenbankverbindungen."""
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        st.error(f"Datenbankfehler: {e}")
        raise
    finally:
        if conn:
            conn.close()


def init_database():
    """Initialisiert die Datenbank mit notwendigen Tabellen."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Haupttabelle für Sitzungen
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sitzungen (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                datum DATE NOT NULL,
                klient TEXT,
                sitzungsart TEXT NOT NULL,
                nummer INTEGER,
                art_supervision TEXT,
                stundenanzahl INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Index für häufige Abfragen
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_klient_datum 
            ON sitzungen(klient, datum)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sitzungsart 
            ON sitzungen(sitzungsart)
        """)


def migrate_from_csv():
    """Migriert Daten von CSV zu SQLite (einmalig bei erstem Start)."""
    csv_file = "klienten_sitzungen.csv"
    
    if not os.path.exists(csv_file):
        return False
    
    try:
        df = pd.read_csv(csv_file, parse_dates=['Datum'])
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Prüfen ob Tabelle leer ist
            cursor.execute("SELECT COUNT(*) FROM sitzungen")
            if cursor.fetchone()[0] > 0:
                return False  # Daten bereits vorhanden
            
            # Daten importieren
            for _, row in df.iterrows():
                # Datum zu String konvertieren
                datum_str = pd.to_datetime(row['Datum']).strftime('%Y-%m-%d')
                
                cursor.execute("""
                    INSERT INTO sitzungen (datum, klient, sitzungsart, nummer, art_supervision, stundenanzahl)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    datum_str,
                    row.get('Klient'),
                    row['Sitzungsart'],
                    row.get('Nummer'),
                    row.get('Art Supervision'),
                    row.get('Stundenanzahl')
                ))
            
            st.success(f"{len(df)} Einträge aus CSV importiert")
            
            # CSV-Backup erstellen
            backup_name = f"klienten_sitzungen_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            os.rename(csv_file, backup_name)
            st.info(f"CSV-Datei gesichert als: {backup_name}")
            
            return True  # Migration erfolgreich
            
    except Exception as e:
        st.error(f"Fehler beim CSV-Import: {e}")
        return False


def load_data() -> pd.DataFrame:
    """Lädt alle Sitzungsdaten aus der Datenbank."""
    try:
        with get_db_connection() as conn:
            df = pd.read_sql_query(
                "SELECT * FROM sitzungen ORDER BY datum, klient",
                conn,
                parse_dates=['datum', 'created_at', 'updated_at']
            )
            
            # Umbenennen für Kompatibilität mit bestehendem Code
            df = df.rename(columns={
                'datum': 'Datum',
                'klient': 'Klient',
                'sitzungsart': 'Sitzungsart',
                'nummer': 'Nummer',
                'art_supervision': 'Art Supervision',
                'stundenanzahl': 'Stundenanzahl'
            })
            
            return df
            
    except Exception as e:
        st.error(f"Fehler beim Laden der Daten: {e}")
        return pd.DataFrame(columns=[
            'Datum', 'Klient', 'Sitzungsart', 'Nummer',
            'Art Supervision', 'Stundenanzahl'
        ])


def save_data(df: pd.DataFrame):
    """Speichert DataFrame in die Datenbank."""
    try:
        # Spaltennamen für DB anpassen
        df_save = df.copy()
        df_save = df_save.rename(columns={
            'Datum': 'datum',
            'Klient': 'klient',
            'Sitzungsart': 'sitzungsart',
            'Nummer': 'nummer',
            'Art Supervision': 'art_supervision',
            'Stundenanzahl': 'stundenanzahl'
        })
        
        # Timestamps zu Strings konvertieren (SQLite-kompatibel)
        if 'datum' in df_save.columns:
            df_save['datum'] = pd.to_datetime(df_save['datum']).dt.strftime('%Y-%m-%d')
        
        # Nur relevante Spalten behalten
        columns_to_save = [
            'datum', 'klient', 'sitzungsart', 'nummer',
            'art_supervision', 'stundenanzahl'
        ]
        df_save = df_save[[col for col in columns_to_save if col in df_save.columns]]
        
        with get_db_connection() as conn:
            # Alte Daten löschen und neue einfügen (einfachster Ansatz)
            conn.execute("DELETE FROM sitzungen")
            df_save.to_sql('sitzungen', conn, if_exists='append', index=False)
            
    except Exception as e:
        st.error(f"Fehler beim Speichern der Daten: {e}")
        raise


# =============================================================================
# SITZUNGSMANAGEMENT
# =============================================================================

def setze_basissitzungen(name: str, start_datum: date, n_sprechstunden: int = 3) -> pd.DataFrame:
    """Erstellt initiale Sprechstunden für neuen Klienten."""
    sitzungen_data = []
    start_timestamp = pd.Timestamp(start_datum)
    
    for i in range(1, n_sprechstunden + 1):
        sitzungen_data.append({
            "Datum": start_timestamp + timedelta(days=(i - 1) * SITZUNGS_DAUER_TAGE),
            "Klient": name,
            "Sitzungsart": "Sprechstunde",
            "Nummer": i,
            "Art Supervision": None,
            "Stundenanzahl": None
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
            'Nummer': i,
            'Art Supervision': None,
            'Stundenanzahl': None
        })
    
    return pd.DataFrame(neue_sitzungen)


def hole_klienten_termine(klient: str) -> pd.DataFrame:
    """Gibt alle Termine eines Klienten zurück."""
    if st.session_state.sitzungen.empty:
        return pd.DataFrame()
    
    return st.session_state.sitzungen[
        st.session_state.sitzungen["Klient"] == klient
    ].reset_index(drop=True)


def update_klient_termine_in_session(client: str, klienten_termine: pd.DataFrame):
    """Aktualisiert Termine eines Klienten im Session State."""
    # Andere Klienten behalten
    st.session_state.sitzungen = st.session_state.sitzungen[
        st.session_state.sitzungen["Klient"] != client
    ].copy()
    
    # Neue Termine hinzufügen
    st.session_state.sitzungen = pd.concat(
        [st.session_state.sitzungen, klienten_termine],
        ignore_index=True
    ).sort_values('Datum').reset_index(drop=True)
    
    save_data(st.session_state.sitzungen)


def bestimme_therapiephase(klient_termine: pd.DataFrame) -> str:
    """Bestimmt die aktuelle Therapiephase eines Klienten."""
    if klient_termine.empty:
        return "Keine Termine"
    
    # Priorität: RFP > LZT > KZT > Probatorik > Sprechstunde
    if not klient_termine[klient_termine["Sitzungsart"] == "RFP"].empty:
        return "RFP"
    if not klient_termine[klient_termine["Sitzungsart"] == "LZT"].empty:
        return "LZT"
    if not klient_termine[klient_termine["Sitzungsart"] == "KZT"].empty:
        return "KZT"
    if not klient_termine[klient_termine["Sitzungsart"] == "Probatorik"].empty:
        return "Probatorik"
    if not klient_termine[klient_termine["Sitzungsart"] == "Sprechstunde"].empty:
        return "Sprechstunde"
    
    return "Unbekannt"


def erstelle_uebersicht_klient(klient_termine: pd.DataFrame) -> pd.DataFrame:
    """Erstellt Übersicht der Sitzungen eines Klienten."""
    if klient_termine.empty:
        return pd.DataFrame()
    
    # Nur Therapiesitzungen (keine Supervision)
    therapy_termine = klient_termine[klient_termine["Sitzungsart"] != "Supervision"].copy()
    
    if therapy_termine.empty:
        return pd.DataFrame()
    
    uebersicht = therapy_termine["Sitzungsart"].value_counts().reset_index()
    uebersicht.columns = ["Therapiephase", "Anzahl Sitzungen"]
    
    return uebersicht


# =============================================================================
# KALENDER-FUNKTIONEN
# =============================================================================

def konvertiere_zu_kalender_events(df: pd.DataFrame) -> List[Dict]:
    """Konvertiert DataFrame zu Kalender-Events."""
    events = []
    
    for _, row in df.iterrows():
        title = row['Sitzungsart']
        
        # Zusätzliche Infos für Titel
        if pd.notna(row.get('Klient')):
            title = f"{row['Klient']} - {title}"
        
        if pd.notna(row.get('Nummer')):
            title += f" #{int(row['Nummer'])}"
        
        if row['Sitzungsart'] == "Supervision":
            if pd.notna(row.get('Art Supervision')):
                title += f" ({row['Art Supervision']})"
            if pd.notna(row.get('Stundenanzahl')):
                title += f" - {int(row['Stundenanzahl'])}h"
        
        # Farbe basierend auf Sitzungsart
        color_map = {
            'Sprechstunde': '#3498db',  # Blau
            'Probatorik': '#9b59b6',    # Lila
            'Anamnese': '#e74c3c',      # Rot
            'KZT': '#2ecc71',           # Grün
            'LZT': '#27ae60',           # Dunkelgrün
            'RFP': '#f39c12',           # Orange
            'PTG': '#e67e22',           # Dunkelorange
            'Supervision': '#95a5a6'    # Grau
        }
        
        events.append({
            'title': title,
            'start': row['Datum'].strftime('%Y-%m-%d'),
            'color': color_map.get(row['Sitzungsart'], '#34495e'),
            'resourceId': row.get('Klient', 'Supervision')
        })
    
    return events


def verschiebe_termine_ab_datum(
    klient: str,
    ab_datum: pd.Timestamp,
    neuer_wochentag: int
) -> pd.DataFrame:
    """Verschiebt alle Termine ab einem Datum auf einen neuen Wochentag."""
    klienten_termine = hole_klienten_termine(klient)
    
    if klienten_termine.empty:
        return klienten_termine
    
    # Termine die verschoben werden sollen
    zu_verschieben = klienten_termine[klienten_termine['Datum'] >= ab_datum].copy()
    
    if zu_verschieben.empty:
        return klienten_termine
    
    # Berechne neues Datum für jeden Termin
    for idx in zu_verschieben.index:
        alter_wochentag = zu_verschieben.loc[idx, 'Datum'].weekday()
        tage_differenz = (neuer_wochentag - alter_wochentag) % 7
        
        if tage_differenz == 0 and neuer_wochentag != alter_wochentag:
            tage_differenz = 7
        
        zu_verschieben.loc[idx, 'Datum'] += timedelta(days=tage_differenz)
    
    # Zusammenführen
    unveraendert = klienten_termine[klienten_termine['Datum'] < ab_datum]
    return pd.concat([unveraendert, zu_verschieben], ignore_index=True).sort_values('Datum')


def verschiebe_termine_bei_abwesenheit(
    klient: str,
    start_abwesenheit: date,
    end_abwesenheit: date
) -> pd.DataFrame:
    """Verschiebt Termine während einer Abwesenheit automatisch nach hinten."""
    klienten_termine = hole_klienten_termine(klient)
    
    if klienten_termine.empty:
        return klienten_termine
    
    start_ts = pd.Timestamp(start_abwesenheit)
    end_ts = pd.Timestamp(end_abwesenheit)
    
    # Termine im Abwesenheitszeitraum
    betroffene_termine = klienten_termine[
        (klienten_termine['Datum'] >= start_ts) &
        (klienten_termine['Datum'] <= end_ts)
    ]
    
    if betroffene_termine.empty:
        return klienten_termine
    
    # Anzahl Tage Abwesenheit
    verschiebung_tage = (end_ts - start_ts).days + 1
    
    # Alle Termine ab Start der Abwesenheit verschieben
    klienten_termine.loc[
        klienten_termine['Datum'] >= start_ts, 'Datum'
    ] += timedelta(days=verschiebung_tage)
    
    return klienten_termine.sort_values('Datum').reset_index(drop=True)


def loesche_termine_ab_datum(klient: str, ab_datum: pd.Timestamp) -> pd.DataFrame:
    """Löscht alle Termine eines Klienten ab einem bestimmten Datum."""
    klienten_termine = hole_klienten_termine(klient)
    
    if klienten_termine.empty:
        return klienten_termine
    
    return klienten_termine[klienten_termine['Datum'] < ab_datum].reset_index(drop=True)


def markiere_als_ptg(klient: str, termin_datum: pd.Timestamp, quartal: str) -> Tuple[pd.DataFrame, bool, str]:
    """
    Markiert eine Sitzung als PTG (Psychotherapie in Gruppen).
    Fügt eine neue Sitzung ein und verschiebt alle Folgesitzungen.
    
    Returns:
        Tuple[DataFrame, bool, str]: (Aktualisierte Termine, Erfolgsstatus, Fehlermeldung)
    """
    klienten_termine = hole_klienten_termine(klient)
    
    if klienten_termine.empty:
        return klienten_termine, False, "Keine Termine gefunden"
    
    # Prüfen wie viele PTGs bereits im Quartal existieren
    ptg_termine_quartal = klienten_termine[
        (klienten_termine['Sitzungsart'] == 'PTG') &
        (klienten_termine['Datum'].dt.to_period('Q').astype(str) == quartal)
    ]
    
    anzahl_ptg = len(ptg_termine_quartal)
    
    # Limit prüfen
    if anzahl_ptg >= 3:
        # Daten der existierenden PTGs formatieren
        ptg_daten = ptg_termine_quartal['Datum'].dt.strftime('%d.%m.%Y').tolist()
        daten_text = ', '.join(ptg_daten)
        return klienten_termine, False, f"PTG-Limit erreicht! In {quartal} fanden bereits 3 PTGs statt am: {daten_text}"
    
    # Termin finden
    termin_index = klienten_termine[klienten_termine['Datum'] == termin_datum].index
    
    if len(termin_index) == 0:
        return klienten_termine, False, "Termin nicht gefunden"
    
    termin_index = termin_index[0]
    
    # Aktuelle Sitzungsart und Nummer
    original_art = klienten_termine.loc[termin_index, 'Sitzungsart']
    original_nummer = klienten_termine.loc[termin_index, 'Nummer']
    
    # Zu PTG umwandeln mit korrekter Nummerierung (1, 2 oder 3)
    ptg_nummer = anzahl_ptg + 1
    klienten_termine.loc[termin_index, 'Sitzungsart'] = 'PTG'
    klienten_termine.loc[termin_index, 'Nummer'] = ptg_nummer
    
    # Neue Sitzung mit ursprünglicher Art einfügen
    neue_sitzung = pd.DataFrame([{
        'Datum': termin_datum + timedelta(days=SITZUNGS_DAUER_TAGE),
        'Klient': klient,
        'Sitzungsart': original_art,
        'Nummer': original_nummer,
        'Art Supervision': None,
        'Stundenanzahl': None
    }])
    
    # Alle Folgesitzungen um eine Woche verschieben
    folge_termine = klienten_termine[klienten_termine['Datum'] > termin_datum].copy()
    folge_termine['Datum'] += timedelta(days=SITZUNGS_DAUER_TAGE)
    
    # Zusammenführen
    vor_termin = klienten_termine[klienten_termine['Datum'] <= termin_datum]
    
    aktualisiert = pd.concat(
        [vor_termin, neue_sitzung, folge_termine],
        ignore_index=True
    ).sort_values('Datum').reset_index(drop=True)
    
    return aktualisiert, True, ""


def zaehle_ptg_im_quartal(klient: str, quartal: str) -> int:
    """Zählt PTG-Sitzungen eines Klienten in einem Quartal."""
    klienten_termine = hole_klienten_termine(klient)
    
    if klienten_termine.empty:
        return 0
    
    # PTG-Sitzungen filtern
    ptg_termine = klienten_termine[klienten_termine['Sitzungsart'] == 'PTG']
    
    if ptg_termine.empty:
        return 0
    
    # Quartal des Termins bestimmen
    ptg_termine['Quartal'] = ptg_termine['Datum'].dt.to_period('Q').astype(str)
    
    return len(ptg_termine[ptg_termine['Quartal'] == quartal])


# =============================================================================
# KZT ZU LZT UMWANDLUNG
# =============================================================================

def wandle_kzt_in_lzt(klient: str, ab_sitzung: int) -> pd.DataFrame:
    """Wandelt KZT-Sitzungen ab einer bestimmten Nummer in LZT um."""
    klienten_termine = hole_klienten_termine(klient)
    
    if klienten_termine.empty:
        return klienten_termine
    
    # KZT-Sitzungen ab der angegebenen Nummer finden
    kzt_termine = klienten_termine[
        (klienten_termine['Sitzungsart'] == 'KZT') &
        (klienten_termine['Nummer'] >= ab_sitzung)
    ]
    
    if kzt_termine.empty:
        return klienten_termine
    
    # Umwandeln in LZT
    klienten_termine.loc[kzt_termine.index, 'Sitzungsart'] = 'LZT'
    
    # LZT-Sitzungen bis 60 ergänzen falls nötig
    max_lzt_nummer = klienten_termine[
        klienten_termine['Sitzungsart'] == 'LZT'
    ]['Nummer'].max()
    
    if max_lzt_nummer < 60:
        letzte_lzt = klienten_termine[
            klienten_termine['Sitzungsart'] == 'LZT'
        ].iloc[-1]
        
        neue_lzt = generiere_folgesitzungen(
            klient,
            letzte_lzt['Datum'],
            'LZT',
            int(max_lzt_nummer) + 1,
            60
        )
        
        klienten_termine = pd.concat(
            [klienten_termine, neue_lzt],
            ignore_index=True
        ).sort_values('Datum').reset_index(drop=True)
    
    return klienten_termine


# =============================================================================
# STREAMLIT SESSION STATE
# =============================================================================

def init_session_state():
    """Initialisiert Session State Variablen."""
    if 'sitzungen' not in st.session_state:
        st.session_state.sitzungen = load_data()
    
    if 'last_button_click' not in st.session_state:
        st.session_state.last_button_click = None
    
    if 'selected_event_data' not in st.session_state:
        st.session_state.selected_event_data = None


# =============================================================================
# HAUPT-APP
# =============================================================================

def main():
    """Hauptfunktion der Streamlit-App."""
    
    # Seiten-Konfiguration
    st.set_page_config(
        page_title="Ambulanzverwaltung",
        layout="wide"
    )
    
    # Datenbank initialisieren
    init_database()
    
    # CSV Migration durchführen (falls vorhanden)
    migration_erfolgt = migrate_from_csv()
    
    # Session State initialisieren (NACH Migration!)
    init_session_state()
    
    # Falls Migration gerade erfolgt ist, Daten neu laden
    if migration_erfolgt:
        st.session_state.sitzungen = load_data()
    
    # Titel
    st.title("Ambulanzverwaltungstool")
    
    # Sidebar mit Hilfe
    with st.sidebar:
        st.header("Hilfe & Anleitung")
        
        for kategorie, hilfetext in HILFE.items():
            with st.expander(kategorie):
                st.markdown(hilfetext)
        
        st.divider()
        
        # Datenimport
        st.subheader("Datenimport")
        uploaded_file = st.file_uploader(
            "CSV-Datei importieren",
            type=['csv'],
            help="Importiere deine bestehenden Sitzungsdaten aus einer CSV-Datei"
        )
        
        if uploaded_file is not None:
            if st.button("Import starten", type="primary"):
                try:
                    # CSV einlesen
                    df_import = pd.read_csv(uploaded_file, parse_dates=['Datum'])
                    
                    # Daten in Datenbank schreiben
                    with get_db_connection() as conn:
                        cursor = conn.cursor()
                        
                        # Bestehende Daten löschen (Warnung vorher!)
                        cursor.execute("DELETE FROM sitzungen")
                        
                        # Neue Daten importieren
                        for _, row in df_import.iterrows():
                            datum_str = pd.to_datetime(row['Datum']).strftime('%Y-%m-%d')
                            
                            cursor.execute("""
                                INSERT INTO sitzungen (datum, klient, sitzungsart, nummer, art_supervision, stundenanzahl)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (
                                datum_str,
                                row.get('Klient'),
                                row['Sitzungsart'],
                                row.get('Nummer'),
                                row.get('Art Supervision'),
                                row.get('Stundenanzahl')
                            ))
                    
                    # Session State aktualisieren
                    st.session_state.sitzungen = load_data()
                    
                    st.success(f"Import erfolgreich! {len(df_import)} Einträge importiert.")
                    
                    # Wichtig: Seite neu laden, damit Kalender aktualisiert wird
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Fehler beim Import: {e}")
        
        st.divider()
        
        # Datenexport
        st.subheader("Datenexport")
        if st.button("CSV exportieren"):
            csv = st.session_state.sitzungen.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"sitzungen_export_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        
        # Statistiken
        st.divider()
        st.subheader("Fortschritt")
        
        # Sitzungen bis heute zählen (nur Psychotherapie, keine Supervision)
        heute = pd.Timestamp(date.today())
        vergangene_sitzungen = st.session_state.sitzungen[
            (st.session_state.sitzungen['Datum'] <= heute) &
            (st.session_state.sitzungen['Sitzungsart'] != 'Supervision')
        ]
        
        # Alle geplanten Sitzungen (auch zukünftige)
        alle_sitzungen = st.session_state.sitzungen[
            st.session_state.sitzungen['Sitzungsart'] != 'Supervision'
        ].copy()
        
        anzahl_sitzungen = len(vergangene_sitzungen)
        ziel_sitzungen = 600
        fortschritt_prozent = (anzahl_sitzungen / ziel_sitzungen) * 100
        
        # Progress Bar
        st.progress(min(anzahl_sitzungen / ziel_sitzungen, 1.0))
        
        # Fortschritt anzeigen
        st.metric(
            "Absolvierte Sitzungen",
            f"{anzahl_sitzungen} / {ziel_sitzungen}",
            f"{fortschritt_prozent:.1f}% geschafft!"
        )
        
        # Grafische Darstellung
        if anzahl_sitzungen > 0 and not alle_sitzungen.empty:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            
            # Daten für Verlauf vorbereiten
            alle_sitzungen_sorted = alle_sitzungen.sort_values('Datum')
            alle_sitzungen_sorted['Kumulative_Anzahl'] = range(1, len(alle_sitzungen_sorted) + 1)
            
            # Vergangene Sitzungen (durchgezogene Linie)
            vergangene_sorted = alle_sitzungen_sorted[alle_sitzungen_sorted['Datum'] <= heute]
            
            # Geplante Sitzungen (gestrichelte Linie)
            geplante_sorted = alle_sitzungen_sorted[alle_sitzungen_sorted['Datum'] > heute]
            
            # Prognose basierend auf letztem Monat berechnen
            vor_einem_monat = heute - timedelta(days=30)
            sitzungen_letzter_monat = vergangene_sitzungen[
                vergangene_sitzungen['Datum'] >= vor_einem_monat
            ]
            anzahl_letzter_monat = len(sitzungen_letzter_monat)
            
            # Figure erstellen
            fig = go.Figure()
            
            # Vergangene Sitzungen (durchgezogene Linie)
            if not vergangene_sorted.empty:
                fig.add_trace(go.Scatter(
                    x=vergangene_sorted['Datum'],
                    y=vergangene_sorted['Kumulative_Anzahl'],
                    mode='lines+markers',
                    name='Absolviert',
                    line=dict(color='#2ecc71', width=3),
                    marker=dict(size=6)
                ))
            
            # Geplante Sitzungen (gestrichelte Linie)
            if not geplante_sorted.empty:
                # Verbindung zwischen letzter absolvierter und erster geplanter Sitzung
                if not vergangene_sorted.empty:
                    letzte_absolviert = vergangene_sorted.iloc[-1]
                    erste_geplant = geplante_sorted.iloc[0]
                    
                    fig.add_trace(go.Scatter(
                        x=[letzte_absolviert['Datum'], erste_geplant['Datum']],
                        y=[letzte_absolviert['Kumulative_Anzahl'], erste_geplant['Kumulative_Anzahl']],
                        mode='lines',
                        name='Geplant',
                        line=dict(color='#3498db', width=2, dash='dash'),
                        showlegend=False
                    ))
                
                fig.add_trace(go.Scatter(
                    x=geplante_sorted['Datum'],
                    y=geplante_sorted['Kumulative_Anzahl'],
                    mode='lines+markers',
                    name='Geplant',
                    line=dict(color='#3498db', width=2, dash='dash'),
                    marker=dict(size=4)
                ))
            
            # Prognose-Linie (wenn genug Daten vorhanden)
            if anzahl_letzter_monat > 0:
                sitzungen_pro_tag = anzahl_letzter_monat / 30
                fehlende_sitzungen = ziel_sitzungen - anzahl_sitzungen
                
                if fehlende_sitzungen > 0 and sitzungen_pro_tag > 0:
                    tage_bis_ziel = fehlende_sitzungen / sitzungen_pro_tag
                    ziel_datum = heute + timedelta(days=int(tage_bis_ziel))
                    
                    # Prognose-Linie von heute bis Zieldatum
                    fig.add_trace(go.Scatter(
                        x=[heute, ziel_datum],
                        y=[anzahl_sitzungen, ziel_sitzungen],
                        mode='lines',
                        name='Prognose (30-Tage-Basis)',
                        line=dict(color='#e74c3c', width=2, dash='dot'),
                        marker=dict(size=8, symbol='star')
                    ))
                    
                    # Ziel-Marker
                    fig.add_trace(go.Scatter(
                        x=[ziel_datum],
                        y=[ziel_sitzungen],
                        mode='markers+text',
                        name='Ziel: 600 Sitzungen',
                        marker=dict(size=12, color='#e74c3c', symbol='star'),
                        text=[f"Ziel: {ziel_datum.strftime('%d.%m.%Y')}"],
                        textposition='top center',
                        showlegend=False
                    ))
            
            # Ziellinie bei 600
            x_min = alle_sitzungen_sorted['Datum'].min()
            x_max = alle_sitzungen_sorted['Datum'].max()
            
            # Wenn Prognose vorhanden, x_max erweitern
            if anzahl_letzter_monat > 0:
                sitzungen_pro_tag = anzahl_letzter_monat / 30
                fehlende_sitzungen = ziel_sitzungen - anzahl_sitzungen
                if fehlende_sitzungen > 0 and sitzungen_pro_tag > 0:
                    tage_bis_ziel = fehlende_sitzungen / sitzungen_pro_tag
                    ziel_datum = heute + timedelta(days=int(tage_bis_ziel))
                    x_max = max(x_max, ziel_datum)
            
            fig.add_trace(go.Scatter(
                x=[x_min, x_max],
                y=[ziel_sitzungen, ziel_sitzungen],
                mode='lines',
                name='Ziel: 600',
                line=dict(color='#95a5a6', width=1, dash='dot'),
                showlegend=False
            ))
            
            # Layout anpassen
            fig.update_layout(
                title="Sitzungsverlauf und Prognose",
                xaxis_title="Datum",
                yaxis_title="Anzahl Sitzungen (kumulativ)",
                hovermode='x unified',
                height=500,
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            
            # Y-Achse bis mindestens 600
            max_y = max(650, alle_sitzungen_sorted['Kumulative_Anzahl'].max() + 50)
            fig.update_yaxis(range=[0, max_y])
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Textliche Prognose
            if anzahl_letzter_monat > 0:
                sitzungen_pro_tag = anzahl_letzter_monat / 30
                fehlende_sitzungen = ziel_sitzungen - anzahl_sitzungen
                
                if fehlende_sitzungen > 0 and sitzungen_pro_tag > 0:
                    tage_bis_ziel = fehlende_sitzungen / sitzungen_pro_tag
                    ziel_datum = heute + timedelta(days=int(tage_bis_ziel))
                    
                    st.info(
                        f"Basierend auf den letzten 30 Tagen ({anzahl_letzter_monat} Sitzungen): "
                        f"Wenn du so weiter machst, hast du am **{ziel_datum.strftime('%d.%m.%Y')}** "
                        f"600 Sitzungen erreicht! Das sind noch **{int(tage_bis_ziel)} Tage**."
                    )
                elif fehlende_sitzungen <= 0:
                    st.success("Glückwunsch! Du hast dein Ziel von 600 Sitzungen erreicht!")
            else:
                st.info("Keine Sitzungen im letzten Monat. Starte wieder durch!")
        else:
            st.info("Noch keine Sitzungen vorhanden. Importiere deine Daten oder füge Klienten hinzu!")
    
    # Hauptbereich mit Tabs
    tabs = st.tabs([
        "Kalender",
        "Abwesenheiten",
        "Klienten",
        "Quartalsprognose",
        "Supervision"
    ])
    
    # =============================================================================
    # TAB 1: KALENDER
    # =============================================================================
    
    with tabs[0]:
        st.header("Kalenderübersicht")
        
        with st.expander("Hilfe"):
            st.markdown(HILFE["Kalender"])
        
        if not st.session_state.sitzungen.empty:
            # Kalender-Events vorbereiten
            events = konvertiere_zu_kalender_events(st.session_state.sitzungen)
            
            # Kalender-Optionen
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
            
            # Kalender anzeigen
            selected = calendar(
                events=events,
                options=calendar_options,
                key="calendar"
            )
            
            # Event-Auswahl behandeln
            if selected and 'eventClick' in selected:
                event_info = selected['eventClick']['event']
                
                # Event-Datum und Klient extrahieren
                event_date_str = event_info.get('start', '')
                event_title = event_info.get('title', '')
                
                # Datum parsen
                if event_date_str:
                    # Nur Datum ohne Uhrzeit
                    event_date = pd.Timestamp(event_date_str.split('T')[0])
                    
                    # Klient aus Titel extrahieren (falls vorhanden)
                    klient_name = None
                    if ' - ' in event_title:
                        klient_name = event_title.split(' - ')[0]
                    
                    # Termin aus DataFrame finden
                    # Zuerst nach Datum filtern
                    termine_an_datum = st.session_state.sitzungen[
                        st.session_state.sitzungen['Datum'].dt.date == event_date.date()
                    ]
                    
                    # Wenn Klient bekannt, weiter filtern
                    if klient_name and not termine_an_datum.empty:
                        termin_gefiltert = termine_an_datum[
                            termine_an_datum['Klient'] == klient_name
                        ]
                        if not termin_gefiltert.empty:
                            termine_an_datum = termin_gefiltert
                    
                    # Wenn genau ein Termin gefunden, diesen speichern
                    if len(termine_an_datum) == 1:
                        st.session_state.selected_event_data = {
                            'datum': event_date,
                            'termin': termine_an_datum.iloc[0]
                        }
                    elif len(termine_an_datum) > 1:
                        # Mehrere Termine am selben Tag - ersten nehmen oder nach Sitzungsart filtern
                        sitzungsart = None
                        for art in ['Sprechstunde', 'Probatorik', 'KZT', 'LZT', 'RFP', 'PTG', 'Supervision']:
                            if art in event_title:
                                sitzungsart = art
                                break
                        
                        if sitzungsart:
                            termin_nach_art = termine_an_datum[
                                termine_an_datum['Sitzungsart'] == sitzungsart
                            ]
                            if not termin_nach_art.empty:
                                st.session_state.selected_event_data = {
                                    'datum': event_date,
                                    'termin': termin_nach_art.iloc[0]
                                }
                        else:
                            st.session_state.selected_event_data = {
                                'datum': event_date,
                                'termin': termine_an_datum.iloc[0]
                            }
            
            # Termin-Details und Aktionen
            if st.session_state.get('selected_event_data'):
                event_date = st.session_state.selected_event_data['datum']
                termin = st.session_state.selected_event_data['termin']
                
                st.divider()
                st.subheader("Termin-Details")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write(f"**Datum:** {event_date.strftime('%d.%m.%Y')}")
                    st.write(f"**Sitzungsart:** {termin['Sitzungsart']}")
                
                with col2:
                    if pd.notna(termin.get('Klient')):
                        st.write(f"**Klient:** {termin['Klient']}")
                    if pd.notna(termin.get('Nummer')):
                        st.write(f"**Nummer:** {int(termin['Nummer'])}")
                
                with col3:
                    if termin['Sitzungsart'] == 'Supervision':
                        if pd.notna(termin.get('Art Supervision')):
                            st.write(f"**Art:** {termin['Art Supervision']}")
                        if pd.notna(termin.get('Stundenanzahl')):
                            st.write(f"**Stunden:** {int(termin['Stundenanzahl'])}")
                
                st.divider()
                
                # Aktionen
                st.subheader("Aktionen")
                
                action_col1, action_col2, action_col3 = st.columns(3)
                
                with action_col1:
                    # Supervision löschen
                    if termin['Sitzungsart'] == 'Supervision':
                        if st.button("Supervision löschen", key="del_sup"):
                            st.session_state.sitzungen = st.session_state.sitzungen[
                                st.session_state.sitzungen['Datum'] != event_date
                            ].reset_index(drop=True)
                            save_data(st.session_state.sitzungen)
                            st.session_state.selected_event_data = None
                            st.success("Supervision gelöscht!")
                            st.rerun()
                
                with action_col2:
                    # PTG markieren (nur für Therapiesitzungen)
                    if termin['Sitzungsart'] in ['KZT', 'LZT'] and pd.notna(termin.get('Klient')):
                        klient = termin['Klient']
                        quartal = event_date.to_period('Q')
                        ptg_count = zaehle_ptg_im_quartal(klient, str(quartal))
                        
                        if ptg_count < 3:
                            if st.button("PTG markieren", key="mark_ptg"):
                                neue_termine, success, error_msg = markiere_als_ptg(
                                    klient,
                                    event_date,
                                    str(quartal)
                                )
                                
                                if success:
                                    update_klient_termine_in_session(klient, neue_termine)
                                    st.session_state.selected_event_data = None
                                    st.success(f"Als PTG {ptg_count + 1} markiert!")
                                    st.rerun()
                                else:
                                    st.error(error_msg if error_msg else "Fehler beim Markieren")
                        else:
                            # Daten der PTGs holen für Warnung
                            klienten_termine = hole_klienten_termine(klient)
                            ptg_termine = klienten_termine[
                                (klienten_termine['Sitzungsart'] == 'PTG') &
                                (klienten_termine['Datum'].dt.to_period('Q').astype(str) == str(quartal))
                            ]
                            ptg_daten = ptg_termine['Datum'].dt.strftime('%d.%m.%Y').tolist()
                            daten_text = ', '.join(ptg_daten)
                            st.warning(f"PTG-Limit erreicht! In {quartal} fanden bereits 3 PTGs statt am: {daten_text}")
                
                with action_col3:
                    # Termine verschieben
                    if pd.notna(termin.get('Klient')):
                        if st.button("Ab hier verschieben", key="verschiebe"):
                            st.session_state.verschiebe_modus = True
                
                # Verschiebe-Modus
                if st.session_state.get('verschiebe_modus', False):
                    st.divider()
                    
                    with st.form("verschiebe_form"):
                        st.subheader("Termine verschieben")
                        
                        neuer_tag = st.selectbox(
                            "Neuer Wochentag",
                            options=list(WOCHENTAGE.keys())
                        )
                        
                        col_submit, col_cancel = st.columns(2)
                        
                        with col_submit:
                            if st.form_submit_button("Verschieben"):
                                neue_termine = verschiebe_termine_ab_datum(
                                    termin['Klient'],
                                    event_date,
                                    WOCHENTAGE[neuer_tag]
                                )
                                update_klient_termine_in_session(termin['Klient'], neue_termine)
                                st.session_state.verschiebe_modus = False
                                st.session_state.selected_event_data = None
                                st.success(f"Termine auf {neuer_tag} verschoben!")
                                st.rerun()
                        
                        with col_cancel:
                            if st.form_submit_button("Abbrechen"):
                                st.session_state.verschiebe_modus = False
                                st.rerun()
                
                # Therapieende
                if pd.notna(termin.get('Klient')) and termin['Sitzungsart'] != 'Supervision':
                    st.divider()
                    
                    if st.button("Therapieende", key="therapieende", type="primary"):
                        st.session_state.therapieende_modus = True
                    
                    if st.session_state.get('therapieende_modus', False):
                        st.warning("Alle Termine ab diesem Datum werden gelöscht!")
                        
                        col_confirm, col_cancel = st.columns(2)
                        
                        with col_confirm:
                            if st.button("Bestätigen", key="confirm_ende"):
                                neue_termine = loesche_termine_ab_datum(
                                    termin['Klient'],
                                    event_date
                                )
                                update_klient_termine_in_session(termin['Klient'], neue_termine)
                                st.session_state.therapieende_modus = False
                                st.session_state.selected_event_data = None
                                st.success("Therapieende dokumentiert!")
                                st.rerun()
                        
                        with col_cancel:
                            if st.button("Abbrechen", key="cancel_ende"):
                                st.session_state.therapieende_modus = False
                                st.rerun()
        else:
            st.info("Noch keine Termine vorhanden. Füge zuerst einen Klienten hinzu.")
    
    # =============================================================================
    # TAB 2: ABWESENHEITEN
    # =============================================================================
    
    with tabs[1]:
        st.header("Abwesenheiten verwalten")
        
        with st.expander("Hilfe"):
            st.markdown(HILFE["Abwesenheiten"])
        
        klienten_liste = ["Alle"] + sorted(
            st.session_state.sitzungen['Klient'].dropna().unique().tolist()
        )
        
        with st.form("abwesenheit_form"):
            st.subheader("Abwesenheitszeitraum eingeben")
            
            col1, col2 = st.columns(2)
            
            with col1:
                start_date = st.date_input(
                    "Startdatum",
                    value=date.today(),
                    format="DD.MM.YYYY"
                )
            
            with col2:
                end_date = st.date_input(
                    "Enddatum",
                    value=date.today() + timedelta(days=7),
                    format="DD.MM.YYYY"
                )
            
            selected_klient = st.selectbox(
                "Betroffener Klient",
                options=klienten_liste,
                help="Wähle 'Alle' für eigene Abwesenheit (z.B. Urlaub)"
            )
            
            if st.form_submit_button("Termine verschieben", type="primary"):
                if start_date > end_date:
                    st.error("Startdatum muss vor Enddatum liegen!")
                else:
                    # Termine verschieben
                    if selected_klient == "Alle":
                        # Alle Klienten
                        for klient in st.session_state.sitzungen['Klient'].dropna().unique():
                            neue_termine = verschiebe_termine_bei_abwesenheit(
                                klient,
                                start_date,
                                end_date
                            )
                            update_klient_termine_in_session(klient, neue_termine)
                        
                        st.success(f"Alle Termine zwischen {start_date.strftime('%d.%m.%Y')} und {end_date.strftime('%d.%m.%Y')} wurden verschoben!")
                    else:
                        # Einzelner Klient
                        neue_termine = verschiebe_termine_bei_abwesenheit(
                            selected_klient,
                            start_date,
                            end_date
                        )
                        update_klient_termine_in_session(selected_klient, neue_termine)
                        
                        st.success(f"Termine von {selected_klient} wurden verschoben!")
                    
                    st.rerun()
    
    # =============================================================================
    # TAB 3: KLIENTEN
    # =============================================================================
    
    with tabs[2]:
        st.header("Klientenverwaltung")
        
        with st.expander("Hilfe"):
            st.markdown(HILFE["Klienten"])
        
        # Neuen Klienten hinzufügen
        with st.form("neuer_klient_form"):
            st.subheader("Neuen Klienten hinzufügen")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                klient_name = st.text_input(
                    "Klientenkürzel",
                    placeholder="z.B. AB",
                    help="Eindeutiges Kürzel für den Klienten"
                )
            
            with col2:
                start_datum = st.date_input(
                    "Startdatum erste Sprechstunde",
                    value=date.today(),
                    format="DD.MM.YYYY"
                )
            
            with col3:
                anzahl_sprechstunden = st.number_input(
                    "Anzahl Sprechstunden",
                    min_value=1,
                    max_value=10,
                    value=3,
                    help="Standard: 3 Sprechstunden"
                )
            
            if st.form_submit_button("Klient hinzufügen", type="primary"):
                if not klient_name:
                    st.error("Bitte Klientenkürzel eingeben!")
                elif klient_name in st.session_state.sitzungen['Klient'].values:
                    st.error(f"Klient {klient_name} existiert bereits!")
                else:
                    # Basis-Sprechstunden erstellen
                    neue_sitzungen = setze_basissitzungen(
                        klient_name,
                        start_datum,
                        anzahl_sprechstunden
                    )
                    
                    st.session_state.sitzungen = pd.concat(
                        [st.session_state.sitzungen, neue_sitzungen],
                        ignore_index=True
                    ).sort_values('Datum').reset_index(drop=True)
                    
                    save_data(st.session_state.sitzungen)
                    
                    st.success(f"Klient {klient_name} mit {anzahl_sprechstunden} Sprechstunden hinzugefügt!")
                    st.rerun()
        
        st.divider()
        
        # Klienten-Übersicht
        klienten = sorted(st.session_state.sitzungen['Klient'].dropna().unique().tolist())
        
        if klienten:
            st.subheader("Klienten-Übersicht")
            
            selected_klient = st.selectbox(
                "Klient auswählen",
                options=klienten,
                key="klient_auswahl"
            )
            
            if selected_klient:
                klient_termine = hole_klienten_termine(selected_klient)
                
                if not klient_termine.empty:
                    # Therapiephase bestimmen
                    current_therapy = bestimme_therapiephase(klient_termine)
                    
                    st.info(f"**Aktuelle Therapiephase:** {current_therapy}")
                    
                    # Übersicht erstellen
                    uebersicht = erstelle_uebersicht_klient(klient_termine)
                    
                    # Layout
                    cola, colb = st.columns(2)
                    
                    # Callback-Funktionen für Sitzungen
                    def add_sessions_callback(sitzungsart: str, start_nr: int):
                        """Fügt neue Sitzungen hinzu."""
                        max_nr = SITZUNGEN_TYPEN[sitzungsart]
                        
                        # Letzte Sitzung finden
                        therapy_termine = klient_termine[klient_termine['Sitzungsart'] != 'Supervision']
                        letzte_sitzung = therapy_termine.iloc[-1]
                        
                        # Neue Sitzungen generieren
                        neue_sitzungen = generiere_folgesitzungen(
                            selected_klient,
                            letzte_sitzung['Datum'],
                            sitzungsart,
                            start_nr,
                            max_nr
                        )
                        
                        # Hinzufügen
                        aktualisiert = pd.concat(
                            [klient_termine, neue_sitzungen],
                            ignore_index=True
                        ).sort_values('Datum').reset_index(drop=True)
                        
                        update_klient_termine_in_session(selected_klient, aktualisiert)
                        st.success(f"{sitzungsart} Sitzungen hinzugefügt!")
                    
                    def convert_kzt_to_lzt_callback(ab_sitzung: int):
                        """Wandelt KZT in LZT um."""
                        aktualisiert = wandle_kzt_in_lzt(selected_klient, ab_sitzung)
                        update_klient_termine_in_session(selected_klient, aktualisiert)
                        st.success("KZT in LZT umgewandelt!")
                    
                    def abbruch_button(key_suffix: str):
                        """Abbruch-Button für Formulare."""
                        if st.button("Abbrechen", key=f"abbruch_{key_suffix}"):
                            st.session_state.last_button_click = None
                            st.rerun()
                    
                    # Aktionsbuttons
                    st.subheader("Aktionen")
                    
                    btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)
                    
                    with btn_col1:
                        if current_therapy == "Sprechstunde":
                            if st.button("Probatorik", key="add_prob"):
                                st.session_state.last_button_click = "Probatorik"
                                st.rerun()
                    
                    with btn_col2:
                        if current_therapy in ["Sprechstunde", "Probatorik"]:
                            if st.button("KZT", key="add_kzt"):
                                st.session_state.last_button_click = "KZT"
                                st.rerun()
                    
                    with btn_col3:
                        if current_therapy in ["Sprechstunde", "Probatorik", "KZT"]:
                            if st.button("LZT", key="add_lzt"):
                                st.session_state.last_button_click = "LZT"
                                st.rerun()
                    
                    with btn_col4:
                        if current_therapy == "LZT":
                            if st.button("RFP", key="add_rfp"):
                                st.session_state.last_button_click = "RFP"
                                st.rerun()
                    
                    # Umwandlungs-Button
                    if current_therapy == "KZT":
                        if st.button("KZT → LZT umwandeln", key="convert"):
                            st.session_state.last_button_click = "Umwandlung"
                            st.rerun()
                    
                    st.divider()
                    
                    # Formulare für Sitzungen
                    if st.session_state.last_button_click == "Probatorik":
                        with st.form("prob_eingabe"):
                            st.subheader("Probatorik-Sitzungen hinzufügen")
                            
                            if current_therapy == "Sprechstunde":
                                start_prob = st.number_input(
                                    "Mit welcher Probatorik-Sitzung soll gestartet werden?",
                                    min_value=1,
                                    max_value=4,
                                    value=1,
                                    help="Standard: Bei Sitzung 1 beginnen"
                                )
                            else:
                                start_prob = 1
                                st.warning("Probatorik (4 Sitzungen) wird hinzugefügt.")
                            
                            col_submit, col_cancel = st.columns(2)
                            
                            with col_submit:
                                if st.form_submit_button("Probatorik hinzufügen"):
                                    add_sessions_callback("Probatorik", start_prob)
                                    st.session_state.last_button_click = None
                                    st.rerun()
                            
                            with col_cancel:
                                if st.form_submit_button("Abbrechen"):
                                    st.session_state.last_button_click = None
                                    st.rerun()
                    
                    elif st.session_state.last_button_click == "KZT":
                        with st.form("kzt_eingabe"):
                            st.subheader("KZT-Sitzungen hinzufügen")
                            
                            if current_therapy in ["Sprechstunde", "Probatorik"]:
                                start_kzt = st.number_input(
                                    "Mit welcher KZT-Sitzung soll gestartet werden?",
                                    min_value=1,
                                    max_value=24,
                                    value=1
                                )
                            else:
                                start_kzt = 1
                                st.warning("KZT (24 Sitzungen) wird hinzugefügt.")
                            
                            col_submit, col_cancel = st.columns(2)
                            
                            with col_submit:
                                if st.form_submit_button("KZT hinzufügen"):
                                    add_sessions_callback("KZT", start_kzt)
                                    st.session_state.last_button_click = None
                                    st.rerun()
                            
                            with col_cancel:
                                if st.form_submit_button("Abbrechen"):
                                    st.session_state.last_button_click = None
                                    st.rerun()
                    
                    elif st.session_state.last_button_click == "LZT":
                        with st.form("lzt_eingabe"):
                            st.subheader("LZT-Sitzungen hinzufügen")
                            
                            if current_therapy in ["Sprechstunde", "Probatorik", "KZT"]:
                                start_lzt = st.number_input(
                                    "Mit welcher LZT-Sitzung soll gestartet werden?",
                                    min_value=1,
                                    max_value=60,
                                    value=1
                                )
                            else:
                                start_lzt = 1
                                st.warning("LZT (60 Sitzungen) wird hinzugefügt.")
                            
                            col_submit, col_cancel = st.columns(2)
                            
                            with col_submit:
                                if st.form_submit_button("LZT hinzufügen"):
                                    add_sessions_callback("LZT", start_lzt)
                                    st.session_state.last_button_click = None
                                    st.rerun()
                            
                            with col_cancel:
                                if st.form_submit_button("Abbrechen"):
                                    st.session_state.last_button_click = None
                                    st.rerun()
                    
                    elif st.session_state.last_button_click == "RFP":
                        with st.form("rfp_eingabe"):
                            st.subheader("RFP-Sitzungen hinzufügen")
                            
                            if current_therapy == "LZT":
                                start_rfp = st.number_input(
                                    "Mit welcher RFP-Sitzung soll gestartet werden?",
                                    min_value=1,
                                    max_value=20,
                                    value=1
                                )
                            else:
                                start_rfp = 1
                                st.warning("RFP (20 Sitzungen) wird hinzugefügt.")
                            
                            col_submit, col_cancel = st.columns(2)
                            
                            with col_submit:
                                if st.form_submit_button("RFP hinzufügen"):
                                    add_sessions_callback("RFP", start_rfp)
                                    st.session_state.last_button_click = None
                                    st.rerun()
                            
                            with col_cancel:
                                if st.form_submit_button("Abbrechen"):
                                    st.session_state.last_button_click = None
                                    st.rerun()
                    
                    elif st.session_state.last_button_click == "Umwandlung":
                        with st.form("umwandlung_eingabe"):
                            st.subheader("KZT in LZT umwandeln")
                            
                            kzt_sitzungen = klient_termine[klient_termine["Sitzungsart"] == "KZT"]
                            
                            if not kzt_sitzungen.empty:
                                start_kzt = int(kzt_sitzungen["Nummer"].min())
                                
                                start_umwandlung = st.number_input(
                                    f"Ab welcher KZT-Sitzung (von {start_kzt} bis 24) soll die Therapie umgewandelt werden?",
                                    min_value=start_kzt,
                                    max_value=24,
                                    value=start_kzt
                                )
                                
                                col_submit, col_cancel = st.columns(2)
                                
                                with col_submit:
                                    if st.form_submit_button("Umwandlung bestätigen"):
                                        convert_kzt_to_lzt_callback(start_umwandlung)
                                        st.session_state.last_button_click = None
                                        st.rerun()
                                
                                with col_cancel:
                                    if st.form_submit_button("Abbrechen"):
                                        st.session_state.last_button_click = None
                                        st.rerun()
                            else:
                                st.error("Keine KZT-Sitzungen gefunden!")
                    
                    # Tabellen anzeigen
                    with cola:
                        st.subheader("Sitzungsübersicht")
                        if not uebersicht.empty:
                            st.dataframe(uebersicht, hide_index=True, use_container_width=True)
                        else:
                            st.info("Keine Therapiesitzungen")
                    
                    with colb:
                        st.subheader("Terminliste")
                        # Nur Therapiesitzungen anzeigen (keine Supervision)
                        therapy_termine = klient_termine[
                            klient_termine['Sitzungsart'] != 'Supervision'
                        ].copy()
                        
                        if not therapy_termine.empty:
                            therapy_termine["Datum_formatiert"] = therapy_termine["Datum"].dt.strftime("%d.%m.%Y")
                            
                            st.dataframe(
                                therapy_termine[["Datum_formatiert", "Sitzungsart", "Nummer"]],
                                hide_index=True,
                                use_container_width=True
                            )
                        else:
                            st.info("Keine Termine")
                else:
                    st.info("Keine Termine für diesen Klienten gefunden.")
        else:
            st.info("Füge zuerst einen Klienten hinzu, um die Übersicht zu sehen.")
    
    # =============================================================================
    # TAB 4: QUARTALSPROGNOSE
    # =============================================================================
    
    with tabs[3]:
        st.header("Quartalsprognose")
        
        with st.expander("Hilfe"):
            st.markdown(HILFE["Quartalsprognose"])
        
        klienten = st.session_state.sitzungen["Klient"].dropna().unique()
        
        if klienten.size > 0:
            with st.form("qp_form"):
                st.subheader("Prognose-Einstellungen")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    praxis_typ = st.radio(
                        "Praxis-Typ",
                        options=["extern", "intern"],
                        format_func=lambda x: "Externe Praxis" if x == "extern" else "IPP (intern)",
                        help="Externe Praxis: EBM Honorar minus 3€"
                    )
                
                with col2:
                    # Quartale extrahieren
                    quartale = sorted(
                        st.session_state.sitzungen["Datum"].dt.to_period('Q').unique()
                    )
                    
                    selected_quartal = st.selectbox(
                        "Quartal auswählen",
                        options=quartale,
                        format_func=lambda x: str(x)
                    )
                
                if st.form_submit_button("Prognose berechnen", type="primary"):
                    st.divider()
                    st.subheader(f"Prognose für {selected_quartal}")
                    
                    # Quartals-Daten filtern
                    quartaljahre = st.session_state.sitzungen["Datum"].dt.to_period('Q')
                    quartals_termine = st.session_state.sitzungen[quartaljahre == selected_quartal]
                    
                    # Supervision ausschließen
                    quartals_termine = quartals_termine[
                        quartals_termine["Sitzungsart"] != "Supervision"
                    ]
                    
                    if not quartals_termine.empty:
                        # Prognose berechnen
                        prognose = quartals_termine["Sitzungsart"].value_counts().reset_index()
                        prognose.columns = ["Sitzungsart", "Anzahl"]
                        
                        # Schätzung (10/12 Formel)
                        prognose["Schätzung (10/12)"] = (prognose["Anzahl"] * 10 / 12).round()
                        
                        # EBM Honorar
                        if praxis_typ == "extern":
                            prognose['EBM Honorar'] = prognose['Sitzungsart'].map(EBM_HONORAR) - 3
                        else:
                            prognose['EBM Honorar'] = prognose['Sitzungsart'].map(EBM_HONORAR)
                        
                        # Entgelt berechnen
                        prognose['Entgelt (€)'] = (
                            prognose["Schätzung (10/12)"] * prognose['EBM Honorar']
                        ).round(2)
                        
                        # Summenzeile
                        summe_anzahl = prognose["Anzahl"].sum()
                        summe_schaetzung = prognose["Schätzung (10/12)"].sum()
                        summe_entgelt = prognose["Entgelt (€)"].sum()
                        
                        # Summenzeile hinzufügen
                        prognose_mit_summe = pd.concat([
                            prognose,
                            pd.DataFrame([{
                                "Sitzungsart": "GESAMT",
                                "Anzahl": summe_anzahl,
                                "Schätzung (10/12)": summe_schaetzung,
                                "EBM Honorar": "",
                                "Entgelt (€)": summe_entgelt
                            }])
                        ], ignore_index=True)
                        
                        # Tabelle anzeigen
                        st.dataframe(
                            prognose_mit_summe,
                            hide_index=True,
                            use_container_width=True
                        )
                        
                        # Kennzahlen
                        col_metric1, col_metric2, col_metric3 = st.columns(3)
                        
                        with col_metric1:
                            st.metric("Geplante Sitzungen", int(summe_anzahl))
                        
                        with col_metric2:
                            st.metric("Geschätzte Sitzungen", int(summe_schaetzung))
                        
                        with col_metric3:
                            st.metric("Geschätztes Entgelt", f"{summe_entgelt:.2f} €")
                    else:
                        st.info("Keine Sitzungen im ausgewählten Quartal gefunden.")
        else:
            st.info("Füge zuerst einen Klienten hinzu, um die Quartalsprognose zu bestimmen.")
    
    # =============================================================================
    # TAB 5: SUPERVISION
    # =============================================================================
    
    with tabs[4]:
        st.header("Supervisionsverwaltung")
        
        with st.expander("Hilfe"):
            st.markdown(HILFE["Supervision"])
        
        sv_choice = st.radio(
            "Aktion wählen",
            options=["Supervisionssitzung hinzufügen", "Supervisions SOLL vs. IST vergleichen"],
            horizontal=True
        )
        
        if sv_choice == "Supervisionssitzung hinzufügen":
            with st.form("sup_add_form"):
                st.subheader("Neue Supervisionssitzung")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    sup_date = st.date_input(
                        "Datum Supervision",
                        value=date.today(),
                        format="DD.MM.YYYY"
                    )
                
                with col2:
                    sup_type = st.radio(
                        "Art der Supervision",
                        options=["E-SV", "G-SV"],
                        format_func=lambda x: "Einzelsupervision" if x == "E-SV" else "Gruppensupervision"
                    )
                
                with col3:
                    sup_stunden = st.number_input(
                        "Anzahl Stunden",
                        min_value=1,
                        max_value=10,
                        value=1,
                        step=1
                    )
                
                if st.form_submit_button("Supervision hinzufügen", type="primary"):
                    # Neue Supervision erstellen
                    sup_sitzung = pd.DataFrame({
                        "Datum": [pd.Timestamp(sup_date)],
                        "Klient": [None],
                        "Sitzungsart": ["Supervision"],
                        "Nummer": [None],
                        "Art Supervision": [sup_type],
                        "Stundenanzahl": [sup_stunden]
                    })
                    
                    st.session_state.sitzungen = pd.concat(
                        [st.session_state.sitzungen, sup_sitzung],
                        ignore_index=True
                    ).sort_values('Datum').reset_index(drop=True)
                    
                    save_data(st.session_state.sitzungen)
                    
                    st.success(
                        f"{sup_stunden}h {sup_type} am {sup_date.strftime('%d.%m.%Y')} "
                        "wurden hinzugefügt. Du kannst diese in der Kalenderübersicht betrachten/bearbeiten."
                    )
                    st.rerun()
        
        elif sv_choice == "Supervisions SOLL vs. IST vergleichen":
            supervisionen = st.session_state.sitzungen[
                st.session_state.sitzungen["Sitzungsart"] == "Supervision"
            ]
            
            if supervisionen.size > 0:
                st.subheader("Supervisionsübersicht (IST vs SOLL)")
                
                with st.form("sup_ov_form"):
                    due_day = st.date_input(
                        "Stichtag auswählen",
                        value=date.today(),
                        format="DD.MM.YYYY",
                        help="Bitte gib den Stichtag ein, zu dem Supervisions SOLL und IST verglichen werden sollen"
                    )
                    
                    if st.form_submit_button("Vergleich berechnen", type="primary"):
                        # Daten bis Stichtag
                        subset = st.session_state.sitzungen[
                            st.session_state.sitzungen["Datum"] <= pd.Timestamp(due_day)
                        ]
                        
                        # Anzahl Therapiesitzungen
                        subset_sitzungen = len(
                            subset[subset["Sitzungsart"] != "Supervision"]
                        )
                        
                        # Supervisionssitzungen
                        subset_sup = subset[subset["Sitzungsart"] == "Supervision"]
                        
                        # Formatierung
                        due_day_de = due_day.strftime("%d. %B %Y")
                        verb = "wurden" if due_day <= date.today() else "werden"
                        
                        st.info(
                            f"Bis zum **{due_day_de}** {verb} **{subset_sitzungen}** "
                            "Sitzungen Psychotherapie absolviert. "
                            "Daraus ergibt sich der folgende Supervisionsbedarf:"
                        )
                        
                        # SOLL-Berechnung
                        vergleich = pd.DataFrame({
                            "SOLL": [
                                round(subset_sitzungen / 4, 1),   # Gesamt-SUP
                                round(subset_sitzungen / 12, 1),  # E-SV
                                round(subset_sitzungen / 6, 1)    # G-SV
                            ],
                            "IST": [
                                subset_sup["Stundenanzahl"].sum(),
                                subset_sup[subset_sup["Art Supervision"] == "E-SV"]["Stundenanzahl"].sum(),
                                subset_sup[subset_sup["Art Supervision"] == "G-SV"]["Stundenanzahl"].sum()
                            ]
                        }, index=["Gesamt-SUP", "E-SV", "G-SV"])
                        
                        # Differenz berechnen
                        vergleich["Differenz"] = vergleich["IST"] - vergleich["SOLL"]
                        
                        # Tabelle anzeigen
                        st.dataframe(vergleich, use_container_width=True)
                        
                        # Farbcodierte Metriken
                        st.divider()
                        
                        col_m1, col_m2, col_m3 = st.columns(3)
                        
                        with col_m1:
                            diff_gesamt = vergleich.loc["Gesamt-SUP", "Differenz"]
                            st.metric(
                                "Gesamt-Differenz",
                                f"{diff_gesamt:+.1f}h",
                                delta=None,
                                delta_color="normal" if diff_gesamt >= 0 else "inverse"
                            )
                        
                        with col_m2:
                            diff_esv = vergleich.loc["E-SV", "Differenz"]
                            st.metric(
                                "E-SV Differenz",
                                f"{diff_esv:+.1f}h",
                                delta=None,
                                delta_color="normal" if diff_esv >= 0 else "inverse"
                            )
                        
                        with col_m3:
                            diff_gsv = vergleich.loc["G-SV", "Differenz"]
                            st.metric(
                                "G-SV Differenz",
                                f"{diff_gsv:+.1f}h",
                                delta=None,
                                delta_color="normal" if diff_gsv >= 0 else "inverse"
                            )
                        
                        # Empfehlungen
                        if any(vergleich["Differenz"] < 0):
                            st.warning("Achtung: Es besteht ein Supervisions-Rückstand!")
                        else:
                            st.success("Alle Supervisions-Anforderungen erfüllt!")
            else:
                st.info("Füge eine erste Supervisionssitzung hinzu, um die Supervisionsübersicht zu öffnen.")


# =============================================================================
# POPUP-WARNUNG BEIM SCHLIESSEN
# =============================================================================

def add_close_warning():
    """Fügt Warnung beim Schließen des Fensters hinzu."""
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


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    main()
    add_close_warning()
