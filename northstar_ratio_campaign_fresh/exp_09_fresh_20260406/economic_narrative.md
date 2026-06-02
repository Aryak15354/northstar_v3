# EXP-09 - CatBoost Depth Ablation + Early Stopping

Notes:
- This fresh notebook is ratio-first and directly addresses the compendium's remaining gate.
- It uses the current merged export and does not import any external project code.

Best candidate:
- mean_test_ic: 0.022451842955973786
- mean_train_test_ratio: 1.3898323975853308
- params: {'depth': 3, 'l2_leaf_reg': 15.0, 'min_data_in_leaf': 40, 'od_wait': 20, 'boosting_type': 'Ordered', 'iterations': 400, 'learning_rate': 0.05}
