"""Standalone PDF-table inspection prototype; not used by the application loader.

Importing this module does not read PDFs, write files or invoke a model.
"""


def main():
    import pymupdf

    doc = pymupdf.open("Tender/BAchra payment terms.pdf")

    page = doc[8]

    ft1 = page.find_tables()

    for i, table in enumerate(ft1.tables):
        print(f"\n--- Table {i} ---")
        for row in table.extract():
            print(row)

    doc.close()


if __name__ == "__main__":
    main()
