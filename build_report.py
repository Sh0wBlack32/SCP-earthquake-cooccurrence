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
NOTE_2_2 = (
    "[NOTA: qui puoi aggiungere 3-4 righe sulle differenze osservate concretamente tra i "
    "due approcci durante l'esecuzione — ad esempio, se uno dei due ha sofferto più shuffle "
    "spill, se uno dei due non è riuscito a completare su cluster piccoli, ecc. — sulla base "
    "di quanto osservato nella Sezione 4.]"
)

NOTE_SETUP_PARTITIONING = (
    "[NOTA: se hai anche testato diverse configurazioni di partizionamento (es. "
    "repartition(16), repartition(32) sul cluster a 4 worker), descrivile qui con una frase "
    "— quali valori, e perché quei valori.]"
)

NOTE_SECTION4_INTRO = (
    "[COMPLETARE CON I DATI REALI DOPO LE PROVE SU DATAPROC. La tabella sottostante è un "
    "modello: riportare, per ogni combinazione worker/approccio/partizioni, il tempo di "
    "esecuzione misurato (ad es. dai log del job o dalla Spark UI/history server).]"
)

NOTE_4_1 = (
    "[COMPLETARE: commentare l'andamento del tempo di esecuzione al crescere del numero di "
    "worker a parità di dataset (strong scaling). Calcolare lo speedup S(n) = T(1 unità di "
    "riferimento)/T(n) e, se rilevante, l'efficienza E(n) = S(n)/n. Discutere se la "
    "scalabilità è vicina a quella ideale o se si osserva un plateau, e ipotizzare le cause "
    "(overhead di shuffle, skew dei dati, costo di comunicazione di rete tra i nodi, ecc.).]"
)

NOTE_4_2 = (
    "[COMPLETARE: confrontare i tempi con partizionamento di default rispetto a "
    "repartition(16)/repartition(32) sul cluster a 4 worker. Discutere se un numero maggiore "
    "di partizioni ha aiutato il bilanciamento del carico o se ha introdotto overhead di "
    "scheduling eccessivo.]"
)

NOTE_4_3 = (
    "[COMPLETARE: quale approccio (groupByKey o self-join) è risultato più efficiente nelle "
    "prove, e perché, sulla base di quanto discusso in Sezione 2.]"
)

NOTE_CONCLUSIONI = (
    "[COMPLETARE: 3-5 righe di sintesi — cosa ha funzionato, quale approccio si è dimostrato "
    "preferibile nel caso in esame, quali limiti o miglioramenti futuri (es. uso di "
    "DataFrame/Dataset invece di RDD, broadcast join per dataset più piccoli, tuning "
    "aggiuntivo dei parametri Spark).]"
)

# Tabella tempi (Sezione 4). Sostituire "" con il tempo misurato in secondi.
TIMING_ROWS = [
    ("2", "default", "groupByKey", ""),
    ("2", "default", "self-join", ""),
    ("3", "default", "groupByKey", ""),
    ("3", "default", "self-join", ""),
    ("4", "default", "groupByKey", ""),
    ("4", "default", "self-join", ""),
    ("4", "16", "groupByKey", ""),
    ("4", "32", "groupByKey", ""),
]

VERSIONS_ROWS = [
    ("Scala", "2.12.17"),
    ("Apache Spark", "3.3.2"),
    ("sbt", "1.9.7"),
    ("Piattaforma", "Google Cloud DataProc"),
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
        "in locale e sulla configurazione solo-master, e una versione completa, usata per "
        "l'esecuzione e la valutazione delle prestazioni su Google Cloud DataProc.",
        body_style))

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
        "Le prove sono state eseguite su Google Cloud DataProc, con macchine di tipo "
        "<b>n2-standard-4</b> sia per il nodo master sia per i nodi worker (configurazione "
        "obbligatoria per poter creare cluster con 4 worker), boot disk da 240 GB per "
        "contenere l'uso entro i limiti degli education credit, e cluster di 2, 3 e 4 "
        "worker. Il dataset completo e il JAR dell'applicazione sono stati caricati su un "
        "bucket Google Cloud Storage e referenziati tramite URI gs:// nei job Spark.",
        body_style))
    story.append(note_box(NOTE_SETUP_PARTITIONING))

    story.append(Paragraph("<b>Versioni e librerie</b>", body_style))
    story.append(data_table(
        ["Componente", "Versione"], VERSIONS_ROWS, [6 * cm, 10.5 * cm]))
    story.append(Spacer(1, 8))

    # 4. Analisi di scalabilità e prestazioni
    story.append(Paragraph("4. Analisi di scalabilità e prestazioni", h1_style))
    story.append(note_box(NOTE_SECTION4_INTRO))
    story.append(data_table(
        ["Worker", "Partizioni", "Approccio", "Tempo (s)"],
        TIMING_ROWS, [3 * cm, 3.5 * cm, 5 * cm, 5 * cm]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("4.1 Scalabilità (strong scaling)", h2_style))
    story.append(note_box(NOTE_4_1))

    story.append(Paragraph("4.2 Effetto del partizionamento", h2_style))
    story.append(note_box(NOTE_4_2))

    story.append(Paragraph("4.3 Confronto tra i due approcci", h2_style))
    story.append(note_box(NOTE_4_3))

    # 5. Conclusioni
    story.append(Paragraph("5. Conclusioni", h1_style))
    story.append(note_box(NOTE_CONCLUSIONI))

    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"<b>Codice sorgente:</b> {REPO_URL} (istruzioni per l'esecuzione su DataProc nel "
        "README del repository).", footer_style))

    doc.build(story)
    print(f"Report generato: {output_path}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "Report_SCP_Earthquake_Cooccurrence.pdf"
    build(out)
