# Query recipes

Replace the placeholders before sending the MongoDB MCP call.

Placeholder names:

- `PRIMARY_COLLECTION`
- `SECONDARY_COLLECTION`
- `FEEDER_FIELD`
- `TIMESTAMP_FIELD`
- `HOURS`
- `MATCH_PATTERN`
- `START_ISO`
- `END_ISO`

If there is no secondary collection, remove the `$unionWith` stage and say that the report used a single collection.

## Rolling window

Run on `PRIMARY_COLLECTION`.

```json
[
  {
    "$match": {
      "$expr": {
        "$and": [
          {
            "$gte": [
              "$TIMESTAMP_FIELD",
              {
                "$dateSubtract": {
                  "startDate": "$$NOW",
                  "unit": "hour",
                  "amount": HOURS
                }
              }
            ]
          },
          { "$lte": ["$TIMESTAMP_FIELD", "$$NOW"] }
        ]
      }
    }
  },
  {
    "$unionWith": {
      "coll": "SECONDARY_COLLECTION",
      "pipeline": [
        {
          "$match": {
            "$expr": {
              "$and": [
                {
                  "$gte": [
                    "$TIMESTAMP_FIELD",
                    {
                      "$dateSubtract": {
                        "startDate": "$$NOW",
                        "unit": "hour",
                        "amount": HOURS
                      }
                    }
                  ]
                },
                { "$lte": ["$TIMESTAMP_FIELD", "$$NOW"] }
              ]
            }
          }
        }
      ]
    }
  },
  {
    "$group": {
      "_id": "$FEEDER_FIELD",
      "count": { "$sum": 1 },
      "latest": { "$max": "$TIMESTAMP_FIELD" }
    }
  },
  { "$sort": { "count": -1, "latest": -1 } }
]
```

## All feeders

Run on `PRIMARY_COLLECTION`.

```json
[
  { "$unionWith": { "coll": "SECONDARY_COLLECTION" } },
  {
    "$group": {
      "_id": "$FEEDER_FIELD",
      "count": { "$sum": 1 },
      "latest": { "$max": "$TIMESTAMP_FIELD" }
    }
  },
  { "$sort": { "latest": -1, "count": -1 } }
]
```

## Substring match

Run on `PRIMARY_COLLECTION`.

```json
[
  {
    "$match": {
      "FEEDER_FIELD": { "$regex": "MATCH_PATTERN", "$options": "i" }
    }
  },
  {
    "$unionWith": {
      "coll": "SECONDARY_COLLECTION",
      "pipeline": [
        {
          "$match": {
            "FEEDER_FIELD": { "$regex": "MATCH_PATTERN", "$options": "i" }
          }
        }
      ]
    }
  },
  {
    "$group": {
      "_id": "$FEEDER_FIELD",
      "count": { "$sum": 1 },
      "latest": { "$max": "$TIMESTAMP_FIELD" }
    }
  },
  { "$sort": { "latest": -1, "count": -1 } }
]
```

## Fixed range

Run on `PRIMARY_COLLECTION`.

```json
[
  {
    "$match": {
      "TIMESTAMP_FIELD": {
        "$gte": { "$date": "START_ISO" },
        "$lte": { "$date": "END_ISO" }
      }
    }
  },
  {
    "$unionWith": {
      "coll": "SECONDARY_COLLECTION",
      "pipeline": [
        {
          "$match": {
            "TIMESTAMP_FIELD": {
              "$gte": { "$date": "START_ISO" },
              "$lte": { "$date": "END_ISO" }
            }
          }
        }
      ]
    }
  },
  {
    "$group": {
      "_id": "$FEEDER_FIELD",
      "count": { "$sum": 1 },
      "latest": { "$max": "$TIMESTAMP_FIELD" }
    }
  },
  { "$sort": { "count": -1, "latest": -1 } }
]
```

## Notes

- Replace quoted field placeholders with the actual dotted field path before sending the MCP call.
- Keep the report grouped by feeder and include the latest timestamp per feeder.
- Use UTC ISO timestamps for fixed ranges unless the user explicitly wants another timezone interpretation.
