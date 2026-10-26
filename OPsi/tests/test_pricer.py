# tests/test_pricer.py
from opsi.pricer import bs_put_delta


def test_put_delta_otm_negative():
    d = bs_put_delta(S=100.0, K=90.0, T=30 / 365, r=0.045, q=0.0, sigma=0.30)
    assert -0.35 < d < -0.05
