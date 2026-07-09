class HtmlCharts:

    def _scale(self, value, min_v, max_v, height):
        if max_v == min_v:
            return height / 2
        return height - ((value - min_v) / (max_v - min_v) * height)

    def line_chart(self, points, x_key, y_key, title="", width=1000, height=260):
        if not points:
            return "<p>No chart data.</p>"

        values = [float(p[y_key]) for p in points]
        min_v = min(values)
        max_v = max(values)

        if min_v == max_v:
            min_v -= 1
            max_v += 1

        step = width / max(len(points) - 1, 1)

        coords = []

        for i, p in enumerate(points):
            x = i * step
            y = self._scale(float(p[y_key]), min_v, max_v, height)
            coords.append(f"{x:.2f},{y:.2f}")

        polyline = " ".join(coords)

        return f"""
<div>
<h3>{title}</h3>
<svg width="100%" viewBox="0 0 {width} {height + 40}" preserveAspectRatio="none">
    <rect x="0" y="0" width="{width}" height="{height}" fill="#fafafa" stroke="#ddd"/>
    <polyline points="{polyline}" fill="none" stroke="#111" stroke-width="2"/>
    <text x="5" y="15" font-size="12">{max_v:,.2f}</text>
    <text x="5" y="{height - 5}" font-size="12">{min_v:,.2f}</text>
</svg>
</div>
"""

    def bar_chart(self, rows, label_key, value_key, title="", width=1000, height=260):
        if not rows:
            return "<p>No chart data.</p>"

        values = [float(r[value_key]) for r in rows]
        max_abs = max(abs(v) for v in values) or 1.0
        bar_width = width / max(len(rows), 1)

        zero_y = height / 2

        bars = ""

        for i, row in enumerate(rows):
            value = float(row[value_key])
            bar_h = abs(value) / max_abs * (height / 2 - 20)
            x = i * bar_width + 4
            y = zero_y - bar_h if value >= 0 else zero_y
            color = "#c8e6c9" if value >= 0 else "#ffcdd2"

            bars += f"""
<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width - 8:.2f}" height="{bar_h:.2f}" fill="{color}" stroke="#999"/>
<text x="{x:.2f}" y="{height + 15}" font-size="10" transform="rotate(45 {x:.2f},{height + 15})">{row[label_key]}</text>
"""

        return f"""
<div>
<h3>{title}</h3>
<svg width="100%" viewBox="0 0 {width} {height + 80}" preserveAspectRatio="none">
    <rect x="0" y="0" width="{width}" height="{height}" fill="#fafafa" stroke="#ddd"/>
    <line x1="0" y1="{zero_y}" x2="{width}" y2="{zero_y}" stroke="#333"/>
    {bars}
</svg>
</div>
"""
