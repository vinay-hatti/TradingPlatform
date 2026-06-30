class SignalEngine:
    """
    Converts engineered features into a directional signal.
    """

    def generate(self, row):

        call_score = row["call_score"]
        put_score = row["put_score"]

        if call_score >= put_score:
            return "CALL"

        return "PUT"
