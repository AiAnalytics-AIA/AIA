"""The signed-off AIA Sociomapa methodology's respondent map (``aia-sociomap-5``).

Ported as written from the methodology folder's ``respondents.py`` (``place_respondents``) and
``sociomap_3d.render_respondents`` (the density), the owner's code, kept outside this repository
(``tests/test_sociomap_signed_off_respondents.py``). With the mapped objects fixed at their
ruler positions:

* the vector model (:func:`place_respondents`): each respondent's ratings of the objects they
  rated, on the declared 0-1 scale, regressed on the objects' coordinates (an intercept and two
  slopes, one 3 x 3 normal-equation solve each, by pseudo-inverse); the respondent drawn from
  the objects' centre in the direction their ratings rise, at the largest object distance from
  the centre times ``sqrt(R2)``; the misfit ``1 - R2``; the chance test
  ``p = (1 - R2)^((n - 3) / 2)``, the chance of fitting at least this well with no preference
  (1 with three ratings, which fit the three parameters exactly); PLACED when ``p`` is at most
  the chance-test level, FADED otherwise; NOT_PLACED with fewer ratings than the minimum or no
  spread among them;
* the density (:func:`respondent_density`): a Gaussian kernel summed over the PLACED
  respondents only, divided by its maximum, on a given grid; zero everywhere when nobody is
  PLACED. FADED respondents add nothing: the vector model puts respondents without a clear
  direction near the centre, and counting them raised one broad central hill.

Ratings are unweighted, as the methodology and the AIA panel read them: survey weights do not
enter. The methodology computes the density in its frame units (ruler x 27 x the frame's scale
k), its kernel ``sigma x 27 k`` wide; on the ruler the same kernel is ``sigma`` wide.

Pure: no I/O, no randomness.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

__all__ = ["FADED", "NOT_PLACED", "PLACED", "Placement", "place_respondents", "respondent_density"]

Floats = NDArray[np.float64]

PLACED: Final = "PLACED"
FADED: Final = "FADED"
NOT_PLACED: Final = "NOT_PLACED"

#: The vector model's parameters per respondent: an intercept and two slopes.
_PARAMETERS: Final = 3
#: At or below this sum of squares a respondent's ratings have no spread; below this slope
#: length they have no direction (the methodology's own thresholds).
_NO_SPREAD: Final = 1e-12


@dataclass(frozen=True, slots=True)
class Placement:
    """Each respondent's position on the ruler (NaN when NOT_PLACED), misfit ``1 - R2``, R2
    and chance-test p-value (NaN when NOT_PLACED), and status."""

    x: Floats
    misfit: Floats
    r2: Floats
    p_value: Floats
    status: tuple[str, ...]


def place_respondents(
    points: Floats, ratings: Floats, *, chance_level: float, min_ratings: int
) -> Placement:
    """The vector model: ``points`` the objects' ruler positions (M x 2), ``ratings`` each
    respondent's ratings of them on the declared 0-1 scale (N x M, NaN where not rated)."""
    y = np.asarray(points, float)
    a = np.asarray(ratings, float)
    n, m = a.shape
    rated = np.isfinite(a)
    a0 = np.where(rated, a, 0.0)
    nr = rated.sum(1)
    z = np.c_[np.ones(m), y]
    gram = (rated.astype(float) @ (z[:, :, None] * z[:, None, :]).reshape(m, 9)).reshape(n, 3, 3)
    b = a0 @ z
    mean = a0.sum(1) / np.maximum(nr, 1)
    sst = (rated * (a0 - mean[:, None]) ** 2).sum(1)
    ok = (nr >= min_ratings) & (sst > _NO_SPREAD)
    beta = np.zeros((n, 3))
    beta[ok] = np.einsum("kij,kj->ki", np.linalg.pinv(gram[ok]), b[ok])
    ssr = (rated * (a0 - beta @ z.T) ** 2).sum(1)
    r2 = np.full(n, np.nan)
    r2[ok] = np.maximum(0.0, 1.0 - ssr[ok] / sst[ok])
    misfit = 1.0 - r2
    c0 = y.mean(0)
    reach = float(np.sqrt(((y - c0) ** 2).sum(1)).max())
    slope = beta[:, 1:]
    length = np.linalg.norm(slope, axis=1)
    x = np.full((n, 2), np.nan)
    unit = slope / np.maximum(length, _NO_SPREAD)[:, None]
    x[ok] = c0 + reach * np.sqrt(r2[ok])[:, None] * unit[ok]
    x[ok & (length < _NO_SPREAD)] = c0
    p_value = np.full(n, np.nan)
    more = ok & (nr > _PARAMETERS)
    p_value[more] = (1.0 - r2[more]) ** ((nr[more] - _PARAMETERS) / 2.0)
    p_value[ok & (nr <= _PARAMETERS)] = 1.0
    status = tuple(
        NOT_PLACED if not fitted else PLACED if p <= chance_level else FADED
        for fitted, p in zip(ok, p_value, strict=True)
    )
    return Placement(x=x, misfit=misfit, r2=r2, p_value=p_value, status=status)


def respondent_density(
    x: Floats,
    status: Sequence[str],
    axes: tuple[Sequence[float], Sequence[float]],
    sigma: float,
) -> Floats:
    """The density of the PLACED respondents at ``x`` (ruler units) on the grid ``axes`` (its x
    and y coordinates), indexed ``[gy][gx]``: the kernel ``exp(-d^2 / (2 sigma^2))`` summed in
    respondent order, divided by its maximum; zero everywhere when nobody is PLACED."""
    gx, gy = np.meshgrid(np.asarray(axes[0], float), np.asarray(axes[1], float))
    height = np.zeros_like(gx)
    counted = np.array([s == PLACED for s in status], dtype=bool) & np.isfinite(x).all(1)
    for p in np.asarray(x, float)[counted]:
        height += np.exp(-((gx - p[0]) ** 2 + (gy - p[1]) ** 2) / (2 * sigma * sigma))
    peak = height.max()
    result: Floats = height / peak if peak > 0 else height
    return result
