# Checklist esperimenti DataProc e consegna

Guida end-to-end: dal setup dell'account GCP alla consegna finale del progetto (scadenza 15 ottobre
2026). Sostituisci `<PROJECT_ID>`, `<BUCKET>` e `<REGION>` una volta sola all'inizio e riusa le stesse
variabili in tutti i comandi.

```bash
export PROJECT_ID=<il-tuo-project-id>
export REGION=europe-west1
export BUCKET=gs://scp-earthquake-<PROJECT_ID>
```

## 0. Prerequisiti (una tantum, se non già fatti)

1. **Installare gcloud CLI** (se non presente sul tuo computer):
   https://cloud.google.com/sdk/docs/install — poi `gcloud init` per autenticarti e scegliere/creare
   un progetto.
2. **Progetto GCP**: se non ne hai già uno collegato ai crediti education, creane uno dalla console
   (https://console.cloud.google.com) o da CLI:
   ```bash
   gcloud projects create $PROJECT_ID --name="SCP Earthquake"
   ```
   Verifica che il progetto abbia il billing account con i crediti education collegato (Console >
   Fatturazione). Senza billing collegato, DataProc non parte.
   > ⚠️ **Pagamento anticipato richiesto da Google**: durante il collegamento del metodo di pagamento, Google puo' chiedere un **pagamento anticipato una tantum (es. 25,00 €)** prima di accreditare i crediti (prova gratuita/education). E' **rimborsabile** se in seguito chiudi l'account di fatturazione Cloud. Non e' un errore: e' normale, basta pagarlo per sbloccare il billing.
3. **Verifica quota `n2-standard-4`**: con crediti education la quota di CPU per regione a volte è
   limitata. Controlla in Console > IAM & Admin > Quote, filtrando per "N2 CPUs" nella regione scelta.
   Con 4 worker + 1 master da 4 vCPU ciascuno servono almeno 20 vCPU N2 disponibili. Se la quota è
   insufficiente, richiedi l'aumento dalla stessa pagina (di solito approvato in pochi minuti per
   progetti education) **prima** di arrivare al cluster a 4 worker, per non perdere tempo a metà test.
4. **sbt** installato in locale per compilare il progetto (`sbt --version` per verificare).

## 1. Setup iniziale del progetto (una tantum)

```bash
gcloud auth login
gcloud config set project $PROJECT_ID
gcloud services enable dataproc.googleapis.com storage.googleapis.com

gsutil mb -l $REGION $BUCKET
```

## 2. Build del JAR (in locale, sul tuo computer)

```bash
cd SCP-earthquake-cooccurrence
sbt assembly
# Output atteso: target/scala-2.12/earthquake-cooccurrence-assembly-1.0.jar
```

## 3. Verifica rapida in locale prima di spendere credit (consigliata)

Con il dataset ridotto, senza cluster, per controllare che l'output abbia senso prima di girare su GCP:

```bash
sbt "runMain EarthquakeCooccurrence dataset-earthquakes-trimmed.csv"
sbt "runMain EarthquakeCooccurrenceJoin dataset-earthquakes-trimmed.csv"
```

I due comandi devono produrre la stessa coppia e le stesse date in output (già verificato che la logica
è corretta su un campione reale del dataset — vedi la conversazione precedente).

## 4. Upload di JAR e dataset su GCS

```bash
gsutil cp target/scala-2.12/earthquake-cooccurrence-assembly-1.0.jar $BUCKET/
gsutil cp dataset-earthquakes-full.csv $BUCKET/
gsutil cp dataset-earthquakes-trimmed.csv $BUCKET/   # utile per un run rapido solo-master
```

## 5. Creazione cluster (uno alla volta, per 2, 3, 4 worker)

Il tipo di macchina `n2-standard-4` va specificato esplicitamente: è l'unico modo per poter creare un
cluster a 4 worker con gli education credit. Crea e cancella un cluster alla volta — non serve tenerli
tutti attivi insieme, e si risparmiano crediti.

```bash
# 2 worker
gcloud dataproc clusters create eq-cluster-2w \
  --region=$REGION --num-workers 2 \
  --master-boot-disk-size 240 --worker-boot-disk-size 240 \
  --master-machine-type=n2-standard-4 --worker-machine-type=n2-standard-4

# 3 worker
gcloud dataproc clusters create eq-cluster-3w \
  --region=$REGION --num-workers 3 \
  --master-boot-disk-size 240 --worker-boot-disk-size 240 \
  --master-machine-type=n2-standard-4 --worker-machine-type=n2-standard-4

# 4 worker
gcloud dataproc clusters create eq-cluster-4w \
  --region=$REGION --num-workers 4 \
  --master-boot-disk-size 240 --worker-boot-disk-size 240 \
  --master-machine-type=n2-standard-4 --worker-machine-type=n2-standard-4
```

