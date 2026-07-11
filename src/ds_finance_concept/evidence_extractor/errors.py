class EvidenceExtractorError(Exception):
    pass


class ConceptsNotFrozenError(EvidenceExtractorError):
    pass


class PageReadError(EvidenceExtractorError):
    pass
