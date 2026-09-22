# Data model (on paper, not built yet)

Goal: a job lives on the shop board from first estimate until it is archived, and its numbers change as
supplements arrive. The parser output already has the shape below; storage comes later.

## Job
One repair order. Identity fields (any may be blank):
- `ro_number` - shop's 4-digit RO#. CCC prints it; Mitchell does not, so it starts blank and is **edited by hand**
  during the live-production phase.
- `claim`, `vin`, `customer`, `vehicle`, `insurance`
- `status` (production board, later) and `archived_at`

## Document (many per job, never overwritten)
One uploaded PDF = one version of the estimate.
- `format` - CCC ONE | Mitchell
- `title_raw` - exact title printed on the PDF
- `stage` - preliminary | estimate | to_repair | of_record | unknown
- `supplement_no` - 0 for the original, N for supplement N
- `printed_at` - print time from the PDF footer
- `supplement_amount` - dollar change of this supplement, when the PDF prints it
- `needs_review` / `review_reasons` - set by `review_flags()` when parsed totals don't match the printed ones, the
  history doesn't add up, or the document type or print time can't be read

**Current values rule:** the job shows its newest document, chosen by `version_key()` in
`estimate_parser/core.py`: highest `supplement_no`, then `stage` rank (unknown < preliminary < estimate <
to_repair < of_record), then `printed_at`. Older documents stay as history (what changed, profitability).
Both CCC and Mitchell totals are cumulative, so the newest document holds the whole job's totals.

## Document summary (what the page shows today)
- Labor by type: body, paint, mechanical, other - each with hours, rate, amount; total hours and amount
- Total parts (pre-tax)
- Other price breakdowns: materials, taxes, grand total, deductible, net, etc.

## Kept for later
Itemized charge rows (`charges` in the parser output): part / labor by type / sublet / other, with part numbers,
hours and rates. Not shown or stored yet.
