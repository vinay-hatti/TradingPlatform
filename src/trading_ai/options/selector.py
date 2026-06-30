class OptionsSelector:

    def score(self, option):

        score = 0

        if option.open_interest > 1000:
            score += 30

        if option.volume > 200:
            score += 20

        spread = option.ask - option.bid

        if spread < 0.20:
            score += 20

        score += max(
            0,
            30 - abs(abs(option.delta) - 0.50) * 100,
        )

        return score
