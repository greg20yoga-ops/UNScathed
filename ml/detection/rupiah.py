"""Rugi rupiah per jam. Rumus final menunggu docs/rupiah.md; biaya patroli/baterai masih asumsi 0."""
import pandas as pd

from .schema import BATTERY_CAUSES, NEEDS_TECHNICIAN


def _in_alarm_run(score, alarm):
    """Jam skor > 0 pada rangkaian yang berakhir alarm: rugi dihitung sejak gangguan mulai terkumpul."""
    active = (score > 0) | alarm
    run = (active != active.shift(fill_value=False)).cumsum()
    return active & alarm.groupby(run).transform("any")


def hourly_loss(actual_w, expected_w, score, alarm, cause, cfg):
    """actual_w dan expected_w per jam, jadi W = Wh pada jam itu."""
    energy_kwh = (expected_w - actual_w).clip(lower=0) / 1000
    loss = (energy_kwh * cfg["tarif_rp_per_kwh"]).where(_in_alarm_run(score, alarm), 0.0)
    onset = alarm & ~alarm.shift(fill_value=False)
    loss = loss + (onset & cause.isin(NEEDS_TECHNICIAN)) * cfg["biaya_patroli_rp"]
    return loss + (onset & cause.isin(BATTERY_CAUSES)) * cfg["biaya_baterai_rp"]
