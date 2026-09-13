name := "earthquake-cooccurrence"
version := "1.0"
scalaVersion := "2.12.17"

libraryDependencies ++= Seq(
  "org.apache.spark" %% "spark-core" % "3.3.2" % "provided",
  "org.apache.spark" %% "spark-sql"  % "3.3.2" % "provided"
)

// Build a fat JAR (Scala and Spark excluded — provided by DataProc)
assembly / assemblyOption := (assembly / assemblyOption).value
  .withIncludeScala(false)

assembly / assemblyMergeStrategy := {
  case PathList("META-INF", _*) => MergeStrategy.discard
  case _                        => MergeStrategy.first
}


// Permette a "sbt run"/"runMain" di trovare Spark in locale (provided lo esclude di default)
Compile / run := Defaults.runTask(Compile / fullClasspath, Compile / run / mainClass, Compile / run / runner).evaluated
Compile / runMain := Defaults.runMainTask(Compile / fullClasspath, Compile / run / runner).evaluated