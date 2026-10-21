import re as _re
_PROV = _re.compile(r"the toolkit|generated from|results/results|results\.json|\.json by ", _re.I)

def _install():
    try:
        import matplotlib  # noqa
        import matplotlib.pyplot as _plt
        from matplotlib.axes import Axes
        from matplotlib.figure import Figure
    except Exception:
        return
    Axes.set_title = lambda self, *a, **k: None      # no titles (caption covers it)
    Figure.suptitle = lambda self, *a, **k: None
    # constrained_layout (enabled in rcParams) handles spacing and prevents overlapping text.
    # Generated code often still calls tight_layout()/subplots_adjust(), which conflict with it and
    # would WARN + override (reintroducing overlaps). Neutralize them so constrained_layout wins.
    Figure.tight_layout = lambda self, *a, **k: None
    Figure.subplots_adjust = lambda self, *a, **k: None
    _plt.tight_layout = lambda *a, **k: None
    _plt.subplots_adjust = lambda *a, **k: None
    _ftext = Figure.text
    def _ftext_guard(self, x, y, s, *a, **k):
        if isinstance(s, str) and _PROV.search(s):
            return None
        return _ftext(self, x, y, s, *a, **k)
    Figure.text = _ftext_guard
    _atext = Axes.text
    def _atext_guard(self, x, y, s, *a, **k):
        if isinstance(s, str) and _PROV.search(s):
            return None
        return _atext(self, x, y, s, *a, **k)
    Axes.text = _atext_guard
    _annot = Axes.annotate
    def _annot_guard(self, text, *a, **k):
        if isinstance(text, str) and _PROV.search(text):
            return None
        return _annot(self, text, *a, **k)
    Axes.annotate = _annot_guard

_install()
