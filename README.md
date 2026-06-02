# Earthquake Co-occurrence — Scalable and Cloud Programming 2025-26

Analisi di co-occorrenza di terremoti su Apache Spark / Google Cloud DataProc.

## Struttura del progetto

```
earthquake-cooccurrence/
├── build.sbt
├── project/
│   ├── build.properties        (sbt 1.9.7)
│   └── plugins.sbt             (sbt-assembly)
└── src/main/scala/
    ├── EarthquakeCooccurrence.scala      # Approccio 1: groupByKey
    └── EarthquakeCooccurrenceJoin.scala  # Approccio 2: self-join
```

## Algoritmo

1. Leggere il CSV e normalizzare `latitude`/`longitude` alla prima cifra decimale (`math.round(x * 10) / 10.0`).
2. Truncare il timestamp alla data (`YYYY-MM-DD`).
3. Deduplicare coppie `(location, date)` identiche prodotte dall'arrotondamento.
4. Per ogni giorno, generare tutte le coppie canoniche di location `(loc_i, loc_j)` con `loc_i < loc_j`.
5. Deduplicare coppie `(pair, date)`.
6. Contare le co-occorrenze per coppia e trovare il massimo.
7. Raccogliere le date ordinate per la coppia vincente.

### Approccio 1 — groupByKey (`EarthquakeCooccurrence`)
Raggruppa le location per data con `groupByKey`, poi genera le coppie in-memory per ogni giorno.
Preferibile quando il numero di location per giorno è limitato.

### Approccio 2 — Self-Join (`EarthquakeCooccurrenceJoin`)
Esegue un self-join distribuito sull'RDD keyed per data. Più scalabile in presenza di molti eventi per giorno.

## Build

Prerequisiti: JDK 8/11, sbt >= 1.9.

```bash
cd earthquake-cooccurrence
sbt assembly
# Produce: target/scala-2.12/earthquake-cooccurrence-assembly-1.0.jar
```

## Esecuzione locale (dataset ridotto)

```bash
spark-submit \
  --class EarthquakeCooccurrence \
  target/scala-2.12/earthquake-cooccurrence-assembly-1.0.jar \
  /path/to/dataset-earthquakes-trimmed.csv
```

Opzionalmente, specificare il numero di partizioni come secondo argomento:

```bash
spark-submit --class EarthquakeCooccurrence ... dataset.csv 8
```

## Esecuzione su DataProc

### 1. Creare il bucket GCS e caricare i file

```bash
gsutil mb gs://<MY_BUCKET>
gsutil cp target/scala-2.12/earthquake-cooccurrence-assembly-1.0.jar gs://<MY_BUCKET>/
gsutil cp dataset-earthquakes-full.csv gs://<MY_BUCKET>/
```

### 2. Creare il cluster

```bash
gcloud dataproc clusters create earthquake-cluster \
  --region=europe-west1 \
  --num-workers 2 \
  --master-boot-disk-size 240 \
  --worker-boot-disk-size 240 \
  --master-machine-type=n2-standard-4 \
  --worker-machine-type=n2-standard-4
```

Ripetere con `--num-workers 3` e `--num-workers 4` per l'analisi di scalabilità.

### 3. Sottomettere il job

```bash
# Approccio 1
gcloud dataproc jobs submit spark \
  --cluster=earthquake-cluster \
  --region=europe-west1 \
  --class=EarthquakeCooccurrence \
  --jars=gs://<MY_BUCKET>/earthquake-cooccurrence-assembly-1.0.jar \
  -- gs://<MY_BUCKET>/dataset-earthquakes-full.csv [numPartitions]

# Approccio 2
gcloud dataproc jobs submit spark \
  --cluster=earthquake-cluster \
  --region=europe-west1 \
  --class=EarthquakeCooccurrenceJoin \
  --jars=gs://<MY_BUCKET>/earthquake-cooccurrence-assembly-1.0.jar \
  -- gs://<MY_BUCKET>/dataset-earthquakes-full.csv [numPartitions]
```

### 4. Eliminare il cluster

```bash
gcloud dataproc clusters delete earthquake-cluster --region europe-west1
```

## Formato output

```
((lat1, lon1), (lat2, lon2))
YYYY-MM-DD
YYYY-MM-DD
...
```

## Analisi di scalabilità

Testare le seguenti configurazioni e registrare i tempi di esecuzione:

| Workers | Partizioni | Approccio     | Tempo (s) |
|---------|------------|---------------|-----------|
| 2       | default    | groupByKey    |           |
| 2       | default    | self-join     |           |
| 3       | default    | groupByKey    |           |
| 3       | default    | self-join     |           |
| 4       | default    | groupByKey    |           |
| 4       | default    | self-join     |           |
| 4       | 16         | groupByKey    |           |
| 4       | 32         | groupByKey    |           |
