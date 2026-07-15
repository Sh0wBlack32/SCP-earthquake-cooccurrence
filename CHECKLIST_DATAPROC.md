# Checklist esperimenti DataProc

Sequenza di comandi pronta all'uso per costruire, caricare ed eseguire il progetto su Google Cloud
DataProc, e per raccogliere i tempi da inserire nel report e nella tabella di scalabilità del README.

Sostituisci `<PROJECT_ID>`, `<BUCKET>` e `<REGION>` una volta sola all'inizio.

```bash
export PROJECT_ID=<il-tuo-project-id>
export REGION=europe-west1
export BUCKET=gs://scp-earthquake-<PROJECT_ID>
```

## 0. Setup iniziale (una tantum)

```bash
gcloud auth login
gcloud config set project $PROJECT_ID
gcloud services enable dataproc.googleapis.com storage.googleapis.com

gsutil mb -l $REGION $BUCKET
```

## 1. Build del JAR (in locale, sul tuo computer)

```bash
cd SCP-earthquake-cooccurrence
sbt assembly
# Output atteso: target/scala-2.12/earthquake-cooccurrence-assembly-1.0.jar
```

## 2. Upload di JAR e dataset su GCS

```bash
gsutil cp target/scala-2.12/earthquake-cooccurrence-assembly-1.0.jar $BUCKET/
gsutil cp dataset-earthquakes-full.csv $BUCKET/
gsutil cp dataset-earthquakes-trimmed.csv $BUCKET/   # utile per un run rapido di verifica
```

## 3. Creazione cluster (ripetere per 2, 3, 4 worker)

Il tipo di macchina `n2-standard-4` va specificato esplicitamente: è l'unico modo per poter creare un
cluster a 4 worker con gli education credit.

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

Crea e cancella un cluster alla volta per non consumare credit inutilmente — non serve tenerli tutti
attivi insieme.

## 4. Esecuzione dei job

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

## 5. Tabella tempi da compilare

Riporta qui i tempi misurati; poi copiali sia nel README sia nel report.

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

## 6. Eliminazione cluster (subito dopo ogni run, per non sprecare credit)

```bash
gcloud dataproc clusters delete eq-cluster-2w --region=$REGION
gcloud dataproc clusters delete eq-cluster-3w --region=$REGION
gcloud dataproc clusters delete eq-cluster-4w --region=$REGION
```

## 7. Verifica rapida in locale prima di spendere credit (opzionale ma consigliata)

Con il dataset ridotto, senza cluster, per controllare che l'output abbia senso prima di girare su GCP:

```bash
sbt "runMain EarthquakeCooccurrence dataset-earthquakes-trimmed.csv"
sbt "runMain EarthquakeCooccurrenceJoin dataset-earthquakes-trimmed.csv"
```

I due comandi devono produrre la stessa coppia e le stesse date in output.
