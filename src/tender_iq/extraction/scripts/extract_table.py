import pymupdf

doc = pymupdf.open("Tender/BAchra payment terms.pdf")

page = doc[8]

ft1 = page.find_tables()

for i, table in enumerate(ft1.tables):
    print(f"\n--- Table {i} ---")
    for row in table.extract():
        print(row)

doc.close()


