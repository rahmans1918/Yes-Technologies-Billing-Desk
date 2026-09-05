# Yes Technologies Billing Desk

A lightweight Python/Flask GST billing application for Yes Technologies. It supports:

- GST invoices with automatic CGST/SGST or IGST calculation
- Quotations
- Proforma invoices
- Purchase orders
- Customer and line-item management
- Draft, sent, paid, and cancelled statuses
- Printable invoice/document view
- Business profile settings
- SQLite local storage

## Setup on Windows

1. Open PowerShell or Command Prompt in this folder.
2. Run `setup.exe` once. If it has not been built yet, run `build_setup_exe.bat` first.
3. Run `run.bat`.
4. Open http://127.0.0.1:5000 in your browser.

The SQLite database is created automatically as `yestech_billing.db`. Update the default GSTIN and company details from **Business profile** before issuing documents. `setup.bat` remains available as a fallback.

## Manual setup

```text
py -3 -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
```

This starter app is intended for local use. Before production deployment, add authentication, backups, audit logging, and a production WSGI server.
