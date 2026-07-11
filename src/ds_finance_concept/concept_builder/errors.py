class ConceptBuilderError(Exception):
    pass


class InputPathError(ConceptBuilderError):
    pass


class MarkdownParseError(ConceptBuilderError):
    pass


class QuoteValidationError(ConceptBuilderError):
    pass


class JsonlWriteError(ConceptBuilderError):
    pass


class QuoteReaderError(ConceptBuilderError):
    pass


class InsightValidationError(ConceptBuilderError):
    pass
