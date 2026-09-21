# Checklist esperimenti DataProc e consegna

Guida end-to-end: dal setup dell'account GCP alla consegna finale del progetto (scadenza 15 ottobre
2026). Sostituisci `<PROJECT_ID>`, `<BUCKET>` e `<REGION>` una volta sola all'inizio e riusa le stesse
variabili in tutti i comandi.

```bash
export PROJECT_ID=scp-earthquake-2026
export REGION=europe-west1
export BUCKET=gs://scp-earthquake-2026-data
```
> Valori già definitivi per questo progetto (vedi log sotto) — non serve più sostituirli.

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
   >
   > **Verificato in console (13/09/2026)**: finche' questo pagamento non risulta accreditato, l'account
   > di fatturazione resta in stato **"Account di prova gratuito"** e Google blocca silenziosamente
   > l'abilitazione delle API a pagamento (es. Compute Engine API) — il pulsante "Abilita" non da' errore
   > ma non abilita nulla. Di conseguenza la quota "N2 CPUs" non compare nemmeno nella pagina Quote finche'
   > Compute Engine API non e' abilitata. **Il pagamento va fatto dall'utente** (i dati di pagamento non possono essere
   > inseriti automaticamente per policy): vai su Fatturazione > "Esegui un pagamento" nella console, completalo,
   > poi attendi fino a 24 ore che venga accreditato prima di riprovare ad abilitare Compute Engine API.
   >
   > **Aggiornamento (13/09/2026)**: pagamento accreditato, ma l'account restava comunque in stato
   > "prova gratuita" (Compute Engine API non si abilitava, nessun errore visibile). Risolto cliccando
   > **"Attiva" nel banner in alto** ("Attiva l'account completo per ottenere l'accesso illimitato a
   > tutti i servizi Google Cloud") in Fatturazione — da li' in poi Compute Engine API, Cloud Dataproc
   > API e Cloud Storage API si sono abilitate correttamente (verificato: 22 → API abilitate ok).
   > **Progetto usato**: `scp-earthquake-2026`.
3. **Verifica quota `n2-standard-4`**: con crediti education la quota di CPU per regione a volte è
   limitata. Controlla in Console > IAM & Admin > Quote, filtrando per "N2 CPUs" nella regione scelta.
   Con 4 worker + 1 master da 4 vCPU ciascuno servono almeno 20 vCPU N2 disponibili. Se la quota è
   insufficiente, richiedi l'aumento dalla stessa pagina (di solito approvato in pochi minuti per
   progetti education) **prima** di arrivare al cluster a 4 worker, per non perdere tempo a metà test.
   > **Verificato (13/09/2026)**: quota N2 CPUs in `europe-west1` = **32** (dopo aver abilitato Compute
   > Engine API). Sufficiente per 4 worker + 1 master (servono 20). Nessun aumento richiesto.
4. **sbt** installato in locale per compilare il progetto (`sbt --version` per verificare).
   > **Nota (13/09/2026)**: sbt 1.9.7 e gcloud CLI 583.0.0 installati temporaneamente in un ambiente di lavoro cloud
   > separato (non sul PC Windows), in attesa di risolvere un problema di collegamento diretto al PC
   > legato a un aggiornamento Windows del 8/9/2026
   > — i comandi gcloud/sbt verranno rieseguiti automaticamente non appena torna disponibile.

## 1. Setup iniziale del progetto (una tantum)

```bash
gcloud auth login
gcloud config set project $PROJECT_ID
gcloud services enable dataproc.googleapis.com storage.googleapis.com

gsutil mb -l $REGION $BUCKET
```

