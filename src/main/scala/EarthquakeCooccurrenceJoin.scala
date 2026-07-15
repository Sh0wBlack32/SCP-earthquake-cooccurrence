import org.apache.spark.sql.SparkSession
import scala.math.Ordering.Implicits._

/**
 * Approach 2 — Self-Join
 *
 * Instead of collecting all locations per day in memory (groupByKey),
 * this approach performs a distributed self-join on the date key.
 * Each event (date, loc) is joined with every other event on the same date,
 * producing all candidate pairs. The canonical ordering (loc1 < loc2) eliminates
 * self-pairs and duplicates.
 *
 * This approach may outperform groupByKey when data is heavily skewed by date
 * (many events per day), since the join is fully distributed.
 *
 * Usage:
 *   spark-submit --class EarthquakeCooccurrenceJoin earthquake-cooccurrence-assembly-1.0.jar \
 *     <path-to-csv> [numPartitions]
 */
object EarthquakeCooccurrenceJoin {

  def round1(v: Double): Double = math.round(v * 10.0) / 10.0

  def main(args: Array[String]): Unit = {
    val spark = SparkSession.builder
      .appName("Earthquake Co-occurrence (Join)")
      .getOrCreate()

    val filename   = if (args.length > 0) args(0) else "dataset-earthquakes-trimmed.csv"
    val partitions = if (args.length > 1) args(1).toInt else 0

    // ── 1. Read & normalise; key by date ─────────────────────────────────────
    var events = spark.read
      .option("header", value = true)
      .csv(filename)
      .rdd
      .map { row =>
        val lat  = round1(row.getAs[String]("latitude").toDouble)
        val lon  = round1(row.getAs[String]("longitude").toDouble)
        val date = row.getAs[String]("date").substring(0, 10)
        (date, (lat, lon))
      }
      .distinct() // remove (date, location) duplicates from rounding

    if (partitions > 0) events = events.repartition(partitions)

    // ── 2. Self-join on date key ─────────────────────────────────────────────
    // Result: (date, (loc1, loc2)) for all ordered pairs loc1 < loc2
    val pairDates = events
      .join(events)
      .filter { case (_, (loc1, loc2)) => loc1 < loc2 }
      .map    { case (date, (loc1, loc2)) => ((loc1, loc2), date) }
      .distinct()

    // ── 3. Count and find maximum ────────────────────────────────────────────
    val pairCounts = pairDates
      .map { case (pair, _) => (pair, 1) }
      .reduceByKey(_ + _)

    val (bestPair, _) = pairCounts.reduce((a, b) => if (a._2 >= b._2) a else b)

    // ── 4. Collect sorted dates for the winning pair ──────────────────────────
    val dates = pairDates
      .filter { case (pair, _) => pair == bestPair }
      .map    { case (_, date) => date }
      .collect()
      .sorted

    // ── Output ────────────────────────────────────────────────────────────────
    val ((lat1, lon1), (lat2, lon2)) = bestPair
    println(s"(($lat1, $lon1), ($lat2, $lon2))")
    dates.foreach(println)

    spark.stop()
  }
}
