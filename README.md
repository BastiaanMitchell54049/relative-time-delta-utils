# relative-time-delta-utils

Applies human relative time phrases like 'last Monday of March' or 'third Wednesday' to datetime objects.

```python
from datetime import datetime
from relative_time_delta_utils import RelativeTimeDelta

base = datetime(2024, 6, 15, 10, 30)

rtd = RelativeTimeDelta("third Wednesday of March")
print(rtd.apply(base))   # 2024-03-20 10:30:00

rtd = RelativeTimeDelta("next Friday")
print(rtd.apply(base))   # 2024-06-21 10:30:00

rtd = RelativeTimeDelta("last day of February")
print(rtd.apply(base))   # 2024-02-29 10:30:00
```

Exported names: `RelativeTimeDelta`, `Weekday`, `Month`, `RelativeTimeError`.

## Why this exists

Scheduling code often needs to compute concrete dates from recurring human phrases — "the third Wednesday of the month", "last Monday" — without pulling in a full recurrence library. This library covers that narrow job with zero dependencies and a single, predictable class.

The deliberate trade-off is scope: only four phrase shapes are supported (ordinal-in-month, ordinal-in-year, proximity weekday, last-day-of-month). No arithmetic, no intervals, no rolling recurrences. Keeping the grammar small makes parsing and error messages easy to reason about.

## Edge cases worth knowing

- **Fifth weekday of a month**: `fifth Monday of March` raises `RelativeTimeError` when applied to a year/month where that occurrence does not exist. Constructing the `RelativeTimeDelta` succeeds; the failure surfaces at `apply` time because existence depends on the reference year.
- **'last' vs 'next' on the same weekday**: `last Monday` applied on a Monday returns the previous week's Monday (7 days back), not today. `next Monday` on a Monday returns next week. This is intentional — strict past/future semantics.
- **Time and timezone**: `apply` preserves the time-of-day and timezone of the base datetime; only the calendar date changes.
