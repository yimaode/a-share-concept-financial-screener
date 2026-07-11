class PdfExtractorError(Exception):
    pass


class PdfOpenError(PdfExtractorError):
    pass


class PdfWriteError(PdfExtractorError):
    pass
