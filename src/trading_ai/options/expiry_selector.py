class ExpirySelector:

    def choose(self, row):

        atr = row["atr14"]

        expected_move = row["expected_move_1d"]

        if atr > expected_move * 1.5:
            return "7D"

        if atr > expected_move:
            return "14D"

        return "30D"
