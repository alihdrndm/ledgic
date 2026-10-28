-- Match consumes PO-line quantity already billed by other invoices (#32): sum invoice_lines by po_line_id.
create index if not exists invoice_lines_po_line_id_idx on public.invoice_lines (po_line_id);
