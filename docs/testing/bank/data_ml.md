# Банк задач: Data Science / ML

30 параметрических шаблонов (T4.3). Код — `backend/app/testing/engine/bank/data_ml/`, сверка ключей — `backend/tests/engine/test_bank_data_ml_verify.py`.

Каждый шаблон даёт не меньше 50 разных вариантов, ответ вычисляет генератор. Общие проверки (контракт, ≥ 50 вариантов, позиция верного ответа) — `test_engine_bank_full.py`. Стартовые `a`, `b` заданы экспертно по целевому грейду и уточняются калибровкой.

Как сверен ключ: **система** — настоящей библиотекой или программой (18); **пересчёт** — независимой реализацией в тесте (1); **экспертно** — ответ задан автором, машиной не проверить (11).

Тесты сверки пропускаются, если нужной библиотеки нет (в CI ставятся только зависимости бэкенда). Для полной сверки: `pip install pandas scikit-learn scipy statsmodels jsonschema lxml cssselect pyyaml cryptography`; для bash-шаблонов нужен bash (на Windows — Git Bash).

| id | тема | формат | грейд | a | b | что проверяет | как сверен ключ |
|---|---|---|---|---|---|---|---|
| `data_ml.activation_values` | deep_learning | code_output | Стажёр | 1.1 | -1.2 | Функции активации на векторе | система: выполнение кода (numpy) |
| `data_ml.accuracy_paradox` | metrics | numeric | Стажёр | 1.1 | -1.6 | Accuracy при дисбалансе классов | система: sklearn accuracy_score |
| `data_ml.kfold_sizes` | model_validation | numeric | Стажёр | 1.0 | -1.5 | Размеры частей при кросс-валидации | система: sklearn KFold, RepeatedKFold, train_test_split |
| `data_ml.numpy_axis` | pandas_numpy | code_output | Стажёр | 1.2 | -1.4 | numpy: агрегаты по осям | система: выполнение кода (numpy) |
| `data_ml.encoding_choice` | preprocessing | single_choice | Стажёр | 1.1 | -1.3 | Как закодировать признак | экспертно: экспертно |
| `data_ml.one_hot_shape` | preprocessing | code_output | Стажёр | 1.2 | -1.1 | Сколько столбцов после get_dummies | система: выполнение кода (pandas get_dummies) |
| `data_ml.knn_predict` | classic_ml | short_text | Junior | 1.2 | -0.6 | Предсказание kNN вручную | система: sklearn KNeighborsClassifier |
| `data_ml.nn_param_count` | deep_learning | numeric | Junior | 1.3 | -0.5 | Число параметров полносвязной сети | система: sklearn MLPRegressor (coefs_ + intercepts_); torch, если есть |
| `data_ml.regression_metrics` | metrics | numeric | Junior | 1.3 | -0.6 | Метрики регрессии: MAE, RMSE, MAPE, R² | система: sklearn: MAE, MSE, RMSE, MAPE, R² |
| `data_ml.crisp_dm_order` | mlops | ordering | Junior | 1.0 | -0.7 | Этапы ML-проекта | экспертно: экспертно (CRISP-DM) |
| `data_ml.split_strategy` | model_validation | single_choice | Junior | 1.3 | -0.4 | Выбор схемы валидации | экспертно: экспертно |
| `data_ml.numpy_broadcasting` | pandas_numpy | code_output | Junior | 1.4 | -0.2 | numpy: broadcasting форм | система: выполнение кода (numpy), исключение → error |
| `data_ml.pandas_nan` | pandas_numpy | code_output | Junior | 1.4 | -0.5 | pandas: пропуски в агрегатах | система: выполнение кода (pandas) |
| `data_ml.pvalue_interpretation` | statistics | multi_choice | Junior | 1.3 | -0.3 | Как читать p-value | экспертно: экспертно |
| `data_ml.gini_split` | classic_ml | numeric | Middle | 1.4 | 0.5 | Индекс Джини и прирост информации | система: sklearn DecisionTreeClassifier: impurity узлов |
| `data_ml.regularization_effects` | classic_ml | multi_choice | Middle | 1.3 | 0.3 | Как параметр регуляризации меняет модель | экспертно: экспертно |
| `data_ml.conv_output_shape` | deep_learning | numeric | Middle | 1.4 | 0.3 | Размер выхода и параметры свёртки | система: numpy sliding_window_view по реальному массиву |
| `data_ml.gradient_step` | deep_learning | numeric | Middle | 1.4 | 0.6 | Один шаг градиентного спуска | пересчёт: численный градиент (numpy) |
| `data_ml.roc_auc_pairs` | metrics | numeric | Middle | 1.5 | 0.6 | ROC-AUC вручную | система: sklearn roc_auc_score |
| `data_ml.leakage_line` | model_validation | find_bug_line | Middle | 1.5 | 0.4 | Найди строку с утечкой данных | экспертно: код разбирается ast; строка — экспертно |
| `data_ml.numpy_view_copy` | pandas_numpy | code_output | Middle | 1.6 | 0.8 | numpy: представление или копия | система: выполнение кода (numpy) |
| `data_ml.pandas_groupby` | pandas_numpy | code_output | Middle | 1.5 | 0.4 | pandas: groupby и агрегаты | система: выполнение кода (pandas) |
| `data_ml.ab_ztest` | statistics | numeric | Middle | 1.4 | 0.7 | z-тест для конверсий | система: scipy chi2_contingency (χ² = z²), statsmodels proportions_ztest |
| `data_ml.torch_loop_bug` | deep_learning | find_bug_line | Senior | 1.5 | 1.2 | Ошибка в цикле обучения PyTorch | экспертно: код разбирается ast; строка — экспертно |
| `data_ml.imbalance_strategies` | metrics | multi_choice | Senior | 1.3 | 1.4 | Работа с сильным дисбалансом классов | экспертно: экспертно |
| `data_ml.metric_choice_business` | metrics | single_choice | Senior | 1.2 | 1.3 | Метрика под бизнес-задачу | экспертно: экспертно |
| `data_ml.drift_psi` | mlops | numeric | Senior | 1.3 | 1.3 | PSI: стабильность распределения признака | система: scipy.special.rel_entr: PSI = KL(a‖e) + KL(e‖a) |
| `data_ml.drift_type` | mlops | single_choice | Senior | 1.2 | 1.2 | Какой это дрейф | экспертно: экспертно |
| `data_ml.model_rollout_order` | mlops | ordering | Senior | 1.1 | 1.0 | Безопасный выпуск модели | экспертно: экспертно |
| `data_ml.multiple_testing` | statistics | numeric | Senior | 1.5 | 1.5 | Поправки на множественные сравнения | система: statsmodels multipletests |

## Покрытие: темы × грейды

| тема | Стажёр | Junior | Middle | Senior | всего |
|---|---|---|---|---|---|
| metrics | 1 | 1 | 1 | 2 | 5 |
| model_validation | 1 | 1 | 1 | 0 | 3 |
| pandas_numpy | 1 | 2 | 2 | 0 | 5 |
| statistics | 0 | 1 | 1 | 1 | 3 |
| preprocessing | 2 | 0 | 0 | 0 | 2 |
| classic_ml | 0 | 1 | 2 | 0 | 3 |
| deep_learning | 1 | 1 | 2 | 1 | 5 |
| mlops | 0 | 1 | 0 | 3 | 4 |
| **всего** | 6 | 8 | 9 | 7 | 30 |

## Форматы

| формат | шаблонов |
|---|---|
| numeric | 11 |
| code_output | 7 |
| single_choice | 4 |
| multi_choice | 3 |
| find_bug_line | 2 |
| ordering | 2 |
| short_text | 1 |
