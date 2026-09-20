#!/usr/bin/env python3
"""
Genera Report_SCP_Earthquake_Cooccurrence.pdf a partire dai contenuti sottostanti.

Uso:
    python3 build_report.py [output.pdf]

Per aggiornare il report (es. con i tempi reali misurati su DataProc):
  1. Modifica le costanti/placeholder in questo file (sezione "DATI DA COMPILARE").
  2. Rilancia lo script: rigenera il PDF da zero, max 5 pagine.
"""
import sys

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem,
    Table, TableStyle, KeepTogether,
)

# ─────────────────────────────────────────────────────────────────────────────
# DATI DA COMPILARE
# ─────────────────────────────────────────────────────────────────────────────

STUDENT_NAME = "Alberto Zini"
MATRICOLA = "0001007558"
REPO_URL = "https://github.com/Sh0wBlack32/SCP-earthquake-cooccurrence"

# Note testuali che compaiono nei riquadri rossi "da completare".
# Sostituire il testo con l'analisi reale quando i dati sono disponibili;
# per rimuovere del tutto un riquadro, impostare il valore a None.
NOTE_2_2 = None  # osservazione integrata nel testo della sezione 2.2 e in 4.3

NOTE_SETUP_PARTITIONING = (
    "Le varianti con repartition(16)/repartition(32) sul cluster a 4 worker, previste nel piano "
    "sperimentale, non sono state eseguite per limiti di tempo e di quota (vedi nota sotto la "
    "tabella dei tempi): la quota globale del progetto education si è rivelata sufficiente solo "
    "per un numero limitato di run cloud completi, e si è scelto di privilegiare la copertura dei "
    "tre punti di scalabilità sul numero di worker rispetto alle varianti di partizionamento."
)

NOTE_SECTION4_INTRO = (
    "Durante gli esperimenti è emerso un vincolo non documentato in anticipo: il progetto GCP "
    "education-tier impone una quota <b>globale</b> (non solo per regione) di 12 vCPU per "
    "l'intero progetto (metrica <font face=\"Courier\">compute.googleapis.com/cpus_all_regions</font>, "
    "verificabile con <font face=\"Courier\">gcloud compute project-info describe</font>). Con "
    "n2-standard-4, un cluster a 2 worker (1 master + 2 worker × 4 vCPU) usa già l'intera quota "
    "disponibile: non è possibile creare cluster a 3 o 4 worker con lo stesso tipo di macchina "
    "senza un aumento di quota, che si è rivelato non ottenibile automaticamente su un progetto "
    "così recente (motivo restituito dall'API: <i>NOT_ENOUGH_USAGE_HISTORY</i>). Si è quindi "
    "proceduto usando n2-standard-2 (2 vCPU / 8 GB) per i cluster a 3 e 4 worker, che introduce "
    "una variabile di confondimento esplicita — i tre punti della curva non condividono lo stesso "
    "hardware per nodo — dichiarata qui per trasparenza metodologica."
)

NOTE_4_1 = (
    "Il risultato più significativo non è la velocità assoluta, ma la sua direzione: passando da "
    "3 a 4 worker il tempo di esecuzione <b>aumenta</b> (da 160.8 a 197.2 minuti) invece di "
    "diminuire, nonostante il cluster a 4 worker abbia più nodi. Questo è coerente con la natura "
    "del dataset: la coppia vincente co-occorre nell'81.8% dei giorni in un intervallo di 33.6 "
    "anni (10032 su 12259 giorni), quindi la data-chiave a cui è associata gran parte del lavoro "
    "di generazione/deduplica delle coppie è fortemente skewata. Sia <font face=\"Courier\">"
    "groupByKey</font> sia <font face=\"Courier\">.join()</font> di Spark RDD ripartizionano per "
    "chiave: tutti i valori di una singola chiave finiscono in un numero di task che non cresce "
    "aggiungendo worker (a differenza delle DataFrame Spark SQL, dove l'Adaptive Query Execution "
    "gestisce lo skew-join automaticamente ridistribuendo la chiave calda su più task). Aggiungere "
    "nodi, in questo scenario, aumenta solo l'overhead di coordinamento e di shuffle di rete tra "
    "più macchine, senza alcun guadagno di parallelismo reale sulla parte di lavoro che conta di "
    "più — da qui il rallentamento anziché lo speedup atteso da un naive strong scaling. Il "
    "confronto è inoltre confondato dal cambio di macchina (n2-standard-4 → n2-standard-2, vedi "
    "sopra): non si può quindi escludere che una parte del rallentamento 2→3 worker derivi anche "
    "dalla minore memoria per nodo (16 GB → 8 GB, con conseguente maggiore spill su disco), ma il "
    "peggioramento 3→4 worker — stessa macchina, più nodi — isola in modo pulito l'effetto dello "
    "skew dall'effetto della memoria."
)

