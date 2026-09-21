# Building the dashboard in Power BI Desktop

The files in `docs/powerbi/` are the finished analysis, already cleaned. The
dashboard only has to display them, so every number on it should match the
README exactly. Step 6 checks that.

| File | One row per | Used for |
|---|---|---|
| `posting.csv` | SEC posting | The dimension every other table links to |
| `market.csv` | posting | Lending, collateral cover, concentration |
| `borrower_groups.csv` | posting and bank group | Who borrows, and how that changes |
| `funds.csv` | posting and lending fund | How much each fund lends, and its cover |
| `fund_flags.csv` | fund | Funds with a problem in every posting |

Amounts are in US dollars and ratios are fractions (0.103 means 10.3%).

## Step 1: load the data

1. Open Power BI Desktop and start a blank report.
2. **Home > Get data > Text/CSV**, choose `docs/powerbi/posting.csv`, then
   **Load**.
3. Repeat for the other four files.
4. In the **Data** pane (the table icon on the left), check the types:
   - `quarter` is **Text** in every table
   - `holdings_from`, `holdings_to` and `report_date` are **Date**
   - money columns (`on_loan_usd`, `net_assets`, `collateral_usd` ...) are
     **Decimal number**
   - ratio columns (`coverage`, `share`, `on_loan_pct_nav` ...) are **Decimal
     number**

## Step 2: connect the tables

1. Open the **Model** view (the third icon on the left).
2. Drag `posting[quarter]` onto `market[quarter]`. Power BI creates a
   one-to-many relationship. Do the same from `posting[quarter]` to
   `borrower_groups[quarter]` and to `funds[quarter]`.
3. Drag `fund_flags[series_id]` onto `funds[series_id]` (one flag row, many
   postings).
4. So the postings appear in time order, not alphabetically: select
   `posting[holdings_label]`, then **Column tools > Sort by column >
   posting_order**.

Every filter on a posting now flows to all three fact tables. This layout, one
dimension with facts around it, is a star schema.

## Step 3: add the measures

A measure is a calculation that responds to whatever is selected; a plain
column cannot. Create a table to hold them: **Home > Enter data**, name it
`Measures`, then **Load**. With it selected, choose **Home > New measure** and
add each of these:

```DAX
On Loan = SUM ( funds[on_loan_usd] )

Lending Funds = DISTINCTCOUNT ( funds[series_id] )

Collateral Cover =
DIVIDE ( SUM ( funds[collateral_usd] ), SUM ( funds[on_loan_usd] ) )

Top Five Share = MAX ( market[top5_share] )

Share Of Lending =
DIVIDE (
    SUM ( borrower_groups[on_loan_usd] ),
    CALCULATE ( SUM ( borrower_groups[on_loan_usd] ), ALL ( borrower_groups[parent_name] ) )
)

Funds Near Limit =
CALCULATE (
    DISTINCTCOUNT ( funds[series_id] ),
    funds[on_loan_pct_nav] >= 0.33,
    funds[reconciliation] = "reconciles"
)

Collateral Shortfall =
SUMX (
    FILTER (
        funds,
        funds[coverage] > 0 && funds[coverage] < 1
            && funds[reconciliation] = "reconciles"
    ),
    funds[on_loan_usd] - funds[collateral_usd]
)
```

Format them in **Measure tools**: `On Loan` and `Collateral Shortfall` as
currency with display units in billions; `Collateral Cover`, `Top Five Share`
and `Share Of Lending` as percentages with one decimal.

`Share Of Lending` is the one worth understanding. The `ALL` removes the filter
on bank group from the bottom half only, so each bank is divided by the total of
all banks in the same posting.

## Step 4: page 1, "Who borrows"

1. **Slicer** with `posting[holdings_label]`, set to **Single select**, at the
   top of the page. Pick the last posting.
2. Four **Card** visuals: `On Loan`, `Lending Funds`, `Collateral Cover`,
   `Top Five Share`.
3. **Clustered bar chart**: `borrower_groups[parent_name]` on the Y axis,
   `Share Of Lending` on the X axis. In the Filters pane, set `parent_name` to
   **Top N**, 8, by `Share Of Lending`. Title: *Five banks borrow most of what
   US funds lend*.
4. **Line chart**: `posting[holdings_label]` on the X axis, `On Loan` on the Y
   axis. This one must ignore the slicer: select it, then **Format > Edit
   interactions** and set the slicer to *None* for this chart. Title:
   *Lending grew 23% over the year*.
5. **Line chart**: `posting[holdings_label]` on the X axis, `Share Of Lending`
   on the Y axis, `borrower_groups[parent_name]` as the legend, filtered to
   Barclays, JPMorgan Chase, Morgan Stanley and Goldman Sachs. Also set the
   slicer to *None* for it. Title: *JPMorgan gained the most share*.

## Step 5: page 2, "Which funds to watch"

1. Add a page and the same posting slicer (**View > Sync slicers** keeps the
   two pages on the same posting).
2. **Table** from `funds`: `series_name`, `on_loan_pct_nav`,
   `largest_borrower`, `largest_borrower_pct_nav`, `coverage`. Filter
   `reconciliation` to *reconciles* and sort by `on_loan_pct_nav`, highest
   first. Title: *Funds lending the most, relative to their size*.
3. **Scatter chart**: `on_loan_pct_nav` on the X axis, `coverage` on the Y
   axis, `series_name` in *Values*. Filter `reconciliation` to *reconciles*.
   The funds worth a look sit far right (lending a lot) or low (thin cover).
4. **Table** from `fund_flags`: `series_name`, `quarters_near_ceiling`,
   `quarters_below_90pct`, `max_on_loan_pct_nav`, `min_coverage`, filtered to
   rows where either count is 4. Title: *A problem in every posting*.
5. Two cards: `Funds Near Limit` and `Collateral Shortfall`.

## Step 6: check it against the analysis

With the last posting selected, the dashboard must show exactly:

| Measure | Expected |
|---|---:|
| On Loan | $339.0bn |
| Lending Funds | 4,109 |
| Collateral Cover | 103.1% |
| Top Five Share | 58.4% |
| Barclays' Share Of Lending | 14.6% |
| Funds Near Limit | 17 |
| Collateral Shortfall | $1.6bn |

If a number differs, the cause is almost always a relationship or a filter,
not the data. Fix it before styling anything.

## Step 7: save and share

1. **File > Save as**, into `docs/powerbi/`, as `securities_lending.pbix`.
2. **File > Export > Export to PDF**, saved next to it as
   `securities_lending.pdf`, so anyone without Power BI can see it.

(Publishing to the web needs a Power BI work account, so the file and the PDF
are how this dashboard is shared.)
