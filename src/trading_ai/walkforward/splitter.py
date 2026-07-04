from dataclasses import dataclass
from datetime import date, datetime
from dateutil.relativedelta import relativedelta


@dataclass
class WalkForwardWindow:
    index: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date


class WalkForwardSplitter:

    def __init__(
        self,
        start,
        end,
        train_months=2,
        test_months=1,
        step_months=1,
    ):
        self.start = self._to_date(start)
        self.end = self._to_date(end)
        self.train_months = int(train_months)
        self.test_months = int(test_months)
        self.step_months = int(step_months)

    def _to_date(self, value):

        if isinstance(value, date):
            return value

        if hasattr(value, "date"):
            return value.date()

        return datetime.fromisoformat(str(value)).date()

    def windows(self):

        windows = []

        current_train_start = self.start
        index = 1

        while True:

            train_start = current_train_start
            train_end = train_start + relativedelta(
                months=self.train_months
            )

            test_start = train_end
            test_end = test_start + relativedelta(
                months=self.test_months
            )

            if test_end > self.end:
                break

            windows.append(
                WalkForwardWindow(
                    index=index,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                )
            )

            index += 1

            current_train_start = (
                current_train_start
                + relativedelta(months=self.step_months)
            )

        return windows
