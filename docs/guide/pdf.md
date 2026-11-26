# PDF

Convert any rendered docx with LibreOffice (headless, in a temp folder: the
only part of qrbar that touches files or runs a process). LibreOffice must be
installed on the machine; there is no Python extra.

```python
# needs: LibreOffice
pdf = qrbar.docx_to_pdf(docx)

Path("sheet.pdf").write_bytes(pdf)

# one PDF per record
pdfs = [qrbar.docx_to_pdf(doc) for doc in docs]
```

`docx` and `docs` are the results of `render` from
[Word templates](docx.md) or [Label sheets](sheets.md).

- LibreOffice is found on `PATH` (`soffice` or `libreoffice`) or in its
  default install folder; otherwise pass
  `soffice="/opt/libreoffice/program/soffice"`.
- `timeout` (default 120 s) stops a stuck conversion and kills its processes.
- Each call uses its own LibreOffice profile, so parallel conversions are safe.
- Input that is not docx bytes raises `ValidationError`.
- A missing, failing or timed-out LibreOffice raises `ConversionError`,
  separate from data errors.
