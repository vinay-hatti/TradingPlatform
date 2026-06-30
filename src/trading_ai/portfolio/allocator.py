class PositionAllocator:

    def size_position(self, account_value, trade_score, pop):
        """
        Higher score + higher probability = larger size
        """

        base_risk = 0.02 * account_value

        confidence_multiplier = trade_score / 100
        probability_multiplier = pop

        position_size = base_risk * confidence_multiplier * probability_multiplier

        return max(position_size, account_value * 0.005)