NOTE_4_2 = (
    "Non essendo state eseguite le varianti di repartition (vedi nota in Sezione 3), non è "
    "possibile riportare un confronto quantitativo. Sulla base dell'analisi teorica in Sezione "
    "4.1, ci si aspetterebbe che un maggior numero di partizioni non aiuti in modo sostanziale "
    "in questo caso: il problema non è un numero insufficiente di partizioni in generale, ma la "
    "concentrazione del carico su una singola chiave logica indipendentemente da quante "
    "partizioni totali esistono — un maggior repartition() ridistribuirebbe meglio le chiavi "
    "poco attive, ma non la chiave dominante, che resta comunque processata da un numero "
    "limitato di task."
)

NOTE_4_3 = (
    "A parità di worker (2, unico punto testato per entrambi con la stessa macchina), il "
    "self-join è risultato leggermente più lento del groupByKey (77.0 contro 74.2 minuti, +3.8%). "
    "Questo è coerente con quanto anticipato in Sezione 2.2: il self-join produce un prodotto "
    "cartesiano di tutte le località osservate nello stesso giorno prima di filtrare le coppie "
    "valide, generando quindi più lavoro intermedio del groupByKey (che invece genera le coppie "
    "già filtrate direttamente in memoria per ogni giorno). La differenza è comunque modesta a "
    "2 worker; non è stato possibile verificare se si amplifichi a 3/4 worker per gli stessi "
    "limiti di tempo/quota descritti sopra. La correttezza del self-join è comunque stata "
    "verificata in ogni condizione testata (campione ridotto e cluster a 2 worker): risultato "
    "identico al groupByKey in tutti i casi."
)

NOTE_CONCLUSIONI = (
    "L'implementazione (in entrambe le varianti) individua correttamente la coppia di location "
    "arrotondate ((38.8, -122.8), (38.8, -122.7)) — un'area compatibile con il campo geotermico "
    "di The Geysers, in California del Nord — come la coppia con il maggior numero di "
    "co-occorrenze giornaliere (10032, dal 1990-01-05 al 2023-07-29). Il groupByKey si è "
    "dimostrato leggermente preferibile al self-join nell'unico confronto diretto disponibile "
    "(2 worker), coerentemente con il minor lavoro intermedio prodotto. Il risultato "
    "sperimentale più rilevante è tuttavia negativo rispetto alle aspettative di scalabilità "
    "naive: con una chiave fortemente skewata, aggiungere worker non solo non velocizza "
    "l'elaborazione oltre un certo punto, ma può peggiorarla per il maggiore overhead di rete, "
    "poiché né groupByKey né self-join su RDD offrono un meccanismo di redistribuzione delle "
    "chiavi calde. Un miglioramento naturale, lasciato come lavoro futuro, sarebbe la "
    "riformulazione del problema con DataFrame/Dataset Spark SQL per beneficiare dell'Adaptive "
    "Query Execution (skew join automatico), oppure l'applicazione manuale di una tecnica di "
    "key salting sulla chiave data per distribuire esplicitamente il lavoro della chiave calda "
    "su più task anche in RDD puro."
)

