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

## Risultato

Su `dataset-earthquakes-full.csv` (1.47M eventi), entrambi gli approcci (verificati indipendentemente,
sia in locale che su più cluster DataProc reali) producono lo stesso risultato:

```
((38.8, -122.8), (38.8, -122.7))
```

con **10032 date di co-occorrenza**, dal **1990-01-05** al **2023-07-29** (33,6 anni). Le coordinate
ricadono nell'area di **The Geysers** (California del Nord), il più grande campo geotermico al
mondo, dove l'estrazione geotermica induce sismicità quasi quotidiana da decenni — un risultato
plausibile e coerente con il dominio, non un artefatto dei dati.

## Analisi di scalabilità

Tempi reali misurati su Google Cloud DataProc (progetto education `scp-earthquake-2026`, regione
`europe-west1`), dataset completo, memoria executor/driver esplicitamente aumentata rispetto ai
default DataProc (necessario per evitare spill eccessivi — vedi `CHECKLIST_DATAPROC.md` §3.1):

| Worker | Macchina        | Partizioni | Approccio  | Tempo        |
|--------|-----------------|------------|------------|--------------|
| 2      | n2-standard-4   | default    | groupByKey | 4451.7 s (74.2 min) |
| 2      | n2-standard-4   | default    | self-join  | 4619.0 s (77.0 min) |
| 3      | n2-standard-2 * | default    | groupByKey | 9647.2 s (160.8 min) |
| 4      | n2-standard-2 * | default    | groupByKey | 11830.1 s (197.2 min) |

\* Il progetto GCP education-tier ha rivelato durante gli esperimenti una quota **globale**
`CPUS_ALL_REGIONS = 12 vCPU per l'intero progetto` (non solo per-regione), che con n2-standard-4
è già saturata da un cluster a 2 worker (1 master + 2 worker × 4 vCPU = 12 vCPU). Non essendo
possibile un aumento automatico di quota su un progetto così recente (`NOT_ENOUGH_USAGE_HISTORY`),
i cluster a 3 e 4 worker usano macchine più piccole (n2-standard-2, 2 vCPU/8GB), con proprietà Spark
`spark.executor.memory=5g,spark.executor.cores=2` invece di `9g,4`. Questo introduce una variabile
confondente esplicita: il confronto 2→3→4 worker non è a parità di hardware per nodo.

**Osservazione principale**: nonostante questo, il dato più interessante è che **4 worker è più
lento di 3 worker** (197 min vs 161 min) pur avendo più nodi. Questo conferma sperimentalmente il
limite teorico discusso in Sezione 4.3: con una singola coppia di location attiva per l'81.8% dei
giorni in 33 anni, sia `groupByKey` che `.join()` di Spark RDD concentrano tutto il lavoro di quella
chiave in un numero di task che NON cresce aggiungendo worker (a differenza delle DataFrame Spark
SQL con Adaptive Query Execution, che gestiscono lo skew-join automaticamente). Aggiungere nodi in
questo scenario aumenta solo l'overhead di coordinamento/rete dello shuffle, senza guadagno di
parallelismo reale sulla partizione skewata — da qui il rallentamento anziché lo speedup atteso.

Self-join a 3/4 worker e le varianti con `repartition(16)`/`repartition(32)` a 4 worker non sono
state eseguite per limiti di tempo/quota: la correttezza del self-join è comunque verificata (stesso
risultato di groupByKey) sia su campione ridotto che sul cluster a 2 worker.
