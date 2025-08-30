# Convertit CSV scalp -> JSON
[
  inputs
  | split("\n")[]
  | select(length > 0)
  | split(",")
  | {
      ts: .[0],
      pair: .[1],
      timeframe: .[2],
      signal: .[3],
      indicators: (.[4:] | join(";"))
    }
]
