import pymupdf4llm
# from pathlib import Path



def load_tender_pdf(file_path):
    result = pymupdf4llm.to_markdown(
        doc=str(file_path),
        # page_chunks=True, It is a list containing one result per page.
    )

    return result


# load_tender_pdf("data/tenders/31-mAY/chandwa/add tnC.pdf")