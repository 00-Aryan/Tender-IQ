import pymupdf

doc = pymupdf.open("Tender/BAchra payment terms.pdf")
with open("docs/output_blocks.txt", "w", encoding="utf-8") as out:
    for page_number, page in enumerate(doc, start=1):
        blocks = page.get_text("blocks", sort=False)
        out.write(f"--- PAGE {page_number} ---\n")
        for block in blocks:
            if len(block) < 5:
                continue
            x0, y0, x1, y1, text = block[:5]
            if not text.strip():
                continue
            out.write(f"{x0},{y0},{x1},{y1}\t{text.strip()}\n")
        out.write("\f\n")

doc.close()

# import pymupdf

# doc = pymupdf.open("BAchra payment terms.pdf")
# with open("output_blocks.txt", "wb") as out:
#     for page in doc:
#         blocks = page.get_text("blocks", sort=False)
#         for block in blocks:
#             text = block[4] if len(block) > 4 else ""
#             if text:
#                 out.write(text.encode("utf-8"))
#                 out.write(b"\n")
#         out.write(b"\x0c")

# doc.close()