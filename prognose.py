import streamlit as st

# --- Hilfsfunktionen ---

# Sitzungsfolge pro Patient
SITZUNGEN = {
    "Sprechstunde": 3,
    "Probatorik": 4,
    "Anamnese": 1,
    "KZT1": 12,
    "KZT2": 12,
    "LZT": 46,  # optional, kann leer bleiben
    "RFP": 20  # optional
}

def berechne_sitzungen(start_sitzung, start_sitzung_nummer, start_woche, umwandlung=False, rueckfallprophylaxe=False):
    """
    Berechnet die theoretisch möglichen Sitzungen im Quartal ab Startwoche und Startsitzung.
    Annahme: 1 Sitzung/Woche. Max Quartal: 12 Wochen.
    start_sitzung_nummer: Bei welcher Sitzungsnummer innerhalb des Typs beginnt der Patient (z.B. Sprechstunde 2 von 3)
    umwandlung: Wenn True und Patient in KZT, wird LZT hinzugefügt (KZT1+KZT2+LZT=60)
    rueckfallprophylaxe: Wenn True und Patient in LZT, wird LZT auf 80 erhöht
    """
    verbleibende_wochen = 13 - start_woche  # inkl. Startwoche
    
    # Angepasste Sitzungszahlen basierend auf Therapiephase
    sitzungen_config = SITZUNGEN.copy()
    
    # KZT Phase: Wenn keine Umwandlung geplant, nur bis KZT2
    if start_sitzung in ["KZT1", "KZT2"]:
        if not umwandlung:
            # Keine LZT Sitzungen
            sitzungen_config["LZT"] = 0
            sitzungen_config["RFP"] = 0
        else:
            # Umwandlung geplant: KZT1(12) + KZT2(12) + LZT(36) = 60
            sitzungen_config["LZT"] = 36
            sitzungen_config["RFP"] = 0
    
    # LZT Phase: LZT = 60, oder 80 mit Rückfallprophylaxe
    # LZT und RFP werden als eine Phase behandelt
    if start_sitzung in ["LZT", "RFP"]:
        total_lzt = 80 if rueckfallprophylaxe else 60
        
        # Wenn Patient in LZT startet, alle Sitzungen in LZT
        if start_sitzung == "LZT":
            sitzungen_config["LZT"] = total_lzt
            sitzungen_config["RFP"] = 0
        # Wenn Patient in RFP startet, verbleibende Sitzungen in RFP
        else:  # RFP
            # LZT ist bereits abgeschlossen, alle verbleibenden Sitzungen in RFP
            sitzungen_config["LZT"] = 0
            sitzungen_config["RFP"] = total_lzt
    
    # Sitzungen ab der gewählten Startsitzung
    ergebnisse = {key: 0 for key in SITZUNGEN.keys()}
    
    session_started = False
    for sitzung, anzahl in sitzungen_config.items():
        if sitzung == start_sitzung:
            session_started = True
            # Verbleibende Sitzungen in diesem Typ = Gesamtanzahl - (Startnummer - 1)
            verbleibende_in_typ = anzahl - (start_sitzung_nummer - 1)
            ergebnisse[sitzung] = min(verbleibende_wochen, verbleibende_in_typ)
            verbleibende_wochen -= ergebnisse[sitzung]
        elif session_started and verbleibende_wochen > 0:
            ergebnisse[sitzung] = min(verbleibende_wochen, anzahl)
            verbleibende_wochen -= ergebnisse[sitzung]
    
    return ergebnisse

# --- Streamlit UI ---

st.title("Patienten-Prognose Quartal")

# Session State für mehrere Patienten
if 'patients' not in st.session_state:
    st.session_state.patients = []

hinzufuegen = st.radio("Willst du einen neuen Patienten hinzufügen?", ["Ja", "Nein"])

if hinzufuegen == "Ja":
    name = st.text_input("Name des Patienten", key="name")
    start_woche = st.number_input("Startwoche im Quartal (1-12)", 1, 12, 1, key="startwoche")
    erste_sitzung = st.selectbox("Erste Sitzung im Quartal", list(SITZUNGEN.keys()), key="erste_sitzung")
    
    # Dynamische Sitzungsnummer basierend auf gewähltem Typ
    max_sitzung_nummer = SITZUNGEN[erste_sitzung]
    sitzung_nummer = st.number_input(
        f"Sitzungsnummer in {erste_sitzung} (1-{max_sitzung_nummer})", 
        1, 
        max_sitzung_nummer, 
        1, 
        key="sitzung_nummer"
    )
    
    # Konditionelle Fragen basierend auf Therapiephase
    umwandlung = False
    rueckfallprophylaxe = False
    
    if erste_sitzung in ["KZT1", "KZT2"]:
        st.write("---")
        umwandlung_antwort = st.radio(
            "Ist in diesem Quartal eine Umwandlung geplant?", 
            ["Nein", "Ja"], 
            key="umwandlung"
        )
        umwandlung = (umwandlung_antwort == "Ja")
        if not umwandlung:
            st.info("Therapie umfasst nur: Sprechstunde, Probatorik, Anamnese, KZT1, KZT2 (max. 32 Sitzungen)")
        else:
            st.info("Umwandlung zu LZT geplant: KZT1 + KZT2 + LZT = 60 Sitzungen (LZT: 36)")
    
    if erste_sitzung in ["LZT", "RFP"]:
        st.write("---")
        rueckfall_antwort = st.radio(
            "Ist eine Rückfallprophylaxe geplant?", 
            ["Nein", "Ja"], 
            key="rueckfallprophylaxe"
        )
        rueckfallprophylaxe = (rueckfall_antwort == "Ja")
        if not rueckfallprophylaxe:
            st.info("LZT: 60 Sitzungen")
        else:
            st.info("LZT mit Rückfallprophylaxe: 80 Sitzungen")
    
    if st.button("Patient hinzufügen"):
        ergebnisse = berechne_sitzungen(erste_sitzung, sitzung_nummer, start_woche, umwandlung, rueckfallprophylaxe)
        patient_data = {
            "Name": name,
            "Startwoche": start_woche,
            "Erste Sitzung": f"{erste_sitzung} {sitzung_nummer}",
            **ergebnisse
        }
        
        # Zusätzliche Info-Felder
        if erste_sitzung in ["KZT1", "KZT2"]:
            patient_data["Umwandlung"] = "Ja" if umwandlung else "Nein"
        if erste_sitzung in ["LZT", "RFP"]:
            patient_data["Rückfallprophylaxe"] = "Ja" if rueckfallprophylaxe else "Nein"
        
        st.session_state.patients.append(patient_data)
        st.success(f"Patient {name} hinzugefügt!")

# Zeige Übersicht aller Patienten
if st.session_state.patients:
    st.subheader("Patientenübersicht")
    st.write(st.session_state.patients)

    # Summen berechnen und mit 10/12 multiplizieren
    summen = {key: 0 for key in SITZUNGEN.keys()}
    for p in st.session_state.patients:
        for key in SITZUNGEN.keys():
            summen[key] += p[key]
    
    faktorisierte_summen = {k: round(v*10/12, 1) for k,v in summen.items()}
    
    st.subheader("Summen über alle Patienten (10/12 Faktor)")
    st.write(faktorisierte_summen)
