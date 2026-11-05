"""Nama kolom dan daftar nilai. Kontrak keluaran mengikuti README repo (Kontrak data v1)."""
CONTRACT_REQUIRED = ["timestamp", "unit_id", "pv_actual_w", "pv_expected_w", "batt_v", "alarm",
                     "cause_guess", "loss_rp", "data_label"]
CONTRACT_OPTIONAL = ["batt_i_a", "alarm_threshold", "data_source", "fault_label"]
CONTRACT_COLUMNS = CONTRACT_REQUIRED + CONTRACT_OPTIONAL

CAUSES = {"kabel_putus", "baterai_dicabut", "panel_kotor", "bayangan", "konektor_kendor",
          "baterai_melemah", "tidak_diketahui"}
NEEDS_TECHNICIAN = {"kabel_putus", "baterai_dicabut", "konektor_kendor", "baterai_melemah"}
BATTERY_CAUSES = {"baterai_dicabut", "baterai_melemah"}
FAULT_CAUSE = {"cable_cut": "kabel_putus", "soiling": "panel_kotor", "partial_shading": "bayangan",
               "loose_connector": "konektor_kendor", "battery_removed": "baterai_dicabut",
               "battery_weak": "baterai_melemah", "real_shading": "bayangan"}

WEATHER_FEATURES = ["ghi", "dni", "dhi", "temp_air", "wind_speed", "cloud_cover", "precip"]
PHYSICS_FEATURES = ["sun_elevation", "sun_azimuth", "poa", "t_cell", "p_pvlib", "clear_index"]
FEATURES = WEATHER_FEATURES + PHYSICS_FEATURES