> **Stato (13/09/2026)**: Compute Engine API, Cloud Dataproc API e Cloud Storage API già abilitate
> tramite console. Bucket **`scp-earthquake-2026-data`** già creato via console (regione europe-west1,
> accesso privato/non pubblico) — equivalente a `gsutil mb`. Restano da fare `gcloud auth login` e
> `gcloud config set project` quando il terminale (device_bash) tornerà disponibile, oppure eseguili tu
> stesso in un terminale sul tuo PC se vuoi procedere subito (basta avere gcloud CLI installato:
> https://cloud.google.com/sdk/docs/install).

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

### 3.1 Diagnosi rallentamento — test locale sul dataset completo (13/09/2026)

Il primo job su cluster DataProc a 2 worker restava bloccato a `progress: 0.1` per ore mentre
`vcoreSeconds`/`memoryMbSeconds` continuavano a salire → non era bloccato, ma molto lento. Per capire
se il problema fosse (a) risorse insufficienti o (b) skew algoritmico intrinseco, il cluster è stato
eliminato (per non sprecare crediti) e `EarthquakeCooccurrence` (groupByKey) è stato rieseguito **in
locale sul dataset completo** (`dataset-earthquakes-full.csv`, 1.47M righe / 174.6 MB) sul PC (Ryzen 7
7800X3D, 64 GB RAM), con heap JVM molto più grande del default:

```
set SBT_OPTS=-Xmx24G
sbt "runMain EarthquakeCooccurrence dataset-earthquakes-full.csv" > output_full_groupbykey.txt 2>&1
```

**Nota Windows**: `sbt.bat` non supporta il flag `-J` per passare opzioni alla JVM (a differenza dello
script sbt Unix) — va usata la variabile d'ambiente `SBT_OPTS` impostata nella stessa sessione di
terminale prima di lanciare sbt.

**Risultato — run completato con successo 2 volte**:
- 1° run: `Total time: 1634 s (27:14)`
- 2° run (output su file): `Total time: 1497 s (24:57)`, di cui la sola `collect()` finale
  (`EarthquakeCooccurrence.scala:71`) ha impiegato **~366 s**.
- Con heap di default (~434 MB) i log Spark mostravano continui spill su disco a piccoli chunk
  (60–80 MB); con `-Xmx24G` gli spill sono molto più rari e più grandi (1.8–2.6 GB), a conferma che
  la memoria di default era un collo di bottiglia significativo.

**Coppia vincente e date** (identica al test rapido sul campione ridotto — logica confermata corretta):

```
((38.8, -122.8), (38.8, -122.7))
```

- **Date totali di co-occorrenza: 10032** (contate correttamente con
  `grep -cE '^[0-9]{4}-[0-9]{2}-[0-9]{2}\r?$'` — il file ha terminatori di riga CRLF perché generato su
  Windows, quindi un `grep`/regex `$`-anchored senza gestire il `\r` restituisce erroneamente 0 match).
- **Intervallo reale: dal 1990-01-05 al 2023-07-29** (33,6 anni, 12259 giorni di calendario).
  L'osservazione iniziale "vedo date solo fino al 1994 scorrendo indietro" era dovuta al buffer di
  scroll del terminale già troncato, non ai dati reali — confermato leggendo il file completo.
- **10032 / 12259 = 81.8%** dei giorni nell'intervallo hanno una co-occorrenza per questa coppia di
  location arrotondate. Plausibile: le coordinate (38.8°N, -122.7/-122.8°W) ricadono nell'area di **The
  Geysers**, il più grande campo geotermico al mondo (California del Nord), zona con sismicità indotta
  praticamente quotidiana per decenni — un risultato reale e coerente con il dominio, non un bug.

**Conclusione diagnosi**: il rallentamento su DataProc è dovuto a **entrambe** le cause:
1. **Memoria per executor insufficiente** (di default DataProc assegna molta meno memoria per executor
   di quanta ne avesse a disposizione il singolo processo locale da 24 GB) → causa spill pesanti.
2. **Skew algoritmico intrinseco e non riducibile aumentando i worker**: sia `groupByKey` che `.join()`
   di Spark RDD ripartizionano per chiave (la data) — **tutti** i valori di una singola chiave finiscono
   in **un solo task**. Con una coppia di location attiva per l'81.8% dei giorni in un range di 33 anni,
   la maggior parte del lavoro di generazione/dedup delle coppie per quella chiave non si distribuisce
   su più executor aggiungendo worker (a differenza di Spark SQL/DataFrame, dove l'Adaptive Query
   Execution gestisce lo skew-join in modo automatico — funzionalità non disponibile sulle RDD "pure").
   Questo va menzionato nella Sezione 4.3 del report come limite noto dell'approccio, indipendentemente
   dal numero di worker testati.

**Azione da fare prima dei run cloud definitivi**: ricreare i cluster con proprietà esplicite di
memoria per evitare lo stesso spill eccessivo, ad es.:

```bash
gcloud dataproc jobs submit spark \
  --cluster=eq-cluster-2w --region=$REGION \
  --class=EarthquakeCooccurrence \
  --jars=$BUCKET/earthquake-cooccurrence-assembly-1.0.jar \
  --properties=spark.executor.memory=6g,spark.driver.memory=6g \
  -- $BUCKET/dataset-earthquakes-full.csv
```

(valori indicativi da adattare alla memoria disponibile per nodo di `n2-standard-4`, 16 GB totali per
VM — lasciando margine per YARN/OS).

**Aggiornamento (13-14/09/2026)**: entrambi gli approcci sono stati eseguiti con successo su cluster
cloud reali a 2 worker (n2-standard-4, memoria tunata come sopra), pilotati da terminale autenticato via OAuth
su un ambiente cloud dedicato (comandi `gcloud` eseguiti in autonomia, non più a mano
sul PC dell'utente). Risultato identico in entrambi i casi rispetto al test locale: coppia
`((38.8, -122.8), (38.8, -122.7))`, 10032 date. Tempi:

| Worker | Macchina        | Approccio  | Tempo reale |
|--------|-----------------|------------|-------------|
| 2      | n2-standard-4   | groupByKey | 4451.7 s (74.19 min) |
| 2      | n2-standard-4   | self-join  | 4619.0 s (76.98 min) |

Il self-join risulta leggermente più lento (~+3.8%) del groupByKey a parità di worker — coerente con
l'ipotesi che il self-join generi più lavoro (prodotto cartesiano prima del filtro) sulla data-chiave
fortemente skewata, anche se la differenza è modesta a 2 worker.

**⚠️ Scoperta importante — quota `CPUS_ALL_REGIONS`**: il progetto education-tier ha una quota
**globale** (non solo per-regione) di **12 vCPU totali su tutto il progetto** (`compute.googleapis.com/cpus_all_regions`,
verificabile con `gcloud compute project-info describe --project=$PROJECT_ID`). La quota "N2 CPUs"
di 32 in `europe-west1` verificata in precedenza (sezione 0.3) NON è quella vincolante — esiste
un tetto più basso e più generale che si applica a TUTTE le famiglie di macchine insieme. Con
n2-standard-4 (4 vCPU/nodo), un cluster a 2 worker (1 master + 2 worker = 3 nodi) usa già 12 vCPU,
cioè l'intera quota disponibile: non è possibile creare un cluster a 3 o 4 worker con n2-standard-4
senza prima ottenere un aumento di quota. Tentativo di richiesta automatica di aumento (via
`gcloud alpha quotas info describe CPUS-ALL-REGIONS-per-project`) risulta **non idoneo**
(`ineligibilityReason: NOT_ENOUGH_USAGE_HISTORY` — il progetto è troppo nuovo per l'approvazione
automatica; un aumento manuale richiederebbe una richiesta in Console con tempi di approvazione non
garantiti prima della scadenza).

**Decisione adottata**: per i cluster a 3 e 4 worker si usa **n2-standard-2** (2 vCPU / 8 GB) sia per
master che per i worker, che rientra nel budget di 12 vCPU:
- 3 worker: 4 nodi × 2 vCPU = 8 vCPU
- 4 worker: 5 nodi × 2 vCPU = 10 vCPU

Questo introduce una variabile confondente (tipo di macchina diverso tra il punto a 2 worker e quelli
a 3/4 worker) che va dichiarata esplicitamente nel report come limite metodologico imposto da un
vincolo reale della piattaforma cloud (esattamente il tipo di "problematiche relative alla
realizzazione di applicazioni distribuite" che il corso vuole far toccare con mano). Proprietà
memoria adattate di conseguenza: `spark.executor.memory=5g, spark.executor.memoryOverhead=800m,
spark.executor.cores=2, spark.driver.memory=3g, spark.driver.memoryOverhead=500m`.

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
- Apri `Zini_Alberto_0001007558_Report_SCP.pdf` (o rigenera da `build_report.py` se preferisci
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
