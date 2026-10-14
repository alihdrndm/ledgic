---
kind: policy
title: Accounts payable policy
---

# Accounts payable policy

Owner: Controller, Northside Group. Applies to every entity and location. Ledgic enforces the numeric
rules below in code and in the database; this document is the human-readable source.

## 1. Three-way match

1.1 Every invoice is matched line by line against the purchase order (PO) and the goods received note
(GRN). Where a supplier contract fixes a price, the **contract price** is the expected price; otherwise
the PO price is.

1.2 An invoice matches when every line is within tolerance on price and the invoiced quantity does not
exceed the quantity received.

1.3 Invoices that match are posted to the ERP without human review ("touchless").

## 2. Price tolerance

2.1 A line passes price matching when the difference between the invoiced amount and the expected
amount is within **±2% or $25.00, whichever is lower**.

2.2 Example: on an expected line amount of $736.00, 2% is $14.72 and $14.72 is lower than $25.00, so
the allowed variance is $14.72.

2.3 Favorable variances (billed below the expected price) always pass and are paid as billed.

2.4 Price variances beyond tolerance on a contracted item are short-paid to the contract price when the
goods were received in full. The vendor receives a notice citing the contract clause.

## 3. Approval limits

3.1 **AP clerks** confirm extracted fields and link purchase orders; they cannot approve payments or
holds.

3.2 **AP managers** may decide price, quantity and no-PO exceptions where the amount at risk is up to
**$5,000.00**.

3.3 Exceptions above $5,000.00, and every new-vendor (fraud) screen, require the **controller**.

3.4 The controller is notified whenever the amount at risk on an exception exceeds $500.00.

## 4. Fraud holds and new vendors

4.1 Ledgic holds an invoice for a fraud screen when risk signals add up to 0.70 or more. Signals
include: bank details differ from the W-9 on file, vendor record younger than 14 days, no purchase
order, remit-to address changed recently, and amount far outside the vendor's usual range.

4.2 **Only the controller can release a fraud hold.** Before releasing, the controller verifies the
bank details by phone using the contact number on the W-9 or the original vendor setup — never a
number printed on the invoice or given in an email — and records "verified by phone" with a comment.

4.3 The person who created a vendor record cannot release a hold on that vendor's invoices.

4.4 New vendors must provide a W-9 before the first payment. Bank changes for existing vendors follow
4.2 and take effect only after verification.

## 5. Segregation of duties

5.1 A person who corrected a monetary field on an invoice (quantity, unit price, amount, subtotal, tax,
freight or total) cannot approve that invoice's exception; someone else must.

5.2 A person cannot approve a payment to a vendor record they created.

5.3 Every decision is written to the hash-chained audit log with the actor, time, amounts and comment.

## 6. Duplicate invoices

6.1 Ledgic compares each invoice with the vendor's invoices from the last 180 days (number, amount,
date, line items and the document image).

6.2 Similarity of **0.90 or more** holds the invoice as a suspected duplicate; 0.75 to 0.90 is flagged
for attention without a hold.

6.3 An AP manager may **merge** the copies (keep the earlier invoice) or **reject the copy**. Marking a
suspected duplicate as **not a duplicate** requires the controller and a comment.

6.4 The same invoice arriving by email and as a dock photo is the most common duplicate; pay it once.

## 7. Service levels and escalation

7.1 Every exception has a **24-hour** service level from the time it was opened.

7.2 Exceptions still open after 24 hours are escalated to the next role up (AP manager → controller)
and flagged in the queue.

7.3 Disputed invoices and invoices awaiting vendor documents (W-9, credit memo) stay open without
escalation while the vendor responds.

## 8. Extraction review

8.1 Ledgic reads invoices with an AI model that reports a confidence for every field. An invoice goes
straight through only if the document confidence is at least 0.90 and no required field is below 0.75.

8.2 Otherwise an AP clerk reviews the flagged fields against the document image and confirms or
corrects them. Human-confirmed values carry confidence 1.0.

8.3 The AI never decides payments: matching, tolerance, holds and recommendations are deterministic
rules, and every decision is made by a person within their limits.

## 9. How Ledgic metrics are calculated

9.1 **Touchless rate** = invoices posted to the ERP with no human touch (no field review, no exception
decision, no manual edit) ÷ all invoices posted in the period. A single human touch at any stage makes an
invoice non-touchless.

9.2 **Cost per invoice** = AI/LLM spend + OCR + infrastructure + human time (decision seconds × the
loaded hourly rate of $35.00) for the period ÷ invoices received in the period.

9.3 **Held variances** = sum of the amounts held on short-pays decided in the period.

9.4 Every figure on the Operations screen is computed in SQL from the ledger tables; nothing is entered
by hand.