# Tabella tempi (Sezione 4) — tempi reali misurati su Google Cloud DataProc (14/09/2026).
TIMING_ROWS = [
    ("2 (n2-std-4)", "default", "groupByKey", "4451.7 (74.2 min)"),
    ("2 (n2-std-4)", "default", "self-join", "4619.0 (77.0 min)"),
    ("3 (n2-std-2)*", "default", "groupByKey", "9647.2 (160.8 min)"),
    ("4 (n2-std-2)*", "default", "groupByKey", "11830.1 (197.2 min)"),
]

VERSIONS_ROWS = [
    ("Scala", "2.12.17"),
    ("Apache Spark", "3.3.2"),
    ("sbt", "1.9.7"),
    ("Piattaforma", "Google Cloud DataProc (europe-west1)"),
]

# ─────────────────────────────────────────────────────────────────────────────
# STILI
# ─────────────────────────────────────────────────────────────────────────────

styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    "TitleCustom", parent=styles["Title"], fontSize=18, leading=22, spaceAfter=4,
)
subtitle_style = ParagraphStyle(
    "SubtitleCustom", parent=styles["Normal"], fontSize=10, leading=13,
    alignment=TA_CENTER, textColor=colors.HexColor("#444444"),
)
h1_style = ParagraphStyle(
    "H1Custom", parent=styles["Heading1"], fontSize=13, spaceBefore=10, spaceAfter=6,
)
h2_style = ParagraphStyle(
    "H2Custom", parent=styles["Heading2"], fontSize=11, spaceBefore=8, spaceAfter=4,
)
body_style = ParagraphStyle(
    "BodyCustom", parent=styles["Normal"], fontSize=9.5, leading=13.5, spaceAfter=6,
    alignment=4,  # justify
)
bullet_style = ParagraphStyle(
    "BulletCustom", parent=body_style, spaceAfter=2,
)
note_style = ParagraphStyle(
    "NoteCustom", parent=body_style, textColor=colors.HexColor("#8a1f1f"), spaceAfter=0,
)
footer_style = ParagraphStyle(
    "FooterCustom", parent=body_style, fontSize=9, textColor=colors.HexColor("#444444"),
)

NOTE_BG = colors.HexColor("#fdecec")
NOTE_BORDER = colors.HexColor("#e2b6b6")