Se la creazione fallisce con un errore di quota, torna al punto 0.3 e richiedi l'aumento per la
regione scelta.

## 6. Esecuzione dei job

Per ciascun cluster, lancia entrambi gli approcci con partizionamento di default:

```bash
# groupByKey
gcloud dataproc jobs submit spark \
  --cluster=eq-cluster-2w --region=$REGION \
  --class=EarthquakeCooccurrence \
  --jars=$BUCKET/earthquake-cooccurrence-assembly-1.0.jar \
  -- $BUCKET/dataset-earthquakes-full.csv

# self-join
gcloud dataproc jobs submit spark \
  --cluster=eq-cluster-2w --region=$REGION \
  --class=EarthquakeCooccurrenceJoin \
  --jars=$BUCKET/earthquake-cooccurrence-assembly-1.0.jar \
  -- $BUCKET/dataset-earthquakes-full.csv
```

Ripeti sostituendo `eq-cluster-2w` con `eq-cluster-3w` e `eq-cluster-4w`.

Sul cluster a 4 worker, ripeti anche con partizionamento esplicito per valutare l'effetto del
repartition:

```bash
gcloud dataproc jobs submit spark \
  --cluster=eq-cluster-4w --region=$REGION \
  --class=EarthquakeCooccurrence \
  --jars=$BUCKET/earthquake-cooccurrence-assembly-1.0.jar \
  -- $BUCKET/dataset-earthquakes-full.csv 16

gcloud dataproc jobs submit spark \
  --cluster=eq-cluster-4w --region=$REGION \
  --class=EarthquakeCooccurrence \
  --jars=$BUCKET/earthquake-cooccurrence-assembly-1.0.jar \
  -- $BUCKET/dataset-earthquakes-full.csv 32
```

**Dove trovare il tempo di esecuzione**: nell'output del comando (`Job [...] finished`) c'è il tempo
totale di sottomissione; per il tempo effettivo di esecuzione del job Spark è più preciso usare la
Spark History Server (link disponibile nella console DataProc, sezione cluster > "Web Interfaces") o
`gcloud dataproc jobs describe <JOB_ID> --region=$REGION`.

## 7. Tabella tempi da compilare

Riporta qui i tempi misurati; poi copiali sia nel README sia nel report (Sezione 4).

| Worker | Partizioni | Approccio  | Tempo (s) |
|--------|------------|------------|-----------|
| 2      | default    | groupByKey |           |
| 2      | default    | self-join  |           |
| 3      | default    | groupByKey |           |
| 3      | default    | self-join  |           |
| 4      | default    | groupByKey |           |
| 4      | default    | self-join  |           |
| 4      | 16         | groupByKey |           |
| 4      | 32         | groupByKey |           |

## 8. Eliminazione cluster (subito dopo ogni run, per non sprecare credit)

```bash
gcloud dataproc clusters delete eq-cluster-2w --region=$REGION
gcloud dataproc clusters delete eq-cluster-3w --region=$REGION
gcloud dataproc clusters delete eq-cluster-4w --region=$REGION
```

## 9. Dopo gli esperimenti

- Aggiorna la tabella di scalabilità nel `README.md` con i tempi reali.
- Apri `Report_SCP_Earthquake_Cooccurrence.pdf` (o rigenera da `build_report.py` se preferisci
  modificare via script) e sostituisci i paragrafi placeholder (evidenziati in rosso) nelle sezioni
  2.2, 3, 4 e 5 con la tua analisi reale: andamento della scalabilità, effetto del partizionamento,
  confronto tra i due approcci, conclusioni.
- Verifica che il PDF finale non superi le 5 pagine.
- Fai il commit del fix già presente in `EarthquakeCooccurrenceJoin.scala` (scrivi tu il messaggio di
  commit) e rimuovi i due file `.tmp` residui nel repo.

## 10. Consegna finale

1. Carica il report PDF sul sito "Virtuale" del corso (nel report deve comparire il link al
   repository: https://github.com/Sh0wBlack32/SCP-earthquake-cooccurrence).
2. Verifica che il repository sia pubblico e che il README contenga le istruzioni per eseguire il
   programma su DataProc (già presente).
3. Invia una email di conferma consegna a **nicolo.pizzo2@unibo.it** e
   **gianluigi.zavattaro@unibo.it**.

Scadenza: **15 ottobre 2026**.
