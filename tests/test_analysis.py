from analysis import Action, Strength, generate_signals


def test_rsi_oversold():
    indicators = {"sma_20": None, "sma_50": None, "prev_sma_20": None, "prev_sma_50": None, "rsi_14": 25.0}
    signals = generate_signals(100.0, indicators)
    rsi_signal = next(s for s in signals if s.name == "RSI")
    assert rsi_signal.action == Action.BUY
    assert rsi_signal.strength == Strength.MODERATE


def test_rsi_overbought():
    indicators = {"sma_20": None, "sma_50": None, "prev_sma_20": None, "prev_sma_50": None, "rsi_14": 75.0}
    signals = generate_signals(100.0, indicators)
    rsi_signal = next(s for s in signals if s.name == "RSI")
    assert rsi_signal.action == Action.SELL
    assert rsi_signal.strength == Strength.MODERATE


def test_rsi_extreme_oversold():
    indicators = {"sma_20": None, "sma_50": None, "prev_sma_20": None, "prev_sma_50": None, "rsi_14": 15.0}
    signals = generate_signals(100.0, indicators)
    rsi_signal = next(s for s in signals if s.name == "RSI")
    assert rsi_signal.action == Action.BUY
    assert rsi_signal.strength == Strength.STRONG


def test_rsi_neutral():
    indicators = {"sma_20": None, "sma_50": None, "prev_sma_20": None, "prev_sma_50": None, "rsi_14": 50.0}
    signals = generate_signals(100.0, indicators)
    rsi_signal = next(s for s in signals if s.name == "RSI")
    assert rsi_signal.action == Action.HOLD


def test_golden_cross():
    indicators = {"sma_20": 105.0, "sma_50": 100.0, "prev_sma_20": 99.0, "prev_sma_50": 100.0, "rsi_14": None}
    signals = generate_signals(110.0, indicators)
    sma_signal = next(s for s in signals if "Crossover" in s.name)
    assert sma_signal.action == Action.BUY
    assert sma_signal.strength == Strength.STRONG


def test_death_cross():
    indicators = {"sma_20": 95.0, "sma_50": 100.0, "prev_sma_20": 101.0, "prev_sma_50": 100.0, "rsi_14": None}
    signals = generate_signals(90.0, indicators)
    sma_signal = next(s for s in signals if "Crossover" in s.name)
    assert sma_signal.action == Action.SELL
    assert sma_signal.strength == Strength.STRONG


def test_stop_loss():
    indicators = {"sma_20": None, "sma_50": None, "prev_sma_20": None, "prev_sma_50": None, "rsi_14": None}
    signals = generate_signals(85.0, indicators, purchase_price=100.0)
    stop_signal = next(s for s in signals if s.name == "Stop-Loss")
    assert stop_signal.action == Action.SELL
    assert stop_signal.strength == Strength.STRONG


def test_take_profit():
    indicators = {"sma_20": None, "sma_50": None, "prev_sma_20": None, "prev_sma_50": None, "rsi_14": None}
    signals = generate_signals(125.0, indicators, purchase_price=100.0)
    tp_signal = next(s for s in signals if s.name == "Take-Profit")
    assert tp_signal.action == Action.SELL
    assert tp_signal.strength == Strength.MODERATE


def test_no_stop_loss_in_range():
    indicators = {"sma_20": None, "sma_50": None, "prev_sma_20": None, "prev_sma_50": None, "rsi_14": None}
    signals = generate_signals(95.0, indicators, purchase_price=100.0)
    stop_signals = [s for s in signals if s.name in ("Stop-Loss", "Take-Profit")]
    assert len(stop_signals) == 0
