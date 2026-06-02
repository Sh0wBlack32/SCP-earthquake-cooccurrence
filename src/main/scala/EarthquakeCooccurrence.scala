import org.apache.spark.sql.SparkSession

/**
 * Approach 1 — groupByKey
 *
 * Steps:
 *  1. Parse CSV: round (lat, lon) to 1 decimal, truncate timestamp to date.
 *  2. Deduplicate (location, date) pairs caused by rounding.
 *  3. Group locations by date.
 *  4. For each date, generate all canonical pairs (loc_i, loc_j) with loc_i < loc_j.
 *  5. Deduplicate (pair, date) entries.
 *  6. Count co-occurrences per pair; find the maximum.
 *  7. Collect and sort the dates for the winning pair.
 *
 * Usage:
 *   spark-submit --class EarthquakeCooccurrence earthquake-cooccurrence-assembly-1.0.jar \
 *     <path-to-csv> [numPartitions]
 */
object EarthquakeCooccurrence {

  /** Round a Double to 1 decimal place. */
  def round1(v: Double): Double = math.round(v * 10.0) / 10.0

  def main(args: Array[String]): Unit = {
    val spark = SparkSession.builder
      .appName("Earthquake Co-occurrence (groupByKey)")
      .getOrCreate()

    val filename   = if (args.length > 0) args(0) else "dataset-earthquakes-trimmed.csv"
    val partitions = if (args.length > 1) args(1).toInt else 0

    // ── 1. Read & normalise ──────────────────────────────────────────────────
    var events = spark.read
      .option("header", value = true)
      .csv(filename)
      .rdd
      .map { row =>
        val lat  = round1(row.getAs[String]("latitude").toDouble)
        val lon  = round1(row.getAs[String]("longitude").toDouble)
        val date = row.getAs[String]("date").substring(0, 10) // YYYY-MM-DD
        ((lat, lon), date)
      }
      .distinct() // ── 2. Remove (location, date) duplicates from rounding

    if (partitions > 0) events = events.repartition(partitions)

    // ── 3. Group locations by date ───────────────────────────────────────────
    val locationsByDate = events
      .map { case (loc, date) => (date, loc) }
      .groupByKey()

    // ── 4. Generate all canonical pairs per date ─────────────────────────────
    val pairDates = locationsByDate.flatMap { case (date, locs) =>
      val sorted = locs.toList.distinct.sorted
      for {
        i <- sorted.indices
        j <- (i + 1) until sorted.size
      } yield ((sorted(i), sorted(j)), date)
    }.distinct() // ── 5. Each (pair, date) counts once

    // ── 6. Count and find maximum ────────────────────────────────────────────
    val pairCounts = pairDates
      .map { case (pair, _) => (pair, 1) }
      .reduceByKey(_ + _)

    val (bestPair, _) = pairCounts.reduce((a, b) => if (a._2 >= b._2) a else b)

    // ── 7. Collect sorted dates for the winning pair ──────────────────────────
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
