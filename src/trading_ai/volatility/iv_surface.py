import numpy as np


class IVSurfaceEngine:

    def build_surface(self, option_chain):

        surface = {}

        for opt in option_chain:

            if opt.implied_volatility <= 0:
                continue

            expiry = opt.expiry
            delta_bucket = round(opt.delta, 1)

            key = (expiry, delta_bucket)

            if key not in surface:
                surface[key] = []

            surface[key].append(opt.implied_volatility)

        # aggregate
        for k, vals in surface.items():
            surface[k] = float(np.mean(vals))

        return surface
