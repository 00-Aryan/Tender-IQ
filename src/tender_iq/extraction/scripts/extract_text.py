"""Standalone PDF-text export prototype; not used by the application loader.

Importing this module does not read PDFs, write files or invoke a model.
"""


def main():
    import pymupdf

    doc = pymupdf.open("/home/aryan/June-2026/Tender_IQ/data/tenders/31-mAY/Bachra.pdf")
    with open("docs/output_text.txt", "wb") as out:
        for page_number, page in enumerate(doc, start=1):
            header = f"\n===== Page {page_number} =====\n".encode("utf-8")
            text = page.get_text("text").encode("utf-8")
            out.write(header)
            out.write(text)
            out.write(b"\x0c")

    doc.close()


if __name__ == "__main__":
    main()
