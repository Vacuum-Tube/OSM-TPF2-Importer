import math
import numpy as np
from scipy.interpolate import CubicSpline
from copy import deepcopy

from vec2 import Vec2


class MyCubicSpline(CubicSpline):

    def __init__(self, y, x=None, bc_method="natural"):
        self.y = [Vec2(yi) for yi in y]
        if x is None:
            x = MyCubicSpline.get_x_lin_spline(self.y)
        super().__init__(x, y, bc_type=bc_method, extrapolate=False)
        self.d1 = self.derivative(1)
        self.d2 = self.derivative(2)
        self.vi = [self.v(xi) for xi in self.x]
        self.viabs = [vi.length() for vi in self.vi]

    @staticmethod
    def get_x_lin_spline(y):  # heuristic approach for path variable lengths
        x = [0]
        for yi, yi1 in zip(y[:-1], y[1:]):
            x.append(x[-1] + (yi1 - yi).length())
        return x

    # def __call__(self, *args, **kwargs):
    #     c = super().__call__(*args, **kwargs)
    #     return Vec2(c)

    def v(self, t):
        return Vec2(self.d1(t))

    def vabs(self, t):
        return self.v(t).length()

    def a(self, t):
        return Vec2(self.d2(t))

    # curvature
    def k(self, t):
        return abs(self.d1(t)[0] * self.d2(t)[1] - self.d1(t)[1] * self.d2(t)[0]) / sum(self.d1(t) ** 2) ** 1.5

    def maxk_at_node(self, i, samples=10):
        x = self.x
        return max(self.k(t) for t in (
            *np.linspace(x[i] - 0.49 * (x[i] - x[i - 1]), x[i], samples),
            *np.linspace(x[i], x[i] + 0.49 * (x[i + 1] - x[i]), samples)))

    def dist_to_point(self, p, i_start, i_end, samples=30):
        # assert (self.y[i_start] - p).length() < (self.y[i_start] - self.y[i_end]).length()
        # assert (self.y[i_end] - p).length() < (self.y[i_start] - self.y[i_end]).length()
        return min((Vec2(self(t)) - p).length() for t in np.linspace(self.x[i_start], self.x[i_end], samples))

    # calc error spline / deviation from linear spline: y[i]+(x-x[i])/(x[i+1]-x[i])*(y[i+1]-y[i])
    # simple approximation of (geometric) spline error
    def error_spline(self):
        cerr = deepcopy(self)
        cerr.iserrorspline = True
        for m in range(cerr.c.shape[1]):
            cerr.c[2, m, :] -= ((self.y[m + 1] - self.y[m]) / (self.x[m + 1] - self.x[m])).toArray()  # linear term
            cerr.c[3, m, :] -= self.y[m].toArray()  # constant term
        return cerr

    def maxerr_at_node(self, i, samples=10):
        assert self.iserrorspline
        x = self.x
        return max(Vec2(self(t)).length() for t in (
            *np.linspace(x[i] - 0.49 * (x[i] - x[i - 1]), x[i], samples),
            *np.linspace(x[i], x[i] + 0.49 * (x[i + 1] - x[i]), samples)))


def approx_length_arc(dist, angle):
    assert 0 <= angle < math.pi / 2, angle
    if angle < .001:
        return dist
    return dist * angle / math.cos(math.pi / 2 - angle / 2) / 2