def note_box(text):
    """Riquadro rosso 'da completare' — stile identico alle note del report originale."""
    if not text:
        return Spacer(1, 0)
    p = Paragraph(text, note_style)
    t = Table([[p]], colWidths=[16.5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NOTE_BG),
        ("BOX", (0, 0), (-1, -1), 0.75, NOTE_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return KeepTogether([t, Spacer(1, 8)])


def data_table(header, rows, col_widths):
    data = [header] + [list(r) for r in rows]
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b2b2b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bbbbbb")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def bullets(items):
    return ListFlowable(
        [ListItem(Paragraph(i, bullet_style), leftIndent=6) for i in items],
        bulletType="bullet", start="•", leftIndent=14,
    )


# ─────────────────────────────────────────────────────────────────────────────
# COSTRUZIONE DOCUMENTO
# ─────────────────────────────────────────────────────────────────────────────

def build(output_path):
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=1.6 * cm, bottomMargin=1.6 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
    )
    story = []

    story.append(Paragraph(
        "Analisi di Co-occorrenza di Terremoti con Scala e Apache Spark", title_style))
    story.append(Paragraph(
        "Progetto — Scalable and Cloud Programming, A.A. 2025-26", subtitle_style))
    story.append(Paragraph(f"{STUDENT_NAME} — {MATRICOLA}", subtitle_style))
    story.append(Paragraph(f"Repository: {REPO_URL}", subtitle_style))
    story.append(Spacer(1, 10))

    # 1. Descrizione del problema
    story.append(Paragraph("1. Descrizione del problema", h1_style))
    story.append(Paragraph(
        "L'obiettivo del progetto è realizzare, in Scala e Apache Spark, un'analisi di "
        "co-occorrenza di eventi sismici in località diverse. Data una serie storica di "
        "terremoti, ciascuno caratterizzato da latitudine, longitudine e istante temporale, "
        "si vuole individuare la coppia di località che co-occorrono più spesso, ovvero la "
        "coppia di aree in cui si registrano eventi sismici nella stessa finestra temporale "
        "(un giorno) nel maggior numero di giorni distinti. Il risultato richiesto è la "
        "coppia vincente e l'elenco, in ordine crescente, delle date in cui i due eventi "
        "co-occorrono.", body_style))
    story.append(Paragraph(
        "Poiché la posizione esatta di un evento non è rilevante quanto l'area in cui esso "
        "si verifica, latitudine e longitudine vengono arrotondate alla prima cifra decimale "
        "(arrotondamento al valore più vicino). Questo introduce duplicati — più eventi "
        "nello stesso giorno che ricadono nella stessa “cella” geografica "
        "arrotondata — che devono essere deduplicati prima di generare le coppie, altrimenti "
        "si rischia di individuare come vincente una coppia di eventi nella stessa cella "
        "geografica.", body_style))

    story.append(Paragraph("1.1 Dataset", h2_style))
    story.append(Paragraph(
        "Il dataset è composto da record (latitude, longitude, date) in formato CSV con "
        "intestazione. Sono disponibili due versioni: una versione ridotta, usata per i test "
        "in locale e sulla configurazione solo-master, e una versione completa (1.47M record), "
        "usata per l'esecuzione e la valutazione delle prestazioni su Google Cloud DataProc.",
        body_style))

    story.append(Paragraph("1.2 Risultato", h2_style))
    story.append(Paragraph(
        "Sul dataset completo, entrambi gli approcci individuano la stessa coppia vincente — "
        "<b>((38.8, -122.8), (38.8, -122.7))</b> — con <b>10032 date di co-occorrenza</b>, dal "
        "1990-01-05 al 2023-07-29 (33.6 anni). Le coordinate ricadono nell'area di The Geysers, "
        "in California del Nord, il più grande campo geotermico al mondo, dove l'estrazione "
        "geotermica induce una sismicità indotta pressoché quotidiana da decenni: la coppia "
        "co-occorre nell'81.8% dei giorni dell'intero intervallo, un risultato coerente col "
        "dominio applicativo e non un artefatto dei dati o dell'algoritmo.", body_style))

    # 2. Approccio implementativo
    story.append(Paragraph("2. Approccio implementativo", h1_style))
    story.append(Paragraph(
        "L'elaborazione segue lo schema map-reduce ed è interamente distribuita tramite RDD "
        "di Spark. La pipeline comune ai due approcci è la seguente:", body_style))
    story.append(bullets([
        "lettura del CSV e arrotondamento di lat/lon alla prima cifra decimale;",
        "troncamento del timestamp alla data (YYYY-MM-DD);",
        "deduplica delle coppie (località, data) generate dall'arrotondamento;",
        "generazione, per ogni giorno, di tutte le coppie canoniche di località "
        "(loc_i, loc_j) con loc_i &lt; loc_j;",
        "deduplica delle coppie (coppia, data);",
        "conteggio delle co-occorrenze per coppia e individuazione del massimo;",
        "raccolta e ordinamento delle date per la coppia vincente.",
    ]))
    story.append(Spacer(1, 4))

    story.append(Paragraph("2.1 Approccio 1 — groupByKey", h2_style))
    story.append(Paragraph(
        "Le località vengono raggruppate per data con <b>groupByKey</b>; per ogni giorno, le "
        "coppie candidate vengono generate localmente (in memoria, sul singolo executor) a "
        "partire dalla lista di località distinte osservate quel giorno. È l'approccio più "
        "efficiente quando il numero di eventi per giorno è contenuto, poiché evita uno "
        "shuffle aggiuntivo per generare le coppie.", body_style))

    story.append(Paragraph("2.2 Approccio 2 — Self-Join", h2_style))
    story.append(Paragraph(
        "In alternativa, le coppie vengono generate tramite un self-join distribuito "
        "dell'RDD chiave-valore (data, località) con se stesso, filtrando poi le coppie con "
        "loc1 &lt; loc2 per eliminare simmetrie e auto-coppie. Questo approccio distribuisce "
        "il lavoro di generazione delle coppie su tutto il cluster invece di concentrarlo sul "
        "singolo executor che gestisce un dato giorno, a costo di uno shuffle più oneroso; "
        "può risultare preferibile quando i giorni con molti eventi (skew) rendono costoso il "
        "groupByKey.", body_style))
    story.append(note_box(NOTE_2_2))

    # 3. Setup sperimentale
    story.append(Paragraph("3. Setup sperimentale", h1_style))
    story.append(Paragraph(
        "Le prove sono state eseguite su Google Cloud DataProc (regione europe-west1), con "
        "cluster di 2, 3 e 4 worker, boot disk da 240 GB, memoria executor/driver aumentata "
        "esplicitamente rispetto ai default di DataProc (necessario per contenere lo shuffle "
        "spill sulla chiave skewata — vedi Sezione 4). Il cluster a 2 worker usa macchine "
        "<b>n2-standard-4</b> (4 vCPU/16 GB); per i cluster a 3 e 4 worker è stato necessario "
        "passare a <b>n2-standard-2</b> (2 vCPU/8 GB) a causa di un vincolo di quota GCP scoperto "
        "durante gli esperimenti stessi, descritto in dettaglio in Sezione 4. Il dataset completo "
        "e il JAR dell'applicazione sono stati caricati su un bucket Google Cloud Storage e "
        "referenziati tramite URI gs:// nei job Spark.",
        body_style))
    story.append(Paragraph(NOTE_SETUP_PARTITIONING, body_style))

    story.append(Paragraph("<b>Versioni e librerie</b>", body_style))
    story.append(data_table(
        ["Componente", "Versione"], VERSIONS_ROWS, [6 * cm, 10.5 * cm]))
    story.append(Spacer(1, 8))

    # 4. Analisi di scalabilità e prestazioni
    story.append(Paragraph("4. Analisi di scalabilità e prestazioni", h1_style))
    story.append(Paragraph(NOTE_SECTION4_INTRO, body_style))
    story.append(data_table(
        ["Worker (macchina)", "Partizioni", "Approccio", "Tempo (s)"],
        TIMING_ROWS, [4 * cm, 3 * cm, 4.5 * cm, 5 * cm]))
    story.append(Paragraph(
        "* macchina più piccola (n2-standard-2) per il vincolo di quota descritto sopra, non per "
        "scelta progettuale.", footer_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph("4.1 Scalabilità (strong scaling)", h2_style))
    story.append(Paragraph(NOTE_4_1, body_style))

    story.append(Paragraph("4.2 Effetto del partizionamento", h2_style))
    story.append(Paragraph(NOTE_4_2, body_style))

    story.append(Paragraph("4.3 Confronto tra i due approcci", h2_style))
    story.append(Paragraph(NOTE_4_3, body_style))

    # 5. Conclusioni
    story.append(Paragraph("5. Conclusioni", h1_style))
    story.append(Paragraph(NOTE_CONCLUSIONI, body_style))

    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"<b>Codice sorgente:</b> {REPO_URL} (istruzioni per l'esecuzione su DataProc nel "
        "README del repository).", footer_style))

    doc.build(story)
    print(f"Report generato: {output_path}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "Report_SCP_Earthquake_Cooccurrence.pdf"
    build(out)
