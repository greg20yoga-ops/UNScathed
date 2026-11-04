"""Lapisan ML ringan di atas pvlib: belajar rasio aktual/seharusnya pada kondisi SEHAT
(bias lokasi, efisiensi redup, pola jam) lalu mengoreksi produksi seharusnya."""
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor


class ResidualCorrector:
    def __init__(self, cfg):
        self.cfg = cfg
        self.model = GradientBoostingRegressor(
            n_estimators=150, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=0)

    @staticmethod
    def _X(df):
        h = df.index.hour + df.index.minute / 60.0
        return np.c_[df["poa_wm2"], df["temp_cell_c"], np.sin(2 * np.pi * h / 24),
                     np.cos(2 * np.pi * h / 24), df["cloud_idx"]]

    def fit(self, train):
        pdc0 = self.cfg["panel"]["pdc0_w"]
        m = train["expected_w"] > self.cfg["data"]["min_expected_frac"] * pdc0
        y = (train["pv_actual_w"] / train["expected_w"]).where(m).clip(0.2, 1.5)
        ok = y.notna()
        self.model.fit(self._X(train[ok]), y[ok])
        return self

    def predict_ratio(self, df):
        return np.clip(self.model.predict(self._X(df)), 0.3, 1.3)

    def expected_adj(self, df):
        return df["expected_w"] * self.predict_ratio(df)
