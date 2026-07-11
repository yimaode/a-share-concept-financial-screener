class MetricSeriesError(Exception):
    pass


class CandidateValidationError(MetricSeriesError):
    pass


class ReviewDecisionError(MetricSeriesError):
    pass
